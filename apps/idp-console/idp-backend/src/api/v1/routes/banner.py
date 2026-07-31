"""Banner authoring, versioning and publication (DPO only)."""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.api.v1.middleware.auth import require_permission
from src.config.database import get_db
from src.services import banner_service
from src.services.banner_service import BannerError

router = APIRouter()

HEX = r"^#[0-9a-fA-F]{6}$"


class BannerCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    slug: str = Field(pattern=r"^[a-z0-9-]+$", max_length=100)
    type: str = Field(default="consent", pattern="^(consent|cookie)$")
    description: str | None = None
    title: str | None = Field(default=None, max_length=255)
    message: str | None = Field(default=None, max_length=5000)
    button_accept_text: str = "Accept all"
    button_reject_text: str = "Reject all"
    button_customize_text: str = "Customise"
    position: str = Field(default="bottom", pattern="^(bottom|top|modal|sidebar)$")
    background_color: str = Field(default="#ffffff", pattern=HEX)
    text_color: str = Field(default="#333333", pattern=HEX)
    button_color: str = Field(default="#2f62d8", pattern=HEX)
    purposes: list[str] = Field(default_factory=list)
    channels: list[str] = Field(default_factory=list)
    target_countries: list[str] = Field(default_factory=list)
    target_languages: list[str] = Field(default_factory=list)


class BannerUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    title: str | None = None
    message: str | None = None
    button_accept_text: str | None = None
    button_reject_text: str | None = None
    button_customize_text: str | None = None
    position: str | None = Field(default=None, pattern="^(bottom|top|modal|sidebar)$")
    background_color: str | None = Field(default=None, pattern=HEX)
    text_color: str | None = Field(default=None, pattern=HEX)
    button_color: str | None = Field(default=None, pattern=HEX)
    purposes: list[str] | None = None
    channels: list[str] | None = None
    target_countries: list[str] | None = None
    target_languages: list[str] | None = None
    materially_changed: bool = Field(
        default=False,
        description="TRUE forces re-consent for everyone. Set only when purposes or "
                    "the meaning of the notice change — not for cosmetic edits.",
    )
    change_note: str | None = None


@router.get("")
def list_banners(status: str | None = Query(None),
                 db: Session = Depends(get_db),
                 user: dict = Depends(require_permission("read:banner"))):
    return {"banners": banner_service.list_banners(db, status)}


@router.get("/{banner_id}")
def get_banner(banner_id: str, db: Session = Depends(get_db),
               user: dict = Depends(require_permission("read:banner"))):
    banner = banner_service.get(db, banner_id)
    if banner is None:
        raise HTTPException(404, "Banner not found")
    return banner


@router.post("", status_code=201)
def create_banner(body: BannerCreate, db: Session = Depends(get_db),
                  user: dict = Depends(require_permission("write:banner"))):
    try:
        return banner_service.create(db, body.model_dump(), user["sub"])
    except BannerError as e:
        raise HTTPException(400, str(e))


@router.put("/{banner_id}")
def update_banner(banner_id: str, body: BannerUpdate, db: Session = Depends(get_db),
                  user: dict = Depends(require_permission("write:banner"))):
    data = body.model_dump(exclude={"materially_changed", "change_note"})
    try:
        return banner_service.update(db, banner_id, data, user["sub"],
                                     body.materially_changed, body.change_note)
    except BannerError as e:
        raise HTTPException(400, str(e))


@router.get("/{banner_id}/versions")
def banner_versions(banner_id: str, db: Session = Depends(get_db),
                    user: dict = Depends(require_permission("read:banner"))):
    return {"versions": banner_service.versions(db, banner_id)}


@router.post("/{banner_id}/publish")
def publish_banner(banner_id: str, db: Session = Depends(get_db),
                   user: dict = Depends(require_permission("write:banner"))):
    try:
        return banner_service.publish(db, banner_id, user["sub"])
    except BannerError as e:
        raise HTTPException(400, str(e))


class RollbackRequest(BaseModel):
    target_version: int = Field(ge=1)


@router.post("/{banner_id}/rollback")
def rollback_banner(banner_id: str, body: RollbackRequest, db: Session = Depends(get_db),
                    user: dict = Depends(require_permission("write:banner"))):
    try:
        return banner_service.rollback(db, banner_id, body.target_version, user["sub"])
    except BannerError as e:
        raise HTTPException(400, str(e))
