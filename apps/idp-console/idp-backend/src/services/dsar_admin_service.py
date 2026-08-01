"""DSAR fulfilment: gather a subject's data and render it in all three formats."""
import csv
import io
import json
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.services.audit_service import log_audit

VALID_FORMATS = {"json", "csv", "pdf"}


class DSARAdminError(Exception):
    pass


def queue(db: Session, status: str | None = None, limit: int = 50) -> list[dict]:
    """Pending requests, most urgent first — overdue work should be impossible to miss."""
    rows = db.execute(
        text("""
            SELECT d.id, d.request_type, d.status, d.description, d.submitted_at,
                   d.due_date, d.fulfilled_at, d.denial_reason,
                   s.email AS subject_email, s.id AS subject_id,
                   GREATEST(0, EXTRACT(DAY FROM d.due_date - NOW())::int) AS days_remaining,
                   (d.due_date < NOW() AND d.status NOT IN
                     ('fulfilled','denied','cancelled')) AS is_overdue
            FROM dsar_requests d
            JOIN subjects s ON s.id = d.subject_id
            WHERE (:status IS NULL OR d.status = :status)
            ORDER BY
              (d.status IN ('fulfilled','denied','cancelled')) ASC,
              d.due_date ASC
            LIMIT :limit
        """),
        {"status": status, "limit": limit},
    ).mappings().all()
    return [dict(r) for r in rows]


def collect_subject_data(db: Session, subject_id: str) -> dict:
    """Everything held about a subject. This IS the Art. 15 response."""
    subject = db.execute(
        text("""SELECT id, email, first_name, last_name, country_code, language,
                       status, created_at, last_activity
                FROM subjects WHERE id = CAST(:sid AS UUID)"""),
        {"sid": subject_id},
    ).mappings().first()
    if subject is None:
        raise DSARAdminError("Subject not found")

    consents = db.execute(
        text("""
            SELECT c.id, p.name AS purpose, ch.name AS channel, c.status, c.legal_basis,
                   c.created_at, c.granted_at, c.withdrawn_at, c.expires_at, c.source_system,
                   c.language_version, c.capture_mode, c.witness_name,
                   bv.version AS notice_version, bv.created_at AS notice_published_at
            FROM consents c
            JOIN purposes p ON c.purpose_id = p.id
            JOIN channels ch ON c.channel_id = ch.id
            LEFT JOIN banner_versions bv ON bv.id = c.banner_version_id
            WHERE c.subject_id = CAST(:sid AS UUID) AND c.deleted_at IS NULL
            ORDER BY c.created_at DESC
        """),
        {"sid": subject_id},
    ).mappings().all()

    audit = db.execute(
        text("""
            SELECT a.created_at, a.action, a.entity_type, a.actor_type, a.reason
            FROM audit_log a
            -- :sid arrives as text; every comparison here is against a UUID
            -- column, so it must be cast. Postgres will not coerce uuid = text.
            WHERE a.entity_id IN (
                SELECT id FROM consents      WHERE subject_id = CAST(:sid AS UUID)
                UNION SELECT id FROM dsar_requests WHERE subject_id = CAST(:sid AS UUID)
                UNION SELECT CAST(:sid AS UUID)
            )
            ORDER BY a.created_at DESC LIMIT 1000
        """),
        {"sid": subject_id},
    ).mappings().all()

    requests = db.execute(
        text("""SELECT id, request_type, status, submitted_at, due_date, fulfilled_at
                FROM dsar_requests WHERE subject_id = CAST(:sid AS UUID) ORDER BY submitted_at DESC"""),
        {"sid": subject_id},
    ).mappings().all()

    return {
        "export_generated_at": datetime.now(timezone.utc).isoformat(),
        "subject": dict(subject),
        "consents": [dict(r) for r in consents],
        "audit_trail": [dict(r) for r in audit],
        "data_requests": [dict(r) for r in requests],
        "notes": (
            "This export contains all personal data held about you. Records proving "
            "consent withdrawal are retained where required by law even after deletion; "
            "these are listed in the audit trail. Each consent below shows the version "
            "of the notice you were shown and the language it was served in, so you can "
            "see exactly what you agreed to."
        ),
    }


def _display(value) -> str:
    """Render a value for a human-facing legal document.

    Python's `None` must never appear in a GDPR response — "None" reads as a
    value rather than an absence and invites a follow-up question we then have
    to answer within the statutory window.
    """
    if value is None or value == "":
        return "—"
    return str(value)


def render_json(data: dict) -> bytes:
    return json.dumps(data, indent=2, default=str).encode()


