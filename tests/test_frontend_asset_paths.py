from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_web_uses_unified_asset_base_url():
    page = (ROOT / "apps/web/app/page.tsx").read_text(encoding="utf-8")
    next_config = (ROOT / "apps/web/next.config.mjs").read_text(encoding="utf-8")
    assert "NEXT_PUBLIC_ASSET_BASE_URL" in page
    assert '"/assets/beauty"' in page
    assert 'source: "/assets/beauty/:path*"' in next_config
    assert "destination: `${backendOrigin}/assets/beauty/:path*`" in next_config
    assert "/beauty/mini/" not in page
    assert "/beauty/IMG_" not in page
    assert "JESR-Fidelity" in page
    assert "JESR-Creative" in page


def test_mini_build_copies_root_beauty_gallery():
    config = (ROOT / "apps/mini/config/index.js").read_text(encoding="utf-8")
    assert "apps/web/public/beauty" not in config

    package = (ROOT / "apps/mini/package.json").read_text(encoding="utf-8")
    sync_script = (ROOT / "scripts/sync-mini-beauty.js").read_text(encoding="utf-8")
    assert "sync-mini-beauty.js" in package
    assert 'path.join(workspaceRoot, "beauty")' in sync_script
    assert '"dist", "beauty"' in sync_script

    swipe = (ROOT / "apps/mini/src/pages/swipe/index.tsx").read_text(encoding="utf-8")
    assert "/beauty/fresh_japanese/fresh_japanese_02.jpeg" in swipe
    assert "/beauty/IMG_" not in swipe


def test_mini_navigation_targets_are_registered():
    app_config = (ROOT / "apps/mini/src/app.config.ts").read_text(encoding="utf-8")
    edit = (ROOT / "apps/mini/src/pages/edit/index.tsx").read_text(encoding="utf-8")
    swipe = (ROOT / "apps/mini/src/pages/swipe/index.tsx").read_text(encoding="utf-8")

    assert '"pages/preference/index"' in app_config
    assert '"pages/retouch/index"' in app_config
    assert 'url: "/pages/preference/index"' in edit
    assert 'url: "/pages/retouch/index"' in edit
    assert 'startFlow("none")' in swipe
    assert "entryMode" not in swipe
    assert "♙" not in swipe


def test_mini_auth_and_upload_do_not_use_dev_shortcuts():
    mini_src = ROOT / "apps/mini/src"
    source_text = "\n".join(path.read_text(encoding="utf-8") for path in mini_src.rglob("*.tsx"))
    api_text = (mini_src / "utils/api.ts").read_text(encoding="utf-8")

    assert "13800138000" not in source_text
    assert "token: string,\n  storeId: string,\n  sessionId: string,\n  filePath: string," in api_text
    assert "token," in api_text
    assert "clearFlowState();" in api_text


def test_mini_smart_optimize_requires_complete_selected_results():
    swipe = (ROOT / "apps/mini/src/pages/swipe/index.tsx").read_text(encoding="utf-8")

    assert "hasCompleteSmartResults" in swipe
    assert "selectedSmartResults.length !== selectedPhotos.length" in swipe
    assert "hasCompleteSmartResults ? selectedSmartResults : await runSmartOptimize()" in swipe
    assert "resultImageUrl: completed.resultImageUrl," in swipe
    assert "completed.resultImageUrl ?? photo.previewUrl" not in swipe


def test_mini_appointment_guards_and_service_retouch_contracts():
    swipe = (ROOT / "apps/mini/src/pages/swipe/index.tsx").read_text(encoding="utf-8")
    swipe_css = (ROOT / "apps/mini/src/pages/swipe/swipe.css").read_text(encoding="utf-8")

    assert "function canStartSession(" in swipe
    assert "const ensureStartableSession" in swipe
    assert 'const activeSession = await ensureStartableSession("start");' in swipe
    assert 'flowStep !== "complete"' not in swipe
    assert "void submitCurrentSession();" not in swipe
    assert "subscription.subscriptionAccepted" in swipe
    assert "disabled={loading || (!!session && !activeSessionCanStart && !appointmentDraftOpen)}" in swipe
    assert ".bar-button[disabled]" in swipe_css


def test_mini_complete_export_page_has_no_bulk_select_and_centered_result_cards():
    swipe = (ROOT / "apps/mini/src/pages/swipe/index.tsx").read_text(encoding="utf-8")
    swipe_css = (ROOT / "apps/mini/src/pages/swipe/swipe.css").read_text(encoding="utf-8")

    complete_start = swipe.index('{flowStep === "complete" ? (')
    complete_end = swipe.index('{flowStep === "profile" ? (')
    complete_branch = swipe[complete_start:complete_end]

    assert "取消全选" in swipe
    assert "全选" in swipe
    assert "取消全选" not in complete_branch
    assert "全选" not in complete_branch
    assert "mini-outline-button" not in complete_branch
    assert "export-selection-row" not in complete_branch
    assert "result-selected-copy" in complete_branch
    assert "result-photo-card" in complete_branch
    assert "<Button" in complete_branch
    assert "ariaLabel={`第 ${index + 1} 张导出结果" in complete_branch

    card_block = swipe_css[
        swipe_css.index(".result-photo-card {"):
        swipe_css.index(".result-photo-card .export-photo-frame-inner")
    ]
    assert "display: block;" in card_block
    assert "border-radius: 4px !important;" in card_block
    assert "background: #ffffff !important;" in card_block

    inner_block = swipe_css[
        swipe_css.index(".result-photo-card .export-photo-frame-inner"):
        swipe_css.index(".result-photo-card .export-photo-frame-image")
    ]
    assert "left: 12px;" in inner_block
    assert "right: 12px;" in inner_block
    assert "top: 12px;" in inner_block
    assert "bottom: 12px;" in inner_block
    assert "align-items: center;" in inner_block
    assert "justify-content: center;" in inner_block

    image_block = swipe_css[swipe_css.index(".result-photo-card .export-photo-frame-image"):]
    assert "object-position: center center;" in image_block


def test_start_backend_script_wires_api_and_web_without_bypassing_web_assets():
    script = (ROOT / "scripts/start_backend.sh").read_text(encoding="utf-8")
    package = (ROOT / "package.json").read_text(encoding="utf-8")

    assert '"start:backend": "bash scripts/start_backend.sh"' in package
    assert "API:" in script
    assert "Docs:" in script
    assert "Health:" in script
    assert "Web:" in script
    assert "validate_port" in script
    assert "choose_port" in script
    assert "uvicorn backend.app:app" in script
    assert "npm --workspace apps/web run dev" in script
    assert "HELLOBEAUTY_START_WEB" in script
    assert "NEXT_PUBLIC_ASSET_BASE_URL" not in script
