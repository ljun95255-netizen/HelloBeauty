from __future__ import annotations

import builtins
import importlib
import sys
from pathlib import Path

import pytest
from PIL import Image

from backend.models.registry import ModelStatus
from backend.providers.model_runtime import ModelAdapterUnavailable


ROOT = Path(__file__).resolve().parents[1]


def _model_status(model_path: Path) -> ModelStatus:
    return ModelStatus(
        model_id="test/model",
        model_type="fidelity",
        version="0.0.0",
        available=True,
        reason="ready",
        model_root=model_path.parent,
        manifest_path=model_path.parent / "manifest.json",
        entry_file=model_path.name,
        path=model_path,
    )


def test_cloud_adapter_modules_import_without_optional_heavy_dependencies(monkeypatch):
    blocked_packages = {
        "basicsr",
        "diffusers",
        "facexlib",
        "gfpgan",
        "safetensors",
        "torch",
    }
    real_import = builtins.__import__

    def fail_on_heavy_import(name, *args, **kwargs):
        if name.split(".", 1)[0] in blocked_packages:
            raise AssertionError(f"{name} should not be imported at module import time")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fail_on_heavy_import)
    for module_name in (
        "backend.model_adapters.external_command",
        "backend.model_adapters.gpen_bfr512",
        "backend.model_adapters.ssd1b_diffusers",
    ):
        sys.modules.pop(module_name, None)
        importlib.import_module(module_name)


def test_gpen_bfr512_requires_runner_env(monkeypatch, tmp_path):
    monkeypatch.delenv("HELLOBEAUTY_GPEN_RUNNER", raising=False)
    model_path = tmp_path / "gpen.pth"
    model_path.write_bytes(b"placeholder")
    adapter = importlib.import_module("backend.model_adapters.gpen_bfr512")

    with pytest.raises(ModelAdapterUnavailable, match="HELLOBEAUTY_GPEN_RUNNER is required"):
        adapter.render(
            Image.new("RGB", (8, 8), color=(10, 20, 30)),
            recipe={},
            params={},
            model=_model_status(model_path),
        )


def test_external_command_adapter_round_trips_pil_image(tmp_path):
    model_path = tmp_path / "model.pth"
    model_path.write_bytes(b"placeholder")
    runner = tmp_path / "runner.py"
    runner.write_text(
        "\n".join(
            [
                "import sys",
                "from PIL import Image, ImageOps",
                "image = Image.open(sys.argv[1]).convert('RGB')",
                "ImageOps.mirror(image).save(sys.argv[2])",
            ]
        ),
        encoding="utf-8",
    )
    adapter = importlib.import_module("backend.model_adapters.external_command")
    image = Image.new("RGB", (2, 1))
    image.putpixel((0, 0), (255, 0, 0))
    image.putpixel((1, 0), (0, 0, 255))

    output = adapter.render_with_command(
        command_template=f"{sys.executable} {runner} {{input}} {{output}}",
        image=image,
        recipe={"op": "mirror"},
        params={"strength": 1},
        model=_model_status(model_path),
    )

    assert output.mode == "RGB"
    assert output.size == image.size
    assert output.getpixel((0, 0)) == (0, 0, 255)
    assert output.getpixel((1, 0)) == (255, 0, 0)


def test_ssd1b_adapter_clamps_strength_and_records_identity_metadata(monkeypatch, tmp_path):
    adapter = importlib.import_module("backend.model_adapters.ssd1b_diffusers")
    model_path = tmp_path / "ssd.safetensors"
    model_path.write_bytes(b"placeholder")
    seen = {}

    class FakeResult:
        images = [Image.new("RGB", (64, 64), color=(200, 20, 20))]

    class FakePipe:
        def __call__(self, **kwargs):
            seen.update(kwargs)
            return FakeResult()

    monkeypatch.setattr(adapter, "_load_pipeline", lambda _path: FakePipe())
    monkeypatch.setenv("HELLOBEAUTY_CREATIVE_MAX_STRENGTH", "0.32")
    monkeypatch.setenv("HELLOBEAUTY_CREATIVE_PRESERVE_BLEND_ALPHA", "0.18")
    params = {"preset_id": "american_hotgirl", "strength": 0.58}

    output = adapter.render(
        Image.new("RGB", (64, 64), color=(10, 10, 10)),
        recipe={"creative": {"preset_id": "american_hotgirl", "strength": 0.58}},
        params=params,
        model=_model_status(model_path),
    )

    assert output.mode == "RGB"
    assert output.size == (64, 64)
    assert seen["strength"] == 0.32
    assert "preserve facial geometry" in seen["prompt"]
    assert "changed facial structure" in seen["negative_prompt"]
    assert params["strength_requested"] == 0.58
    assert params["strength_effective"] == 0.32
    assert params["max_strength"] == 0.32
    assert params["preserve_blend_alpha"] == 0.18
    assert params["prompt_source"] == "preset:american_hotgirl"
    assert params["negative_prompt_source"] == "default"


def test_gitignore_blocks_paper_artifacts_and_model_weights():
    patterns = set((ROOT / ".gitignore").read_text(encoding="utf-8").splitlines())

    assert {
        "paper/",
        "*.tex",
        "*.aux",
        "*.bbl",
        "main.pdf",
        "fig*.pdf",
        "fig*.png",
    }.issubset(patterns)
    assert {
        "model_assets/**/*.safetensors",
        "model_assets/**/*.safetensors.part-*",
        "model_assets/**/*.pth",
        "cloud_mount/models/**/*.safetensors",
        "cloud_mount/models/**/*.safetensors.part-*",
        "cloud_mount/models/**/*.pth",
        "!cloud_mount/models/**/.gitkeep",
    }.issubset(patterns)
