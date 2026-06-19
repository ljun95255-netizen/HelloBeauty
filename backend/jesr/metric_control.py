from __future__ import annotations

import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Protocol


class IdentityMetric(Protocol):
    backend: str
    available: bool
    reason: str
    threshold: float

    def similarity(self, a_path: Path, b_path: Path) -> float | None:
        ...


RenderAttempt = Callable[[float, int, Path], tuple[Path, str, float, dict[str, Any]]]


@dataclass
class MetricControlAttempt:
    attempt_index: int
    strength: float
    path: Path
    status: str
    render_seconds: float
    params: dict[str, Any] = field(default_factory=dict)
    identity_scores: dict[str, float | None] = field(default_factory=dict)
    identity_status: dict[str, str] = field(default_factory=dict)
    identity_eval_seconds: float = 0.0
    passed: bool = False
    reason: str = ""

    @property
    def render_ok(self) -> bool:
        return is_creative_render_ok(self.status)


@dataclass
class MetricControlDecision:
    source_variant: str
    selected_path: Path
    selected_attempt: int | None
    selected_reason: str
    selected_similarity: float | None
    best_similarity: float | None
    primary_backend: str
    required_backends: list[str]
    identity_threshold: float
    attempts: list[MetricControlAttempt]
    render_seconds: float
    identity_eval_seconds: float
    total_seconds: float
    preserve_blend_alpha: float | None
    fallback_to_fidelity: bool
    guard_reason: str
    guarded_path: Path | None = None

    def metadata(self) -> dict[str, Any]:
        selected = self.selected_attempt_record()
        arcface_similarity = _score_for_alias(selected, "insightface")
        facenet_similarity = _score_for_alias(selected, "facenet")
        return {
            "creative_strength_requested": _param_float(selected, "strength_requested", self.selected_strength()),
            "creative_strength_effective": _param_float(selected, "strength_effective", self.selected_strength()),
            "creative_retry_attempts": len(self.attempts),
            "creative_retry_primary_backend": self.primary_backend,
            "creative_retry_best_similarity": self.best_similarity,
            "creative_retry_selected_similarity": self.selected_similarity,
            "creative_retry_arcface_similarity": arcface_similarity,
            "creative_retry_facenet_similarity": facenet_similarity,
            "creative_retry_required_backends": ",".join(self.required_backends),
            "creative_retry_selected_reason": self.selected_reason,
            "creative_retry_render_seconds": self.render_seconds,
            "identity_eval_seconds": self.identity_eval_seconds,
            "total_guarded_seconds": self.total_seconds,
            "creative_preserve_blend_alpha": self.preserve_blend_alpha,
            "creative_retry_selected_attempt": self.selected_attempt,
            "creative_retry_selected_rate": int(self.selected_reason.startswith("identity_retry_passed")),
            "creative_retry_pass_rate": int(any(attempt.passed for attempt in self.attempts)),
        }

    def selected_attempt_record(self) -> MetricControlAttempt | None:
        if self.selected_attempt is None:
            return None
        return next((attempt for attempt in self.attempts if attempt.attempt_index == self.selected_attempt), None)

    def selected_strength(self) -> float | None:
        selected = self.selected_attempt_record()
        return selected.strength if selected is not None else None


def retry_strengths(original_strength: float, *, floor: float = 0.08) -> list[float]:
    values = [
        original_strength,
        max(floor, original_strength - 0.10),
        max(floor, original_strength - 0.18),
        max(floor, original_strength - 0.26),
    ]
    result: list[float] = []
    for value in values:
        rounded = round(float(value), 6)
        if rounded not in result:
            result.append(rounded)
    return result


