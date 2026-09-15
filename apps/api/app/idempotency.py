"""
Storage is a DATABASE TABLE, not a dict.

With two API tasks behind a load balancer, a retry lands on a different
process about half the time. An in-memory idempotency cache is worse than
none, because it works in development and fails only under load.
"""

import hashlib
import json
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from edlo.models import IdempotencyRecord

RETENTION = timedelta(hours=24)


def fingerprint(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def lookup(db: Session, key: str, route: str, fp: str) -> dict | None:
    rec = db.get(IdempotencyRecord, (key, route))
    if rec is None:
        return None
    created = rec.created_at.replace(tzinfo=rec.created_at.tzinfo or UTC)
    if created < datetime.now(UTC) - RETENTION:
        db.delete(rec)
        db.flush()
        return None
    if rec.request_fingerprint != fp:
        # Same key, different body: that is a client bug worth surfacing.
        raise ValueError("idempotency key reused with a different request body")
    return json.loads(rec.response_json)


def remember(db: Session, key: str, route: str, fp: str, response: dict) -> None:
    db.add(
        IdempotencyRecord(
            key=key,
            route=route,
            request_fingerprint=fp,
            response_json=json.dumps(response),
            created_at=datetime.now(UTC),
        )
    )
