from __future__ import annotations

from fastapi import APIRouter

from backend.models import model_registry_status


router = APIRouter()


@router.get("/api/models/status")
def models_status():
    return {"ok": True, **model_registry_status()}
