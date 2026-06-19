from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_required_architecture_exists():
    required_paths = [
        "README.md",
        "pyproject.toml",
        "package.json",
        "package-lock.json",
        "tsconfig.base.json",
        ".gitignore",
        ".env.example",
        "beauty/profiles.json",
        "apps/web",
        "apps/mini",
        "packages/api-client",
        "packages/design-tokens",
        "packages/domain",
        "packages/jesr_core",
        "backend/app.py",
        "backend/api/auth.py",
        "backend/api/sessions.py",
        "backend/api/photos.py",
        "backend/api/recipes.py",
        "backend/api/render.py",
        "backend/api/assets.py",
        "backend/jesr/orchestrator.py",
        "backend/jesr/translator.py",
        "backend/jesr/feedback.py",
        "backend/jesr/recipe_trace.py",
        "backend/providers/base.py",
        "backend/providers/jesr_fidelity.py",
        "backend/providers/jesr_creative.py",
        "backend/providers/model_runtime.py",
        "backend/api/models.py",
        "backend/models/manifest.py",
        "backend/models/registry.py",
        "backend/models/fidelity",
        "backend/models/creative",
        "backend/services/storage.py",
        "backend/services/ingress.py",
        "backend/services/experiments.py",
        "backend/services/session_store.py",
        "backend/workers/render_worker.py",
        "model_assets",
        "cloud_mount/models/fidelity",
        "cloud_mount/models/creative",
        "cloud_mount/manifests/hellobeauty.models.json",
        "cloud_mount/env/hellobeauty.env.example",
        "cloud_mount/scripts/download_release_models.py",
        "cloud_mount/scripts/verify_models.py",
        "runtime",
        "docs",
        "scripts",
        "tests",
    ]
    missing = [path for path in required_paths if not (ROOT / path).exists()]
    assert missing == []


def test_no_disallowed_names_or_old_gallery_paths_in_source():
    source_roots = ["backend", "apps", "packages"]
    hits = []
    for root_name in source_roots:
        for path in (ROOT / root_name).rglob("*"):
            if not path.is_file():
                continue
            if any(part in {".next", "dist", "node_modules"} for part in path.parts):
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            markers = [
                "jesr" + "_gpen",
                "jesr" + "-gpen",
                "apps/web/public/" + "beauty",
                "/beauty/" + "IMG_",
                "/beauty/" + "mini/",
            ]
            for marker in markers:
                if marker in text:
                    hits.append(f"{path.relative_to(ROOT)}:{marker}")
    assert hits == []


def test_fidelity_provider_does_not_import_cv_fallback():
    source = (ROOT / "backend/providers/jesr_fidelity.py").read_text(encoding="utf-8")
    assert "CVFallbackProvider" not in source
    assert ".cv_fallback" not in source
