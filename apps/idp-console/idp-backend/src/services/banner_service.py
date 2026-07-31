"""Banner authoring, versioning and publication.

Every save snapshots the full banner into banner_versions. That snapshot is what
proof-of-consent records point at: to demonstrate valid consent you must show the
exact wording and purposes presented, not merely that a click occurred.

`materially_changed` is set by the author, not inferred from a diff. A colour
tweak must not force 40 million people to re-consent; adding a purpose must.
"""
import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.services import event_publisher
from src.services.audit_service import log_audit

SNAPSHOT_FIELDS = [
    "name", "slug", "description", "title", "message",
    "button_accept_text", "button_reject_text", "button_customize_text",
    "position", "background_color", "text_color", "button_color",
    "purposes", "channels", "target_countries", "target_languages", "type",
]


class BannerError(Exception):
    pass


def _snapshot(banner: dict) -> dict:
    return {k: banner.get(k) for k in SNAPSHOT_FIELDS}


def list_banners(db: Session, status: str | None = None) -> list[dict]:
    rows = db.execute(
        text("""
            SELECT b.id, b.name, b.slug, b.type, b.status, b.current_version,
                   b.published_at, b.created_at, b.updated_at, b.is_active,
                   u.email AS created_by
            FROM banners b
            LEFT JOIN users u ON u.id = b.created_by_user_id
            WHERE (:status IS NULL OR b.status = :status)
            ORDER BY b.updated_at DESC
        """),
        {"status": status},
    ).mappings().all()
    return [dict(r) for r in rows]


def get(db: Session, banner_id: str) -> dict | None:
    row = db.execute(
        text("SELECT * FROM banners WHERE id = :bid"), {"bid": banner_id}
    ).mappings().first()
    return dict(row) if row else None


def create(db: Session, data: dict, user_id: str) -> dict:
    existing = db.execute(
        text("SELECT id FROM banners WHERE slug = :slug"), {"slug": data["slug"]}
    ).scalar()
    if existing:
        raise BannerError(f"A banner with slug '{data['slug']}' already exists")

    row = db.execute(
        text("""
            INSERT INTO banners (name, slug, description, type, title, message,
                                 button_accept_text, button_reject_text, button_customize_text,
                                 position, background_color, text_color, button_color,
                                 purposes, channels, target_countries, target_languages,
                                 status, current_version, created_by_user_id)
            VALUES (:name, :slug, :description, :type, :title, :message,
                    :accept, :reject, :customize,
                    :position, :bg, :fg, :btn,
                    CAST(:purposes AS UUID[]), CAST(:channels AS UUID[]),
                    :countries, :languages,
                    'draft', 1, :uid)
            RETURNING id, name, slug, status, current_version, created_at
        """),
        {
            "name": data["name"], "slug": data["slug"],
            "description": data.get("description"), "type": data.get("type", "consent"),
            "title": data.get("title"), "message": data.get("message"),
            "accept": data.get("button_accept_text", "Accept all"),
            "reject": data.get("button_reject_text", "Reject all"),
            "customize": data.get("button_customize_text", "Customise"),
            "position": data.get("position", "bottom"),
            "bg": data.get("background_color", "#ffffff"),
            "fg": data.get("text_color", "#333333"),
            "btn": data.get("button_color", "#2f62d8"),
            "purposes": data.get("purposes", []), "channels": data.get("channels", []),
            "countries": data.get("target_countries", []),
            "languages": data.get("target_languages", []),
            "uid": user_id,
        },
    ).mappings().first()
    db.commit()

    banner_id = str(row["id"])
    _write_version(db, banner_id, 1, {**data, "type": data.get("type", "consent")},
                   user_id, "Initial version", materially_changed=True)
    log_audit(db, entity_type="banner", entity_id=banner_id, action="create",
              actor_id=user_id, new_values={"name": data["name"], "slug": data["slug"]})
    return dict(row)


