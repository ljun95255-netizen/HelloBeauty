from __future__ import annotations

import secrets
from datetime import timedelta
from typing import BinaryIO

from .session_store import _parse_iso_datetime, iso_now, session_store, utc_now
from .storage import storage_service

TEMPORARY_UPLOAD_TTL_SECONDS = 30 * 60


class IngressService:
    def cleanup_temporary_uploads(self, max_age_seconds: int = TEMPORARY_UPLOAD_TTL_SECONDS) -> int:
        cutoff = utc_now() - timedelta(seconds=max_age_seconds)
        removed = 0
        for photo_id, photo in list(session_store.photos.items()):
            if not photo.get("temporary"):
                continue
            try:
                captured_at = _parse_iso_datetime(str(photo.get("capturedAt", "")))
            except ValueError:
                captured_at = cutoff - timedelta(seconds=1)
            if captured_at > cutoff:
                continue
            storage_service.delete_photo_assets(photo_id)
            session_store.remove_photo_record(photo_id)
            removed += 1
        return removed

    def ingest_camera_upload(
        self,
        session_id: str,
        store_id: str,
        filename: str,
        file_obj: BinaryIO,
        temporary: bool = False,
    ) -> dict:
        if session_id not in session_store.sessions:
            raise KeyError("Session not found")
        self.cleanup_temporary_uploads()
        photo_id = f"pho_{secrets.token_hex(8)}"
        path = storage_service.save_upload(photo_id, filename, file_obj)
        photo = {
            "id": photo_id,
            "sessionId": session_id,
            "storeId": store_id,
            "filename": path.name,
            "source": "iphone",
            "selected": False,
            "capturedAt": iso_now(),
            "previewUrl": f"/api/assets/photo/{photo_id}",
            "originalImageUrl": f"/api/assets/photo/{photo_id}",
            "thumbnailUrl": f"/api/assets/thumbnail/{photo_id}",
            "albumImageUrl": f"/api/assets/photo/{photo_id}",
            "latestJob": None,
            "assetPath": str(path),
            "temporary": temporary,
        }
        session_store.photos[photo_id] = photo
        if not temporary:
            session_store.sessions[session_id]["status"] = "WAITING_SELECTION"
        return photo


ingress_service = IngressService()
