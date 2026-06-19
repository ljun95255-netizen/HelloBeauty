import argparse
import csv
import json
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from scripts.run_real_metric_experiments import (
    DEFAULT_RESULTS_ROOT,
    METRIC_VARIANTS,
    WORKSPACE_ROOT,
    LPIPSEvaluator,
    RenderedCase,
    build_jesr_proxy_eval_records,
    build_metric_rows,
    case_variant_specs,
    compute_jesr_proxy_evaluation,
    env_snapshot,
    fid_score_against,
    is_status_ok,
    jesr_theme_label,
    main,
    materialize_identity_guard_outputs,
    materialize_metric_control_outputs,
    paper_label,
    profile_cases_for_styles,
    read_csv_dicts,
    refresh_style_retention_artifacts,
    run_ablation_grid,
    summarize_metrics,
    summarize_metrics_by_style_variant,
    write_style_retention_artifacts,
    write_style_retention_summary,
    write_profile_case_artifacts,
    write_result_collection_manifest,
    write_user_eval_summary,
    write_jesr_proxy_eval_summary,
    write_jesr_proxy_eval_records,
    write_system_contract_summary,
)
from backend.jesr.metric_control import run_metric_control_loop, write_guarded_output
from scripts.jesr_profile_case_templates import JESR_PROFILE_CASES


class UnavailableIdentity:
    available = False
    reason = "disabled_for_test"
    threshold = 0.72
    backend = "none"

    def similarity(self, _a_path: Path, _b_path: Path):
        return None


class PassingIdentity:
    available = True
    reason = "ready"
    threshold = 0.72
    backend = "test"

    def similarity(self, _a_path: Path, _b_path: Path):
        return 0.99


class BorderlineIdentity:
    available = True
    reason = "ready"
    threshold = 0.72
    backend = "test"

    def similarity(self, _a_path: Path, _b_path: Path):
        return 0.71


class MappedIdentity:
    available = True
    reason = "ready"
    threshold = 0.72

    def __init__(self, backend: str, values: dict[str, float | None]):
        self.backend = backend
        self.values = values

    def similarity(self, _a_path: Path, b_path: Path):
        return self.values.get(b_path.name)


def write_image(path: Path, value: int) -> None:
    Image.fromarray(np.full((16, 16, 3), value, dtype=np.uint8)).save(path)


def rendered_case(tmp_path: Path) -> RenderedCase:
    image_dir = tmp_path / "images" / "fresh_japanese" / "sample"
    image_dir.mkdir(parents=True)
    paths = {
        "input": image_dir / "input.png",
        "slider": image_dir / "slider_only.png",
        "prompt": image_dir / "prompt_only.png",
        "creative": image_dir / "creative_only.png",
        "fidelity": image_dir / "fidelity.png",
        "full": image_dir / "jesr_full.png",
        "feedback": image_dir / "jesr_feedback_full.png",
    }
    for index, path in enumerate(paths.values()):
        write_image(path, 80 + index * 10)

    return RenderedCase(
        style="fresh_japanese",
        sample="sample.png",
        session_id="session-1",
        photo_id="photo-1",
        input_path=paths["input"],
        slider_path=paths["slider"],
        prompt_only_path=paths["prompt"],
        creative_only_path=paths["creative"],
        fidelity_path=paths["fidelity"],
        full_path=paths["full"],
        feedback_full_path=paths["feedback"],
        guarded_full_path=None,
        guarded_feedback_full_path=None,
        slider_status="slider_only_ok",
        prompt_only_status="prompt_only_ok",
        creative_only_status="creative_only_ok",
        fidelity_status="jesr_fidelity_ok",
        full_status="jesr_full_ok",
        feedback_full_status="jesr_feedback_full_ok",
        guarded_full_status=None,
        guarded_feedback_full_status=None,
        rollback_restored=True,
        latency_seconds={variant: 0.1 for variant in METRIC_VARIANTS},
        export_path=str(tmp_path / "export.json"),
        trace_ids={variant: f"trace-{variant}" for variant in METRIC_VARIANTS},
        recipe_delta={
            "face_slim_delta": -0.1,
            "eye_size_delta": -0.1,
            "creative_strength_delta": -0.1,
        },
    )


def test_default_results_root_points_to_workspace_results():
    assert DEFAULT_RESULTS_ROOT == WORKSPACE_ROOT / "results"


def test_write_profile_case_artifacts_persists_profile_and_recipe_json(tmp_path: Path):
    profile = {
        "version": "jesr_aesthetic_profile.v1",
        "profile_id": "profile-1",
        "profile_revision": 2,
    }
    full_recipe = {"version": "jesr_core.v1", "jesr": {"profile_recipe_version": "jesr_profile_recipe.v1"}}
    feedback_recipe = {
        "version": "jesr_core.v1",
        "feedback": {"pain_tags": ["identity_not_preserved"]},
        "jesr": {"profile_recipe_version": "jesr_profile_recipe.v1"},
    }

    write_profile_case_artifacts(
        tmp_path,
        aesthetic_profile=profile,
        recipe_before_feedback=full_recipe,
        recipe_after_feedback=feedback_recipe,
    )

    artifact_dir = tmp_path / "profile_artifacts"
    assert (artifact_dir / "jesr_aesthetic_profile.json").exists()
    assert (artifact_dir / "jesr_profile_recipe_full.json").exists()
    assert (artifact_dir / "jesr_profile_recipe_feedback_full.json").exists()
    assert '"profile_id": "profile-1"' in (artifact_dir / "jesr_aesthetic_profile.json").read_text(encoding="utf-8")
    assert '"identity_not_preserved"' in (
        artifact_dir / "jesr_profile_recipe_feedback_full.json"
    ).read_text(encoding="utf-8")


