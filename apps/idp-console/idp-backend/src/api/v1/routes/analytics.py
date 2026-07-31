"""Dashboard metrics."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.api.v1.middleware.auth import require_permission
from src.config.database import get_db
from src.services import analytics_service

router = APIRouter()


@router.get("/overview")
def overview(db: Session = Depends(get_db),
             user: dict = Depends(require_permission("read:audit"))):
    return analytics_service.overview(db)


@router.get("/timeseries")
def timeseries(days: int = Query(30, ge=7, le=365), db: Session = Depends(get_db),
               user: dict = Depends(require_permission("read:audit"))):
    return {"series": analytics_service.timeseries(db, days)}


@router.get("/by-purpose")
def by_purpose(db: Session = Depends(get_db),
               user: dict = Depends(require_permission("read:audit"))):
    return {"purposes": analytics_service.by_purpose(db)}


@router.get("/by-source")
def by_source(db: Session = Depends(get_db),
              user: dict = Depends(require_permission("read:audit"))):
    return {"sources": analytics_service.by_source(db)}


@router.get("/webhook-health")
def webhook_health(db: Session = Depends(get_db),
                   user: dict = Depends(require_permission("read:webhook"))):
    return {"systems": analytics_service.webhook_health(db)}
