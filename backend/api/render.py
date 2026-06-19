from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from backend.api.authz import require_job_owner, require_photo_in_session, require_session_owner
from backend.services.session_store import session_store
from backend.workers.render_worker import render_worker


router = APIRouter()


class SessionRenderPayload(BaseModel):
    photo_id: str
    mode: str = "auto"


class PipelineRenderPayload(BaseModel):
    session_id: str
    photo_id: str
    mode: str = "auto"
    style_id: str | None = None


@router.post("/api/sessions/{session_id}/render")
def render_session(session_id: str, payload: SessionRenderPayload, authorization: str | None = Header(default=None)):
    require_session_owner(session_id, authorization)
    require_photo_in_session(payload.photo_id, session_id)
    try:
        job = render_worker.create_job(photo_id=payload.photo_id, mode=payload.mode)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Photo not found") from exc
    return {"ok": True, "job": _public_job(job)}


@router.post("/api/render/pipeline")
def render_pipeline(payload: PipelineRenderPayload, authorization: str | None = Header(default=None)):
    require_session_owner(payload.session_id, authorization)
    require_photo_in_session(payload.photo_id, payload.session_id)
    try:
        job = render_worker.create_pipeline_job(
            session_id=payload.session_id,
            photo_id=payload.photo_id,
            mode=payload.mode,
            style_id=payload.style_id,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Photo not found") from exc
    return {"ok": True, "job": job}


@router.get("/api/render/jobs/{job_id}")
def render_job(job_id: str, authorization: str | None = Header(default=None)):
    require_job_owner(job_id, authorization)
    return {"ok": True, "job": session_store.jobs[job_id]}


@router.post("/api/renders")
def legacy_render(payload: PipelineRenderPayload, authorization: str | None = Header(default=None)):
    return render_pipeline(payload, authorization)


def _public_job(job: dict):
    return {key: value for key, value in job.items() if key not in {"provider", "traceId"}}
