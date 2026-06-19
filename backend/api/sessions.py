from __future__ import annotations

import secrets
from typing import Any

from fastapi import APIRouter, Body, Header, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from backend.jesr.orchestrator import jesr_orchestrator
from jesr_core import JESRProfileValidationError
from backend.api.authz import (
    require_customer_context,
    require_photo_in_session,
    require_session_owner,
    require_staff_context,
)
from backend.services.experiments import experiment_service
from backend.services.session_store import iso_now, session_store, _parse_iso_datetime


router = APIRouter()


class CreateSessionPayload(BaseModel):
    store_id: str = Field(default="default-store")
    duration_minutes: int = Field(default=12, ge=1, le=240)
    session_code: str | None = None
    start_time: str | None = None


class SelectStylePayload(BaseModel):
    preset_id: str | None = None


class IteratePayload(BaseModel):
    photo_id: str
    pain_tags: list[str] = Field(default_factory=list)
    free_text_feedback: str | None = None


class RollbackPayload(BaseModel):
    iteration_id: str | None = None


class PrintPayload(BaseModel):
    session_id: str
    photo_id: str


class PreShootReminderPayload(BaseModel):
    subscription_accepted: bool = False
    subscription_status: str | None = None
    template_id: str | None = None


class ReminderStatusPayload(BaseModel):
    status: str = Field(pattern="^(SCHEDULED|DUE|SENT|CANCELLED)$")


@router.post("/api/sessions")
def create_session(payload: CreateSessionPayload, authorization: str | None = Header(default=None)):
    context = require_customer_context(authorization)
    phone = context["phone"]
    start_time = None
    if payload.start_time:
        try:
            start_time = _parse_iso_datetime(payload.start_time)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="start_time must be an ISO datetime") from exc
    session = session_store.create_session(
        phone=phone,
        store_id=payload.store_id,
        duration_minutes=payload.duration_minutes,
        session_code=payload.session_code,
        start_time=start_time,
    )
    jesr_orchestrator.initialize_recipe(session["id"])
    return {"session": session}


@router.get("/api/sessions/{session_id}")
def get_session(session_id: str, authorization: str | None = Header(default=None)):
    require_session_owner(session_id, authorization)
    return {"session": session_store.get_public_session(session_id)}


@router.get("/api/customer/sessions")
def list_customer_sessions(authorization: str | None = Header(default=None)):
    context = require_customer_context(authorization)
    return {"sessions": session_store.list_customer_sessions(context["phone"])}


@router.get("/api/sessions/{session_id}/photos")
def list_session_photos(session_id: str, authorization: str | None = Header(default=None)):
    require_session_owner(session_id, authorization)
    photos = [
        _public_photo(photo)
        for photo in session_store.photos.values()
        if photo["sessionId"] == session_id and not photo.get("temporary")
    ]
    return {"photos": photos}


@router.get("/api/sessions/{session_id}/reminders")
def list_session_reminders(session_id: str, authorization: str | None = Header(default=None)):
    require_session_owner(session_id, authorization)
    return {"ok": True, "reminders": session_store.list_session_reminders(session_id)}


@router.post("/api/sessions/{session_id}/reminders/pre-shoot-style")
def schedule_pre_shoot_style_reminder(
    session_id: str,
    payload: PreShootReminderPayload | None = None,
    authorization: str | None = Header(default=None),
):
    require_session_owner(session_id, authorization)
    payload = payload or PreShootReminderPayload()
    reminder = session_store.schedule_pre_shoot_style_reminder(
        session_id,
        subscription_accepted=payload.subscription_accepted,
        subscription_status=payload.subscription_status,
        template_id=payload.template_id,
    )
    return {"ok": True, "reminder": reminder}


@router.post("/api/sessions/{session_id}/complete")
def complete_session(session_id: str, authorization: str | None = Header(default=None)):
    require_session_owner(session_id, authorization)
    session_store.sessions[session_id]["status"] = "COMPLETED"
    session_store.sessions[session_id]["completedAt"] = iso_now()
    return {"session": session_store.get_public_session(session_id)}


