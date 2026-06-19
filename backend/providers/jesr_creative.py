from __future__ import annotations

from PIL import Image

from backend.models import resolve_model_status
from .base import ProviderResult
from .model_runtime import ModelAdapterUnavailable, run_configured_adapter


class JESRCreativeProvider:
    provider_name = "JESR-Creative"

    def __init__(self) -> None:
        pass

    def is_available(self) -> bool:
        return resolve_model_status("creative").available

    def render(
        self,
        image: Image.Image,
        recipe: dict,
        params: dict | None = None,
    ) -> ProviderResult:
        preset_id = recipe.get("creative", {}).get("preset_id") or recipe.get("style_id")
        strength = float(recipe.get("creative", {}).get("strength", 0.0))
        if not preset_id:
            return ProviderResult(
                image=image,
                status="jesr_creative_skipped_no_preset",
                provider=self.provider_name,
                params={"preset_id": None, **resolve_model_status("creative").provider_params()},
            )
        model = resolve_model_status("creative")
        result_params = {
            "preset_id": preset_id,
            "strength": strength,
            "adapter": "diffusion_img2img",
            **model.provider_params(),
        }
        if not model.available:
            return ProviderResult(
                image=image,
                status=f"jesr_creative_unavailable_{_status_token(model.reason)}",
                provider=self.provider_name,
                params=result_params,
            )
        try:
            result = run_configured_adapter(
                env_var="HELLOBEAUTY_CREATIVE_ADAPTER",
                image=image,
                recipe=recipe,
                params=result_params,
                model=model,
            )
        except ModelAdapterUnavailable as exc:
            result_params["adapter_error"] = str(exc)
            return ProviderResult(
                image=image,
                status="jesr_creative_unavailable_adapter_runtime_not_configured",
                provider=self.provider_name,
                params=result_params,
            )
        return ProviderResult(
            image=result,
            status="jesr_creative_diffusion_img2img_ok",
            provider=self.provider_name,
            params=result_params,
        )


def _status_token(reason: str) -> str:
    return "".join(char if char.isalnum() else "_" for char in reason).strip("_") or "unknown"
