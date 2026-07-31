"""Webhook delivery worker.

Consumes events from Redis queue:webhook_delivery and fans them out to every
active webhook registered for that event type. Exponential backoff on failure
(1s -> 2s -> 4s ... capped at 32s, max 10 attempts), then dead-letter queue.

Run:  python -m src.workers.webhook_worker
"""
import json
import time

import httpx
import redis
from sqlalchemy import text

from src.config.database import SessionLocal
from src.config.settings import settings

_redis = redis.from_url(settings.redis_url, decode_responses=True)

QUEUE = "queue:webhook_delivery"
DLQ = "queue:webhook_delivery:dead"
MAX_RETRIES = 10
BACKOFF_CAP = 32


def deliver(webhook: dict, event: dict, db) -> bool:
    delivery_id = db.execute(
        text("""
            INSERT INTO webhook_deliveries (webhook_id, event_type, request_payload,
                                            status, sent_at)
            VALUES (:wid, :etype, :payload, 'pending', NOW())
            RETURNING id
        """),
        {"wid": webhook["id"], "etype": event["type"],
         "payload": json.dumps(event, default=str)},
    ).scalar()
    db.commit()

    headers = {"Content-Type": "application/json", **(webhook.get("headers") or {})}
    if webhook.get("api_key"):
        headers["X-API-Key"] = webhook["api_key"]

    attempt, delay = 1, 1
    while attempt <= MAX_RETRIES:
        try:
            resp = httpx.post(webhook["target_url"], json=event, headers=headers,
                              timeout=webhook.get("timeout_seconds", 30))
            if resp.status_code < 300:
                db.execute(
                    text("""
                        UPDATE webhook_deliveries
                        SET status = 'delivered', delivered_at = NOW(),
                            response_status_code = :code, attempt_number = :attempt
                        WHERE id = CAST(:did AS UUID)
                    """),
                    {"did": delivery_id, "code": resp.status_code, "attempt": attempt},
                )
                db.execute(
                    text("""
                        UPDATE webhooks SET last_delivery_at = NOW(),
                            last_delivery_status = 'success', consecutive_failures = 0
                        WHERE id = :wid
                    """),
                    {"wid": webhook["id"]},
                )
                db.commit()
                return True
            error = f"HTTP {resp.status_code}"
        except httpx.HTTPError as e:
            error = str(e)

        db.execute(
            text("""
                UPDATE webhook_deliveries
                SET status = 'retrying', attempt_number = :attempt, error_message = :err
                WHERE id = CAST(:did AS UUID)
            """),
            {"did": delivery_id, "attempt": attempt, "err": error},
        )
        db.commit()
        time.sleep(delay)
        delay = min(delay * 2, BACKOFF_CAP)
        attempt += 1

    db.execute(
        text("""
            UPDATE webhook_deliveries SET status = 'failed' WHERE id = CAST(:did AS UUID);
        """),
        {"did": delivery_id},
    )
    db.execute(
        text("""
            UPDATE webhooks SET last_delivery_status = 'failed',
                consecutive_failures = consecutive_failures + 1
            WHERE id = :wid
        """),
        {"wid": webhook["id"]},
    )
    db.commit()
    return False


def run():
    print(f"Webhook worker started. Listening on {QUEUE}")
    while True:
        item = _redis.brpop(QUEUE, timeout=5)
        if not item:
            continue
        event = json.loads(item[1])
        db = SessionLocal()
        try:
            webhooks = db.execute(
                text("""
                    SELECT id, target_system, target_url, api_key, headers, timeout_seconds
                    FROM webhooks
                    WHERE event_type = :etype AND is_active = TRUE
                """),
                {"etype": event.get("type", "")},
            ).mappings().all()
            for wh in webhooks:
                ok = deliver(dict(wh), event, db)
                if not ok:
                    _redis.lpush(DLQ, json.dumps({"webhook_id": str(wh["id"]),
                                                  "event": event}, default=str))
        finally:
            db.close()


if __name__ == "__main__":
    run()
