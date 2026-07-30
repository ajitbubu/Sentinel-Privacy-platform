"""DSAR submission and tracking (user side)."""
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.services.event_publisher import publish_event


class DSARService:
    def __init__(self, db: Session):
        self.db = db

    def submit(self, subject_id: str, request_type: str,
               description: str | None, created_by_system: str) -> dict:
        row = self.db.execute(
            text("""
                INSERT INTO dsar_requests (subject_id, request_type, description,
                                           status, due_date, created_by_system)
                VALUES (:sid, :rtype, :descr, 'submitted', NOW() + INTERVAL '30 days', :sys)
                RETURNING id, status, submitted_at, due_date, request_type
            """),
            {"sid": subject_id, "rtype": request_type, "descr": description,
             "sys": created_by_system},
        ).mappings().first()
        self.db.commit()
        publish_event("dsar:created", {
            "dsar_id": str(row["id"]), "subject_id": subject_id,
            "request_type": request_type,
        })
        return dict(row)

    def get_for_subject(self, dsar_id: UUID, subject_id: str) -> dict | None:
        row = self.db.execute(
            text("""
                SELECT id, request_type, status, submitted_at, due_date, fulfilled_at
                FROM dsar_requests
                WHERE id = :did AND subject_id = :sid
            """),
            {"did": str(dsar_id), "sid": subject_id},
        ).mappings().first()
        return dict(row) if row else None

    def list_for_subject(self, subject_id: str) -> list[dict]:
        rows = self.db.execute(
            text("""
                SELECT id, request_type, status, submitted_at, due_date, fulfilled_at
                FROM dsar_requests WHERE subject_id = :sid
                ORDER BY submitted_at DESC
            """),
            {"sid": subject_id},
        ).mappings().all()
        return [dict(r) for r in rows]
