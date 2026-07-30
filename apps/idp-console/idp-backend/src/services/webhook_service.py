"""Webhook config CRUD + test delivery + delivery logs."""
import json
import time
from uuid import UUID

import httpx
from sqlalchemy import text
from sqlalchemy.orm import Session


class WebhookService:
    def __init__(self, db: Session):
        self.db = db

    def list(self) -> dict:
        rows = self.db.execute(
            text("""
                SELECT id, target_system, target_url, event_type, is_active,
                       last_delivery_at, last_delivery_status, consecutive_failures
                FROM webhooks ORDER BY created_at DESC
            """)
        ).mappings().all()
        return {"webhooks": [dict(r) for r in rows]}

    def create(self, data: dict, created_by: str) -> dict:
        results = []
        for event_type in data["event_types"]:
            row = self.db.execute(
                text("""
                    INSERT INTO webhooks (target_system, target_url, event_type, auth_type,
                                          api_key, headers, retry_strategy, max_retries,
                                          timeout_seconds, created_by_user_id)
                    VALUES (:sys, :url, :event, :auth, :key, :headers, :retry, :max_r, :timeout, :actor)
                    RETURNING id, target_system, event_type
                """),
                {"sys": data["target_system"], "url": data["target_url"], "event": event_type,
                 "auth": data["auth_type"], "key": data.get("api_key"),
                 "headers": json.dumps(data.get("headers", {})), "retry": data["retry_strategy"],
                 "max_r": data["max_retries"], "timeout": data["timeout_seconds"],
                 "actor": created_by},
            ).mappings().first()
            results.append(dict(row))
        self.db.commit()
        return {"webhooks": results}

    def test(self, webhook_id: UUID) -> dict:
        wh = self.db.execute(
            text("SELECT target_url, timeout_seconds, headers FROM webhooks WHERE id = :wid"),
            {"wid": str(webhook_id)},
        ).mappings().first()
        if not wh:
            return {"test_status": "error", "message": "Webhook not found"}
        start = time.monotonic()
        try:
            resp = httpx.post(
                wh["target_url"],
                json={"event": "test", "source": "sentinel-privacy-platform"},
                timeout=wh["timeout_seconds"],
            )
            elapsed_ms = int((time.monotonic() - start) * 1000)
            return {
                "test_status": "success" if resp.status_code < 300 else "failed",
                "response_code": resp.status_code,
                "response_time_ms": elapsed_ms,
            }
        except httpx.HTTPError as e:
            return {"test_status": "failed", "error": str(e)}

    def deliveries(self, webhook_id: UUID, status: str | None, limit: int) -> dict:
        where, params = ["webhook_id = :wid"], {"wid": str(webhook_id), "limit": min(limit, 200)}
        if status:
            where.append("status = :status")
            params["status"] = status
        rows = self.db.execute(
            text(f"""
                SELECT id, event_type, status, attempt_number, response_status_code,
                       sent_at, delivered_at, error_message
                FROM webhook_deliveries WHERE {' AND '.join(where)}
                ORDER BY created_at DESC LIMIT :limit
            """),
            params,
        ).mappings().all()
        return {"deliveries": [dict(r) for r in rows]}
