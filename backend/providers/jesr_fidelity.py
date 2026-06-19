from __future__ import annotations

from PIL import Image

from backend.models import resolve_model_status
from backend.jesr.translator import RecipeTranslator
from .base import ProviderResult
from .model_runtime import ModelAdapterUnavailable, run_configured_adapter


class JESRFidelityProvider:
    provider_name = "JESR-Fidelity"

    def __init__(self) -> None:
        self.translator = RecipeTranslator()

    def smart_optimize(self, image: Image.Image, recipe: dict) -> ProviderResult:
        params = self.translator.to_fidelity_params(recipe, mode="smart-optimize")
        return self._render_with_gan_prior(image, recipe, params, mode="smart_optimize")

    def targeted_retouch(self, image: Image.Image, recipe: dict, params: dict | None = None) -> ProviderResult:
        recipe = {**recipe, "face": {**recipe.get("face", {}), **(params or {})}}
        translated = self.translator.to_fidelity_params(recipe, mode="targeted-retouch")
        return self._render_with_gan_prior(image, recipe, translated, mode="targeted_retouch")

    def render(self, image: Image.Image, recipe: dict, params: dict | None = None) -> ProviderResult:
        mode = (params or {}).get("mode", "smart-optimize")
        if mode == "targeted-retouch":
            return self.targeted_retouch(image, recipe, (params or {}).get("retouch_params"))
        return self.smart_optimize(image, recipe)

    def _render_with_gan_prior(
        self,
        image: Image.Image,
        recipe: dict,
        params: dict,
        *,
        mode: str,
    ) -> ProviderResult:
        model = resolve_model_status("fidelity")
        result_params = {**params, **model.provider_params(), "adapter": "gan_prior", "mode": mode}
        if not model.available:
            return ProviderResult(
                image=image,
                status=f"jesr_fidelity_unavailable_{_status_token(model.reason)}",
                provider=self.provider_name,
                params=result_params,
            )
        try:
            result = run_configured_adapter(
                env_var="HELLOBEAUTY_FIDELITY_ADAPTER",
                image=image,
                recipe=recipe,
                params=result_params,
                model=model,
            )
        except ModelAdapterUnavailable as exc:
            result_params["adapter_error"] = str(exc)
            return ProviderResult(
                image=image,
                status="jesr_fidelity_unavailable_adapter_runtime_not_configured",
                provider=self.provider_name,
                params=result_params,
            )
        return ProviderResult(
            image=result,
            status=f"jesr_fidelity_{mode}_ok",
            provider=self.provider_name,
            params=result_params,
        )


def _status_token(reason: str) -> str:
    return "".join(char if char.isalnum() else "_" for char in reason).strip("_") or "unknown"
