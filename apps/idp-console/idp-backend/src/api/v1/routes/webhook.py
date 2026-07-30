"""Webhook configuration for pushing to external systems (Salesforce, HubSpot, etc.)."""
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.api.v1.middleware.auth import require_permission
from src.config.database import get_db
from src.services.webhook_service import WebhookService

router = APIRouter()


class WebhookCreate(BaseModel):
    target_system: str  # salesforce | hubspot | outreach | highspot | custom
    target_url: str
    event_types: list[str]
    auth_type: str = "api_key"
    api_key: str | None = None
    headers: dict = {}
    retry_strategy: str = "exponential"
    max_retries: int = 10
    timeout_seconds: int = 30


@router.get("")
def list_webhooks(
    user=Depends(require_permission("read:webhook")),
    db: Session = Depends(get_db),
):
    return WebhookService(db).list()


@router.post("", status_code=201)
def create_webhook(
    body: WebhookCreate,
    user=Depends(require_permission("write:webhook")),
    db: Session = Depends(get_db),
):
    return WebhookService(db).create(body.model_dump(), created_by=user["sub"])


@router.post("/{webhook_id}/test")
def test_webhook(
    webhook_id: UUID,
    user=Depends(require_permission("write:webhook")),
    db: Session = Depends(get_db),
):
    return WebhookService(db).test(webhook_id)


@router.get("/{webhook_id}/deliveries")
def delivery_log(
    webhook_id: UUID,
    status: str | None = None,
    limit: int = 50,
    user=Depends(require_permission("read:webhook")),
    db: Session = Depends(get_db),
):
    return WebhookService(db).deliveries(webhook_id, status=status, limit=limit)
