from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.services.session_store import session_store


router = APIRouter()


class CustomerLoginPayload(BaseModel):
    phone: str
    nickname: str | None = None


class StaffLoginPayload(BaseModel):
    username: str
    password: str


@router.post("/api/customer/auth/wechat-phone")
def login_customer(payload: CustomerLoginPayload):
    phone = "".join(ch for ch in payload.phone if ch.isdigit())
    if len(phone) < 7:
        raise HTTPException(status_code=400, detail="A valid phone number is required")
    token, user = session_store.issue_customer(phone, payload.nickname)
    return {"token": token, "user": user}


@router.post("/api/staff/auth/login")
def login_staff(payload: StaffLoginPayload):
    try:
        token, staff = session_store.issue_staff(payload.username, payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    return {"token": token, "staff": staff}
