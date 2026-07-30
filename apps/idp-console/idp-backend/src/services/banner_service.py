"""Banner lifecycle: create -> version -> publish -> broadcast (<1s)."""
import json
from uuid import UUID

import redis
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.config.settings import settings

_redis = redis.from_url(settings.redis_url, decode_responses=True)


class BannerService:
    def __init__(self, db: Session):
        self.db = db

    def list(self, status: str | None = None) -> dict:
        q = "SELECT id, name, slug, status, current_version, created_at, published_at FROM banners"
        params = {}
        if status:
            q += " WHERE status = :status"
            params["status"] = status
        rows = self.db.execute(text(q + " ORDER BY created_at DESC"), params).mappings().all()
        return {"banners": [dict(r) for r in rows]}

    def create(self, data: dict, created_by: str) -> dict:
        row = self.db.execute(
            text("""
                INSERT INTO banners (name, slug, title, message, button_accept_text,
                                     button_reject_text, button_customize_text, position,
                                     background_color, text_color, button_color,
                                     status, created_by_user_id, metadata)
                VALUES (:name, :slug, :title, :message, :accept, :reject, :customize,
                        :position, :bg, :text_color, :btn, 'draft', :creator, :meta)
                RETURNING id, slug, status, current_version, created_at
            """),
            {"name": data["name"], "slug": data["slug"], "title": data.get("title"),
             "message": data.get("message"), "accept": data["button_accept_text"],
             "reject": data["button_reject_text"], "customize": data["button_customize_text"],
             "position": data["position"], "bg": data["background_color"],
             "text_color": data["text_color"], "btn": data["button_color"],
             "creator": created_by, "meta": json.dumps(data.get("metadata", {}))},
        ).mappings().first()
        self._snapshot_version(row["id"], 1, data, created_by, "Initial version")
        self.db.commit()
        return dict(row)

    def update(self, banner_id: UUID, data: dict, updated_by: str) -> dict | None:
        row = self.db.execute(
            text("""
                UPDATE banners
                SET title = :title, message = :message, updated_by_user_id = :actor,
                    updated_at = NOW(), current_version = current_version + 1
                WHERE id = :bid
                RETURNING id, current_version, status, updated_at
            """),
            {"bid": str(banner_id), "title": data.get("title"),
             "message": data.get("message"), "actor": updated_by},
        ).mappings().first()
        if not row:
            return None
        self._snapshot_version(banner_id, row["current_version"], data, updated_by, "Updated")
        self.db.commit()
        return dict(row)

    def publish(self, banner_id: UUID, published_by: str) -> dict | None:
        """1. DB write (sync)  2. Redis broadcast (<10ms)  3. Webhook fan-out (async)."""
        row = self.db.execute(
            text("""
                UPDATE banners
                SET status = 'published', is_active = TRUE, published_at = NOW()
                WHERE id = :bid
                RETURNING id, slug, status, current_version, published_at
            """),
            {"bid": str(banner_id)},
        ).mappings().first()
        if not row:
            return None
        self.db.commit()
        event = {
            "type": "banner.published",
            "banner_id": str(banner_id),
            "slug": row["slug"],
            "version": row["current_version"],
        }
        # Real-time broadcast to PMP + IDP UIs
        _redis.publish("channel:banner:published", json.dumps(event, default=str))
        # Queue webhook fan-out to external systems
        _redis.lpush("queue:webhook_delivery", json.dumps(event, default=str))
        return {**dict(row), "webhook_status": "queued", "estimated_sync_time": "< 1 second"}

    def versions(self, banner_id: UUID) -> dict:
        rows = self.db.execute(
            text("""
                SELECT version, change_description, changed_by_user_id, created_at, is_current
                FROM banner_versions WHERE banner_id = :bid ORDER BY version DESC
            """),
            {"bid": str(banner_id)},
        ).mappings().all()
        return {"versions": [dict(r) for r in rows]}

    def rollback(self, banner_id: UUID, target_version: int, actor: str) -> dict | None:
        snap = self.db.execute(
            text("""
                SELECT snapshot FROM banner_versions
                WHERE banner_id = :bid AND version = :v
            """),
            {"bid": str(banner_id), "v": target_version},
        ).mappings().first()
        if not snap:
            return None
        data = snap["snapshot"]
        self.db.execute(
            text("UPDATE banners SET current_version = :v, updated_by_user_id = :actor WHERE id = :bid"),
            {"v": target_version, "actor": actor, "bid": str(banner_id)},
        )
        self.db.commit()
        return {"id": str(banner_id), "current_version": target_version, "message": "Rolled back"}

    def _snapshot_version(self, banner_id, version: int, data: dict, actor: str, descr: str):
        self.db.execute(
            text("""
                INSERT INTO banner_versions (banner_id, version, snapshot,
                                             change_description, changed_by_user_id)
                VALUES (:bid, :v, :snap, :descr, :actor)
            """),
            {"bid": str(banner_id), "v": version, "snap": json.dumps(data, default=str),
             "descr": descr, "actor": actor},
        )
