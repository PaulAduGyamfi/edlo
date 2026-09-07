from datetime import date

from edlo.models import Episode


def test_rollback_does_not_persist(session_factory):
    with session_factory() as session:
        session.add(
            Episode(
                title="Fixture",
                recorded_on=date(2026, 3, 1),
                publish_on=date(2026, 3, 15),
                idempotency_key="rollback-123",
            )
        )
        session.rollback()

    with session_factory() as session:
        assert (
            session.query(Episode)
            .filter_by(idempotency_key="rollback-123")
            .one_or_none()
            is None
        )
