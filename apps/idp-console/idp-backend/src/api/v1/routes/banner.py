"""Banner CRUD, versioning, publish (<1s propagation)."""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.api.v1.middleware.auth import require_permission
from src.config.database import get_db
from src.services.banner_service import BannerService

router = APIRouter()


class BannerCreate(BaseModel):
    name: str
    slug: str
    title: str | None = None
    message: str | None = None
    button_accept_text: str = "Accept All"
    button_reject_text: str = "Reject All"
    button_customize_text: str = "Customize"
    position: str = "bottom"
    background_color: str = "#ffffff"
    text_color: str = "#333333"
    button_color: str = "#667eea"
    purposes: list[str] = []
    channels: list[str] = []
    target_countries: list[str] = []
    target_languages: list[str] = []
    metadata: dict = {}


class PublishRequest(BaseModel):
    publish_immediately: bool = True
    scheduled_at: str | None = None
    message: str | None = None


@router.get("")
def list_banners(
    status: str | None = None,
    user=Depends(require_permission("read:banner")),
    db: Session = Depends(get_db),
):
    return BannerService(db).list(status=status)


@router.post("", status_code=201)
def create_banner(
    body: BannerCreate,
    user=Depends(require_permission("write:banner")),
    db: Session = Depends(get_db),
):
    return BannerService(db).create(body.model_dump(), created_by=user["sub"])


@router.put("/{banner_id}")
def update_banner(
    banner_id: UUID,
    body: BannerCreate,
    user=Depends(require_permission("write:banner")),
    db: Session = Depends(get_db),
):
    result = BannerService(db).update(banner_id, body.model_dump(), updated_by=user["sub"])
    if not result:
        raise HTTPException(status_code=404, detail="Banner not found")
    return result


@router.post("/{banner_id}/publish")
def publish_banner(
    banner_id: UUID,
    body: PublishRequest,
    user=Depends(require_permission("write:banner")),
    db: Session = Depends(get_db),
):
    """Publishes banner: DB write -> Redis Pub/Sub broadcast -> webhook fan-out. Target <1s."""
    result = BannerService(db).publish(banner_id, published_by=user["sub"])
    if not result:
        raise HTTPException(status_code=404, detail="Banner not found")
    return result


@router.get("/{banner_id}/versions")
def banner_versions(
    banner_id: UUID,
    user=Depends(require_permission("read:banner")),
    db: Session = Depends(get_db),
):
    return BannerService(db).versions(banner_id)


@router.post("/{banner_id}/rollback")
def rollback_banner(
    banner_id: UUID,
    target_version: int,
    user=Depends(require_permission("write:banner")),
    db: Session = Depends(get_db),
):
    result = BannerService(db).rollback(banner_id, target_version, user["sub"])
    if not result:
        raise HTTPException(status_code=404, detail="Version not found")
    return result