def run_metric_control_loop(
    *,
    source_variant: str,
    input_path: Path,
    fidelity_path: Path,
    original_strength: float,
    render_attempt: RenderAttempt,
    candidate_dir: Path,
    primary_evaluator: IdentityMetric,
    identity_evaluators: dict[str, IdentityMetric],
    required_backends: list[str],
    identity_threshold: float,
    floor: float = 0.08,
    retry_when_identity_unavailable: bool = False,
) -> MetricControlDecision:
    candidate_dir.mkdir(parents=True, exist_ok=True)
    attempts: list[MetricControlAttempt] = []
    render_seconds = 0.0
    identity_eval_seconds = 0.0

    for attempt_index, strength in enumerate(retry_strengths(original_strength, floor=floor), start=1):
        path, status, seconds, params = render_attempt(strength, attempt_index, candidate_dir)
        render_seconds += float(seconds)
        attempt = MetricControlAttempt(
            attempt_index=attempt_index,
            strength=strength,
            path=path,
            status=status,
            render_seconds=float(seconds),
            params=params,
        )
        _score_attempt(
            attempt,
            input_path=input_path,
            primary_evaluator=primary_evaluator,
            identity_evaluators=identity_evaluators,
            required_backends=required_backends,
            identity_threshold=identity_threshold,
        )
        identity_eval_seconds += attempt.identity_eval_seconds
        attempts.append(attempt)

        if attempt.passed or (
            not retry_when_identity_unavailable
            and (not primary_evaluator.available or attempt.reason == "identity_similarity_unavailable")
        ):
            break

    selected = next((attempt for attempt in attempts if attempt.passed), None)
    if selected is None:
        selected = _best_attempt(attempts, primary_evaluator.backend)

    fallback, guard_reason = _guard_fallback_reason(selected, primary_evaluator, identity_threshold)
    selected_reason = (
        f"identity_retry_passed_attempt_{selected.attempt_index}"
        if selected.passed
        else _failed_selection_reason(source_variant, selected, primary_evaluator.backend)
    )
    return MetricControlDecision(
        source_variant=source_variant,
        selected_path=selected.path,
        selected_attempt=selected.attempt_index,
        selected_reason=selected_reason,
        selected_similarity=selected.identity_scores.get(primary_evaluator.backend),
        best_similarity=_best_similarity(attempts, primary_evaluator.backend),
        primary_backend=primary_evaluator.backend,
        required_backends=[backend for backend in required_backends if backend in identity_evaluators],
        identity_threshold=identity_threshold,
        attempts=attempts,
        render_seconds=render_seconds,
        identity_eval_seconds=identity_eval_seconds,
        total_seconds=render_seconds + identity_eval_seconds,
        preserve_blend_alpha=_preserve_blend_alpha(selected),
        fallback_to_fidelity=fallback,
        guard_reason=guard_reason,
        guarded_path=fidelity_path if fallback else selected.path,
    )


def write_guarded_output(
    *,
    decision: MetricControlDecision,
    target_path: Path,
    fidelity_path: Path,
) -> tuple[Path, str, dict[str, Any]]:
    selected_path = fidelity_path if decision.fallback_to_fidelity else decision.selected_path
    shutil.copy2(selected_path, target_path)
    guarded_variant = f"guarded_{decision.source_variant}"
    status = (
        f"{guarded_variant}_fallback_to_fidelity_{decision.guard_reason}"
        if decision.fallback_to_fidelity
        else f"{guarded_variant}_ok_{decision.selected_reason}"
    )
    guard = {
        "source_variant": decision.source_variant,
        "selected_variant": "fidelity" if decision.fallback_to_fidelity else decision.source_variant,
        "fallback_to_fidelity": int(decision.fallback_to_fidelity),
        "guard_reason": decision.guard_reason,
        "guard_identity_similarity": decision.selected_similarity,
        "guard_identity_evaluable": int(decision.selected_similarity is not None),
        "guard_unavailable_fallback": int(
            decision.guard_reason.startswith("identity_not_evaluable")
            or decision.guard_reason == "identity_similarity_unavailable"
        ),
        "identity_threshold": decision.identity_threshold,
        "source_status": decision.selected_reason,
    }
    return target_path, status, guard


def is_creative_render_ok(status: str) -> bool:
    return "jesr_creative_diffusion_img2img_ok" in str(status)


