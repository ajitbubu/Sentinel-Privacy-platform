"""Role-based auth for admin console. Roles: admin, dpo, auditor, analyst."""
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from src.config.settings import settings

security = HTTPBearer()

ROLE_PERMISSIONS = {
    "admin": {"*"},
    "dpo": {"read:banner", "write:banner", "read:consent_admin", "write:consent_admin",
            "read:audit", "read:dsar", "write:dsar", "read:webhook", "write:webhook"},
    "auditor": {"read:banner", "read:consent_admin", "read:audit", "read:dsar"},
    "analyst": {"read:audit", "read:consent_admin"},
}


def get_current_admin(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    try:
        payload = jwt.decode(
            credentials.credentials, settings.secret_key, algorithms=[settings.jwt_algorithm]
        )
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    if payload.get("role") not in ROLE_PERMISSIONS:
        raise HTTPException(status_code=403, detail="Not an admin token")
    return payload


def require_permission(permission: str):
    def checker(user: dict = Depends(get_current_admin)) -> dict:
        perms = ROLE_PERMISSIONS.get(user["role"], set())
        if "*" not in perms and permission not in perms:
            raise HTTPException(status_code=403, detail=f"Missing permission: {permission}")
        return user
    return checker
