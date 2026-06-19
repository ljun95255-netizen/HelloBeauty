from __future__ import annotations

import base64
import io
import os
import shutil
from pathlib import Path
from typing import BinaryIO

from PIL import Image


ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.environ.get("HELLOBEAUTY_DATA_DIR", ROOT_DIR / "runtime")).resolve()
BEAUTY_DIR = ROOT_DIR / "beauty"


class StorageService:
    def __init__(self, data_dir: Path = DATA_DIR):
        self.data_dir = data_dir
        self.assets_dir = self.data_dir / "assets"
        self.photo_dir = self.assets_dir / "photo-originals"
        self.thumbnail_dir = self.assets_dir / "photo-thumbnails"
        self.job_dir = self.assets_dir / "job-results"
        self.exports_dir = self.data_dir / "experiments"
        self.ensure_dirs()

    def ensure_dirs(self) -> None:
        for path in [self.photo_dir, self.thumbnail_dir, self.job_dir, self.exports_dir]:
            path.mkdir(parents=True, exist_ok=True)

    def reset(self) -> None:
        if self.data_dir.exists():
            shutil.rmtree(self.data_dir)
        self.ensure_dirs()

    def save_upload(self, photo_id: str, filename: str, file_obj: BinaryIO) -> Path:
        _ = filename
        raw = file_obj.read()
        try:
            image = Image.open(io.BytesIO(raw)).convert("RGB")
        except Exception as exc:
            raise ValueError("Uploaded file must be a valid image") from exc
        path = self.photo_dir / f"{photo_id}.png"
        image.save(path, format="PNG")
        self._write_thumbnail(path, self.thumbnail_dir / f"{photo_id}.png")
        return path

    def delete_photo_assets(self, photo_id: str) -> None:
        for folder in [self.photo_dir, self.thumbnail_dir]:
            for path in folder.glob(f"{photo_id}.*"):
                try:
                    path.unlink()
                except FileNotFoundError:
                    pass

    def save_image(self, image: Image.Image, folder: str, identifier: str) -> Path:
        target_dir = self.job_dir if folder == "job" else self.photo_dir
        target_dir.mkdir(parents=True, exist_ok=True)
        path = target_dir / f"{identifier}.png"
        image.save(path, format="PNG")
        return path

    def image_to_data_url(self, image: Image.Image) -> str:
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
        return f"data:image/png;base64,{encoded}"

    def resolve_asset(self, kind: str, identifier: str) -> Path | None:
        if kind == "photo":
            matches = list(self.photo_dir.glob(f"{identifier}.*"))
            return matches[0] if matches else None
        if kind == "thumbnail":
            path = self.thumbnail_dir / f"{identifier}.png"
            return path if path.exists() else None
        if kind == "job":
            path = self.job_dir / f"{identifier}.png"
            return path if path.exists() else None
        return None

    def _write_thumbnail(self, source: Path, target: Path) -> None:
        image = Image.open(source).convert("RGB")
        image.thumbnail((640, 640))
        image.save(target, format="PNG")


storage_service = StorageService()