def _score_attempt(
    attempt: MetricControlAttempt,
    *,
    input_path: Path,
    primary_evaluator: IdentityMetric,
    identity_evaluators: dict[str, IdentityMetric],
    required_backends: list[str],
    identity_threshold: float,
) -> None:
    evaluators: dict[str, IdentityMetric] = dict(identity_evaluators)
    evaluators.setdefault(primary_evaluator.backend, primary_evaluator)

    start = time.perf_counter()
    for backend, evaluator in evaluators.items():
        if not evaluator.available:
            attempt.identity_scores[backend] = None
            attempt.identity_status[backend] = f"not_evaluable:{evaluator.reason}"
            continue
        value = evaluator.similarity(input_path, attempt.path)
        attempt.identity_scores[backend] = value
        attempt.identity_status[backend] = "ready" if value is not None else "similarity_unavailable"
    attempt.identity_eval_seconds = time.perf_counter() - start

    if not primary_evaluator.available:
        attempt.passed = False
        attempt.reason = f"identity_not_evaluable:{primary_evaluator.reason}"
        return
    if not attempt.render_ok:
        attempt.passed = False
        attempt.reason = f"render_status_not_ok:{attempt.status}"
        return
    primary_value = attempt.identity_scores.get(primary_evaluator.backend)
    if primary_value is None:
        attempt.passed = False
        attempt.reason = "identity_similarity_unavailable"
        return
    if primary_value < identity_threshold:
        attempt.passed = False
        attempt.reason = "primary_identity_below_threshold"
        return
    for backend in required_backends:
        evaluator = identity_evaluators.get(backend)
        if evaluator is None or not evaluator.available:
            continue
        value = attempt.identity_scores.get(backend)
        if value is None:
            attempt.passed = False
            attempt.reason = f"{backend}_identity_similarity_unavailable"
            return
        if value < identity_threshold:
            attempt.passed = False
            attempt.reason = f"{backend}_identity_below_threshold"
            return
    attempt.passed = True
    attempt.reason = "identity_passed"


def _best_attempt(attempts: list[MetricControlAttempt], backend: str) -> MetricControlAttempt:
    render_ok_scored = [
        attempt for attempt in attempts if attempt.render_ok and attempt.identity_scores.get(backend) is not None
    ]
    if render_ok_scored:
        return max(render_ok_scored, key=lambda attempt: float(attempt.identity_scores[backend] or -1.0))
    scored = [attempt for attempt in attempts if attempt.identity_scores.get(backend) is not None]
    if scored:
        return max(scored, key=lambda attempt: float(attempt.identity_scores[backend] or -1.0))
    return attempts[-1]


def _best_similarity(attempts: list[MetricControlAttempt], backend: str) -> float | None:
    render_ok_values = [attempt.identity_scores.get(backend) for attempt in attempts if attempt.render_ok]
    values = render_ok_values or [attempt.identity_scores.get(backend) for attempt in attempts]
    clean = [float(value) for value in values if value is not None]
    return max(clean) if clean else None


def _guard_fallback_reason(
    selected: MetricControlAttempt,
    primary_evaluator: IdentityMetric,
    threshold: float,
) -> tuple[bool, str]:
    value = selected.identity_scores.get(primary_evaluator.backend)
    if not primary_evaluator.available:
        return True, f"identity_not_evaluable:{primary_evaluator.reason}"
    if value is None:
        return True, "identity_similarity_unavailable"
    if value < threshold:
        return True, "identity_below_threshold"
    if not selected.passed:
        return True, selected.reason or "identity_below_threshold"
    return False, "identity_retry_passed"


def _failed_selection_reason(source_variant: str, selected: MetricControlAttempt, backend: str) -> str:
    value = selected.identity_scores.get(backend)
    if value is None:
        return f"{source_variant}_identity_retry_similarity_unavailable"
    return f"{source_variant}_identity_retry_best_below_threshold"


def _preserve_blend_alpha(selected: MetricControlAttempt) -> float | None:
    value = selected.params.get("preserve_blend_alpha")
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _score_for_alias(attempt: MetricControlAttempt | None, backend: str) -> float | None:
    if attempt is None:
        return None
    return attempt.identity_scores.get(backend)


def _param_float(attempt: MetricControlAttempt | None, key: str, default: float | None) -> float | None:
    if attempt is None:
        return default
    value = attempt.params.get(key, default)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
