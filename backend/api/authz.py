from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from backend.services.session_store import session_store


def _token_context(authorization: str | None) -> dict[str, str]:
    context = session_store.token_context(authorization)
    if context is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return context


def require_customer_context(authorization: str | None) -> dict[str, str]:
    context = _token_context(authorization)
    if context.get("kind") != "customer":
        raise HTTPException(status_code=403, detail="Customer authorization required")
    return context


def require_staff_context(authorization: str | None) -> dict[str, str]:
    context = _token_context(authorization)
    if context.get("kind") != "staff":
        raise HTTPException(status_code=403, detail="Staff authorization required")
    return context


def require_session_owner(session_id: str, authorization: str | None) -> dict[str, Any]:
    if session_id not in session_store.sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    context = require_customer_context(authorization)
    session = session_store.sessions[session_id]
    if session["phone"] != context["phone"]:
        raise HTTPException(status_code=403, detail="Session access denied")
    return session


def require_session_access(session_id: str, authorization: str | None) -> dict[str, Any]:
    if session_id not in session_store.sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    context = _token_context(authorization)
    session = session_store.sessions[session_id]
    if context.get("kind") == "staff" or session["phone"] == context.get("phone"):
        return session
    raise HTTPException(status_code=403, detail="Session access denied")


def require_photo_owner(photo_id: str, authorization: str | None) -> dict[str, Any]:
    if photo_id not in session_store.photos:
        raise HTTPException(status_code=404, detail="Photo not found")
    photo = session_store.photos[photo_id]
    require_session_owner(photo["sessionId"], authorization)
    return photo


def require_photo_in_session(photo_id: str, session_id: str) -> dict[str, Any]:
    if photo_id not in session_store.photos:
        raise HTTPException(status_code=404, detail="Photo not found")
    photo = session_store.photos[photo_id]
    if photo["sessionId"] != session_id:
        raise HTTPException(status_code=403, detail="Photo does not belong to this session")
    return photo


def require_job_owner(job_id: str, authorization: str | None) -> dict[str, Any]:
    if job_id not in session_store.jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    job = session_store.jobs[job_id]
    session_id = job.get("sessionId") or job.get("session_id")
    if not session_id and job.get("photoId") in session_store.photos:
        session_id = session_store.photos[job["photoId"]]["sessionId"]
    if not session_id and job.get("photo_id") in session_store.photos:
        session_id = session_store.photos[job["photo_id"]]["sessionId"]
    if not session_id:
        raise HTTPException(status_code=404, detail="Job asset not found")
    require_session_access(str(session_id), authorization)
    return job


def require_asset_access(kind: str, identifier: str, authorization: str | None) -> None:
    if kind in {"photo", "thumbnail"}:
        if identifier not in session_store.photos:
            raise HTTPException(status_code=404, detail="Asset not found")
        require_session_access(session_store.photos[identifier]["sessionId"], authorization)
        return
    if kind == "job":
        require_job_owner(identifier, authorization)
        return
    raise HTTPException(status_code=404, detail="Asset not found")