def render_csv(data: dict) -> bytes:
    """Flat CSV with a section column — one file, readable in any spreadsheet."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["section", "field", "value"])
    for key, value in data["subject"].items():
        writer.writerow(["subject", key, value])
    for i, consent in enumerate(data["consents"]):
        for key, value in consent.items():
            writer.writerow([f"consent[{i}]", key, value])
    for i, entry in enumerate(data["audit_trail"]):
        for key, value in entry.items():
            writer.writerow([f"audit[{i}]", key, value])
    for i, req in enumerate(data["data_requests"]):
        for key, value in req.items():
            writer.writerow([f"request[{i}]", key, value])
    return buf.getvalue().encode()


def render_pdf(data: dict) -> bytes:
    """Human-readable PDF. reportlab is the only hard dependency here."""
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import (PageBreak, Paragraph, SimpleDocTemplate,
                                        Spacer, Table, TableStyle)
    except ImportError:
        raise DSARAdminError("PDF export requires reportlab (pip install reportlab)")

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=20 * mm, bottomMargin=18 * mm)
    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=styles["Heading1"], fontSize=18,
                        textColor=colors.HexColor("#2f62d8"), spaceAfter=6)
    body = ParagraphStyle("body", parent=styles["Normal"], fontSize=9.5, leading=14)
    story = []

    story.append(Paragraph("Personal Data Export", h1))
    generated = str(data["export_generated_at"])[:19].replace("T", " ") + " UTC"
    story.append(Paragraph(
        f"Generated {generated} · Subject: {data['subject'].get('email', '')}", body))
    story.append(Spacer(1, 8))
    story.append(Paragraph(data["notes"], body))
    story.append(Spacer(1, 14))

    def table(title: str, rows: list[list], widths: list[float]) -> None:
        story.append(Paragraph(title, styles["Heading2"]))
        t = Table(rows, colWidths=widths, repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2f62d8")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#d4d4d8")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#fafafa")]),
        ]))
        story.append(t)
        story.append(Spacer(1, 14))

    table("Your details",
          [["Field", "Value"]]
          + [[k.replace("_", " ").capitalize(), _display(v)]
             for k, v in data["subject"].items()],
          [55 * mm, 110 * mm])

    if data["consents"]:
        rows = [["Purpose", "Channel", "Status", "Notice", "Lang", "Mode", "Updated"]]
        for c in data["consents"]:
            rows.append([c["purpose"], c["channel"], c["status"].capitalize(),
                         _display(c.get("notice_version") and f"v{c['notice_version']}"),
                         _display(c.get("language_version")),
                         _display((c.get("capture_mode") or "").replace("_", " ")),
                         _display(str(c.get("granted_at") or c.get("withdrawn_at") or "")[:19])])
        table("Your consents", rows,
              [30 * mm, 22 * mm, 22 * mm, 16 * mm, 16 * mm, 30 * mm, 29 * mm])

    if data["audit_trail"]:
        story.append(PageBreak())
        rows = [["When", "Action", "Type", "Actor"]]
        for a in data["audit_trail"][:250]:
            rows.append([str(a["created_at"])[:19], a["action"].capitalize(),
                         a["entity_type"].capitalize(), a["actor_type"].capitalize()])
        table("Change history", rows, [42 * mm, 42 * mm, 38 * mm, 43 * mm])

    doc.build(story)
    return buf.getvalue()


RENDERERS = {"json": render_json, "csv": render_csv, "pdf": render_pdf}


def fulfil(db: Session, dsar_id: str, user_id: str, fmt: str = "json") -> tuple[bytes, str, str]:
    if fmt not in VALID_FORMATS:
        raise DSARAdminError(f"format must be one of {sorted(VALID_FORMATS)}")

    row = db.execute(
        text("SELECT subject_id, request_type, status FROM dsar_requests WHERE id = CAST(:did AS UUID)"),
        {"did": dsar_id},
    ).mappings().first()
    if row is None:
        raise DSARAdminError("Request not found")
    if row["status"] in ("fulfilled", "denied", "cancelled"):
        raise DSARAdminError(f"Request is already {row['status']}")

    data = collect_subject_data(db, str(row["subject_id"]))
    content = RENDERERS[fmt](data)

    db.execute(
        text("""UPDATE dsar_requests
                SET status = 'fulfilled', fulfilled_at = NOW(),
                    response_method = :fmt, processed_by_user_id = :uid,
                    response_download_expires_at = NOW() + INTERVAL '7 days'
                WHERE id = CAST(:did AS UUID)"""),
        {"did": dsar_id, "fmt": fmt, "uid": user_id},
    )
    db.commit()

    log_audit(db, entity_type="dsar", entity_id=dsar_id, action="fulfil",
              actor_id=user_id, new_values={"format": fmt, "records": len(data["consents"])})

    media = {"json": "application/json", "csv": "text/csv", "pdf": "application/pdf"}[fmt]
    return content, media, f"data-export-{dsar_id[:8]}.{fmt}"


def deny(db: Session, dsar_id: str, user_id: str, reason: str) -> dict:
    updated = db.execute(
        text("""UPDATE dsar_requests
                SET status = 'denied', denial_reason = :reason, processed_by_user_id = :uid
                WHERE id = CAST(:did AS UUID) AND status NOT IN ('fulfilled','denied','cancelled')
                RETURNING id"""),
        {"did": dsar_id, "reason": reason, "uid": user_id},
    ).scalar()
    if not updated:
        raise DSARAdminError("Request not found or already closed")
    db.commit()
    log_audit(db, entity_type="dsar", entity_id=dsar_id, action="deny",
              actor_id=user_id, reason=reason)
    return {"id": dsar_id, "status": "denied", "reason": reason}
