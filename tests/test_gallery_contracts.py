import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STYLE_IDS = {
    "fresh_japanese",
    "retro_hongkong",
    "clear_korean",
    "lazy_french",
    "american_hotgirl",
}


def test_single_source_gallery_shape():
    beauty = ROOT / "beauty"
    profiles = json.loads((beauty / "profiles.json").read_text(encoding="utf-8"))
    assert {path.name for path in beauty.iterdir() if path.is_dir()} == STYLE_IDS
    assert len(profiles) == 150
    assert {item["style_id"] for item in profiles} == STYLE_IDS
    for style_id in STYLE_IDS:
        assert len(list((beauty / style_id).glob("*.*"))) == 30


def test_only_source_gallery_is_hellobeauty_beauty():
    beauty_dirs = []
    for path in ROOT.rglob("beauty"):
        if not path.is_dir():
            continue
        if any(part in {"dist", ".next", "node_modules", "runtime"} for part in path.parts):
            continue
        beauty_dirs.append(path.relative_to(ROOT).as_posix())
    assert beauty_dirs == ["beauty"]
