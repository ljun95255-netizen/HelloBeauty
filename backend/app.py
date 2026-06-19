from __future__ import annotations

import os
import socket
import sys
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(ROOT_DIR / "packages" / "jesr_core"))

from backend.api.assets import router as assets_router
from backend.api.auth import router as auth_router
from backend.api.models import router as models_router
from backend.api.photos import router as photos_router
from backend.api.recipes import router as recipes_router
from backend.api.render import router as render_router
from backend.api.sessions import router as sessions_router
from backend.services.session_store import session_store
from backend.services.storage import storage_service


def _cors_origins() -> list[str]:
    configured = os.environ.get(
        "HELLOBEAUTY_CORS_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000,http://localhost:10086,http://127.0.0.1:10086",
    )
    return [origin.strip() for origin in configured.split(",") if origin.strip()]


def _is_web_home_available(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return False
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        with socket.create_connection((parsed.hostname, port), timeout=0.2):
            return True
    except OSError:
        return False


app = FastAPI(
    title="HelloBeauty API",
    description="JESR-Orchestrator, JESR-Fidelity, and JESR-Creative API",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for router in [
    auth_router,
    sessions_router,
    photos_router,
    recipes_router,
    render_router,
    models_router,
    assets_router,
]:
    app.include_router(router)


@app.get("/", include_in_schema=False)
def root():
    web_url = os.environ.get("HELLOBEAUTY_WEB_URL", "http://127.0.0.1:3000/").strip()
    if _is_web_home_available(web_url):
        return RedirectResponse(web_url)
    return RedirectResponse("/docs")


@app.get("/api/health")
def health():
    return {
        "ok": True,
        "service": "HelloBeauty",
        "backend": ["JESR-Orchestrator", "JESR-Fidelity", "JESR-Creative"],
        "beauty_gallery": str(ROOT_DIR / "beauty"),
        "runtime": str(storage_service.data_dir),
    }


def reset_for_tests() -> None:
    session_store.reset()
    storage_service.reset()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.app:app", host="127.0.0.1", port=7860, reload=False)
