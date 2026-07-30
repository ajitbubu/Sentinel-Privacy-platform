"""Passwordless authentication: magic link -> JWT (+ refresh rotation)."""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from jose import jwt
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.config.settings import settings
from src.services import auth_service

router = APIRouter()


class MagicLinkRequest(BaseModel):
    email: EmailStr


class VerifyRequest(BaseModel):
    token: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int


def create_access_token(subject_id: str, email: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": subject_id, "email": email, "type": "pmp_user", "exp": expire}
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def _token_response(subject_id: str, email: str) -> TokenResponse:
    return TokenResponse(
        access_token=create_access_token(subject_id, email),
        refresh_token=auth_service.store_refresh_token(subject_id),
        expires_in=settings.access_token_expire_minutes * 60,
    )


@router.post("/magic-link", status_code=202)
def request_magic_link(body: MagicLinkRequest):
    """Send a sign-in link. Response is identical whether or not the email exists."""
    try:
        auth_service.request_magic_link(body.email)
    except auth_service.RateLimitedError:
        raise HTTPException(status_code=429, detail="Too many requests. Try again later.")
    return {"message": "If that address is valid, a sign-in link is on its way."}


@router.post("/verify", response_model=TokenResponse)
def verify(body: VerifyRequest, db: Session = Depends(get_db)):
    """Exchange a magic-link token for access + refresh tokens (single use)."""
    result = auth_service.verify_magic_link(body.token, db)
    if result is None:
        raise HTTPException(status_code=401, detail="Invalid or expired sign-in link")
    subject_id, email = result
    return _token_response(subject_id, email)


@router.post("/refresh", response_model=TokenResponse)
def refresh(body: RefreshRequest, db: Session = Depends(get_db)):
    """Rotate the refresh token and issue a new access token."""
    rotated = auth_service.rotate_refresh_token(body.refresh_token)
    if rotated is None:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")
    subject_id, new_refresh = rotated
    from sqlalchemy import text
    email = db.execute(
        text("SELECT email FROM subjects WHERE id = :sid"), {"sid": subject_id}
    ).scalar()
    if not email:
        raise HTTPException(status_code=401, detail="Subject not found")
    return TokenResponse(
        access_token=create_access_token(subject_id, email),
        refresh_token=new_refresh,
        expires_in=settings.access_token_expire_minutes * 60,
    )


@router.post("/logout", status_code=204)
def logout(body: RefreshRequest):
    """Revoke the refresh token. Access token expires naturally (30 min)."""
    auth_service.revoke_refresh_token(body.refresh_token)
    return None
