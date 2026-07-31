"""Aggregate metrics for the DPO dashboard."""
from sqlalchemy import text
from sqlalchemy.orm import Session


def overview(db: Session) -> dict:
    row = db.execute(text("""
        SELECT
          (SELECT COUNT(*) FROM consents WHERE status = 'granted' AND deleted_at IS NULL)   AS active_consents,
          (SELECT COUNT(*) FROM consents WHERE status = 'withdrawn' AND deleted_at IS NULL) AS withdrawn_consents,
          (SELECT COUNT(*) FROM subjects WHERE deleted_at IS NULL)                          AS total_subjects,
          (SELECT COUNT(*) FROM dsar_requests
             WHERE status IN ('submitted','acknowledged','in_progress'))                    AS open_dsar,
          (SELECT COUNT(*) FROM dsar_requests
             WHERE status IN ('submitted','acknowledged','in_progress')
               AND due_date < NOW() + INTERVAL '5 days')                                    AS dsar_due_soon,
          (SELECT COUNT(*) FROM dsar_requests
             WHERE status IN ('submitted','acknowledged','in_progress')
               AND due_date < NOW())                                                        AS dsar_overdue,
          (SELECT COUNT(*) FROM consents
             WHERE created_at > NOW() - INTERVAL '7 days' AND deleted_at IS NULL)           AS consents_7d
    """)).mappings().first()
    result = dict(row)
    total = (result["active_consents"] or 0) + (result["withdrawn_consents"] or 0)
    result["opt_out_rate"] = round(100 * (result["withdrawn_consents"] or 0) / total, 1) if total else 0.0
    return result


def timeseries(db: Session, days: int = 30) -> list[dict]:
    """Daily granted/withdrawn counts. generate_series fills gaps so the chart
    shows real zero days rather than silently collapsing them."""
    rows = db.execute(
        text("""
            SELECT to_char(d.day, 'YYYY-MM-DD') AS date,
                   COALESCE(g.count, 0) AS granted,
                   COALESCE(w.count, 0) AS withdrawn
            FROM generate_series(
                   CURRENT_DATE - make_interval(days => :days - 1), CURRENT_DATE, '1 day'
                 ) AS d(day)
            LEFT JOIN (
                SELECT date_trunc('day', granted_at) AS day, COUNT(*) AS count
                FROM consents WHERE granted_at IS NOT NULL AND deleted_at IS NULL
                GROUP BY 1
            ) g ON g.day = d.day
            LEFT JOIN (
                SELECT date_trunc('day', withdrawn_at) AS day, COUNT(*) AS count
                FROM consents WHERE withdrawn_at IS NOT NULL AND deleted_at IS NULL
                GROUP BY 1
            ) w ON w.day = d.day
            ORDER BY d.day
        """),
        {"days": days},
    ).mappings().all()
    return [dict(r) for r in rows]


def by_purpose(db: Session) -> list[dict]:
    rows = db.execute(text("""
        SELECT p.name AS purpose,
               COUNT(*) FILTER (WHERE c.status = 'granted')   AS granted,
               COUNT(*) FILTER (WHERE c.status = 'withdrawn') AS withdrawn,
               ROUND(100.0 * COUNT(*) FILTER (WHERE c.status = 'granted')
                     / NULLIF(COUNT(*), 0), 1) AS grant_rate
        FROM purposes p
        LEFT JOIN consents c ON c.purpose_id = p.id AND c.deleted_at IS NULL
        GROUP BY p.id, p.name
        ORDER BY granted DESC NULLS LAST
    """)).mappings().all()
    return [dict(r) for r in rows]


def by_source(db: Session) -> list[dict]:
    rows = db.execute(text("""
        SELECT COALESCE(source_system, 'unknown') AS source, COUNT(*) AS total,
               COUNT(*) FILTER (WHERE status = 'granted') AS granted
        FROM consents WHERE deleted_at IS NULL
        GROUP BY 1 ORDER BY total DESC
    """)).mappings().all()
    return [dict(r) for r in rows]


def webhook_health(db: Session) -> list[dict]:
    rows = db.execute(text("""
        SELECT w.target_system,
               COUNT(d.*)                                              AS attempts,
               COUNT(d.*) FILTER (WHERE d.status = 'delivered')        AS delivered,
               COUNT(d.*) FILTER (WHERE d.status = 'failed')           AS failed,
               ROUND(AVG(EXTRACT(EPOCH FROM (d.delivered_at - d.created_at)))::numeric, 3)
                                                                       AS avg_latency_seconds
        FROM webhooks w
        LEFT JOIN webhook_deliveries d
               ON d.webhook_id = w.id AND d.created_at > NOW() - INTERVAL '24 hours'
        GROUP BY w.target_system ORDER BY w.target_system
    """)).mappings().all()
    return [dict(r) for r in rows]
