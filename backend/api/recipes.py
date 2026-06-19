from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Header, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from jesr_core import STYLE_IDS, list_style_presets

from backend.api.authz import require_session_owner
from backend.jesr.orchestrator import jesr_orchestrator
from backend.services.session_store import session_store


router = APIRouter()


class InitializeRecipePayload(BaseModel):
    photo_id: str | None = None
    style_id: str | None = None


@router.get("/api/style-presets")
def style_presets():
    return {"ok": True, "presets": list_style_presets()}


@router.get("/api/sessions/{session_id}/jesr-recipe")
def get_recipe(session_id: str, authorization: str | None = Header(default=None)):
    require_session_owner(session_id, authorization)
    return {"ok": True, "recipe": jesr_orchestrator.get_recipe(session_id)}


@router.post("/api/sessions/{session_id}/jesr-recipe/initialize")
def initialize_recipe(
    session_id: str,
    payload: InitializeRecipePayload | None = None,
    authorization: str | None = Header(default=None),
):
    require_session_owner(session_id, authorization)
    recipe = jesr_orchestrator.initialize_recipe(session_id, payload.style_id if payload else None)
    return {"ok": True, "recipe": recipe}


@router.get("/api/sessions/{session_id}/jesr/profile-recipe")
def get_profile_recipe(session_id: str, authorization: str | None = Header(default=None)):
    if session_id not in session_store.sessions:
        return _jesr_error("session_not_found", "Session not found", {"session_id": session_id}, status_code=404)
    require_session_owner(session_id, authorization)
    profile = jesr_orchestrator.get_aesthetic_profile(session_id)
    recipe = jesr_orchestrator.get_profile_recipe(session_id)
    return {
        "ok": True,
        "recipe": recipe,
        "jesr_profile_recipe": recipe,
        "recipe_status": "ready" if profile else "not_initialized",
    }


@router.post("/api/sessions/{session_id}/jesr/profile-recipe/initialize")
def initialize_profile_recipe(
    session_id: str,
    payload: Any = Body(default=None),
    authorization: str | None = Header(default=None),
):
    if session_id not in session_store.sessions:
        return _jesr_error("session_not_found", "Session not found", {"session_id": session_id}, status_code=404)
    require_session_owner(session_id, authorization)
    style_id, error = _style_id_from_jesr_payload(payload)
    if error is not None:
        return error
    if style_id is not None and style_id not in STYLE_IDS:
        return _jesr_error(
            "invalid_jesr_profile_recipe",
            f"Unknown style_id: {style_id}",
            {"style_id": style_id, "allowed_style_ids": list(STYLE_IDS)},
        )
    recipe = jesr_orchestrator.initialize_profile_recipe(session_id, style_id)
    return {"ok": True, "recipe": recipe, "jesr_profile_recipe": recipe}


def _jesr_error(code: str, message: str, details: dict[str, Any] | None = None, status_code: int = 422) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message, "details": details or {}}},
    )


def _style_id_from_jesr_payload(payload: Any) -> tuple[str | None, JSONResponse | None]:
    if payload is None:
        return None, None
    if not isinstance(payload, dict):
        return None, _jesr_error("invalid_payload", "JSON payload must be an object", {"expected": "object"})
    style_id = payload.get("style_id")
    if style_id is None:
        return None, None
    if not isinstance(style_id, str):
        return None, _jesr_error(
            "invalid_payload",
            "style_id must be a string or null",
            {"field": "style_id", "expected": "string"},
        )
    value = style_id.strip()
    return (value or None), None
