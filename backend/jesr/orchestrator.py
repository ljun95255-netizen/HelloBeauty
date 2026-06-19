from __future__ import annotations

import secrets
import tempfile
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from PIL import Image

from jesr_core import (
    aesthetic_profile_from_seed_choices,
    apply_aesthetic_profile as apply_profile_to_recipe,
    apply_style_preset,
    default_aesthetic_profile,
    default_recipe,
    is_profile_recipe_stale,
    normalize_aesthetic_profile,
    recipe_with_jesr_metadata,
)

from backend.jesr.feedback import FeedbackInterpreter
from backend.jesr.metric_control import run_metric_control_loop
from backend.jesr.recipe_trace import trace_recorder
from backend.providers.base import ProviderResult
from backend.providers.jesr_creative import JESRCreativeProvider
from backend.providers.jesr_fidelity import JESRFidelityProvider
from backend.services.session_store import iso_now, session_store
from backend.services.storage import BEAUTY_DIR, storage_service


class JESROrchestrator:
    name = "JESR-Orchestrator"

    def __init__(
        self,
        fidelity_provider: JESRFidelityProvider | None = None,
        creative_provider: JESRCreativeProvider | None = None,
    ) -> None:
        self.fidelity = fidelity_provider or JESRFidelityProvider()
        self.creative = creative_provider or JESRCreativeProvider()
        self.feedback = FeedbackInterpreter()

    def initialize_recipe(self, session_id: str, style_id: str | None = None) -> dict[str, Any]:
        recipe = default_recipe(style_id)
        session_store.recipes[session_id] = recipe
        return deepcopy(recipe)

    def get_recipe(self, session_id: str) -> dict[str, Any]:
        if session_id not in session_store.recipes:
            return self.initialize_recipe(session_id)
        return deepcopy(session_store.recipes[session_id])

    def select_style(self, session_id: str, preset_id: str | None) -> dict[str, Any]:
        if session_id in session_store.aesthetic_profiles:
            return self.select_style_with_profile(session_id, preset_id)
        recipe = self.get_recipe(session_id)
        recipe = apply_style_preset(recipe, preset_id)
        session_store.recipes[session_id] = recipe
        return deepcopy(recipe)

    def get_aesthetic_profile(self, session_id: str) -> dict[str, Any] | None:
        profile = session_store.aesthetic_profiles.get(session_id)
        return deepcopy(profile) if profile is not None else None

    def reset_aesthetic_profile(self, session_id: str) -> None:
        session_store.aesthetic_profiles.pop(session_id, None)

    def initialize_aesthetic_profile(self, session_id: str, source: str, payload: dict[str, Any]) -> dict[str, Any]:
        if source in {"reference_photos", "reference_photo"}:
            previous = session_store.aesthetic_profiles.get(session_id)
            if previous and previous.get("profile_status") == "ready":
                profile = self._merge_reference_photos_into_profile(previous, payload)
                return self.apply_aesthetic_profile(session_id, profile)
        profile = self._aesthetic_profile_from_payload(source, payload)
        return self.apply_aesthetic_profile(session_id, profile)

    def sync_legacy_aesthetic_profile(self, session_id: str, source: str, payload: dict[str, Any]) -> dict[str, Any]:
        profile = self._aesthetic_profile_from_payload(source, payload)
        return self.apply_aesthetic_profile(session_id, profile, update_recipe=False)

    def _aesthetic_profile_from_payload(self, source: str, payload: dict[str, Any]) -> dict[str, Any]:
        if source in {"seed_gallery", "seed_selection"}:
            return aesthetic_profile_from_seed_choices(payload.get("choices", []), self._seed_catalog())
        elif source in {"reference_photos", "reference_photo"}:
            profile = default_aesthetic_profile("reference_photos")
            profile["profile_id"] = "jap_reference_photos"
            profile["profile_status"] = "defaulted"
            profile["evidence"]["reference_photo_ids"] = _reference_photo_ids(payload)
            return profile
        else:
            profile = default_aesthetic_profile(source)
            profile["profile_status"] = "ready"
            profile["evidence"]["questionnaire_answers"] = deepcopy(payload)
            vector = payload.get("profile_vector") or payload.get("base_style_profile")
            if isinstance(vector, dict):
                profile["profile_vector"].update(vector)
            return profile

    def _merge_reference_photos_into_profile(self, profile: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
        merged = deepcopy(profile)
        evidence = deepcopy(merged.get("evidence") or {})
        reference_photo_ids = _reference_photo_ids(payload)
        existing_reference_ids = evidence.get("reference_photo_ids", [])
        if not isinstance(existing_reference_ids, list):
            existing_reference_ids = []
        evidence["reference_photo_ids"] = _unique_strings([*existing_reference_ids, *reference_photo_ids])
        merged["source"] = "hybrid"
        merged["profile_status"] = "ready"
        merged["evidence"] = evidence
        metadata = deepcopy(merged.get("metadata") or {})
        if not isinstance(metadata, dict):
            metadata = {}
        metadata["reference_photo_merge"] = {
            "source": "reference_photos",
            "reference_photo_ids": evidence["reference_photo_ids"],
            "preserved_profile_vector": True,
            "preserved_style_preferences": True,
        }
        merged["metadata"] = metadata
        return merged

    def apply_aesthetic_profile(self, session_id: str, profile: dict[str, Any], *, update_recipe: bool = True) -> dict[str, Any]:
        normalized = normalize_aesthetic_profile(profile)
        previous = session_store.aesthetic_profiles.get(session_id)
        revision = int(previous.get("profile_revision", 0)) + 1 if previous else int(normalized.get("profile_revision", 1))
        now = iso_now()
        normalized["profile_revision"] = revision
        normalized["created_at"] = previous.get("created_at", normalized.get("created_at", now)) if previous else normalized.get("created_at", now)
        normalized["updated_at"] = now
        session_store.aesthetic_profiles[session_id] = deepcopy(normalized)
        if update_recipe:
            self.initialize_profile_recipe(session_id)
        return deepcopy(normalized)

    def initialize_profile_recipe(self, session_id: str, style_id: str | None = None) -> dict[str, Any]:
        profile = self.get_aesthetic_profile(session_id)
        if profile is None:
            recipe = recipe_with_jesr_metadata(default_recipe(style_id), None)
        else:
            selected_style = style_id if style_id is not None else self._current_or_profile_style(session_id, profile)
            recipe = default_recipe()
            if selected_style:
                recipe = apply_style_preset(recipe, selected_style)
            recipe = apply_profile_to_recipe(recipe, profile)
            recipe = recipe_with_jesr_metadata(recipe, profile)
        session_store.recipes[session_id] = deepcopy(recipe)
        return deepcopy(recipe)

    def get_profile_recipe(self, session_id: str) -> dict[str, Any]:
        profile = self.get_aesthetic_profile(session_id)
        recipe = self.get_recipe(session_id)
        if profile is not None and is_profile_recipe_stale(recipe, profile):
            return self.initialize_profile_recipe(session_id, recipe.get("style_id"))
        if "jesr" not in recipe:
            recipe = recipe_with_jesr_metadata(recipe, profile)
            session_store.recipes[session_id] = deepcopy(recipe)
        return deepcopy(recipe)

    def select_style_with_profile(self, session_id: str, style_id: str | None) -> dict[str, Any]:
        if session_id in session_store.aesthetic_profiles:
            return self.initialize_profile_recipe(session_id, style_id)
        return self.select_style(session_id, style_id)

    def _current_or_profile_style(self, session_id: str, profile: dict[str, Any]) -> str | None:
        current = session_store.recipes.get(session_id, {})
        if current.get("style_id"):
            return str(current["style_id"])
        preferred = profile.get("style_preferences", {}).get("preferred_style_ids", [])
        return preferred[0] if preferred else None

    def _seed_catalog(self) -> list[dict[str, Any]]:
        profiles_path = BEAUTY_DIR / "profiles.json"
        if not profiles_path.exists():
            return []
        return json.loads(profiles_path.read_text(encoding="utf-8"))

    def iterate(
        self,
        *,
        session_id: str,
        photo_id: str,
        pain_tags: list[str] | None = None,
        free_text: str | None = None,
    ) -> dict[str, Any]:
        previous = self.get_recipe(session_id)
        updated = self.feedback.apply(previous, pain_tags, free_text)
        session_store.recipes[session_id] = updated
        iteration = {
            "id": f"itr_{secrets.token_hex(8)}",
            "session_id": session_id,
            "photo_id": photo_id,
            "created_at": iso_now(),
            "pain_tags": pain_tags or [],
            "free_text": free_text,
            "previous_recipe": previous,
            "updated_recipe": updated,
        }
        session_store.iterations.setdefault(session_id, []).append(iteration)
        return iteration

    def rollback(self, session_id: str, iteration_id: str | None = None) -> dict[str, Any]:
        iterations = session_store.iterations.get(session_id, [])
        if not iterations:
            recipe = self.get_recipe(session_id)
            return {"id": None, "recipe": recipe, "status": "no_iterations"}
        target = None
        if iteration_id:
            target = next((item for item in iterations if item["id"] == iteration_id), None)
        target = target or iterations[-1]
        session_store.recipes[session_id] = deepcopy(target["previous_recipe"])
        rollback_iteration = {
            "id": f"rbk_{secrets.token_hex(8)}",
            "session_id": session_id,
            "rolled_back_from": target["id"],
            "created_at": iso_now(),
            "recipe": deepcopy(target["previous_recipe"]),
        }
        return rollback_iteration

    def render(
        self,
        *,
        session_id: str,
        photo_id: str,
        image: Image.Image,
        mode: str = "auto",
        retouch_params: dict[str, Any] | None = None,
        metric_control: dict[str, Any] | None = None,
    ) -> tuple[ProviderResult, dict[str, Any]]:
        recipe = self.get_recipe(session_id)
        provider_chain = [self.name]
        render_params: dict[str, Any] = {"mode": mode}

        if mode == "targeted-retouch":
            fidelity_result = self.fidelity.targeted_retouch(image, recipe, retouch_params)
        else:
            fidelity_result = self.fidelity.smart_optimize(image, recipe)
        provider_chain.append(fidelity_result.provider)
        render_params["fidelity"] = fidelity_result.params

        final_result = fidelity_result
        creative_needed = mode in {"auto", "creative", "aigc"} and bool(recipe.get("creative", {}).get("preset_id"))
        if creative_needed:
            creative_result = self.creative.render(fidelity_result.image, recipe)
            provider_chain.append(creative_result.provider)
            render_params["creative"] = creative_result.params
            if creative_result.status == "jesr_creative_diffusion_img2img_ok":
                final_result = creative_result
            else:
                final_result.status = f"{final_result.status}; {creative_result.status}"
            if metric_control:
                final_result = self._render_metric_controlled(
                    input_image=image,
                    fidelity_result=fidelity_result,
                    creative_result=creative_result,
                    recipe=recipe,
                    metric_control=metric_control,
                )
                render_params["metric_control"] = final_result.params.get("metric_control", {})

        job_id = f"job_{secrets.token_hex(8)}"
        storage_service.save_image(final_result.image, "job", job_id)
        output_asset = f"/api/assets/job/{job_id}"
        trace = trace_recorder.record(
            session_id=session_id,
            recipe=recipe,
            provider_chain=provider_chain,
            render_params=render_params,
            model_info=_model_info(render_params),
            output_asset=output_asset,
        )
        final_result.params["trace_id"] = trace["id"]
        final_result.params["job_id"] = job_id
        return final_result, trace

    def _render_metric_controlled(
        self,
        *,
        input_image: Image.Image,
        fidelity_result: ProviderResult,
        creative_result: ProviderResult,
        recipe: dict[str, Any],
        metric_control: dict[str, Any],
    ) -> ProviderResult:
        primary_evaluator = metric_control["primary_evaluator"]
        identity_evaluators = metric_control.get("identity_evaluators") or {
            getattr(primary_evaluator, "backend", "identity"): primary_evaluator
        }
        required_backends = metric_control.get("required_backends") or list(identity_evaluators.keys())
        source_variant = str(metric_control.get("source_variant") or "full")
        original_strength = float(recipe.get("creative", {}).get("strength", 0.0))
        threshold = float(metric_control.get("identity_threshold", getattr(primary_evaluator, "threshold", 0.72)))

        with tempfile.TemporaryDirectory(prefix="jesr_metric_control_") as tmp:
            tmp_dir = Path(tmp)
            input_path = tmp_dir / "input.png"
            fidelity_path = tmp_dir / "fidelity.png"
            source_path = tmp_dir / "attempt_1_source.png"
            input_image.convert("RGB").save(input_path)
            fidelity_result.image.convert("RGB").save(fidelity_path)
            creative_result.image.convert("RGB").save(source_path)

            def render_attempt(strength: float, attempt_index: int, directory: Path) -> tuple[Path, str, float, dict[str, Any]]:
                target = directory / f"attempt_{attempt_index}.png"
                if attempt_index == 1:
                    source_path.replace(target)
                    return target, creative_result.status, 0.0, dict(creative_result.params)
                retry_recipe = deepcopy(recipe)
                retry_recipe.setdefault("creative", {})["strength"] = float(strength)
                retry = self.creative.render(fidelity_result.image, retry_recipe)
                retry.image.convert("RGB").save(target)
                return target, retry.status, 0.0, dict(retry.params)

            decision = run_metric_control_loop(
                source_variant=source_variant,
                input_path=input_path,
                fidelity_path=fidelity_path,
                original_strength=original_strength,
                render_attempt=render_attempt,
                candidate_dir=tmp_dir / "retry_candidates" / source_variant,
                primary_evaluator=primary_evaluator,
                identity_evaluators=identity_evaluators,
                required_backends=required_backends,
                identity_threshold=threshold,
            )
            output_path = fidelity_path if decision.fallback_to_fidelity else decision.selected_path
            output_image = Image.open(output_path).convert("RGB").copy()

        status = (
            f"guarded_{source_variant}_fallback_to_fidelity_{decision.guard_reason}"
            if decision.fallback_to_fidelity
            else f"guarded_{source_variant}_ok_{decision.selected_reason}"
        )
        params = {
            **(fidelity_result.params if decision.fallback_to_fidelity else creative_result.params),
            "metric_control": decision.metadata(),
        }
        return ProviderResult(
            image=output_image,
            status=status,
            provider=self.name,
            params=params,
        )


jesr_orchestrator = JESROrchestrator()


def _model_info(render_params: dict[str, Any]) -> dict[str, dict[str, str | None]]:
    model_info: dict[str, dict[str, str | None]] = {}
    for key in ("fidelity", "creative"):
        params = render_params.get(key)
        if not isinstance(params, dict):
            continue
        model_info[key] = {
            "id": params.get("model_id"),
            "version": params.get("model_version"),
            "reason": params.get("model_reason"),
        }
    return model_info


def _reference_photo_ids(payload: dict[str, Any]) -> list[str]:
    raw = (
        payload.get("reference_photo_ids")
        or payload.get("photo_ids")
        or payload.get("reference_photos")
        or payload.get("reference_photo")
        or []
    )
    if isinstance(raw, str):
        raw = [raw]
    if not isinstance(raw, list):
        return []
    result: list[str] = []
    for value in raw:
        text = str(value).strip()
        if text and text not in result:
            result.append(text)
    return result


def _unique_strings(values: list[Any]) -> list[str]:
    result: list[str] = []
    for value in values:
        text = str(value).strip()
        if text and text not in result:
            result.append(text)
    return result
