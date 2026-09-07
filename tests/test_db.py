from datetime import date
from edlo.db import get_sessionmaker
from edlo.models import Episode

def test_rollback_does_not_persist():
    sessionmaker = get_sessionmaker()
    with sessionmaker() as session:
        session.add(Episode(
            title="Fixture",
            recorded_on=date.today(),
            publish_on=date.today(),
            idempotency_key="rollback-123",
        ))
        session.rollback()

    with sessionmaker() as session:
        assert session.query(Episode).filter_by(
            idempotency_key="rollback-123"
        ).one_or_none() is None