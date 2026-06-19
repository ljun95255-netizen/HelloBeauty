from __future__ import annotations

from typing import Any

from fastapi import APIRouter, File, Form, Header, HTTPException, UploadFile
from pydantic import BaseModel

from backend.api.authz import require_job_owner, require_photo_owner, require_session_owner
from backend.services.ingress import ingress_service
from backend.services.session_store import session_store
from backend.workers.render_worker import render_worker


router = APIRouter()


class SelectPhotoPayload(BaseModel):
    selected: bool = True


class EditJobPayload(BaseModel):
    photo_id: str
    mode: str = "beauty"
    style_name: str | None = None


class SmartOptimizePayload(BaseModel):
    mode: str = "style_only"


class TargetedRetouchPayload(BaseModel):
    params: dict[str, Any] = {}


def require_persistent_photo_owner(photo_id: str, authorization: str | None) -> dict[str, Any]:
    photo = require_photo_owner(photo_id, authorization)
    if photo.get("temporary"):
        raise HTTPException(status_code=400, detail="Temporary photos cannot be used for this operation")
    return photo


@router.post("/api/ingress/camera/{store_id}/upload")
async def upload_camera_photo(
    store_id: str,
    session_id: str = Form(...),
    temporary: bool = Form(False),
    image: UploadFile = File(...),
    authorization: str | None = Header(default=None),
):
    require_session_owner(session_id, authorization)
    try:
        photo = ingress_service.ingest_camera_upload(
            session_id=session_id,
            store_id=store_id,
            filename=image.filename or "capture.png",
            file_obj=image.file,
            temporary=temporary,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Session not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"photo": _public_photo(photo)}


@router.post("/api/photos/{photo_id}/select")
def select_photo(photo_id: str, payload: SelectPhotoPayload, authorization: str | None = Header(default=None)):
    require_photo_owner(photo_id, authorization)
    session_store.photos[photo_id]["selected"] = payload.selected
    return {"photo": _public_photo(session_store.photos[photo_id])}


@router.post("/api/edit-jobs")
def create_edit_job(payload: EditJobPayload, authorization: str | None = Header(default=None)):
    require_photo_owner(payload.photo_id, authorization)
    try:
        job = render_worker.create_job(
            photo_id=payload.photo_id,
            mode=payload.mode,
            style_name=payload.style_name,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Photo not found") from exc
    return {"job": _public_job(job)}


@router.get("/api/edit-jobs/{job_id}")
def get_edit_job(job_id: str, authorization: str | None = Header(default=None)):
    if job_id not in session_store.jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    job = require_job_owner(job_id, authorization)
    return {"job": _public_job(job)}


@router.post("/api/photos/{photo_id}/smart-optimize")
def smart_optimize(
    photo_id: str,
    payload: SmartOptimizePayload | None = None,
    authorization: str | None = Header(default=None),
):
    require_photo_owner(photo_id, authorization)
    mode = (payload.mode if payload else "style_only") or "style_only"
    try:
        job = render_worker.create_job(photo_id=photo_id, mode="beauty")
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Photo not found") from exc
    return {
        "ok": True,
        "status": job["statusMessage"],
        "image": job["resultImageUrl"],
        "preference_used": mode != "plain",
        "render_mode": "JESR-Fidelity",
    }


@router.post("/api/photos/{photo_id}/targeted-retouch-v2")
def targeted_retouch_v2(
    photo_id: str,
    payload: TargetedRetouchPayload,
    authorization: str | None = Header(default=None),
):
    require_photo_owner(photo_id, authorization)
    try:
        job = render_worker.create_job(
            photo_id=photo_id,
            mode="targeted-retouch",
            retouch_params=payload.params,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Photo not found") from exc
    return {"ok": True, "status": job["statusMessage"], "image": job["resultImageUrl"]}


@router.post("/api/photos/{photo_id}/diagnose")
def diagnose_photo(photo_id: str, authorization: str | None = Header(default=None)):
    require_persistent_photo_owner(photo_id, authorization)
    return {"ok": True, "diagnostics": {"photo_id": photo_id, "quality": "usable"}}


@router.post("/api/photos/{photo_id}/probe/generate")
def generate_probe(photo_id: str, authorization: str | None = Header(default=None)):
    require_persistent_photo_owner(photo_id, authorization)
    photo = session_store.photos[photo_id]
    probes = [
        {"id": f"{photo_id}_probe_1", "photo_id": photo_id, "label": "Natural", "liked": None},
        {"id": f"{photo_id}_probe_2", "photo_id": photo_id, "label": "Polished", "liked": None},
    ]
    session_store.probes.setdefault(photo["sessionId"], []).extend(probes)
    return {"ok": True, "probes": probes}


@router.post("/api/probe-feedback")
def probe_feedback(payload: dict[str, Any], authorization: str | None = Header(default=None)):
    photo_id = payload.get("photo_id")
    if isinstance(photo_id, str):
        require_persistent_photo_owner(photo_id, authorization)
    else:
        raise HTTPException(status_code=422, detail="photo_id is required")
    return {"ok": True, "recorded": payload.get("feedback", [])}


def _public_photo(photo: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in photo.items() if key != "assetPath"}


def _public_job(job: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in job.items() if key not in {"provider", "traceId"}}
