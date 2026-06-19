from __future__ import annotations

import secrets
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from typing import Any

PRE_SHOOT_STYLE_LEAD_MINUTES = 3


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_now() -> str:
    return utc_now().isoformat()


def public_session(session: dict[str, Any], photos: list[dict[str, Any]], jobs: list[dict[str, Any]], prints: list[dict[str, Any]]) -> dict[str, Any]:
    session_photos = [
        photo
        for photo in photos
        if photo["sessionId"] == session["id"] and not photo.get("temporary")
    ]
    session_jobs = [
        job
        for job in jobs
        if job.get("sessionId") == session["id"] and not job.get("temporaryPhoto")
    ]
    session_prints = [record for record in prints if record["sessionId"] == session["id"]]
    payload = deepcopy(session)
    payload["photoCount"] = len(session_photos)
    payload["selectedCount"] = sum(1 for photo in session_photos if photo["selected"])
    payload["completedJobCount"] = sum(1 for job in session_jobs if job["status"] == "completed")
    payload["printCount"] = len(session_prints)
    return payload


class SessionStore:
    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.customers: dict[str, dict[str, Any]] = {}
        self.staff: dict[str, dict[str, Any]] = {}
        self.tokens: dict[str, dict[str, str]] = {}
        self.sessions: dict[str, dict[str, Any]] = {}
        self.photos: dict[str, dict[str, Any]] = {}
        self.jobs: dict[str, dict[str, Any]] = {}
        self.prints: dict[str, dict[str, Any]] = {}
        self.recipes: dict[str, dict[str, Any]] = {}
        self.aesthetic_profiles: dict[str, dict[str, Any]] = {}
        self.iterations: dict[str, list[dict[str, Any]]] = {}
        self.traces: list[dict[str, Any]] = []
        self.probes: dict[str, list[dict[str, Any]]] = {}
        self.preferences: dict[str, dict[str, Any]] = {}
        self.reminders: dict[str, dict[str, Any]] = {}

    def remove_photo_record(self, photo_id: str) -> dict[str, Any] | None:
        photo = self.photos.pop(photo_id, None)
        if photo is None:
            return None
        for session_id, probes in list(self.probes.items()):
            remaining = [probe for probe in probes if probe.get("photo_id") != photo_id]
            if remaining:
                self.probes[session_id] = remaining
            else:
                self.probes.pop(session_id, None)
        return deepcopy(photo)

    def issue_customer(self, phone: str, nickname: str | None = None) -> tuple[str, dict[str, Any]]:
        user = self.customers.get(phone)
        if not user:
            user = {
                "id": f"cus_{secrets.token_hex(6)}",
                "phone": phone,
                "nickname": nickname or "HelloBeauty User",
                "createdAt": iso_now(),
            }
            self.customers[phone] = user
        token = f"cust_{secrets.token_urlsafe(24)}"
        self.tokens[token] = {"kind": "customer", "id": user["id"], "phone": phone}
        return token, deepcopy(user)

    def issue_staff(self, username: str, password: str) -> tuple[str, dict[str, Any]]:
        if username != "store-admin" or password != "hellobeauty123":
            raise ValueError("Invalid staff credentials")
        staff = self.staff.setdefault(
            username,
            {
                "id": "staff_default",
                "storeId": "default-store",
                "username": username,
                "role": "admin",
                "createdAt": iso_now(),
            },
        )
        token = f"staff_{secrets.token_urlsafe(24)}"
        self.tokens[token] = {"kind": "staff", "id": staff["id"], "username": username}
        return token, deepcopy(staff)

    def token_context(self, authorization: str | None) -> dict[str, str] | None:
        if not authorization:
            return None
        prefix = "Bearer "
        token = authorization[len(prefix) :] if authorization.startswith(prefix) else authorization
        return self.tokens.get(token)

    def create_session(
        self,
        phone: str,
        store_id: str,
        duration_minutes: int,
        session_code: str | None = None,
        start_time: datetime | None = None,
    ) -> dict[str, Any]:
        session_id = f"ses_{secrets.token_hex(8)}"
        now = utc_now()
        has_explicit_start_time = start_time is not None
        appointment_start = _as_utc(start_time or now)
        stamp = appointment_start.strftime("%Y%m%d_%H%M")
        prefix = f"{session_code}_{phone}__" if session_code else f"{phone}_"
        session = {
            "id": session_id,
            "storeId": store_id,
            "phone": phone,
            "sessionName": f"{prefix}{stamp}",
            "status": "CREATED",
            "startTime": appointment_start.isoformat(),
            "endTime": (appointment_start + timedelta(minutes=duration_minutes)).isoformat(),
            "durationMinutes": duration_minutes,
            "createdAt": now.isoformat(),
            "startTimeSource": "appointment" if has_explicit_start_time else "immediate",
        }
        self.sessions[session_id] = session
        self.iterations[session_id] = []
        if has_explicit_start_time:
            self.schedule_pre_shoot_style_reminder(session_id)
        return self.get_public_session(session_id)

    def get_public_session(self, session_id: str) -> dict[str, Any]:
        session = self.sessions[session_id]
        return public_session(session, list(self.photos.values()), list(self.jobs.values()), list(self.prints.values()))

    def list_public_sessions(self, phone: str | None = None) -> list[dict[str, Any]]:
        sessions = list(self.sessions.values())
        if phone:
            sessions = [session for session in sessions if phone in session["phone"]]
        return [self.get_public_session(session["id"]) for session in sessions]

    def list_customer_sessions(self, phone: str) -> list[dict[str, Any]]:
        sessions = [session for session in self.sessions.values() if session["phone"] == phone]
        sessions.sort(key=lambda session: str(session.get("startTime") or ""), reverse=True)
        return [self.get_public_session(session["id"]) for session in sessions]

    def schedule_pre_shoot_style_reminder(
        self,
        session_id: str,
        *,
        subscription_accepted: bool = False,
        subscription_status: str | None = None,
        template_id: str | None = None,
    ) -> dict[str, Any]:
        session = self.sessions[session_id]
        start_time = _parse_iso_datetime(str(session["startTime"]))
        due_at = start_time - timedelta(minutes=PRE_SHOOT_STYLE_LEAD_MINUTES)
        now = utc_now()
        reminder_id = f"rem_{session_id}_pre_shoot_style"
        previous = self.reminders.get(reminder_id, {})
        reminder = {
            "id": reminder_id,
            "sessionId": session_id,
            "kind": "pre_shoot_aesthetic_profile",
            "title": "拍摄前准备",
            "message": f"开拍前{PRE_SHOOT_STYLE_LEAD_MINUTES}分钟完成风格爱好，拍摄效果会更稳定。",
            "dueAt": due_at.isoformat(),
            "status": "DUE" if due_at <= now else "SCHEDULED",
            "subscriptionAccepted": subscription_accepted,
            "subscriptionStatus": subscription_status or ("ACCEPTED" if subscription_accepted else "PENDING"),
            "templateId": template_id,
            "createdAt": previous.get("createdAt", now.isoformat()),
            "updatedAt": now.isoformat(),
        }
        self.reminders[reminder_id] = reminder
        session["preShootReminder"] = deepcopy(reminder)
        return deepcopy(reminder)

    def update_reminder_status(self, reminder_id: str, status: str) -> dict[str, Any]:
        if reminder_id not in self.reminders:
            raise KeyError(reminder_id)
        reminder = self.reminders[reminder_id]
        reminder["status"] = status
        reminder["updatedAt"] = iso_now()
        session = self.sessions.get(reminder["sessionId"])
        if session is not None:
            session["preShootReminder"] = deepcopy(reminder)
        return deepcopy(reminder)

    def list_session_reminders(self, session_id: str) -> list[dict[str, Any]]:
        return [
            deepcopy(reminder)
            for reminder in self.reminders.values()
            if reminder["sessionId"] == session_id
        ]

    def list_due_reminders(self, now: datetime | None = None) -> list[dict[str, Any]]:
        current = _as_utc(now or utc_now())
        result: list[dict[str, Any]] = []
        for reminder in self.reminders.values():
            if reminder["status"] not in {"SCHEDULED", "DUE"}:
                continue
            if _parse_iso_datetime(str(reminder["dueAt"])) <= current:
                if reminder["status"] != "DUE":
                    reminder["status"] = "DUE"
                    reminder["updatedAt"] = current.isoformat()
                    session = self.sessions.get(reminder["sessionId"])
                    if session is not None:
                        session["preShootReminder"] = deepcopy(reminder)
                result.append(deepcopy(reminder))
        return result


session_store = SessionStore()


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _parse_iso_datetime(value: str) -> datetime:
    text = value.strip()
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    return _as_utc(datetime.fromisoformat(text))
