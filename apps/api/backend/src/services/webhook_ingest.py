"""Process inbound vendor webhooks into canonical consent writes."""
import logging

from sqlalchemy.orm import Session

from src.integrations import get_connector
from src.services import consent_sync, identity_service
from src.services.identity_service import IdentityError

log = logging.getLogger(__name__)


class WebhookError(Exception):
    pass


def process(db: Session, system: str, payload: dict, raw_body: bytes,
            headers: dict[str, str], secret: str) -> dict:
    connector = get_connector(system)
    if connector is None:
        raise WebhookError(f"No connector registered for '{system}'")

    if not connector.verify(raw_body, headers, secret):
        raise WebhookError("Signature verification failed")

    signals = connector.parse_inbound(payload)
    if not signals:
        # Not an error: vendors send many events we don't care about.
        return {"accepted": 0, "ignored": 1, "reason": "no consent fields in payload"}

    applied, skipped, errors = 0, 0, []
    for signal in signals:
        try:
            subject_id = identity_service.resolve_or_create(
                db, signal.email, source_system=signal.source_system,
                external_id=signal.external_id,
            )
            result = consent_sync.apply(db, subject_id=subject_id, signal=signal)
            if result["applied"]:
                applied += 1
            else:
                skipped += 1
        except IdentityError as e:
            errors.append({"email": signal.email, "error": str(e)})
        except Exception as e:  # noqa: BLE001 - one bad signal must not drop the batch
            log.exception("signal processing failed")
            errors.append({"email": signal.email, "error": str(e)})

    return {"accepted": applied, "skipped": skipped, "errors": errors,
            "signals": len(signals)}
