from __future__ import annotations


class RecipeTranslator:
    def to_fidelity_params(self, recipe: dict, mode: str) -> dict:
        tone = recipe.get("tone", {})
        face = recipe.get("face", {})
        multiplier = 1.0 if mode == "smart-optimize" else 0.85
        return {
            "brightness": float(tone.get("brightness", 0.08)) * multiplier,
            "contrast": float(tone.get("contrast", 0.0)) * multiplier,
            "warmth": float(tone.get("warmth", 0.0)) * multiplier,
            "skin_smooth": float(face.get("skin_smooth", 0.20)),
            "face_slim": float(face.get("face_slim", 0.0)),
            "eye_size": float(face.get("eye_size", 0.0)),
            "lip_saturation": float(face.get("lip_saturation", 0.0)),
        }

    def to_creative_params(self, recipe: dict) -> dict:
        creative = recipe.get("creative", {})
        return {
            "preset_id": creative.get("preset_id"),
            "strength": float(creative.get("strength", 0.0)),
            "download": "disabled",
        }
