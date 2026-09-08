from datetime import date

import pytest

from edlo.models import Episode
from edlo.services.schedule import ScheduleService, SlotInPast, SlotTaken

TODAY = date(2026, 3, 1)


def test_two_episodes_cannot_share_a_date(db):
    svc = ScheduleService(db, today=TODAY)
    a, b = Episode(title="A", recorded_on=TODAY), Episode(title="B", recorded_on=TODAY)
    db.add_all([a, b])
    db.flush()
    svc.assign(a, date(2026, 3, 15))
    with pytest.raises(SlotTaken):
        svc.assign(b, date(2026, 3, 15))


def test_past_dates_rejected(db):
    svc = ScheduleService(db, today=TODAY)
    ep = Episode(title="A", recorded_on=TODAY)
    db.add(ep)
    db.flush()
    with pytest.raises(SlotInPast):
        svc.assign(ep, date(2026, 2, 1))


def test_countdown_states(db):
    svc = ScheduleService(db, today=TODAY)
    ep = Episode(title="A", recorded_on=TODAY)
    db.add(ep)
    db.flush()
    svc.assign(ep, date(2026, 3, 20))
    assert svc.countdown(ep).status == "on_track"
    ep.publish_on = date(2026, 3, 3)
    assert svc.countdown(ep).status == "due_soon"
    ep.publish_on = date(2026, 2, 25)
    assert svc.countdown(ep).status == "overdue"


def test_next_free_slot_skips_taken_dates(db):
    svc = ScheduleService(db, today=TODAY)
    ep = Episode(title="A", recorded_on=TODAY)
    db.add(ep)
    db.flush()
    first = svc.next_free_slot(after=TODAY)
    svc.assign(ep, first)
    assert svc.next_free_slot(after=TODAY) != first
