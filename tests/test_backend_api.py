import io
from collections import Counter
from datetime import timedelta

import numpy as np
from fastapi.testclient import TestClient
from PIL import Image

import backend.app as app_module
from backend.jesr.orchestrator import JESROrchestrator
from backend.providers.base import ProviderResult
from backend.services.ingress import ingress_service
from backend.services.session_store import session_store, utc_now
from backend.services.storage import storage_service


def _upload_bytes() -> bytes:
    image = Image.fromarray(np.full((48, 48, 3), 180, dtype=np.uint8))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _customer_headers(client: TestClient, phone: str = "19500008285") -> dict[str, str]:
    response = client.post(
        "/api/customer/auth/wechat-phone",
        json={"phone": phone, "nickname": "tester"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['token']}"}


def _staff_headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/staff/auth/login",
        json={"username": "store-admin", "password": "hellobeauty123"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['token']}"}


def _upload_session_photo(client: TestClient, headers: dict[str, str], session_id: str) -> dict:
    response = client.post(
        "/api/ingress/camera/default-store/upload",
        headers=headers,
        data={"session_id": session_id},
        files={"image": ("capture.png", _upload_bytes(), "image/png")},
    )
    assert response.status_code == 200
    return response.json()["photo"]


def test_assets_and_main_customer_flow():
    app_module.reset_for_tests()
    client = TestClient(app_module.app)

    profiles = client.get("/assets/beauty/profiles.json")
    assert profiles.status_code == 200
    assert len(profiles.json()) == 150

    image = client.get("/assets/beauty/fresh_japanese/fresh_japanese_01.jpeg")
    assert image.status_code == 200
    assert image.headers["content-type"].startswith("image/")

    headers = _customer_headers(client)
    session_response = client.post(
        "/api/sessions",
        headers=headers,
        json={"store_id": "default-store", "duration_minutes": 12, "session_code": "001"},
    )
    assert session_response.status_code == 200
    session = session_response.json()["session"]

    upload_response = client.post(
        "/api/ingress/camera/default-store/upload",
        headers=headers,
        data={"session_id": session["id"]},
        files={"image": ("capture.png", _upload_bytes(), "image/png")},
    )
    assert upload_response.status_code == 200
    photo = upload_response.json()["photo"]

    temp_upload_response = client.post(
        "/api/ingress/camera/default-store/upload",
        headers=headers,
        data={"session_id": session["id"], "temporary": "true"},
        files={"image": ("retouch-only.png", _upload_bytes(), "image/png")},
    )
    assert temp_upload_response.status_code == 200
    temp_photo = temp_upload_response.json()["photo"]
    assert storage_service.resolve_asset("photo", temp_photo["id"]) is not None
    assert storage_service.resolve_asset("thumbnail", temp_photo["id"]) is not None

    customer_sessions = client.get("/api/customer/sessions", headers=headers)
    assert customer_sessions.status_code == 200
    assert [item["id"] for item in customer_sessions.json()["sessions"]] == [session["id"]]
    assert customer_sessions.json()["sessions"][0]["photoCount"] == 1

    assert client.post(f"/api/photos/{temp_photo['id']}/diagnose", headers=headers).status_code == 400
    assert client.post(f"/api/photos/{temp_photo['id']}/probe/generate", headers=headers).status_code == 400
    temp_probe_feedback = client.post(
        "/api/probe-feedback",
        headers=headers,
        json={"photo_id": temp_photo["id"], "feedback": []},
    )
    assert temp_probe_feedback.status_code == 400

    temp_smart = client.post(f"/api/photos/{temp_photo['id']}/smart-optimize", headers=headers, json={})
    assert temp_smart.status_code == 200
    temp_job_id = temp_smart.json()["image"].rsplit("/", 1)[-1]
    assert client.get(f"/api/edit-jobs/{temp_job_id}", headers=headers).status_code == 200
    assert client.get(temp_smart.json()["image"], headers=headers).status_code == 200
    assert client.get(temp_photo["previewUrl"], headers=headers).status_code == 404
    assert storage_service.resolve_asset("photo", temp_photo["id"]) is None
    assert storage_service.resolve_asset("thumbnail", temp_photo["id"]) is None

    other_headers = _customer_headers(client, phone="19500008287")
    assert client.get(f"/api/edit-jobs/{temp_job_id}").status_code == 401
    assert client.get(f"/api/edit-jobs/{temp_job_id}", headers=other_headers).status_code == 403
    assert client.get(temp_smart.json()["image"]).status_code == 401
    assert client.get(temp_smart.json()["image"], headers=other_headers).status_code == 403

    temp_retouch_upload = client.post(
        "/api/ingress/camera/default-store/upload",
        headers=headers,
        data={"session_id": session["id"], "temporary": "true"},
        files={"image": ("retouch-v2-only.png", _upload_bytes(), "image/png")},
    )
    assert temp_retouch_upload.status_code == 200
    temp_retouch_photo = temp_retouch_upload.json()["photo"]
    assert storage_service.resolve_asset("photo", temp_retouch_photo["id"]) is not None
    selected_temp_retouch = client.post(
        f"/api/photos/{temp_retouch_photo['id']}/select",
        headers=headers,
        json={"selected": True},
    )
    assert selected_temp_retouch.status_code == 200
    temp_retouch = client.post(
        f"/api/photos/{temp_retouch_photo['id']}/targeted-retouch-v2",
        headers=headers,
        json={"params": {"skin_smooth": 0.25}},
    )
    assert temp_retouch.status_code == 200
    assert client.get(temp_retouch.json()["image"], headers=headers).status_code == 200
    assert client.get(temp_retouch_photo["previewUrl"], headers=headers).status_code == 404
    assert storage_service.resolve_asset("photo", temp_retouch_photo["id"]) is None
    assert storage_service.resolve_asset("thumbnail", temp_retouch_photo["id"]) is None

    temp_render_upload = client.post(
        "/api/ingress/camera/default-store/upload",
        headers=headers,
        data={"session_id": session["id"], "temporary": "true"},
        files={"image": ("creative-only.png", _upload_bytes(), "image/png")},
    )
    assert temp_render_upload.status_code == 200
    temp_render_photo = temp_render_upload.json()["photo"]
    temp_pipeline = client.post(
        "/api/render/pipeline",
        headers=headers,
        json={"session_id": session["id"], "photo_id": temp_render_photo["id"], "mode": "auto"},
    )
    assert temp_pipeline.status_code == 200
    temp_pipeline_id = temp_pipeline.json()["job"]["id"]
    assert client.get(f"/api/edit-jobs/{temp_pipeline_id}", headers=headers).status_code == 200
    assert client.get(f"/api/edit-jobs/{temp_pipeline_id}").status_code == 401
    assert client.get(f"/api/edit-jobs/{temp_pipeline_id}", headers=other_headers).status_code == 403
    assert client.get(f"/api/render/jobs/{temp_pipeline_id}", headers=headers).status_code == 200
    assert client.get(f"/api/render/jobs/{temp_pipeline_id}").status_code == 401
    assert client.get(f"/api/render/jobs/{temp_pipeline_id}", headers=other_headers).status_code == 403
    assert client.get(temp_render_photo["previewUrl"], headers=headers).status_code == 404

    customer_sessions_after_temp = client.get("/api/customer/sessions", headers=headers)
    assert customer_sessions_after_temp.status_code == 200
    assert customer_sessions_after_temp.json()["sessions"][0]["photoCount"] == 1
    assert customer_sessions_after_temp.json()["sessions"][0]["completedJobCount"] == 0
    assert customer_sessions_after_temp.json()["sessions"][0]["status"] == "WAITING_SELECTION"

    abandoned_upload = client.post(
        "/api/ingress/camera/default-store/upload",
        headers=headers,
        data={"session_id": session["id"], "temporary": "true"},
        files={"image": ("abandoned.png", _upload_bytes(), "image/png")},
    )
    assert abandoned_upload.status_code == 200
    abandoned_photo = abandoned_upload.json()["photo"]
    session_store.photos[abandoned_photo["id"]]["capturedAt"] = (utc_now() - timedelta(hours=1)).isoformat()
    assert ingress_service.cleanup_temporary_uploads(max_age_seconds=60) == 1
    assert abandoned_photo["id"] not in session_store.photos
    assert storage_service.resolve_asset("photo", abandoned_photo["id"]) is None
    assert storage_service.resolve_asset("thumbnail", abandoned_photo["id"]) is None

    visible_photos = client.get(f"/api/sessions/{session['id']}/photos", headers=headers)
    assert visible_photos.status_code == 200
    visible_photo_ids = {item["id"] for item in visible_photos.json()["photos"]}
    assert photo["id"] in visible_photo_ids
    assert temp_photo["id"] not in visible_photo_ids

    smart = client.post(f"/api/photos/{photo['id']}/smart-optimize", headers=headers, json={})
    assert smart.status_code == 200
    assert smart.json()["render_mode"] == "JESR-Fidelity"
    assert smart.json()["image"].startswith("/api/assets/job/")

    retouch = client.post(
        f"/api/photos/{photo['id']}/targeted-retouch-v2",
        headers=headers,
        json={"params": {"skin_smooth": 0.25}},
    )
    assert retouch.status_code == 200
    assert retouch.json()["status"].startswith("jesr_fidelity")

    style = client.post(
        f"/api/sessions/{session['id']}/style-select",
        headers=headers,
        json={"preset_id": "fresh_japanese"},
    )
    assert style.status_code == 200
    assert style.json()["recipe"]["creative"]["preset_id"] == "fresh_japanese"

    iteration = client.post(
        f"/api/sessions/{session['id']}/iterate",
        headers=headers,
        json={
            "photo_id": photo["id"],
            "pain_tags": ["texture_too_fake"],
            "free_text_feedback": "skin looks fake",
        },
    )
    assert iteration.status_code == 200
    iteration_id = iteration.json()["iteration"]["id"]

    rollback = client.post(
        f"/api/sessions/{session['id']}/rollback",
        headers=headers,
        json={"iteration_id": iteration_id},
    )
    assert rollback.status_code == 200
    assert rollback.json()["rollback"]["rolled_back_from"] == iteration_id

    render = client.post(
        "/api/render/pipeline",
        headers=headers,
        json={"session_id": session["id"], "photo_id": photo["id"], "mode": "auto"},
    )
    assert render.status_code == 200
    job_id = render.json()["job"]["id"]

    job = client.get(f"/api/render/jobs/{job_id}", headers=headers)
    assert job.status_code == 200
    assert job.json()["job"]["status"] == "completed"

    runtime_asset = client.get(smart.json()["image"], headers=headers)
    assert runtime_asset.status_code == 200
    assert runtime_asset.headers["content-type"].startswith("image/")

    unauth_runtime_asset = client.get(smart.json()["image"])
    assert unauth_runtime_asset.status_code == 401

    other_runtime_asset = client.get(smart.json()["image"], headers=_customer_headers(client, phone="19500008287"))
    assert other_runtime_asset.status_code == 403


def test_session_photo_and_runtime_assets_require_owner_token():
    app_module.reset_for_tests()
    client = TestClient(app_module.app)
    owner_headers = _customer_headers(client, phone="19500008285")
    other_headers = _customer_headers(client, phone="19500008286")

    session = client.post(
        "/api/sessions",
        headers=owner_headers,
        json={"store_id": "default-store", "duration_minutes": 12, "session_code": "101"},
    ).json()["session"]

    no_token_upload = client.post(
        "/api/ingress/camera/default-store/upload",
        data={"session_id": session["id"]},
        files={"image": ("capture.png", _upload_bytes(), "image/png")},
    )
    assert no_token_upload.status_code == 401

    forbidden_upload = client.post(
        "/api/ingress/camera/default-store/upload",
        headers=other_headers,
        data={"session_id": session["id"]},
        files={"image": ("capture.png", _upload_bytes(), "image/png")},
    )
    assert forbidden_upload.status_code == 403

    upload = client.post(
        "/api/ingress/camera/default-store/upload",
        headers=owner_headers,
        data={"session_id": session["id"]},
        files={"image": ("capture.png", _upload_bytes(), "image/png")},
    )
    assert upload.status_code == 200
    photo = upload.json()["photo"]

    other_session = client.post(
        "/api/sessions",
        headers=other_headers,
        json={"store_id": "default-store", "duration_minutes": 12, "session_code": "102"},
    ).json()["session"]
    other_photo = _upload_session_photo(client, other_headers, other_session["id"])

    assert client.get(f"/api/sessions/{session['id']}/photos").status_code == 401
    assert client.get(f"/api/sessions/{session['id']}/photos", headers=other_headers).status_code == 403
    assert client.post(f"/api/photos/{photo['id']}/select", json={"selected": True}).status_code == 401
    assert client.post(
        f"/api/photos/{photo['id']}/select",
        headers=other_headers,
        json={"selected": True},
    ).status_code == 403

    cross_reference = client.post(
        f"/api/sessions/{session['id']}/jesr/aesthetic-profile/reference-photos",
        headers=owner_headers,
        json={"reference_photo_ids": [other_photo["id"]]},
    )
    assert cross_reference.status_code == 403

    cross_legacy_reference = client.post(
        f"/api/sessions/{session['id']}/base-style/reference-photos",
        headers=owner_headers,
        json={"photo_ids": [other_photo["id"]]},
    )
    assert cross_legacy_reference.status_code == 403


def test_seed_sample_returns_balanced_style_preferences():
    app_module.reset_for_tests()
    client = TestClient(app_module.app)

    response = client.get("/api/seeds/sample?count=25")
    assert response.status_code == 200
    seeds = response.json()["seeds"]

    assert len(seeds) == 25
    assert Counter(seed["style_id"] for seed in seeds) == {
        "fresh_japanese": 5,
        "clear_korean": 5,
        "retro_hongkong": 5,
        "lazy_french": 5,
        "american_hotgirl": 5,
    }
    assert all(seed["imageUrl"].startswith("/assets/beauty/") for seed in seeds)


def test_session_start_time_and_pre_shoot_style_reminder_schedule():
    app_module.reset_for_tests()
    client = TestClient(app_module.app)
    headers = _customer_headers(client)
    start_time = utc_now() + timedelta(hours=2)

    session_response = client.post(
        "/api/sessions",
        headers=headers,
        json={
            "store_id": "default-store",
            "duration_minutes": 30,
            "session_code": "002",
            "start_time": start_time.isoformat(),
        },
    )
    assert session_response.status_code == 200
    session = session_response.json()["session"]
    assert session["startTime"] == start_time.isoformat()
    assert session["endTime"] == (start_time + timedelta(minutes=30)).isoformat()
    assert session["preShootReminder"]["dueAt"] == (start_time - timedelta(minutes=3)).isoformat()
    assert session["preShootReminder"]["status"] == "SCHEDULED"

    reminder_response = client.post(
        f"/api/sessions/{session['id']}/reminders/pre-shoot-style",
        headers=headers,
        json={
            "subscription_accepted": True,
            "subscription_status": "ACCEPT",
            "template_id": "tmpl_pre_shoot",
        },
    )
    assert reminder_response.status_code == 200
    reminder = reminder_response.json()["reminder"]
    assert reminder["subscriptionAccepted"] is True
    assert reminder["subscriptionStatus"] == "ACCEPT"
    assert reminder["templateId"] == "tmpl_pre_shoot"

    reminders = client.get(f"/api/sessions/{session['id']}/reminders", headers=headers)
    assert reminders.status_code == 200
    assert reminders.json()["reminders"][0]["id"] == reminder["id"]


    legacy_session = client.post(
        "/api/sessions",
        headers=headers,
        json={"store_id": "default-store", "duration_minutes": 12, "session_code": "003"},
    ).json()["session"]
    assert "preShootReminder" not in legacy_session


def test_due_reminder_can_be_marked_sent():
    app_module.reset_for_tests()
    client = TestClient(app_module.app)
    headers = _customer_headers(client)
    staff_headers = _staff_headers(client)
    start_time = utc_now() + timedelta(minutes=2)

    session = client.post(
        "/api/sessions",
        headers=headers,
        json={
            "store_id": "default-store",
            "duration_minutes": 30,
            "session_code": "004",
            "start_time": start_time.isoformat(),
        },
    ).json()["session"]
    reminder_id = session["preShootReminder"]["id"]

    assert client.get("/api/staff/reminders/due").status_code == 401
    assert client.get("/api/staff/reminders/due", headers=headers).status_code == 403

    due = client.get("/api/staff/reminders/due", headers=staff_headers)
    assert due.status_code == 200
    assert [reminder["id"] for reminder in due.json()["reminders"]] == [reminder_id]

    sent = client.post(
        f"/api/staff/reminders/{reminder_id}/status",
        headers=staff_headers,
        json={"status": "SENT"},
    )
    assert sent.status_code == 200
    assert sent.json()["reminder"]["status"] == "SENT"

    due_after_sent = client.get("/api/staff/reminders/due", headers=staff_headers)
    assert due_after_sent.status_code == 200
    assert due_after_sent.json()["reminders"] == []


def test_creative_provider_does_not_download_when_model_missing():
    app_module.reset_for_tests()
    client = TestClient(app_module.app)
    headers = _customer_headers(client)
    session = client.post("/api/sessions", headers=headers, json={}).json()["session"]
    photo = client.post(
        "/api/ingress/camera/default-store/upload",
        headers=headers,
        data={"session_id": session["id"]},
        files={"image": ("capture.png", _upload_bytes(), "image/png")},
    ).json()["photo"]
    client.post(
        f"/api/sessions/{session['id']}/style-select",
        headers=headers,
        json={"preset_id": "clear_korean"},
    )
    job = client.post(
        "/api/render/pipeline",
        headers=headers,
        json={"session_id": session["id"], "photo_id": photo["id"], "mode": "auto"},
    ).json()["job"]
    result_job = client.get(f"/api/edit-jobs/{job['result_job_id']}", headers=headers).json()["job"]
    assert "jesr_creative_unavailable_model_file_missing" in result_job["statusMessage"]


def test_model_status_is_unavailable_without_downloaded_assets():
    app_module.reset_for_tests()
    client = TestClient(app_module.app)

    response = client.get("/api/models/status")

    assert response.status_code == 200
    body = response.json()
    assert body["download"] == "disabled_at_request_time"
    assert body["models"]["fidelity"]["available"] is False
    assert body["models"]["fidelity"]["reason"] == "model_file_missing"
    assert body["models"]["creative"]["available"] is False
    assert body["models"]["creative"]["reason"] == "model_file_missing"
    assert body["models"]["fidelity"]["id"] == "hellobeauty/jesr-fidelity-gpen-prior"
    assert body["models"]["creative"]["id"] == "hellobeauty/jesr-creative-ssd1b"


def test_identity_feedback_reduces_identity_sensitive_recipe_fields():
    app_module.reset_for_tests()
    client = TestClient(app_module.app)
    headers = _customer_headers(client)
    session = client.post("/api/sessions", headers=headers, json={}).json()["session"]
    photo = client.post(
        "/api/ingress/camera/default-store/upload",
        headers=headers,
        data={"session_id": session["id"]},
        files={"image": ("capture.png", _upload_bytes(), "image/png")},
    ).json()["photo"]
    recipe = client.post(
        f"/api/sessions/{session['id']}/style-select",
        headers=headers,
        json={"preset_id": "american_hotgirl"},
    ).json()["recipe"]

    iteration = client.post(
        f"/api/sessions/{session['id']}/iterate",
        headers=headers,
        json={
            "photo_id": photo["id"],
            "pain_tags": ["identity_not_preserved"],
            "free_text_feedback": "not me",
        },
    )

    assert iteration.status_code == 200
    updated = iteration.json()["updated_recipe"]
    assert round(updated["face"]["face_slim"], 6) == 0.02
    assert updated["face"]["eye_size"] == 0.0
    assert round(updated["creative"]["strength"], 6) == 0.14


def test_identity_feedback_never_revives_disabled_or_floor_creative_strength():
    from jesr_core import merge_feedback

    disabled = {
        "face": {"face_slim": -0.04, "eye_size": 0.04},
        "creative": {"preset_id": None, "strength": 0.0},
        "feedback": {"pain_tags": []},
    }
    disabled_update = merge_feedback(disabled, ["identity_not_preserved"])

    assert disabled_update["creative"]["strength"] == 0.0
    assert disabled_update["face"]["face_slim"] == 0.0
    assert disabled_update["face"]["eye_size"] == 0.0

    at_floor = {
        "face": {"face_slim": 0.0, "eye_size": 0.0},
        "creative": {"preset_id": "fresh_japanese", "strength": 0.04},
        "feedback": {"pain_tags": []},
    }
    floor_update = merge_feedback(at_floor, ["identity_not_preserved"])

    assert floor_update["creative"]["strength"] == 0.04


def test_jesr_aesthetic_profile_alias_routes_and_recipe_metadata():
    app_module.reset_for_tests()
    client = TestClient(app_module.app)
    headers = _customer_headers(client)
    session = client.post("/api/sessions", headers=headers, json={}).json()["session"]

    initial = client.get(f"/api/sessions/{session['id']}/jesr/aesthetic-profile", headers=headers)
    assert initial.status_code == 200
    assert initial.json()["profile_status"] == "not_initialized"
    assert initial.json()["jesr_aesthetic_profile"] is None

    profile_vector = {
        "light_tendency": 0.4,
        "warmth": 0.2,
        "contrast": 0.1,
        "texture_tendency": 0.2,
        "makeup_intensity": 0.3,
        "facial_detail_preference": 1.0,
        "style_strength": 1.0,
        "identity_tolerance": 0.0,
    }
    ready = client.post(
        f"/api/sessions/{session['id']}/jesr/aesthetic-profile/seed-gallery",
        headers=headers,
        json={
            "choices": [
                {
                    "seed_id": "seed-ready",
                    "liked": True,
                    "style_id": "american_hotgirl",
                    "profile": profile_vector,
                }
            ]
        },
    )
    assert ready.status_code == 200
    body = ready.json()
    profile = body["jesr_aesthetic_profile"]
    recipe = body["jesr_profile_recipe"]
    assert profile["profile_status"] == "ready"
    assert profile["source"] == "seed_gallery"
    assert recipe["version"] == "jesr_core.v1"
    assert recipe["style_id"] == "american_hotgirl"
    assert recipe["style_preset_id"] == "american_hotgirl"
    assert recipe["jesr"]["profile_recipe_version"] == "jesr_profile_recipe.v1"
    assert recipe["jesr"]["aesthetic_profile_revision"] == profile["profile_revision"]
    assert recipe["face"]["face_slim"] == 0.0
    assert recipe["creative"]["strength"] <= 0.22

    current_recipe = client.get(f"/api/sessions/{session['id']}/jesr/profile-recipe", headers=headers)
    assert current_recipe.status_code == 200
    assert current_recipe.json()["recipe_status"] == "ready"
    assert current_recipe.json()["recipe"]["jesr"]["display_label"] == "JESR-Profile-Recipe"


def test_jesr_aesthetic_profile_validation_and_legacy_compatibility():
    app_module.reset_for_tests()
    client = TestClient(app_module.app)
    headers = _customer_headers(client)
    session = client.post("/api/sessions", headers=headers, json={}).json()["session"]
    reference_photo_1 = _upload_session_photo(client, headers, session["id"])
    reference_photo_2 = _upload_session_photo(client, headers, session["id"])

    missing = client.get("/api/sessions/not-real/jesr/aesthetic-profile", headers=headers)
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "session_not_found"

    invalid_payload = client.post(
        f"/api/sessions/{session['id']}/jesr/aesthetic-profile/seed-gallery",
        headers=headers,
        json=["not-object"],
    )
    assert invalid_payload.status_code == 422
    assert invalid_payload.json()["error"]["code"] == "invalid_payload"

    unknown_style = client.post(
        f"/api/sessions/{session['id']}/jesr/aesthetic-profile/seed-gallery",
        headers=headers,
        json={"choices": [{"seed_id": "s1", "liked": True, "style_id": "unknown", "profile": {}}]},
    )
    assert unknown_style.status_code == 422
    assert unknown_style.json()["error"]["details"]["style_id"] == "unknown"

    duplicate_conflict = client.post(
        f"/api/sessions/{session['id']}/jesr/aesthetic-profile/seed-gallery",
        headers=headers,
        json={
            "choices": [
                {"seed_id": "s1", "liked": True, "style_id": "fresh_japanese", "profile": {}},
                {"seed_id": "s1", "liked": False, "style_id": "fresh_japanese", "profile": {}},
            ]
        },
    )
    assert duplicate_conflict.status_code == 422
    assert duplicate_conflict.json()["error"]["details"]["conflict_seed_id"] == "s1"

    reference = client.post(
        f"/api/sessions/{session['id']}/jesr/aesthetic-profile/reference-photos",
        headers=headers,
        json={"reference_photo": [reference_photo_1["id"], reference_photo_1["id"], reference_photo_2["id"]]},
    )
    assert reference.status_code == 200
    assert reference.json()["jesr_aesthetic_profile"]["source"] == "reference_photos"
    assert reference.json()["jesr_aesthetic_profile"]["evidence"]["reference_photo_ids"] == [
        reference_photo_1["id"],
        reference_photo_2["id"],
    ]

    legacy = client.post(
        f"/api/sessions/{session['id']}/base-style/seed-selection",
        headers=headers,
        json={"choices": [{"seed_id": "legacy-missing", "liked": True}]},
    )
    assert legacy.status_code == 200
    assert legacy.json()["base_style"]["source"] == "seed_selection"


def test_jesr_reference_photos_merge_with_ready_seed_profile():
    app_module.reset_for_tests()
    client = TestClient(app_module.app)
    headers = _customer_headers(client)
    session = client.post("/api/sessions", headers=headers, json={}).json()["session"]
    reference_photo_1 = _upload_session_photo(client, headers, session["id"])
    reference_photo_2 = _upload_session_photo(client, headers, session["id"])

    profile_vector = {
        "light_tendency": 0.4,
        "warmth": 0.2,
        "contrast": 0.1,
        "texture_tendency": 0.2,
        "makeup_intensity": 0.3,
        "facial_detail_preference": 0.4,
        "style_strength": 0.5,
        "identity_tolerance": -0.3,
    }
    seed_profile = client.post(
        f"/api/sessions/{session['id']}/jesr/aesthetic-profile/seed-gallery",
        headers=headers,
        json={
            "choices": [
                {
                    "seed_id": "seed-ready",
                    "liked": True,
                    "style_id": "lazy_french",
                    "profile": profile_vector,
                }
            ]
        },
    )
    assert seed_profile.status_code == 200
    original_profile = seed_profile.json()["jesr_aesthetic_profile"]

    merged = client.post(
        f"/api/sessions/{session['id']}/jesr/aesthetic-profile/reference-photos",
        headers=headers,
        json={"reference_photo_ids": [reference_photo_1["id"], reference_photo_1["id"], reference_photo_2["id"]]},
    )
    assert merged.status_code == 200
    merged_profile = merged.json()["jesr_aesthetic_profile"]
    assert merged_profile["source"] == "hybrid"
    assert merged_profile["profile_status"] == "ready"
    assert merged_profile["profile_vector"] == original_profile["profile_vector"]
    assert merged_profile["style_preferences"] == original_profile["style_preferences"]
    assert merged_profile["evidence"]["seed_choices"] == original_profile["evidence"]["seed_choices"]
    assert merged_profile["evidence"]["reference_photo_ids"] == [
        reference_photo_1["id"],
        reference_photo_2["id"],
    ]
    assert merged_profile["metadata"]["reference_photo_merge"]["preserved_profile_vector"] is True
    assert merged_profile["profile_revision"] == original_profile["profile_revision"] + 1

    recipe = client.get(f"/api/sessions/{session['id']}/jesr/profile-recipe", headers=headers)
    assert recipe.status_code == 200
    body = recipe.json()["recipe"]
    assert body["version"] == "jesr_core.v1"
    assert body["style_id"] == "lazy_french"
    assert body["jesr"]["profile_recipe_version"] == "jesr_profile_recipe.v1"
    assert body["jesr"]["source"] == "JESR-Aesthetic-Profile"
    assert body["jesr"]["display_label"] == "JESR-Profile-Recipe"
    assert body["jesr"]["aesthetic_profile_id"] == merged_profile["profile_id"]
    assert body["jesr"]["aesthetic_profile_revision"] == merged_profile["profile_revision"]


def test_legacy_base_style_writes_do_not_overwrite_active_recipe():
    app_module.reset_for_tests()
    client = TestClient(app_module.app)
    headers = _customer_headers(client)
    session = client.post("/api/sessions", headers=headers, json={}).json()["session"]

    style = client.post(
        f"/api/sessions/{session['id']}/style-select",
        headers=headers,
        json={"preset_id": "american_hotgirl"},
    )
    assert style.status_code == 200
    before = style.json()["recipe"]
    assert before["style_id"] == "american_hotgirl"
    assert before["creative"]["strength"] == 0.30

    legacy = client.post(
        f"/api/sessions/{session['id']}/base-style/seed-gallery",
        headers=headers,
        json={
            "choices": [
                {
                    "seed_id": "legacy-ready",
                    "liked": True,
                    "style_id": "fresh_japanese",
                    "profile": {
                        "light_tendency": 0.5,
                        "warmth": 0.0,
                        "contrast": 0.0,
                        "texture_tendency": 0.0,
                        "makeup_intensity": 0.0,
                        "facial_detail_preference": 1.0,
                        "style_strength": 1.0,
                        "identity_tolerance": 0.0,
                    },
                }
            ]
        },
    )
    assert legacy.status_code == 200
    assert legacy.json()["jesr_aesthetic_profile"]["profile_status"] == "ready"

    current = client.get(f"/api/sessions/{session['id']}/jesr-recipe", headers=headers)
    assert current.status_code == 200
    assert current.json()["recipe"] == before

    profile_recipe = client.post(
        f"/api/sessions/{session['id']}/jesr/profile-recipe/initialize",
        headers=headers,
        json={},
    )
    assert profile_recipe.status_code == 200
    assert profile_recipe.json()["recipe"]["jesr"]["profile_recipe_version"] == "jesr_profile_recipe.v1"
    assert profile_recipe.json()["recipe"] != before


def test_jesr_profile_recipe_initialize_unknown_style_uses_error_contract():
    app_module.reset_for_tests()
    client = TestClient(app_module.app)
    headers = _customer_headers(client)
    session = client.post("/api/sessions", headers=headers, json={}).json()["session"]

    response = client.post(
        f"/api/sessions/{session['id']}/jesr/profile-recipe/initialize",
        headers=headers,
        json={"style_id": "unknown"},
    )

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "invalid_jesr_profile_recipe"
    assert body["error"]["details"]["style_id"] == "unknown"

    malformed = client.post(
        f"/api/sessions/{session['id']}/jesr/profile-recipe/initialize",
        headers=headers,
        json=["not-object"],
    )
    assert malformed.status_code == 422
    assert malformed.json()["error"]["code"] == "invalid_payload"

    wrong_type = client.post(
        f"/api/sessions/{session['id']}/jesr/profile-recipe/initialize",
        headers=headers,
        json={"style_id": 123},
    )
    assert wrong_type.status_code == 422
    assert wrong_type.json()["error"]["details"]["field"] == "style_id"


def test_orchestrator_metric_control_retries_failed_creative_attempt():
    class FakeFidelity:
        provider_name = "fake-fidelity"

        def smart_optimize(self, image, recipe):
            return ProviderResult(
                image=Image.new("RGB", image.size, color=(80, 80, 80)),
                status="jesr_fidelity_smart_optimize_ok",
                provider=self.provider_name,
                params={},
            )

    class FakeCreative:
        provider_name = "fake-creative"

        def __init__(self):
            self.calls = 0

        def render(self, image, recipe, params=None):
            self.calls += 1
            if self.calls == 1:
                return ProviderResult(
                    image=Image.new("RGB", image.size, color=(80, 80, 80)),
                    status="jesr_creative_unavailable_adapter_runtime_not_configured",
                    provider=self.provider_name,
                    params={"strength_requested": recipe["creative"]["strength"]},
                )
            return ProviderResult(
                image=Image.new("RGB", image.size, color=(120, 120, 120)),
                status="jesr_creative_diffusion_img2img_ok",
                provider=self.provider_name,
                params={
                    "strength_requested": recipe["creative"]["strength"],
                    "strength_effective": recipe["creative"]["strength"],
                    "preserve_blend_alpha": 0.0,
                },
            )

    class AlwaysPassingIdentity:
        backend = "insightface"
        available = True
        reason = "ready"
        threshold = 0.72

        def similarity(self, _a_path, _b_path):
            return 0.99

    app_module.reset_for_tests()
    creative = FakeCreative()
    orchestrator = JESROrchestrator(fidelity_provider=FakeFidelity(), creative_provider=creative)
    orchestrator.initialize_recipe("session-metric", "american_hotgirl")

    result, trace = orchestrator.render(
        session_id="session-metric",
        photo_id="photo-metric",
        image=Image.new("RGB", (32, 32), color=(10, 10, 10)),
        mode="auto",
        metric_control={
            "source_variant": "full",
            "primary_evaluator": AlwaysPassingIdentity(),
            "identity_evaluators": {},
            "required_backends": [],
            "identity_threshold": 0.72,
        },
    )

    assert creative.calls == 2
    assert result.status == "guarded_full_ok_identity_retry_passed_attempt_2"
    assert result.params["metric_control"]["creative_retry_selected_attempt"] == 2
    assert trace["render_params"]["metric_control"]["creative_retry_selected_reason"] == "identity_retry_passed_attempt_2"
