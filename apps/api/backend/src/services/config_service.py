"""Banner config generation, per language.

Output is what the loader script fetches. It is public — no secrets, nothing
visitor-specific — so it can sit on a CDN. Generated on publish rather than
per request: a static object is cheap, fast, and keeps customers' banners
working even if this API is down, which matters when our script sits on their
critical rendering path.
"""
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.services import site_service


def build(db: Session, site: dict, language: str) -> dict:
    banner = None
    if site.get("banner_id"):
        banner = db.execute(
            text("""
                SELECT b.id, b.slug, b.position, b.background_color, b.text_color,
                       b.button_color, b.title, b.message,
                       b.button_accept_text, b.button_reject_text, b.button_customize_text,
                       b.current_version, bv.id AS banner_version_id
                FROM banners b
                LEFT JOIN banner_versions bv
                       ON bv.banner_id = b.id AND bv.is_current = TRUE
                WHERE b.id = :bid AND b.status = 'published' AND b.is_active = TRUE
            """),
            {"bid": str(site["banner_id"])},
        ).mappings().first()

    translation = None
    reviewed = None
    if banner:
        row = db.execute(
            text("""
                SELECT title, message, button_accept_text, button_reject_text,
                       button_customize_text, withdraw_text,
                       is_machine_translated, reviewed_at
                FROM banner_translations
                WHERE banner_id = :bid AND language_code = :lang
            """),
            {"bid": str(banner["id"]), "lang": language},
        ).mappings().first()
        if row:
            translation = dict(row)
            reviewed = translation["reviewed_at"] is not None

    lang_meta = db.execute(
        text("SELECT code, name_english, name_native, is_rtl FROM languages WHERE code = :c"),
        {"c": language},
    ).mappings().first()

    languages = db.execute(
        text("""SELECT code, name_native, is_rtl FROM languages
                WHERE code = ANY(:codes) ORDER BY code"""),
        {"codes": site.get("available_languages") or ["en"]},
    ).mappings().all()

    purposes = db.execute(
        text("""SELECT slug, name, description, is_mandatory
                FROM purposes ORDER BY is_mandatory DESC, name""")
    ).mappings().all()

    def pick(field: str, fallback_field: str | None = None):
        if translation and translation.get(field):
            return translation[field]
        if banner:
            return banner.get(fallback_field or field)
        return None

    return {
        "site": {
            "key": site["publishable_key"],
            "slug": site["slug"],
            "auto_block": site["auto_block"],
        },
        # DPDP s.6(3), s.8(9), R.9 — the notice must name the Data Fiduciary
        # and the person who answers queries. Shipped in the config so the
        # loader can render them without a second call.
        "data_fiduciary": {
            "name": site["data_fiduciary_name"],
            "address": site.get("data_fiduciary_address"),
            "grievance_officer": site.get("grievance_officer_name"),
            "grievance_email": site.get("grievance_officer_email"),
            "grievance_phone": site.get("grievance_officer_phone"),
        },
        "language": {
            "code": language,
            "native_name": lang_meta["name_native"] if lang_meta else language,
            "rtl": bool(lang_meta["is_rtl"]) if lang_meta else False,
            # The loader surfaces this so a visitor can switch; the choice is
            # then recorded with their consent.
            "available": [
                {"code": r["code"], "name": r["name_native"], "rtl": r["is_rtl"]}
                for r in languages
            ],
            # Honest about provenance. A machine translation of a legal notice
            # is not equivalent to a reviewed one and should not silently
            # present itself as such.
            "translation_reviewed": reviewed,
            "machine_translated": bool(translation and translation["is_machine_translated"]),
        },
        "notice": {
            "title": pick("title"),
            "message": pick("message"),
            "accept": pick("button_accept_text") or "Accept all",
            "reject": pick("button_reject_text") or "Reject all",
            "customise": pick("button_customize_text") or "Manage preferences",
            "withdraw": (translation or {}).get("withdraw_text") or "Privacy settings",
        },
        "appearance": {
            "position": banner["position"] if banner else "bottom",
            "background": banner["background_color"] if banner else "#ffffff",
            "text": banner["text_color"] if banner else "#333333",
            "button": banner["button_color"] if banner else "#2f62d8",
        } if banner else None,
        "purposes": [
            {"slug": p["slug"], "name": p["name"], "description": p["description"],
             "required": p["is_mandatory"]}
            for p in purposes
        ],
        # Recorded against every consent captured under this config.
        "banner_version_id": str(banner["banner_version_id"]) if banner and banner["banner_version_id"] else None,
        "banner_version": banner["current_version"] if banner else None,
        "published": banner is not None,
    }
