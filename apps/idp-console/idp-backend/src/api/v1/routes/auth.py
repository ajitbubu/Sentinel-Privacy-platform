"""Admin authentication with role + optional MFA."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr

router = APIRouter()


class AdminLoginRequest(BaseModel):
    email: EmailStr
    password: str
    mfa_code: str | None = None


@router.post("/login")
def login(body: AdminLoginRequest):
    # TODO: verify against users table (Argon2 hash), check MFA, issue JWT with role
    raise HTTPException(status_code=501, detail="Wire up admin identity verification")