@router.post("/api/sessions/{session_id}/style-select")
def style_select(session_id: str, payload: SelectStylePayload, authorization: str | None = Header(default=None)):
    require_session_owner(session_id, authorization)
    recipe = jesr_orchestrator.select_style(session_id, payload.preset_id)
    return {"ok": True, "recipe": recipe}


@router.post("/api/sessions/{session_id}/iterate")
def iterate(session_id: str, payload: IteratePayload, authorization: str | None = Header(default=None)):
    require_session_owner(session_id, authorization)
    require_photo_in_session(payload.photo_id, session_id)
    iteration = jesr_orchestrator.iterate(
        session_id=session_id,
        photo_id=payload.photo_id,
        pain_tags=payload.pain_tags,
        free_text=payload.free_text_feedback,
    )
    render_job = {
        "id": f"itrjob_{secrets.token_hex(6)}",
        "status": "queued",
        "photo_id": payload.photo_id,
    }
    return {
        "ok": True,
        "iteration": iteration,
        "updated_recipe": iteration["updated_recipe"],
        "render_job": render_job,
    }


@router.get("/api/sessions/{session_id}/iterations")
def iterations(session_id: str, authorization: str | None = Header(default=None)):
    require_session_owner(session_id, authorization)
    return {"ok": True, "iterations": session_store.iterations.get(session_id, [])}


@router.post("/api/sessions/{session_id}/iterations/{iteration_id}/rollback")
def rollback_iteration(session_id: str, iteration_id: str, authorization: str | None = Header(default=None)):
    require_session_owner(session_id, authorization)
    rollback = jesr_orchestrator.rollback(session_id, iteration_id)
    return {"ok": True, "rollback_iteration": rollback}


@router.post("/api/sessions/{session_id}/rollback")
def rollback_session(
    session_id: str,
    payload: RollbackPayload | None = None,
    authorization: str | None = Header(default=None),
):
    require_session_owner(session_id, authorization)
    rollback = jesr_orchestrator.rollback(session_id, payload.iteration_id if payload else None)
    return {"ok": True, "rollback": rollback}


@router.get("/api/sessions/{session_id}/preference-profile")
def preference_profile(session_id: str, authorization: str | None = Header(default=None)):
    require_session_owner(session_id, authorization)
    preference = dict(session_store.preferences.get(session_id, {}))
    profile = jesr_orchestrator.get_aesthetic_profile(session_id)
    if profile is not None:
        preference.setdefault("source", profile.get("source"))
        preference["profile"] = profile.get("profile_vector")
        preference["is_set"] = profile.get("profile_status") == "ready"
        preference["aesthetic_profile_id"] = profile.get("profile_id")
        preference["aesthetic_profile_revision"] = profile.get("profile_revision")
    else:
        preference.setdefault("is_set", False)
    return {"ok": True, "preference": preference}


@router.get("/api/sessions/{session_id}/base-style")
def base_style(session_id: str, authorization: str | None = Header(default=None)):
    require_session_owner(session_id, authorization)
    recipe = jesr_orchestrator.get_recipe(session_id)
    return {"ok": True, "base_style": {"style_id": recipe.get("style_id"), "recipe": recipe}}


@router.post("/api/sessions/{session_id}/base-style/reference-photos")
def base_style_reference(
    session_id: str,
    payload: dict[str, Any],
    authorization: str | None = Header(default=None),
):
    require_session_owner(session_id, authorization)
    photo_ids = _reference_photo_ids_from_payload(payload)
    if not photo_ids:
        raise HTTPException(status_code=422, detail="reference_photo_ids must be a non-empty string array")
    _validate_reference_photo_ids(session_id, photo_ids)
    normalized_payload = {"reference_photo_ids": photo_ids}
    session_store.preferences[session_id] = {"source": "reference_photos", **normalized_payload}
    profile = _legacy_profile_update(session_id, "reference_photos", normalized_payload)
    return {"ok": True, "base_style": session_store.preferences[session_id], "jesr_aesthetic_profile": profile}