def test_env_snapshot_records_model_adapter_timeout(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HELLOBEAUTY_MODEL_ADAPTER_TIMEOUT_SECONDS", "900")

    env_snapshot(tmp_path, model_status={"models": {}}, config={"seed": 1}, extras={})

    snapshot = json.loads((tmp_path / "env_snapshot.json").read_text(encoding="utf-8"))
    assert snapshot["environment"]["HELLOBEAUTY_MODEL_ADAPTER_TIMEOUT_SECONDS"] == "900"


def test_all_v3_profile_case_templates_normalize_and_build_profile_recipes():
    from jesr_core import apply_aesthetic_profile, default_recipe, normalize_aesthetic_profile, recipe_with_jesr_metadata

    expected_case_ids = {
        "fresh_japanese",
        "retro_hongkong",
        "clear_korean",
        "lazy_french",
        "american_hotgirl",
    }

    assert set(JESR_PROFILE_CASES) == expected_case_ids
    for case_id, template in JESR_PROFILE_CASES.items():
        assert template["case_id"].endswith(case_id)
        assert template["style_id"] == case_id
        profile = normalize_aesthetic_profile(template["profile"])
        assert profile["version"] == "jesr_aesthetic_profile.v1"
        assert profile["profile_status"] == "ready"
        assert profile["style_preferences"]["preferred_style_ids"] == [case_id]
        recipe = recipe_with_jesr_metadata(
            apply_aesthetic_profile(default_recipe(template["style_id"]), profile),
            profile,
        )
        assert recipe["version"] == "jesr_core.v1"
        assert recipe["jesr"]["profile_recipe_version"] == "jesr_profile_recipe.v1"
        assert recipe["jesr"]["aesthetic_profile_id"] == profile["profile_id"]
        assert recipe["jesr"]["aesthetic_profile_revision"] == profile["profile_revision"]


def test_profile_case_study_selection_and_metric_rows_attach_profile_metadata(tmp_path: Path):
    from jesr_core import normalize_aesthetic_profile

    selected = profile_cases_for_styles(["fresh_japanese", "clear_korean"])
    case = rendered_case(tmp_path)
    profile_case = selected["fresh_japanese"]
    case.aesthetic_profile = normalize_aesthetic_profile(profile_case["profile"])
    case.profile_case_id = profile_case["case_id"]
    materialize_identity_guard_outputs(case, PassingIdentity())

    rows = build_metric_rows([case], LPIPSEvaluator(enabled=False), PassingIdentity())
    full = next(row for row in rows if row["variant"] == "full")

    assert set(selected) == {"fresh_japanese", "clear_korean"}
    assert full["profile_case_id"] == "case_1_fresh_japanese"
    assert full["aesthetic_profile_id"] == "jap_profile_case_fresh_japanese"
    assert full["aesthetic_profile_revision"] == 1


def test_metric_control_rejects_primary_pass_when_required_facenet_fails(tmp_path: Path):
    image_dir = tmp_path / "case"
    image_dir.mkdir()
    input_path = image_dir / "input.png"
    fidelity_path = image_dir / "fidelity.png"
    write_image(input_path, 80)
    write_image(fidelity_path, 90)
    arcface = MappedIdentity("insightface", {"attempt_1.png": 0.82, "attempt_2.png": 0.90})
    facenet = MappedIdentity("facenet", {"attempt_1.png": 0.50, "attempt_2.png": 0.81})

    def render_attempt(strength: float, attempt_index: int, directory: Path):
        target = directory / f"attempt_{attempt_index}.png"
        write_image(target, 110 + attempt_index)
        return target, "jesr_creative_diffusion_img2img_ok", 0.2, {
            "strength_requested": strength,
            "strength_effective": strength,
            "preserve_blend_alpha": 0.0,
        }

    decision = run_metric_control_loop(
        source_variant="feedback_full",
        input_path=input_path,
        fidelity_path=fidelity_path,
        original_strength=0.30,
        render_attempt=render_attempt,
        candidate_dir=image_dir / "retry_candidates" / "feedback_full",
        primary_evaluator=arcface,
        identity_evaluators={"insightface": arcface, "facenet": facenet},
        required_backends=["insightface", "facenet"],
        identity_threshold=0.72,
    )
    guarded_path, guarded_status, guard = write_guarded_output(
        decision=decision,
        target_path=image_dir / "guarded.png",
        fidelity_path=fidelity_path,
    )

    assert decision.selected_path.name == "attempt_2.png"
    assert decision.selected_reason == "identity_retry_passed_attempt_2"
    assert decision.fallback_to_fidelity is False
    assert guarded_status == "guarded_feedback_full_ok_identity_retry_passed_attempt_2"
    assert guarded_path.read_bytes() == decision.selected_path.read_bytes()
    assert guard["selected_variant"] == "feedback_full"


def test_metric_control_rejects_failed_render_even_when_identity_scores_pass(tmp_path: Path):
    image_dir = tmp_path / "case"
    image_dir.mkdir()
    input_path = image_dir / "input.png"
    fidelity_path = image_dir / "fidelity.png"
    write_image(input_path, 80)
    write_image(fidelity_path, 90)
    arcface = MappedIdentity("insightface", {"attempt_1.png": 0.99, "attempt_2.png": 0.91})

    def render_attempt(strength: float, attempt_index: int, directory: Path):
        target = directory / f"attempt_{attempt_index}.png"
        write_image(target, 110 + attempt_index)
        status = (
            "jesr_creative_unavailable_adapter_runtime_not_configured"
            if attempt_index == 1
            else "jesr_creative_diffusion_img2img_ok"
        )
        return target, status, 0.1, {"strength_requested": strength, "strength_effective": strength}

    decision = run_metric_control_loop(
        source_variant="feedback_full",
        input_path=input_path,
        fidelity_path=fidelity_path,
        original_strength=0.30,
        render_attempt=render_attempt,
        candidate_dir=image_dir / "retry_candidates" / "feedback_full",
        primary_evaluator=arcface,
        identity_evaluators={"insightface": arcface},
        required_backends=["insightface"],
        identity_threshold=0.72,
    )

    assert decision.attempts[0].reason.startswith("render_status_not_ok:")
    assert decision.selected_path.name == "attempt_2.png"
    assert decision.selected_reason == "identity_retry_passed_attempt_2"


def test_metric_control_keeps_best_creative_for_analysis_and_falls_back_for_guard(tmp_path: Path):
    image_dir = tmp_path / "case"
    image_dir.mkdir()
    input_path = image_dir / "input.png"
    fidelity_path = image_dir / "fidelity.png"
    write_image(input_path, 80)
    write_image(fidelity_path, 90)
    arcface = MappedIdentity(
        "insightface",
        {
            "attempt_1.png": 0.20,
            "attempt_2.png": 0.45,
            "attempt_3.png": 0.61,
            "attempt_4.png": 0.58,
        },
    )

    def render_attempt(strength: float, attempt_index: int, directory: Path):
        target = directory / f"attempt_{attempt_index}.png"
        write_image(target, 120 + attempt_index)
        return target, "jesr_creative_diffusion_img2img_ok", 0.1, {
            "strength_requested": strength,
            "strength_effective": strength,
            "preserve_blend_alpha": 0.18,
        }

    decision = run_metric_control_loop(
        source_variant="feedback_full",
        input_path=input_path,
        fidelity_path=fidelity_path,
        original_strength=0.30,
        render_attempt=render_attempt,
        candidate_dir=image_dir / "retry_candidates" / "feedback_full",
        primary_evaluator=arcface,
        identity_evaluators={"insightface": arcface},
        required_backends=["insightface"],
        identity_threshold=0.72,
    )
    guarded_path, guarded_status, _guard = write_guarded_output(
        decision=decision,
        target_path=image_dir / "guarded.png",
        fidelity_path=fidelity_path,
    )

    assert decision.selected_path.name == "attempt_3.png"
    assert decision.selected_reason == "feedback_full_identity_retry_best_below_threshold"
    assert decision.fallback_to_fidelity is True
    assert guarded_status == "guarded_feedback_full_fallback_to_fidelity_identity_below_threshold"
    assert guarded_path.read_bytes() == fidelity_path.read_bytes()
    assert decision.metadata()["creative_retry_attempts"] == 4
    assert decision.metadata()["creative_preserve_blend_alpha"] == 0.18


def test_identity_guard_falls_back_when_identity_backend_is_unavailable(tmp_path: Path):
    case = rendered_case(tmp_path)

    materialize_identity_guard_outputs(case, UnavailableIdentity())

    guarded = case.guard_decisions["guarded_full"]
    assert guarded["selected_variant"] == "fidelity"
    assert guarded["fallback_to_fidelity"] == 1
    assert guarded["guard_reason"].startswith("identity_not_evaluable:")
    assert case.guarded_full_status.startswith("guarded_full_fallback_to_fidelity_")
    assert case.guarded_full_path.read_bytes() == case.fidelity_path.read_bytes()


def test_metric_rows_cover_all_paper_variants_after_guard_materialization(tmp_path: Path):
    case = rendered_case(tmp_path)
    materialize_identity_guard_outputs(case, PassingIdentity())
    lpips_eval = LPIPSEvaluator(enabled=False)

    rows = build_metric_rows([case], lpips_eval, PassingIdentity())

    assert [variant for variant, _, _ in case_variant_specs(case)] == METRIC_VARIANTS
    assert {row["variant"] for row in rows} == set(METRIC_VARIANTS)
    assert {row["paper_label"] for row in rows} == {paper_label(variant) for variant in METRIC_VARIANTS}
    assert next(row for row in rows if row["variant"] == "full")["jesr_theme_label"] == "JESR-Profile-Recipe"
    assert all("latency_seconds" in row for row in rows)
    assert all("status_ok" in row for row in rows)


def test_system_contract_summary_writes_guard_fallback_rate(tmp_path: Path):
    case = rendered_case(tmp_path)
    materialize_identity_guard_outputs(case, UnavailableIdentity())
    rows = build_metric_rows([case], LPIPSEvaluator(enabled=False), UnavailableIdentity())

    write_system_contract_summary(tmp_path, rows)

    summary = (tmp_path / "system_contract_summary.csv").read_text(encoding="utf-8")
    assert "guarded_full,JESR full + identity guard" in summary
    assert "guarded_feedback_full,JESR + feedback + identity guard" in summary
    assert "identity_guard_fallback_rate" in summary


def test_metric_rows_include_arcface_and_facenet_columns(tmp_path: Path):
    case = rendered_case(tmp_path)
    materialize_identity_guard_outputs(case, PassingIdentity())
    rows = build_metric_rows(
        [case],
        LPIPSEvaluator(enabled=False),
        PassingIdentity(),
        {"insightface": PassingIdentity(), "facenet": BorderlineIdentity()},
    )

    first = rows[0]
    assert first["arcface_similarity"] == 0.99
    assert first["arcface_pass"] == 1
    assert first["facenet_similarity"] == 0.71
    assert first["facenet_pass"] == 0


def test_metric_rows_and_summary_include_retry_schema(tmp_path: Path):
    case = rendered_case(tmp_path)
    materialize_identity_guard_outputs(case, PassingIdentity())
    case.retry_decisions["feedback_full"] = {
        "creative_strength_requested": 0.30,
        "creative_strength_effective": 0.20,
        "creative_retry_attempts": 2,
        "creative_retry_primary_backend": "insightface",
        "creative_retry_best_similarity": 0.82,
        "creative_retry_selected_similarity": 0.82,
        "creative_retry_arcface_similarity": 0.82,
        "creative_retry_facenet_similarity": 0.80,
        "creative_retry_required_backends": "insightface,facenet",
        "creative_retry_selected_reason": "identity_retry_passed_attempt_2",
        "creative_retry_render_seconds": 0.4,
        "identity_eval_seconds": 0.05,
        "total_guarded_seconds": 0.45,
        "creative_preserve_blend_alpha": 0.0,
        "creative_retry_selected_attempt": 2,
        "creative_retry_pass_rate": 1,
        "creative_retry_selected_rate": 1,
    }

    rows = build_metric_rows([case], LPIPSEvaluator(enabled=False), PassingIdentity())
    feedback = next(row for row in rows if row["variant"] == "feedback_full")
    summary = summarize_metrics(rows)
    feedback_summary = next(row for row in summary if row["variant"] == "feedback_full")

    assert feedback["creative_retry_attempts"] == 2
    assert feedback["creative_retry_required_backends"] == "insightface,facenet"
    assert feedback["total_guarded_seconds"] == 0.45
    assert feedback_summary["creative_retry_attempts_mean"] == 2.0
    assert feedback_summary["creative_retry_pass_rate"] == 1.0
    assert feedback_summary["creative_retry_selected_rate"] == 1.0


def test_materialized_metric_control_uses_trace_provider_params_for_first_attempt(tmp_path: Path):
    case = rendered_case(tmp_path)
    case.full_status = "jesr_creative_diffusion_img2img_ok"
    case.feedback_full_status = "jesr_creative_diffusion_img2img_ok"
    case.provider_params = {
        "full": {"strength_requested": 0.58, "strength_effective": 0.32, "preserve_blend_alpha": 0.18},
        "feedback_full": {"strength_requested": 0.30, "strength_effective": 0.30, "preserve_blend_alpha": 0.18},
    }

    materialize_metric_control_outputs(
        case,
        PassingIdentity(),
        {"insightface": PassingIdentity()},
        max_side=64,
    )

    assert case.retry_decisions["full"]["creative_strength_requested"] == 0.58
    assert case.retry_decisions["full"]["creative_strength_effective"] == 0.32
    assert case.retry_decisions["full"]["creative_preserve_blend_alpha"] == 0.18


def test_style_retention_artifact_schema(tmp_path: Path):
    case = rendered_case(tmp_path)
    materialize_identity_guard_outputs(case, PassingIdentity())

    write_style_retention_artifacts(tmp_path, [case])

    review = (tmp_path / "style_retention_review.csv").read_text(encoding="utf-8")
    summary = (tmp_path / "style_retention_summary.csv").read_text(encoding="utf-8")
    assert "style_visible_0_1" in review
    assert "style_strength_1_5" in review
    assert "identity_acceptable_0_1" in review
    assert "contact_sheet_path" in review
    assert "style_visible_rate" in summary
    assert (tmp_path / "contact_sheets" / "fresh_japanese" / "sample.png").exists()


def test_style_retention_contact_sheet_has_six_columns(tmp_path: Path):
    case = rendered_case(tmp_path)
    materialize_identity_guard_outputs(case, PassingIdentity())

    write_style_retention_artifacts(tmp_path, [case])

    sheet = Image.open(tmp_path / "contact_sheets" / "fresh_japanese" / "sample.png")
    review_rows = read_csv_dicts(tmp_path / "style_retention_review.csv")
    assert sheet.width == 6 * 16 + 7 * 8
    assert {row["variant"] for row in review_rows} == {
        "full",
        "feedback_full",
        "guarded_full",
        "guarded_feedback_full",
    }
    assert len({row["contact_sheet_path"] for row in review_rows}) == 1


def test_style_retention_summary_aggregates_filled_review(tmp_path: Path):
    filled = tmp_path / "style_retention_review_filled.csv"
    filled.write_text(
        "\n".join(
            [
                "style,sample,profile_case_id,aesthetic_profile_id,aesthetic_profile_revision,variant,style_visible_0_1,style_strength_1_5,identity_acceptable_0_1,reviewer_id",
                "fresh_japanese,sample.png,case_1,profile_1,2,full,1,4,1,r1",
                "fresh_japanese,sample2.png,case_1,profile_1,2,full,0,5,invalid,r1",
                "fresh_japanese,sample.png,case_1,profile_1,2,feedback_full,1,4,,r1",
                "fresh_japanese,sample.png,case_1,profile_1,2,guarded_feedback_full,1,5,1,r1",
                "fresh_japanese,sample.png,case_1,profile_1,2,guarded_full,,,,r1",
            ]
        ),
        encoding="utf-8",
    )

    write_style_retention_summary(tmp_path, filled)

    rows = read_csv_dicts(tmp_path / "style_retention_summary.csv")
    full = next(row for row in rows if row["variant"] == "full")
    feedback = next(row for row in rows if row["variant"] == "feedback_full")
    guarded = next(row for row in rows if row["variant"] == "guarded_full")
    guarded_feedback = next(row for row in rows if row["variant"] == "guarded_feedback_full")
    by_case = read_csv_dicts(tmp_path / "style_retention_summary_by_profile_case.csv")
    full_case = next(row for row in by_case if row["variant"] == "full")

    assert full["status"] == "invalid"
    assert float(full["style_visible_rate"]) == 0.5
    assert float(full["style_strength_mean"]) == 4.5
    assert float(full["identity_acceptable_rate"]) == 1.0
    assert full["invalid_count"] == "1"
    assert feedback["status"] == "partial"
    assert feedback["missing_count"] == "1"
    assert guarded["status"] == "pending_manual_review"
    assert guarded["missing_count"] == "3"
    assert guarded_feedback["status"] == "ready"
    assert full_case["style"] == "fresh_japanese"
    assert full_case["profile_case_id"] == "case_1"
    assert full_case["aesthetic_profile_id"] == "profile_1"


def test_style_retention_summary_keeps_pending_when_blank(tmp_path: Path):
    case = rendered_case(tmp_path)
    materialize_identity_guard_outputs(case, PassingIdentity())

    write_style_retention_artifacts(tmp_path, [case])

    rows = read_csv_dicts(tmp_path / "style_retention_summary.csv")
    assert {row["status"] for row in rows} == {"pending_manual_review"}
    assert all(row["missing_count"] == "3" for row in rows)


def test_style_retention_review_preserves_profile_provenance(tmp_path: Path):
    from jesr_core import normalize_aesthetic_profile

    case = rendered_case(tmp_path)
    profile_case = JESR_PROFILE_CASES["fresh_japanese"]
    case.aesthetic_profile = normalize_aesthetic_profile(profile_case["profile"])
    case.profile_case_id = profile_case["case_id"]
    materialize_identity_guard_outputs(case, PassingIdentity())

    write_style_retention_artifacts(tmp_path, [case])

    rows = read_csv_dicts(tmp_path / "style_retention_review.csv")
    assert {row["profile_case_id"] for row in rows} == {"case_1_fresh_japanese"}
    assert {row["aesthetic_profile_id"] for row in rows} == {"jap_profile_case_fresh_japanese"}
    assert {row["aesthetic_profile_revision"] for row in rows} == {"1"}


def test_style_variant_summary_reports_guard_fallback(tmp_path: Path):
    case = rendered_case(tmp_path)
    materialize_identity_guard_outputs(case, UnavailableIdentity())
    rows = build_metric_rows([case], LPIPSEvaluator(enabled=False), UnavailableIdentity())

    summary = summarize_metrics_by_style_variant(rows)
    guarded = next(row for row in summary if row["variant"] == "guarded_full")

    assert guarded["identity_guard_fallback_rate"] == 1.0
    assert guarded["identity_guard_fallback_count"] == 1
    assert guarded["identity_guard_evaluable_rate"] == 0.0
    assert guarded["identity_guard_unavailable_fallback_rate"] == 1.0


def test_not_evaluable_guard_fallback_is_not_counted_as_success(tmp_path: Path):
    case = rendered_case(tmp_path)
    materialize_identity_guard_outputs(case, UnavailableIdentity())

    assert is_status_ok(case.guarded_full_status) is False


def test_fid_score_keeps_errors_out_of_numeric_score(tmp_path: Path):
    reference = tmp_path / "reference"
    generated = tmp_path / "generated"
    reference.mkdir()
    generated.mkdir()

    def raises(_paths, batch_size, device, dims):
        raise RuntimeError("fid failed")

    score, status, error = fid_score_against(raises, reference=reference, generated=generated, device="cpu")

    assert score is None
    assert status == "error"
    assert "fid failed" in error


def test_fid_score_uses_single_item_batches_for_mixed_image_sizes(tmp_path: Path):
    reference = tmp_path / "reference"
    generated = tmp_path / "generated"
    reference.mkdir()
    generated.mkdir()
    seen = {}

    def succeeds(_paths, batch_size, device, dims):
        seen["batch_size"] = batch_size
        seen["device"] = device
        seen["dims"] = dims
        return 12.5

    score, status, error = fid_score_against(succeeds, reference=reference, generated=generated, device="cpu")

    assert score == 12.5
    assert status == "ok"
    assert error == ""
    assert seen == {"batch_size": 1, "device": "cpu", "dims": 2048}


def test_user_eval_summary_aggregates_filled_scores(tmp_path: Path):
    user_eval = tmp_path / "filled_user_eval.csv"
    user_eval.write_text(
        "\n".join(
            [
                "variant,paper_label,identity_score_1_5,naturalness_score_1_5,style_match_score_1_5,controllability_score_1_5,preferred_for_save_0_1,reviewer_id",
                "full,JESR full,4,3,4,5,1,r1",
                "full,JESR full,5,4,4,4,1,r2",
            ]
        ),
        encoding="utf-8",
    )

    write_user_eval_summary(tmp_path, user_eval)

    summary = (tmp_path / "user_eval_summary.csv").read_text(encoding="utf-8")
    assert "full,JESR full" in summary
    assert "ready" in summary
    assert "4.5" in summary


def test_jesr_proxy_eval_summary_is_separate_from_user_eval_and_statused(tmp_path: Path):
    assert jesr_theme_label("feedback_full") == "JESR-Feedback"

    write_jesr_proxy_eval_summary(tmp_path)
    pending = (tmp_path / "jesr_proxy_eval_summary.csv").read_text(encoding="utf-8")
    assert "pending_jesr_proxy_eval" in pending
    assert "JESR-Profile-Recipe" in pending

    proxy_eval = tmp_path / "proxy_eval.csv"
    proxy_eval.write_text(
        "\n".join(
            [
                "variant,proxy_eval_status,profile_alignment_score,identity_acceptability,style_cue_score,naturalness_proxy_score,negative_rule_violation_rate",
                "full,evaluated,0.9,0.8,1.0,0.7,0.0",
                "feedback_full,not_evaluable,,,,,",
                "guarded_full,evaluated,1.4,0.8,1.0,0.7,0.0",
            ]
        ),
        encoding="utf-8",
    )

    write_jesr_proxy_eval_summary(tmp_path, proxy_eval)
    summary = (tmp_path / "jesr_proxy_eval_summary.csv").read_text(encoding="utf-8")
    assert "full,JESR full,JESR-Profile-Recipe" in summary
    assert "feedback_full,JESR + feedback,JESR-Feedback" in summary
    assert "not_evaluable" in summary
    assert "invalid_input" in summary


def test_compute_jesr_proxy_evaluation_uses_recipe_and_profile_not_human_scores():
    from jesr_core import apply_aesthetic_profile, default_aesthetic_profile, default_recipe, recipe_with_jesr_metadata

    profile = default_aesthetic_profile("seed_gallery")
    profile["profile_status"] = "ready"
    profile["profile_vector"]["style_strength"] = 0.5
    profile["style_preferences"]["preferred_style_ids"] = ["fresh_japanese"]
    recipe = recipe_with_jesr_metadata(
        apply_aesthetic_profile(default_recipe("fresh_japanese"), profile),
        profile,
    )

    record = compute_jesr_proxy_evaluation(
        profile=profile,
        recipe=recipe,
        identity_similarity=0.9,
        naturalness_score=0.8,
    )

    assert record["proxy_eval_status"] == "evaluated"
    assert 0.0 <= record["profile_alignment_score"] <= 1.0
    assert record["style_cue_score"] == 1.0
    assert record["identity_acceptability"] == 0.9

    missing = compute_jesr_proxy_evaluation(profile=None, recipe=recipe)
    assert missing["proxy_eval_status"] == "not_evaluable"


def test_normal_run_proxy_eval_records_are_explicit_when_profile_is_missing(tmp_path: Path):
    case = rendered_case(tmp_path)
    materialize_identity_guard_outputs(case, PassingIdentity())
    rows = build_metric_rows([case], LPIPSEvaluator(enabled=False), PassingIdentity())

    records = write_jesr_proxy_eval_records(tmp_path, [case], rows)
    records_csv = (tmp_path / "jesr_proxy_eval_records.csv").read_text(encoding="utf-8")
    write_jesr_proxy_eval_summary(tmp_path)
    summary_csv = (tmp_path / "jesr_proxy_eval_summary.csv").read_text(encoding="utf-8")
    full = next(record for record in records if record["variant"] == "full")

    assert records
    assert {record["proxy_eval_status"] for record in records} == {"not_evaluable"}
    assert {record["proxy_eval_reason"] for record in records} == {"missing_profile"}
    assert full["profile_case_id"] is None
    assert full["aesthetic_profile_id"] is None
    assert "not_evaluable" in records_csv
    assert "missing_profile" in records_csv
    assert "not_evaluable" in summary_csv


def test_profile_case_proxy_eval_records_include_metadata_and_evaluated_status(tmp_path: Path):
    from jesr_core import apply_aesthetic_profile, default_recipe, normalize_aesthetic_profile, recipe_with_jesr_metadata

    case = rendered_case(tmp_path)
    profile_case = JESR_PROFILE_CASES["fresh_japanese"]
    profile = normalize_aesthetic_profile(profile_case["profile"])
    recipe = recipe_with_jesr_metadata(
        apply_aesthetic_profile(default_recipe("fresh_japanese"), profile),
        profile,
    )
    case.aesthetic_profile = profile
    case.profile_case_id = profile_case["case_id"]
    case.recipe_snapshots["full"] = recipe
    materialize_identity_guard_outputs(case, PassingIdentity())
    rows = build_metric_rows([case], LPIPSEvaluator(enabled=False), PassingIdentity())

    records = build_jesr_proxy_eval_records([case], rows)
    full = next(record for record in records if record["variant"] == "full")
    slider = next(record for record in records if record["variant"] == "slider_only")

    assert full["proxy_eval_status"] == "evaluated"
    assert full["profile_case_id"] == "case_1_fresh_japanese"
    assert full["aesthetic_profile_id"] == "jap_profile_case_fresh_japanese"
    assert full["aesthetic_profile_revision"] == 1
    assert full["profile_alignment_score"] == 1.0
    assert full["style_cue_score"] == 1.0
    assert 0.0 <= full["naturalness_proxy_score"] <= 1.0
    assert slider["proxy_eval_status"] == "not_evaluable"
    assert slider["proxy_eval_reason"] == "missing_recipe"


def write_csv_fixture(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as file_obj:
        writer = csv.DictWriter(file_obj, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_manifest_run_fixture(root: Path, run_name: str, *, fallback_rate: float) -> Path:
    run_dir = root / run_name
    run_dir.mkdir(parents=True)
    (run_dir / "contact_sheets").mkdir()
    write_csv_fixture(
        run_dir / "metrics_summary_by_variant.csv",
        [
            {
                "variant": "full",
                "identity_pass_rate": 0.7,
                "identity_guard_fallback_rate": "",
                "ssim_mean": 0.81,
                "lpips_mean": 0.22,
            },
            {
                "variant": "guarded_full",
                "identity_pass_rate": 1.0,
                "identity_guard_fallback_rate": fallback_rate,
                "ssim_mean": 0.93,
                "lpips_mean": 0.08,
            },
        ],
    )
    write_csv_fixture(
        run_dir / "jesr_proxy_eval_summary.csv",
        [
            {
                "variant": "full",
                "proxy_eval_status": "evaluated",
                "n_records": 30,
                "profile_alignment_score_mean": 0.98,
                "negative_rule_violation_rate_mean": 0.0,
            }
        ],
    )
    write_csv_fixture(
        run_dir / "style_retention_summary.csv",
        [
            {
                "variant": "full",
                "status": "pending_manual_review",
            }
        ],
    )
    (run_dir / "env_snapshot.json").write_text(
        json.dumps(
            {
                "environment": {
                    "HELLOBEAUTY_CREATIVE_MAX_STRENGTH": "0.32",
                    "HELLOBEAUTY_CREATIVE_PRESERVE_BLEND_ALPHA": "0.18",
                }
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "run_config.json").write_text("{}", encoding="utf-8")
    return run_dir


def test_manifest_classifies_formal_and_non_paper_runs_and_reads_metrics(tmp_path: Path):
    write_manifest_run_fixture(tmp_path, "formal_a", fallback_rate=0.3)
    write_manifest_run_fixture(tmp_path, "formal_b", fallback_rate=0.4)
    write_manifest_run_fixture(tmp_path, "smoke_a", fallback_rate=0.0)

    manifest = write_result_collection_manifest(
        tmp_path,
        formal_runs=["formal_a", "formal_b"],
        non_paper_runs=["smoke_a"],
    )

    readme = (tmp_path / "README.md").read_text(encoding="utf-8")
    disk_manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    formal_a = manifest["formal_paper_used_runs"][0]

    assert [run["run_name"] for run in manifest["formal_paper_used_runs"]] == ["formal_a", "formal_b"]
    assert [run["run_name"] for run in manifest["non_paper_runs"]] == ["smoke_a"]
    assert "proxy_eval_is_deterministic_offline_not_human_eval" in manifest["claim_boundaries"]
    assert "guarded_identity_pass_is_containment_not_creative_success" in manifest["claim_boundaries"]
    assert formal_a["key_metrics"]["guarded_full"]["identity_guard_fallback_rate"] == 0.3
    assert formal_a["proxy_eval"]["full"]["profile_alignment_score_mean"] == 0.98
    assert disk_manifest["formal_paper_used_runs"][0]["files"]["contact_sheets/"] is True
    assert "identity_guard_fallback_rate=0.3" in readme
    assert "deterministic offline evidence, not human evaluation" in readme


@pytest.mark.parametrize(
    ("mode_args", "root_arg"),
    [
        (
            [
                "--aggregate-user-eval-only",
                "--user-eval-results",
                "filled.csv",
                "--output-dir",
                "run",
            ],
            "--output-dir",
        ),
        (
            [
                "--aggregate-style-retention-only",
                "--style-retention-results",
                "filled.csv",
                "--output-dir",
                "run",
            ],
            "--output-dir",
        ),
        (
            [
                "--aggregate-jesr-proxy-eval-only",
                "--jesr-proxy-eval-results",
                "filled.csv",
                "--output-dir",
                "run",
            ],
            "--output-dir",
        ),
        (
            [
                "--refresh-style-retention-artifacts-only",
                "--output-dir",
                "run",
            ],
            "--output-dir",
        ),
        (
            [
                "--write-result-collection-manifest",
                "--result-root",
                "collection",
            ],
            "--result-root",
        ),
    ],
)
def test_read_only_modes_reject_clean_before_deleting_existing_files(
    tmp_path: Path,
    monkeypatch,
    mode_args: list[str],
    root_arg: str,
):
    root_name = "collection" if root_arg == "--result-root" else "run"
    protected_root = tmp_path / root_name
    protected_root.mkdir()
    sentinel = protected_root / "sentinel.txt"
    sentinel.write_text("keep", encoding="utf-8")
    filled = tmp_path / "filled.csv"
    filled.write_text(
        "variant,style_visible_0_1,style_strength_1_5,identity_acceptable_0_1\nfull,1,5,1\n",
        encoding="utf-8",
    )
    argv = ["run_real_metric_experiments.py", "--clean"]
    for item in mode_args:
        argv.append(str(tmp_path / item) if item in {"run", "collection", "filled.csv"} else item)
    monkeypatch.setattr(sys, "argv", argv)

    with pytest.raises(SystemExit):
        main()

    assert sentinel.read_text(encoding="utf-8") == "keep"


def test_ablation_grid_writes_four_contract_complete_runs(tmp_path: Path):
    sentinel = tmp_path / "keep.txt"
    sentinel.write_text("do-not-delete", encoding="utf-8")
    stale_run_dir = tmp_path / "v4_ablation_n6_strength_0p38_blend_0"
    stale_run_dir.mkdir()
    stale_file = stale_run_dir / "stale.txt"
    stale_file.write_text("old", encoding="utf-8")
    args = argparse.Namespace(
        ablation_output_root=tmp_path,
        ablation_strengths="0.38,0.32",
        ablation_blend_alphas="0,0.18",
        clean=True,
        samples_per_style=6,
        seed=20260513,
        styles="fresh_japanese,clear_korean",
    )

    def fake_run(_args, run_dir: Path, env: dict[str, str]) -> None:
        assert not (run_dir / "stale.txt").exists()
        run_dir.mkdir(parents=True)
        (run_dir / "fresh.txt").write_text("new", encoding="utf-8")
        write_csv_fixture(
            run_dir / "metrics_summary_by_variant.csv",
            [
                {
                    "variant": "full",
                    "identity_pass_rate": 0.7,
                    "identity_guard_fallback_rate": "",
                    "ssim_mean": 0.8,
                    "lpips_mean": 0.2,
                },
                {
                    "variant": "guarded_full",
                    "identity_pass_rate": 1.0,
                    "identity_guard_fallback_rate": 0.3,
                    "ssim_mean": 0.9,
                    "lpips_mean": 0.1,
                },
            ],
        )
        (run_dir / "env_snapshot.json").write_text(
            json.dumps(
                {
                    "environment": {
                        "HELLOBEAUTY_CREATIVE_MAX_STRENGTH": env["HELLOBEAUTY_CREATIVE_MAX_STRENGTH"],
                        "HELLOBEAUTY_CREATIVE_PRESERVE_BLEND_ALPHA": env[
                            "HELLOBEAUTY_CREATIVE_PRESERVE_BLEND_ALPHA"
                        ],
                        "HELLOBEAUTY_CREATIVE_SEED": env["HELLOBEAUTY_CREATIVE_SEED"],
                    }
                }
            ),
            encoding="utf-8",
        )

    manifest = run_ablation_grid(args, run_invocation=fake_run)

    summary = read_csv_dicts(tmp_path / "ablation_summary_by_setting.csv")
    assert (tmp_path / "ablation_grid_manifest.json").exists()
    assert len(manifest["settings"]) == 4
    assert sentinel.read_text(encoding="utf-8") == "do-not-delete"
    assert not stale_file.exists()
    assert (stale_run_dir / "fresh.txt").exists()
    assert {Path(setting["run_dir"]).name for setting in manifest["settings"]} == {
        "v4_ablation_n6_strength_0p38_blend_0",
        "v4_ablation_n6_strength_0p38_blend_0p18",
        "v4_ablation_n6_strength_0p32_blend_0",
        "v4_ablation_n6_strength_0p32_blend_0p18",
    }
    assert len(summary) == 16
    assert any(row["variant"] == "guarded_full" and row["identity_guard_fallback_rate"] == "0.3" for row in summary)


def test_refresh_style_retention_artifacts_rebuilds_from_metrics_by_image(tmp_path: Path):
    image_dir = tmp_path / "images" / "fresh_japanese" / "sample"
    image_dir.mkdir(parents=True)
    paths = {}
    for index, name in enumerate(["input", "fidelity", "full", "feedback_full", "guarded_full", "guarded_feedback_full"]):
        paths[name] = image_dir / f"{name}.png"
        write_image(paths[name], 80 + index)
    write_csv_fixture(
        tmp_path / "metrics_by_image.csv",
        [
            {
                "style": "fresh_japanese",
                "sample": "sample.png",
                "session_id": "s1",
                "photo_id": "p1",
                "variant": variant,
                "image_path": str(paths[variant]),
                "profile_case_id": "case_1",
                "aesthetic_profile_id": "profile_1",
                "aesthetic_profile_revision": 2,
            }
            for variant in ["fidelity", "full", "feedback_full", "guarded_full", "guarded_feedback_full"]
        ],
    )

    refresh_style_retention_artifacts(tmp_path)

    sheet = Image.open(tmp_path / "contact_sheets" / "fresh_japanese" / "sample.png")
    rows = read_csv_dicts(tmp_path / "style_retention_review.csv")
    assert sheet.width == 6 * 16 + 7 * 8
    assert {row["variant"] for row in rows} == {
        "full",
        "feedback_full",
        "guarded_full",
        "guarded_feedback_full",
    }
    assert {row["profile_case_id"] for row in rows} == {"case_1"}


def test_refresh_style_retention_artifacts_fails_when_guarded_variant_is_missing(tmp_path: Path):
    image_dir = tmp_path / "images" / "fresh_japanese" / "sample"
    image_dir.mkdir(parents=True)
    paths = {}
    for index, name in enumerate(["fidelity", "full", "feedback_full", "guarded_feedback_full"]):
        paths[name] = image_dir / f"{name}.png"
        write_image(paths[name], 80 + index)
    write_csv_fixture(
        tmp_path / "metrics_by_image.csv",
        [
            {
                "style": "fresh_japanese",
                "sample": "sample.png",
                "session_id": "s1",
                "photo_id": "p1",
                "variant": variant,
                "image_path": str(paths[variant]),
                "profile_case_id": "",
                "aesthetic_profile_id": "",
                "aesthetic_profile_revision": "",
            }
            for variant in ["fidelity", "full", "feedback_full", "guarded_feedback_full"]
        ],
    )

    with pytest.raises(SystemExit, match="missing variants: guarded_full"):
        refresh_style_retention_artifacts(tmp_path)

    assert not (tmp_path / "style_retention_review.csv").exists()


def test_refresh_style_retention_artifacts_fails_on_header_only_metrics_csv(tmp_path: Path):
    (tmp_path / "metrics_by_image.csv").write_text(
        "style,sample,session_id,photo_id,variant,image_path\n",
        encoding="utf-8",
    )

    with pytest.raises(SystemExit, match="empty metrics_by_image.csv"):
        refresh_style_retention_artifacts(tmp_path)

    assert not (tmp_path / "style_retention_review.csv").exists()
