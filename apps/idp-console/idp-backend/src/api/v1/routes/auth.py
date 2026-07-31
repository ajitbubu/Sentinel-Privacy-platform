"""Admin authentication: password + TOTP MFA, role-scoped JWTs."""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from jose import jwt
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from src.api.v1.middleware.auth import ROLE_PERMISSIONS, get_current_admin
from src.config.database import get_db
from src.config.settings import settings
from src.services import auth_service
from src.services.audit_service import log_audit

router = APIRouter()


class AdminLoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)
    mfa_code: str | None = None


class AdminUser(BaseModel):
    id: str
    email: str
    name: str
    role: str
    permissions: list[str]


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int
    user: AdminUser


def create_admin_token(user: dict) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.admin_access_token_expire_minutes
    )
    payload = {
        "sub": str(user["id"]),
        "email": user["email"],
        "role": user["role"],
        "type": "idp_admin",
        "exp": expire,
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def _build_response(user: dict) -> TokenResponse:
    perms = sorted(ROLE_PERMISSIONS.get(user["role"], set()))
    name = " ".join(filter(None, [user.get("first_name"), user.get("last_name")])) or user["email"]
    return TokenResponse(
        access_token=create_admin_token(user),
        refresh_token=auth_service.store_admin_refresh(str(user["id"])),
        expires_in=settings.admin_access_token_expire_minutes * 60,
        user=AdminUser(
            id=str(user["id"]), email=user["email"], name=name,
            role=user["role"], permissions=perms,
        ),
    )


@router.post("/login", response_model=TokenResponse)
def login(body: AdminLoginRequest, request: Request, db: Session = Depends(get_db)):
    """Authenticate an admin. MFA is mandatory for admin and dpo roles."""
    client_ip = request.client.host if request.client else None
    try:
        user = auth_service.authenticate(body.email, body.password, body.mfa_code, db)
    except auth_service.MFARequiredError:
        # 401 + explicit flag so the UI can prompt for the code without treating it as failure
        raise HTTPException(
            status_code=401,
            detail={"code": "MFA_REQUIRED", "message": "Enter your authenticator code"},
        )
    except auth_service.AccountLockedError as e:
        raise HTTPException(status_code=423, detail=str(e))
    except auth_service.AuthError as e:
        raise HTTPException(status_code=401, detail=str(e))

    log_audit(db, entity_type="user", entity_id=str(user["id"]), action="login",
              actor_id=str(user["id"]), actor_ip=client_ip,
              new_values={"role": user["role"]})
    return _build_response(user)


class RefreshRequest(BaseModel):
    refresh_token: str


@router.post("/refresh", response_model=TokenResponse)
def refresh(body: RefreshRequest, db: Session = Depends(get_db)):
    user_id = auth_service.rotate_admin_refresh(body.refresh_token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    from sqlalchemy import text
    row = db.execute(
        text("""SELECT id, email, first_name, last_name, role, status
                FROM users WHERE id = CAST(:uid AS UUID)"""),
        {"uid": user_id},
    ).mappings().first()
    if row is None or row["status"] != "active":
        raise HTTPException(status_code=401, detail="Account unavailable")
    return _build_response(dict(row))


@router.post("/logout", status_code=204)
def logout(body: RefreshRequest):
    auth_service.revoke_admin_refresh(body.refresh_token)
    return None


@router.get("/me", response_model=AdminUser)
def me(user: dict = Depends(get_current_admin), db: Session = Depends(get_db)):
    from sqlalchemy import text
    row = db.execute(
        text("SELECT id, email, first_name, last_name, role FROM users WHERE id = CAST(:uid AS UUID)"),
        {"uid": user["sub"]},
    ).mappings().first()
    if row is None:
        raise HTTPException(status_code=404, detail="User not found")
    name = " ".join(filter(None, [row["first_name"], row["last_name"]])) or row["email"]
    return AdminUser(id=str(row["id"]), email=row["email"], name=name, role=row["role"],
                     permissions=sorted(ROLE_PERMISSIONS.get(row["role"], set())))


# ---- MFA enrollment ----

class MFAConfirmRequest(BaseModel):
    code: str = Field(min_length=6, max_length=6)


@router.post("/mfa/enroll")
def mfa_enroll(user: dict = Depends(get_current_admin), db: Session = Depends(get_db)):
    """Start MFA enrollment. Returns a secret + otpauth:// URI for the authenticator app."""
    result = auth_service.enroll_mfa(user["sub"], user["email"], db)
    return {**result, "next": "Scan the QR code, then POST the 6-digit code to /auth/mfa/confirm"}


@router.post("/mfa/confirm")
def mfa_confirm(
    body: MFAConfirmRequest,
    user: dict = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    if not auth_service.confirm_mfa(user["sub"], body.code, db):
        raise HTTPException(status_code=400, detail="Invalid code — try the next one")
    log_audit(db, entity_type="user", entity_id=user["sub"], action="mfa_enabled",
              actor_id=user["sub"])
    return {"mfa_enabled": True}