def update(db: Session, banner_id: str, data: dict, user_id: str,
           materially_changed: bool = False, change_note: str | None = None) -> dict:
    current = get(db, banner_id)
    if current is None:
        raise BannerError("Banner not found")
    if current["status"] == "archived":
        raise BannerError("Archived banners cannot be edited")

    merged = {**current, **{k: v for k, v in data.items() if v is not None}}
    next_version = (current["current_version"] or 1) + 1

    db.execute(
        text("""
            UPDATE banners SET
              name = :name, description = :description, title = :title, message = :message,
              button_accept_text = :accept, button_reject_text = :reject,
              button_customize_text = :customize, position = :position,
              background_color = :bg, text_color = :fg, button_color = :btn,
              purposes = CAST(:purposes AS UUID[]), channels = CAST(:channels AS UUID[]),
              target_countries = :countries, target_languages = :languages,
              current_version = :version, updated_by_user_id = :uid, updated_at = NOW()
            WHERE id = :bid
        """),
        {
            "bid": banner_id, "name": merged["name"], "description": merged.get("description"),
            "title": merged.get("title"), "message": merged.get("message"),
            "accept": merged.get("button_accept_text"), "reject": merged.get("button_reject_text"),
            "customize": merged.get("button_customize_text"), "position": merged.get("position"),
            "bg": merged.get("background_color"), "fg": merged.get("text_color"),
            "btn": merged.get("button_color"),
            "purposes": merged.get("purposes") or [], "channels": merged.get("channels") or [],
            "countries": merged.get("target_countries") or [],
            "languages": merged.get("target_languages") or [],
            "version": next_version, "uid": user_id,
        },
    )
    db.commit()

    _write_version(db, banner_id, next_version, merged, user_id, change_note, materially_changed)
    log_audit(db, entity_type="banner", entity_id=banner_id, action="update",
              actor_id=user_id, old_values=_snapshot(current), new_values=_snapshot(merged),
              reason=change_note)
    return {"id": banner_id, "version": next_version, "materially_changed": materially_changed}


def _write_version(db: Session, banner_id: str, version: int, data: dict,
                   user_id: str, note: str | None, materially_changed: bool) -> None:
    db.execute(text("UPDATE banner_versions SET is_current = FALSE WHERE banner_id = :bid"),
               {"bid": banner_id})
    db.execute(
        text("""
            INSERT INTO banner_versions (banner_id, version, snapshot, change_description,
                                         changed_by_user_id, is_current, materially_changed)
            VALUES (:bid, :ver, CAST(:snap AS JSONB), :note, :uid, TRUE, :material)
        """),
        {"bid": banner_id, "ver": version, "snap": json.dumps(_snapshot(data), default=str),
         "note": note, "uid": user_id, "material": materially_changed},
    )
    db.commit()


def versions(db: Session, banner_id: str) -> list[dict]:
    rows = db.execute(
        text("""
            SELECT v.id, v.version, v.change_description, v.created_at, v.is_current,
                   v.materially_changed, u.email AS changed_by
            FROM banner_versions v
            LEFT JOIN users u ON u.id = v.changed_by_user_id
            WHERE v.banner_id = :bid
            ORDER BY v.version DESC
        """),
        {"bid": banner_id},
    ).mappings().all()
    return [dict(r) for r in rows]


def publish(db: Session, banner_id: str, user_id: str) -> dict:
    """Publish and fan out. The DB write is synchronous and authoritative;
    edge/CDN propagation is eventually consistent (~30s) by design."""
    banner = get(db, banner_id)
    if banner is None:
        raise BannerError("Banner not found")
    if not banner.get("purposes"):
        raise BannerError("Add at least one purpose before publishing")

    db.execute(
        text("""
            UPDATE banners SET status = 'published', is_active = TRUE,
                               published_at = NOW(), updated_at = NOW()
            WHERE id = :bid
        """),
        {"bid": banner_id},
    )
    # Only one banner of a given type may be live at a time.
    db.execute(
        text("""
            UPDATE banners SET is_active = FALSE, status = 'archived', archived_at = NOW()
            WHERE id != :bid AND type = :type AND status = 'published'
        """),
        {"bid": banner_id, "type": banner.get("type", "consent")},
    )
    db.commit()

    version = banner["current_version"]
    log_audit(db, entity_type="banner", entity_id=banner_id, action="publish",
              actor_id=user_id, new_values={"version": version, "status": "published"})

    event_id = event_publisher.publish("banner.published", {
        "banner_id": banner_id, "slug": banner["slug"], "type": banner.get("type", "consent"),
        "version": version, "name": banner["name"],
    })

    return {
        "id": banner_id, "status": "published", "version": version,
        "event_id": event_id,
        "propagation": {
            "platform": "<1s", "integrated_systems": "<1s via webhook queue",
            "end_user_browsers": "~30s via CDN",
        },
    }


def rollback(db: Session, banner_id: str, target_version: int, user_id: str) -> dict:
    snapshot = db.execute(
        text("SELECT snapshot FROM banner_versions WHERE banner_id = :bid AND version = :ver"),
        {"bid": banner_id, "ver": target_version},
    ).scalar()
    if snapshot is None:
        raise BannerError(f"Version {target_version} not found")

    data = snapshot if isinstance(snapshot, dict) else json.loads(snapshot)
    result = update(db, banner_id, data, user_id, materially_changed=True,
                    change_note=f"Rolled back to version {target_version}")
    log_audit(db, entity_type="banner", entity_id=banner_id, action="rollback",
              actor_id=user_id, new_values={"target_version": target_version})
    return result
