from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any


STYLE_IDS = (
    "fresh_japanese",
    "retro_hongkong",
    "clear_korean",
    "lazy_french",
    "american_hotgirl",
)

PROFILE_VECTOR_KEYS = (
    "light_tendency",
    "warmth",
    "contrast",
    "texture_tendency",
    "makeup_intensity",
    "facial_detail_preference",
    "style_strength",
    "identity_tolerance",
)

PROFILE_STATUSES = ("not_initialized", "ready", "defaulted", "invalid")
PROFILE_SOURCES = ("seed_gallery", "reference_photos", "questionnaire", "hybrid")
SOURCE_ALIASES = {
    "seed_selection": "seed_gallery",
    "reference_photo": "reference_photos",
    "preference": "questionnaire",
    "preference_profile": "questionnaire",
}


class JESRProfileValidationError(ValueError):
    def __init__(self, message: str, *, code: str = "invalid_jesr_aesthetic_profile", details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.details = details or {}


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical_source(source: str | None) -> str:
    value = SOURCE_ALIASES.get(str(source or "questionnaire"), str(source or "questionnaire"))
    if value not in PROFILE_SOURCES:
        raise JESRProfileValidationError(
            f"Unknown JESR-Aesthetic-Profile source: {value}",
            details={"source": value, "allowed_sources": list(PROFILE_SOURCES), "aliases": SOURCE_ALIASES},
        )
    return value


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def _number(value: Any, path: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise JESRProfileValidationError(
            f"{path} must be a number",
            code="invalid_payload",
            details={"field": path, "expected": "number"},
        )
    return float(value)


_STYLE_PRESETS: dict[str, dict[str, Any]] = {
    "fresh_japanese": {
        "label": "Fresh Japanese",
        "recipe": {
            "tone": {"brightness": 0.16, "warmth": 0.04, "contrast": -0.04},
            "face": {"skin_smooth": 0.28, "eye_size": 0.08},
            "creative": {"preset_id": "fresh_japanese", "strength": 0.22},
        },
    },
    "retro_hongkong": {
        "label": "Retro Hong Kong",
        "recipe": {
            "tone": {"brightness": 0.02, "warmth": 0.22, "contrast": 0.18},
            "face": {"skin_smooth": 0.18, "lip_saturation": 0.20},
            "creative": {"preset_id": "retro_hongkong", "strength": 0.28},
        },
    },
    "clear_korean": {
        "label": "Clear Korean",
        "recipe": {
            "tone": {"brightness": 0.18, "warmth": -0.03, "contrast": 0.02},
            "face": {"skin_smooth": 0.34, "eye_size": 0.05},
            "creative": {"preset_id": "clear_korean", "strength": 0.22},
        },
    },
    "lazy_french": {
        "label": "Lazy French",
        "recipe": {
            "tone": {"brightness": 0.05, "warmth": 0.10, "contrast": -0.08},
            "face": {"skin_smooth": 0.16, "lip_saturation": 0.04},
            "creative": {"preset_id": "lazy_french", "strength": 0.20},
        },
    },
    "american_hotgirl": {
        "label": "American Hot Girl",
        "recipe": {
            "tone": {"brightness": 0.04, "warmth": 0.16, "contrast": 0.24},
            "face": {"skin_smooth": 0.22, "face_slim": 0.08, "lip_saturation": 0.22},
            "creative": {"preset_id": "american_hotgirl", "strength": 0.30},
        },
    },
}


def default_recipe(style_id: str | None = None) -> dict[str, Any]:
    recipe: dict[str, Any] = {
        "version": "jesr_core.v1",
        "style_id": None,
        "tone": {"brightness": 0.08, "warmth": 0.0, "contrast": 0.0},
        "face": {
            "skin_smooth": 0.20,
            "face_slim": 0.0,
            "eye_size": 0.0,
            "nose_lift": 0.0,
            "lip_saturation": 0.0,
            "neck_smooth": 0.0,
            "body_ratio": 0.0,
        },
        "creative": {"preset_id": None, "strength": 0.0},
        "feedback": {"pain_tags": [], "free_text": None},
    }
    if style_id:
        return apply_style_preset(recipe, style_id)
    return recipe


def default_aesthetic_profile(source: str = "questionnaire") -> dict[str, Any]:
    now = _iso_now()
    return {
        "version": "jesr_aesthetic_profile.v1",
        "profile_id": "jap_default",
        "profile_status": "defaulted",
        "source": _canonical_source(source),
        "profile_revision": 1,
        "profile_vector": {key: 0.0 for key in PROFILE_VECTOR_KEYS},
        "style_preferences": {
            "preferred_style_ids": [],
            "rejected_style_ids": [],
            "atmosphere_tags": [],
            "color_tags": [],
            "angle_tags": [],
        },
        "constraints": {
            "negative_rules": [],
            "identity_preservation_priority": "high",
            "allow_face_shape_change": False,
            "allow_eye_enlarge": False,
            "allow_heavy_smoothing": False,
        },
        "evidence": {
            "seed_choices": [],
            "reference_photo_ids": [],
            "questionnaire_answers": {},
            "unresolved_seed_ids": [],
        },
        "metadata": {"clamped_fields": []},
        "created_at": now,
        "updated_at": now,
    }


def normalize_aesthetic_profile(profile: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(profile, dict):
        raise JESRProfileValidationError(
            "JESR-Aesthetic-Profile payload must be an object",
            code="invalid_payload",
            details={"expected": "object"},
        )
    source = _canonical_source(profile.get("source"))
    normalized = default_aesthetic_profile(source)
    normalized.update(
        {
            "version": str(profile.get("version") or "jesr_aesthetic_profile.v1"),
            "profile_id": str(profile.get("profile_id") or normalized["profile_id"]),
            "profile_status": str(profile.get("profile_status") or normalized["profile_status"]),
            "source": source,
            "profile_revision": int(profile.get("profile_revision") or normalized["profile_revision"]),
            "created_at": str(profile.get("created_at") or normalized["created_at"]),
            "updated_at": str(profile.get("updated_at") or normalized["updated_at"]),
        }
    )
    if normalized["profile_status"] not in PROFILE_STATUSES:
        raise JESRProfileValidationError(
            f"Invalid profile_status: {normalized['profile_status']}",
            details={"profile_status": normalized["profile_status"], "allowed_statuses": list(PROFILE_STATUSES)},
        )

    clamped_fields: list[str] = []
    raw_vector = profile.get("profile_vector") or {}
    if not isinstance(raw_vector, dict):
        raise JESRProfileValidationError(
            "profile_vector must be an object",
            code="invalid_payload",
            details={"field": "profile_vector", "expected": "object"},
        )
    vector: dict[str, float] = {}
    for key in PROFILE_VECTOR_KEYS:
        raw_value = raw_vector.get(key, 0.0)
        number = _number(raw_value, f"profile_vector.{key}")
        clamped = _clamp(number, -1.0, 1.0)
        if clamped != number:
            clamped_fields.append(f"profile_vector.{key}")
        vector[key] = clamped
    normalized["profile_vector"] = vector

    raw_style = profile.get("style_preferences") or {}
    if not isinstance(raw_style, dict):
        raise JESRProfileValidationError(
            "style_preferences must be an object",
            code="invalid_payload",
            details={"field": "style_preferences", "expected": "object"},
        )
    normalized["style_preferences"] = {
        "preferred_style_ids": _unique_strings(raw_style.get("preferred_style_ids", [])),
        "rejected_style_ids": _unique_strings(raw_style.get("rejected_style_ids", [])),
        "atmosphere_tags": _unique_strings(raw_style.get("atmosphere_tags", [])),
        "color_tags": _unique_strings(raw_style.get("color_tags", [])),
        "angle_tags": _unique_strings(raw_style.get("angle_tags", [])),
    }

    raw_constraints = profile.get("constraints") or {}
    if not isinstance(raw_constraints, dict):
        raise JESRProfileValidationError(
            "constraints must be an object",
            code="invalid_payload",
            details={"field": "constraints", "expected": "object"},
        )
    identity_priority = str(raw_constraints.get("identity_preservation_priority") or "high")
    if identity_priority not in {"low", "medium", "high"}:
        raise JESRProfileValidationError(
            f"Invalid identity_preservation_priority: {identity_priority}",
            details={"identity_preservation_priority": identity_priority, "allowed_values": ["low", "medium", "high"]},
        )
    normalized["constraints"] = {
        "negative_rules": _unique_strings(raw_constraints.get("negative_rules", [])),
        "identity_preservation_priority": identity_priority,
        "allow_face_shape_change": bool(raw_constraints.get("allow_face_shape_change", False)),
        "allow_eye_enlarge": bool(raw_constraints.get("allow_eye_enlarge", False)),
        "allow_heavy_smoothing": bool(raw_constraints.get("allow_heavy_smoothing", False)),
    }

    raw_evidence = profile.get("evidence") or {}
    if not isinstance(raw_evidence, dict):
        raise JESRProfileValidationError(
            "evidence must be an object",
            code="invalid_payload",
            details={"field": "evidence", "expected": "object"},
        )
    normalized["evidence"] = {
        "seed_choices": deepcopy(raw_evidence.get("seed_choices", [])) if isinstance(raw_evidence.get("seed_choices", []), list) else [],
        "reference_photo_ids": _unique_strings(raw_evidence.get("reference_photo_ids", [])),
        "questionnaire_answers": deepcopy(raw_evidence.get("questionnaire_answers", {})) if isinstance(raw_evidence.get("questionnaire_answers", {}), dict) else {},
        "unresolved_seed_ids": _unique_strings(raw_evidence.get("unresolved_seed_ids", [])),
    }
    metadata = deepcopy(profile.get("metadata") or {})
    if not isinstance(metadata, dict):
        metadata = {}
    metadata["clamped_fields"] = _unique_strings(metadata.get("clamped_fields", []) + clamped_fields)
    normalized["metadata"] = metadata
    return normalized


def aesthetic_profile_from_seed_choices(
    choices: list[dict[str, Any]],
    seed_catalog: dict[str, dict[str, Any]] | list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if not isinstance(choices, list):
        raise JESRProfileValidationError(
            "choices must be an array",
            code="invalid_payload",
            details={"field": "choices", "expected": "array"},
        )
    catalog = _seed_catalog_by_id(seed_catalog)
    if not choices:
        return default_aesthetic_profile("seed_gallery")

    normalized_choices: list[dict[str, Any]] = []
    seen_likes: dict[str, bool] = {}
    unresolved: list[str] = []
    liked_vectors: list[dict[str, float]] = []
    disliked_vectors: list[dict[str, float]] = []
    liked_styles: list[str] = []
    disliked_styles: list[str] = []

    for index, choice in enumerate(choices):
        if not isinstance(choice, dict):
            raise JESRProfileValidationError(
                "seed choice must be an object",
                code="invalid_payload",
                details={"field": f"choices.{index}", "expected": "object"},
            )
        seed_id = str(choice.get("seed_id") or choice.get("id") or "").strip()
        if not seed_id:
            raise JESRProfileValidationError(
                "seed choice requires seed_id",
                code="invalid_payload",
                details={"field": f"choices.{index}.seed_id"},
            )
        liked = bool(choice.get("liked", False))
        if seed_id in seen_likes and seen_likes[seed_id] != liked:
            raise JESRProfileValidationError(
                "Duplicate seed choice has conflicting liked values",
                details={"conflict_seed_id": seed_id},
            )
        seen_likes[seed_id] = liked
        catalog_item = catalog.get(seed_id, {})
        profile_source = choice.get("profile") if isinstance(choice.get("profile"), dict) else catalog_item.get("profile")
        style_id = choice.get("style_id") or catalog_item.get("style_id")
        if profile_source is None:
            unresolved.append(seed_id)
            continue
        vector = _normalize_vector(profile_source, f"choices.{index}.profile")
        style_text = str(style_id).strip() if style_id is not None else ""
        if style_text and style_text not in STYLE_IDS:
            raise JESRProfileValidationError(
                f"Unknown style_id: {style_text}",
                details={"style_id": style_text, "allowed_style_ids": list(STYLE_IDS)},
            )
        normalized_choice = {
            "seed_id": seed_id,
            "liked": liked,
            "style_id": style_text or None,
            "profile": vector,
        }
        normalized_choices.append(normalized_choice)
        if liked:
            liked_vectors.append(vector)
            if style_text:
                liked_styles.append(style_text)
        else:
            disliked_vectors.append(vector)
            if style_text:
                disliked_styles.append(style_text)

    if unresolved:
        raise JESRProfileValidationError(
            "Some seed choices could not be resolved",
            details={"unresolved_seed_ids": unresolved},
        )

    profile = default_aesthetic_profile("seed_gallery")
    profile["profile_id"] = "jap_seed_gallery"
    profile["profile_status"] = "ready" if liked_vectors else "defaulted"
    profile["evidence"]["seed_choices"] = normalized_choices
    profile["style_preferences"]["preferred_style_ids"] = _ranked_unique(liked_styles)
    profile["style_preferences"]["rejected_style_ids"] = _ranked_unique(disliked_styles)

    if liked_vectors:
        liked_mean = _mean_vector(liked_vectors)
        disliked_mean = _mean_vector(disliked_vectors)
        profile["profile_vector"] = {
            key: _clamp(liked_mean[key] - 0.35 * disliked_mean[key], -1.0, 1.0)
            for key in PROFILE_VECTOR_KEYS
        }
    return profile


def apply_aesthetic_profile(recipe: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_aesthetic_profile(profile)
    vector = normalized["profile_vector"]
    next_recipe = deepcopy(recipe)
    tone = next_recipe.setdefault("tone", {})
    face = next_recipe.setdefault("face", {})
    creative = next_recipe.setdefault("creative", {})

    tone["brightness"] = _clamp(0.08 + 0.10 * vector["light_tendency"], 0.00, 0.24)
    tone["warmth"] = _clamp(0.00 + 0.16 * vector["warmth"], -0.12, 0.22)
    tone["contrast"] = _clamp(0.00 + 0.16 * vector["contrast"], -0.10, 0.24)
    face["skin_smooth"] = _clamp(
        0.20 + 0.12 * vector["makeup_intensity"] - 0.08 * vector["texture_tendency"],
        0.05,
        0.38,
    )
    facial_detail = max(vector["facial_detail_preference"], 0.0)
    face["face_slim"] = _clamp(0.04 * facial_detail, 0.00, 0.08)
    face["eye_size"] = _clamp(0.04 * facial_detail, 0.00, 0.08)
    face["lip_saturation"] = _clamp(0.10 * vector["makeup_intensity"], 0.00, 0.22)
    creative["strength"] = _clamp(0.16 + 0.14 * vector["style_strength"], 0.00, 0.30)

    constraints = normalized["constraints"]
    if not constraints["allow_face_shape_change"]:
        face["face_slim"] = 0.0
    if not constraints["allow_eye_enlarge"]:
        face["eye_size"] = 0.0
    if not constraints["allow_heavy_smoothing"]:
        face["skin_smooth"] = min(float(face.get("skin_smooth", 0.0)), 0.28)
    if constraints["identity_preservation_priority"] == "high":
        creative["strength"] = min(float(creative.get("strength", 0.0)), 0.22)
    return next_recipe


def recipe_with_jesr_metadata(recipe: dict[str, Any], profile: dict[str, Any] | None) -> dict[str, Any]:
    next_recipe = deepcopy(recipe)
    next_recipe["version"] = "jesr_core.v1"
    next_recipe["style_preset_id"] = next_recipe.get("style_id")
    jesr = next_recipe.setdefault("jesr", {})
    jesr.update(
        {
            "profile_recipe_version": "jesr_profile_recipe.v1",
            "source": "JESR-Aesthetic-Profile",
            "display_label": "JESR-Profile-Recipe",
            "compat_version": "jesr_core.v1",
        }
    )
    if profile is None:
        jesr["aesthetic_profile_id"] = None
        jesr["aesthetic_profile_revision"] = None
    else:
        normalized = normalize_aesthetic_profile(profile)
        jesr["aesthetic_profile_id"] = normalized["profile_id"]
        jesr["aesthetic_profile_revision"] = normalized["profile_revision"]
    return next_recipe


def is_profile_recipe_stale(recipe: dict[str, Any], profile: dict[str, Any] | None) -> bool:
    if profile is None:
        return False
    normalized = normalize_aesthetic_profile(profile)
    metadata = recipe.get("jesr") if isinstance(recipe, dict) else None
    if not isinstance(metadata, dict):
        return True
    return (
        metadata.get("aesthetic_profile_id") != normalized["profile_id"]
        or metadata.get("aesthetic_profile_revision") != normalized["profile_revision"]
    )


def _deep_update(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _deep_update(base[key], value)
        else:
            base[key] = value
    return base


def _unique_strings(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    result: list[str] = []
    for value in values:
        text = str(value).strip()
        if text and text not in result:
            result.append(text)
    return result


def _normalize_vector(raw: dict[str, Any], path: str) -> dict[str, float]:
    if not isinstance(raw, dict):
        raise JESRProfileValidationError(
            f"{path} must be an object",
            code="invalid_payload",
            details={"field": path, "expected": "object"},
        )
    return {key: _clamp(_number(raw.get(key, 0.0), f"{path}.{key}"), -1.0, 1.0) for key in PROFILE_VECTOR_KEYS}


def _seed_catalog_by_id(seed_catalog: dict[str, dict[str, Any]] | list[dict[str, Any]] | None) -> dict[str, dict[str, Any]]:
    if seed_catalog is None:
        return {}
    if isinstance(seed_catalog, dict):
        return seed_catalog
    result: dict[str, dict[str, Any]] = {}
    if isinstance(seed_catalog, list):
        for item in seed_catalog:
            if isinstance(item, dict) and item.get("id"):
                result[str(item["id"])] = item
    return result


def _mean_vector(vectors: list[dict[str, float]]) -> dict[str, float]:
    if not vectors:
        return {key: 0.0 for key in PROFILE_VECTOR_KEYS}
    return {
        key: sum(vector[key] for vector in vectors) / len(vectors)
        for key in PROFILE_VECTOR_KEYS
    }


def _ranked_unique(values: list[str]) -> list[str]:
    counts: dict[str, int] = {}
    first_index: dict[str, int] = {}
    for index, value in enumerate(values):
        counts[value] = counts.get(value, 0) + 1
        first_index.setdefault(value, index)
    return sorted(counts, key=lambda value: (-counts[value], first_index[value]))


def _toward_zero(value: float, step: float) -> float:
    if value > 0:
        return max(0.0, value - step)
    if value < 0:
        return min(0.0, value + step)
    return 0.0


def apply_style_preset(recipe: dict[str, Any], style_id: str | None) -> dict[str, Any]:
    next_recipe = deepcopy(recipe)
    if style_id is None:
        next_recipe["style_id"] = None
        next_recipe.setdefault("creative", {})["preset_id"] = None
        next_recipe["creative"]["strength"] = 0.0
        return next_recipe
    if style_id not in _STYLE_PRESETS:
        raise ValueError(f"Unknown JESR style preset: {style_id}")
    next_recipe["style_id"] = style_id
    return _deep_update(next_recipe, deepcopy(_STYLE_PRESETS[style_id]["recipe"]))


def list_style_presets() -> list[dict[str, str]]:
    return [
        {"id": style_id, "label": preset["label"]}
        for style_id, preset in _STYLE_PRESETS.items()
    ]


def merge_feedback(
    recipe: dict[str, Any],
    pain_tags: list[str] | None = None,
    free_text: str | None = None,
) -> dict[str, Any]:
    next_recipe = deepcopy(recipe)
    tags = list(dict.fromkeys((pain_tags or []) + next_recipe.get("feedback", {}).get("pain_tags", [])))
    face = next_recipe.setdefault("face", {})
    tone = next_recipe.setdefault("tone", {})
    creative = next_recipe.setdefault("creative", {})

    if "texture_too_fake" in tags:
        face["skin_smooth"] = max(0.05, float(face.get("skin_smooth", 0.2)) - 0.08)
    if "identity_not_preserved" in tags:
        creative_floor = 0.08
        current_strength = float(creative.get("strength", 0.0))
        if creative.get("preset_id") and current_strength >= creative_floor:
            creative["strength"] = max(creative_floor, current_strength - 0.16)
        else:
            creative["strength"] = current_strength
        face["face_slim"] = _toward_zero(float(face.get("face_slim", 0.0)), 0.06)
        face["eye_size"] = _toward_zero(float(face.get("eye_size", 0.0)), 0.04)
    if "style_or_lighting_mismatch" in tags:
        tone["brightness"] = min(0.24, float(tone.get("brightness", 0.08)) + 0.04)
        tone["contrast"] = max(-0.10, float(tone.get("contrast", 0.0)) - 0.04)

    next_recipe["feedback"] = {"pain_tags": tags, "free_text": free_text}
    return next_recipe
