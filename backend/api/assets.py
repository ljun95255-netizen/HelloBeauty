from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import FileResponse, JSONResponse

from backend.api.authz import require_asset_access
from backend.services.storage import BEAUTY_DIR, storage_service


router = APIRouter()

STYLE_ORDER = ["fresh_japanese", "clear_korean", "retro_hongkong", "lazy_french", "american_hotgirl"]


def _safe_gallery_path(style_id: str, filename: str) -> Path:
    if "/" in style_id or ".." in style_id or "/" in filename or ".." in filename:
        raise HTTPException(status_code=404, detail="Asset not found")
    path = (BEAUTY_DIR / style_id / filename).resolve()
    if not str(path).startswith(str(BEAUTY_DIR.resolve())) or not path.exists():
        raise HTTPException(status_code=404, detail="Asset not found")
    return path


@router.get("/assets/beauty/profiles.json")
def beauty_profiles():
    path = BEAUTY_DIR / "profiles.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="profiles.json not found")
    return JSONResponse(json.loads(path.read_text(encoding="utf-8")))


@router.get("/assets/beauty/{style_id}/{filename}")
def beauty_asset(style_id: str, filename: str):
    return FileResponse(_safe_gallery_path(style_id, filename))


@router.get("/api/assets/{kind}/{identifier}")
def runtime_asset(kind: str, identifier: str, authorization: str | None = Header(default=None)):
    require_asset_access(kind, identifier, authorization)
    path = storage_service.resolve_asset(kind, identifier)
    if path is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    return FileResponse(path)


def _balanced_seed_profiles(profiles: list[dict], count: int) -> list[dict]:
    safe_count = max(0, min(count, len(profiles)))
    if safe_count == 0:
        return []

    grouped: dict[str, list[dict]] = {style_id: [] for style_id in STYLE_ORDER}
    for item in profiles:
        style_id = item.get("style_id")
        if style_id in grouped:
            grouped[style_id].append(item)

    per_style = max(1, (safe_count + len(STYLE_ORDER) - 1) // len(STYLE_ORDER))
    selected: list[dict] = []
    selected_ids: set[str] = set()

    for style_id in STYLE_ORDER:
        for item in grouped[style_id][:per_style]:
            selected.append(item)
            selected_ids.add(item.get("id", ""))
            if len(selected) >= safe_count:
                return selected

    for item in profiles:
        item_id = item.get("id", "")
        if item_id in selected_ids:
            continue
        selected.append(item)
        if len(selected) >= safe_count:
            break

    return selected


@router.get("/api/seeds/sample")
def seed_sample(count: int = 10):
    profiles_path = BEAUTY_DIR / "profiles.json"
    profiles = json.loads(profiles_path.read_text(encoding="utf-8"))
    seeds = []
    for item in _balanced_seed_profiles(profiles, count):
        seeds.append(
            {
                "id": item["id"],
                "style_id": item["style_id"],
                "imageUrl": f"/assets/beauty/{item['photo_path']}",
                "profile": item.get("profile", {}),
            }
        )
    return {"ok": True, "seeds": seeds}


@router.get("/api/seeds/{path_str:path}")
def seed_file(path_str: str):
    if ".." in path_str:
        raise HTTPException(status_code=404, detail="Seed not found")
    path = (BEAUTY_DIR / path_str).resolve()
    if not str(path).startswith(str(BEAUTY_DIR.resolve())) or not path.exists():
        raise HTTPException(status_code=404, detail="Seed not found")
    return FileResponse(path)