@router.post("/api/sessions/{session_id}/base-style/seed-selection")
def base_style_seed_selection(
    session_id: str,
    payload: dict[str, Any],
    authorization: str | None = Header(default=None),
):
    require_session_owner(session_id, authorization)
    session_store.preferences[session_id] = {"source": "seed_selection", **payload}
    profile = _legacy_profile_update(session_id, "seed_selection", payload)
    return {"ok": True, "base_style": session_store.preferences[session_id], "jesr_aesthetic_profile": profile}


@router.post("/api/sessions/{session_id}/base-style/seed-gallery")
def base_style_seed_gallery(
    session_id: str,
    payload: dict[str, Any],
    authorization: str | None = Header(default=None),
):
    require_session_owner(session_id, authorization)
    session_store.preferences[session_id] = {"source": "seed_gallery", **payload}
    profile = _legacy_profile_update(session_id, "seed_gallery", payload)
    return {
        "ok": True,
        "base_style": session_store.preferences[session_id],
        "preference": session_store.preferences[session_id],
        "jesr_aesthetic_profile": profile,
    }


@router.get("/api/sessions/{session_id}/jesr/aesthetic-profile")
def get_jesr_aesthetic_profile(session_id: str, authorization: str | None = Header(default=None)):
    if session_id not in session_store.sessions:
        return _jesr_error("session_not_found", "Session not found", {"session_id": session_id}, status_code=404)
    require_session_owner(session_id, authorization)
    profile = jesr_orchestrator.get_aesthetic_profile(session_id)
    return {
        "ok": True,
        "jesr_aesthetic_profile": profile,
        "profile_status": profile.get("profile_status") if profile else "not_initialized",
    }


@router.post("/api/sessions/{session_id}/jesr/aesthetic-profile/reference-photos")
def set_jesr_reference_photos(
    session_id: str,
    payload: Any = Body(default=None),
    authorization: str | None = Header(default=None),
):
    if session_id not in session_store.sessions:
        return _jesr_error("session_not_found", "Session not found", {"session_id": session_id}, status_code=404)
    require_session_owner(session_id, authorization)
    if not isinstance(payload, dict):
        return _jesr_error("invalid_payload", "JSON payload must be an object", {"expected": "object"})
    photo_ids = _reference_photo_ids_from_payload(payload)
    if not photo_ids:
        return _jesr_error(
            "invalid_payload",
            "reference_photo_ids must be a non-empty string array",
            {"field": "reference_photo_ids"},
        )
    _validate_reference_photo_ids(session_id, photo_ids)
    try:
        profile = jesr_orchestrator.initialize_aesthetic_profile(
            session_id,
            "reference_photos",
            {"reference_photo_ids": photo_ids},
        )
    except JESRProfileValidationError as exc:
        return _jesr_error(exc.code, str(exc), exc.details)
    return {"ok": True, "jesr_aesthetic_profile": profile, "profile_status": profile["profile_status"]}


@router.post("/api/sessions/{session_id}/jesr/aesthetic-profile/seed-gallery")
def set_jesr_seed_gallery(
    session_id: str,
    payload: Any = Body(default=None),
    authorization: str | None = Header(default=None),
):
    if session_id not in session_store.sessions:
        return _jesr_error("session_not_found", "Session not found", {"session_id": session_id}, status_code=404)
    require_session_owner(session_id, authorization)
    if not isinstance(payload, dict):
        return _jesr_error("invalid_payload", "JSON payload must be an object", {"expected": "object"})
    try:
        profile = jesr_orchestrator.initialize_aesthetic_profile(session_id, "seed_gallery", payload)
    except JESRProfileValidationError as exc:
        return _jesr_error(exc.code, str(exc), exc.details)
    return {
        "ok": True,
        "jesr_aesthetic_profile": profile,
        "profile_status": profile["profile_status"],
        "jesr_profile_recipe": jesr_orchestrator.get_profile_recipe(session_id),
    }


@router.get("/api/sessions/{session_id}/probe-results")
def probe_results(session_id: str, authorization: str | None = Header(default=None)):
    require_session_owner(session_id, authorization)
    return {"ok": True, "probes": session_store.probes.get(session_id, [])}


