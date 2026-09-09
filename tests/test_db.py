from datetime import date

from edlo.models import Episode


def test_rollback_does_not_persist(db):
    db.add(
        Episode(
            title="Fixture",
            recorded_on=date(2026, 3, 1),
            publish_on=date(2026, 3, 15),
            id="rollback-123",
        )
    )
    db.rollback()

    assert (
        db.query(Episode)
        .filter_by(id="rollback-123")
        .one_or_none()
        is None
    )
