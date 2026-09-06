from datetime import date
from edlo.db import SessionLocal
from edlo.models import Episode

def test_rollback_does_not_persist():
    with SessionLocal() as session:
        session.add(Episode(
            title="Fixture",
            recorded_on=date.today(),
            publish_on=date.today(),
            idempotency_key="rollback-123",
        ))
        session.rollback()

    with SessionLocal() as session:
        assert session.query(Episode).filter_by(
            idempotency_key="rollback-123"
        ).one_or_none() is None