@router.get("/api/sessions/{session_id}/export-experiments")
def export_experiments(session_id: str, authorization: str | None = Header(default=None)):
    require_session_owner(session_id, authorization)
    path = experiment_service.export_session(session_id)
    return {"ok": True, "export_path": str(path)}


@router.get("/api/staff/sessions/search")
def staff_search_sessions(phone: str | None = None, authorization: str | None = Header(default=None)):
    require_staff_context(authorization)
    return {"sessions": session_store.list_public_sessions(phone=phone)}


@router.get("/api/staff/reminders/due")
def staff_due_reminders(authorization: str | None = Header(default=None)):
    require_staff_context(authorization)
    return {"ok": True, "reminders": session_store.list_due_reminders()}


@router.post("/api/staff/reminders/{reminder_id}/status")
def staff_update_reminder_status(
    reminder_id: str,
    payload: ReminderStatusPayload,
    authorization: str | None = Header(default=None),
):
    require_staff_context(authorization)
    try:
        reminder = session_store.update_reminder_status(reminder_id, payload.status)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Reminder not found") from exc
    return {"ok": True, "reminder": reminder}


@router.get("/api/staff/sessions/{session_id}")
def staff_session_detail(session_id: str, authorization: str | None = Header(default=None)):
    require_staff_context(authorization)
    if session_id not in session_store.sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    photos = [
        _public_photo(photo)
        for photo in session_store.photos.values()
        if photo["sessionId"] == session_id and not photo.get("temporary")
    ]
    print_records = [
        record for record in session_store.prints.values() if record["sessionId"] == session_id
    ]
    return {
        "session": session_store.get_public_session(session_id),
        "photos": photos,
        "printRecords": print_records,
    }


@router.get("/api/staff/sessions/{session_id}/photos")
def staff_session_photos(session_id: str, authorization: str | None = Header(default=None)):
    require_staff_context(authorization)
    if session_id not in session_store.sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    return {
        "photos": [
            _public_photo(photo)
            for photo in session_store.photos.values()
            if photo["sessionId"] == session_id and not photo.get("temporary")
        ]
    }


@router.post("/api/staff/prints")
def staff_print(payload: PrintPayload, authorization: str | None = Header(default=None)):
    require_staff_context(authorization)
    if payload.session_id not in session_store.sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    if payload.photo_id not in session_store.photos:
        raise HTTPException(status_code=404, detail="Photo not found")
    require_photo_in_session(payload.photo_id, payload.session_id)
    record = {
        "id": f"prt_{secrets.token_hex(8)}",
        "sessionId": payload.session_id,
        "photoId": payload.photo_id,
        "staffUserId": "staff_default",
        "printedAt": iso_now(),
    }
    session_store.prints[record["id"]] = record
    return {"record": record}


def _public_photo(photo: dict[str, Any]) -> dict[str, Any]:
    payload = {key: value for key, value in photo.items() if key != "assetPath"}
    latest = payload.get("latestJob")
    if latest:
        payload["latestJob"] = {
            key: value for key, value in latest.items() if key not in {"provider", "traceId"}
        }
    return payload


def _legacy_profile_update(session_id: str, source: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    try:
        return jesr_orchestrator.sync_legacy_aesthetic_profile(session_id, source, payload)
    except JESRProfileValidationError:
        return jesr_orchestrator.get_aesthetic_profile(session_id)


def _jesr_error(code: str, message: str, details: dict[str, Any] | None = None, status_code: int = 422) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message, "details": details or {}}},
    )


def _reference_photo_ids_from_payload(payload: dict[str, Any]) -> list[str]:
    raw = (
        payload.get("reference_photo_ids")
        or payload.get("photo_ids")
        or payload.get("reference_photos")
        or payload.get("reference_photo")
    )
    if isinstance(raw, str):
        raw = [raw]
    if not isinstance(raw, list):
        return []
    result: list[str] = []
    for item in raw:
        if not isinstance(item, str):
            return []
        text = item.strip()
        if not text:
            return []
        if text not in result:
            result.append(text)
    return result


def _validate_reference_photo_ids(session_id: str, photo_ids: list[str]) -> None:
    for photo_id in photo_ids:
        require_photo_in_session(photo_id, session_id)
