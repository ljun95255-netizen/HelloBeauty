from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

from backend.models.manifest import load_manifest_entries


ROOT = Path(__file__).resolve().parents[1]


def test_default_cloud_manifest_shape():
    entries = load_manifest_entries(ROOT / "cloud_mount/manifests/hellobeauty.models.json")

    assert {entry.model_type for entry in entries} == {"fidelity", "creative"}
    assert {entry.asset_name for entry in entries} == {
        "jesr-fidelity-gpen-prior-v0.1.0.pth",
        "jesr-creative-ssd1b-v0.1.0.safetensors",
    }
    assert all(entry.entry_file.startswith(f"models/{entry.model_type}/") for entry in entries)
    creative = next(entry for entry in entries if entry.model_type == "creative")
    assert creative.asset_parts == [
        "jesr-creative-ssd1b-v0.1.0.safetensors.part-000",
        "jesr-creative-ssd1b-v0.1.0.safetensors.part-001",
        "jesr-creative-ssd1b-v0.1.0.safetensors.part-002",
    ]


def test_verify_models_fails_on_hash_mismatch(tmp_path):
    root = tmp_path / "mount"
    model_path = root / "models/fidelity/model.safetensors"
    model_path.parent.mkdir(parents=True)
    model_path.write_bytes(b"bad-model")
    manifest_path = root / "manifests/hellobeauty.models.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "models": [
                    {
                        "id": "test/fidelity",
                        "type": "fidelity",
                        "version": "0.0.1",
                        "asset_name": "model.safetensors",
                        "sha256": "0" * 64,
                        "entry_file": "models/fidelity/model.safetensors",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "cloud_mount/scripts/verify_models.py"),
            "--root",
            str(root),
            "--manifest",
            str(manifest_path),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 1
    assert "sha256 mismatch" in result.stderr


def test_verify_models_accepts_matching_hash(tmp_path):
    root = tmp_path / "mount"
    model_path = root / "models/creative/model.safetensors"
    model_path.parent.mkdir(parents=True)
    payload = b"ok-model"
    model_path.write_bytes(payload)
    manifest_path = root / "manifests/hellobeauty.models.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "models": [
                    {
                        "id": "test/creative",
                        "type": "creative",
                        "version": "0.0.1",
                        "asset_name": "model.safetensors",
                        "sha256": hashlib.sha256(payload).hexdigest(),
                        "entry_file": "models/creative/model.safetensors",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "cloud_mount/scripts/verify_models.py"),
            "--root",
            str(root),
            "--manifest",
            str(manifest_path),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "OK: test/creative" in result.stdout
