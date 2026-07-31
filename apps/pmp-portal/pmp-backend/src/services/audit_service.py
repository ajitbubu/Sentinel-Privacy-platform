"""Append-only audit logging. audit_log blocks UPDATE/DELETE by DB rule."""
import json

from sqlalchemy import text
from sqlalchemy.orm import Session


def log_audit(db: Session, *, entity_type: str, entity_id: str, action: str,
              actor_id: str | None = None, actor_type: str = "user",
              actor_ip: str | None = None, old_values: dict | None = None,
              new_values: dict | None = None, reason: str | None = None,
              legal_basis: str | None = None) -> None:
    changed = sorted(set((old_values or {}) | (new_values or {}))) if (old_values or new_values) else []
    db.execute(
        text("""
            INSERT INTO audit_log (entity_type, entity_id, action, actor_type, actor_id,
                                   actor_ip_address, old_values, new_values, changed_fields,
                                   reason, legal_basis)
            VALUES (:etype, :eid, :action, :atype, :aid, CAST(:aip AS INET),
                    CAST(:old AS JSONB), CAST(:new AS JSONB), :changed, :reason, :basis)
        """),
        {"etype": entity_type, "eid": entity_id, "action": action, "atype": actor_type,
         "aid": actor_id, "aip": actor_ip,
         "old": json.dumps(old_values or {}, default=str),
         "new": json.dumps(new_values or {}, default=str),
         "changed": changed, "reason": reason, "basis": legal_basis},
    )
    db.commit()
