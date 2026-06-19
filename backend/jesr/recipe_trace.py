from __future__ import annotations

import secrets
from copy import deepcopy
from typing import Any

from backend.services.session_store import iso_now, session_store


class RecipeTraceRecorder:
    def record(
        self,
        *,
        session_id: str,
        recipe: dict[str, Any],
        provider_chain: list[str],
        render_params: dict[str, Any],
        model_info: dict[str, dict[str, Any]] | None,
        output_asset: str | None,
        rollback_parent: str | None = None,
    ) -> dict[str, Any]:
        model_info = model_info or {}
        trace = {
            "id": f"trc_{secrets.token_hex(8)}",
            "created_at": iso_now(),
            "session_id": session_id,
            "recipe_version": recipe.get("version", "unknown"),
            "provider_chain": provider_chain,
            "model_id": {key: value.get("id") for key, value in model_info.items()},
            "model_version": {key: value.get("version") for key, value in model_info.items()},
            "model_reason": {key: value.get("reason") for key, value in model_info.items()},
            "render_params": deepcopy(render_params),
            "output_asset": output_asset,
            "rollback_parent": rollback_parent,
        }
        session_store.traces.append(trace)
        return trace


trace_recorder = RecipeTraceRecorder()
