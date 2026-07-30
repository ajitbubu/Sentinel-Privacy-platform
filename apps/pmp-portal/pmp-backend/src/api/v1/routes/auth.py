"""User authentication: login, refresh, logout."""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from jose import jwt
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.config.settings import settings

router = APIRouter()


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    expires_in: int


def create_access_token(subject_id: str, email: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {
        "sub": subject_id,
        "email": email,
        "type": "pmp_user",
        "exp": expire,
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    # TODO: verify credentials against subjects table (passwordless magic-link or password)
    # Placeholder: reject until identity verification is wired up
    raise HTTPException(status_code=501, detail="Wire up identity verification")


@router.post("/logout", status_code=204)
def logout():
    # Token invalidation via Redis denylist
    return None
