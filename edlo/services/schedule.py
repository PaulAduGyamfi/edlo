from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from edlo.models import Episode, PostingSlot, utcnow


class SlotTaken(Exception): ...


class SlotInPast(Exception): ...


@dataclass(frozen=True)
class Countdown:
    publish_on: date
    days_remaining: int
    status: str  # on_track | due_soon | overdue | published


class ScheduleService:
    """
    All scheduling rules. Knows nothing about HTTP.
    """

    def __init__(self, db: Session, today: date | None = None):
        self.db = db
        self.today = today or utcnow().date()

    def assign(self, episode: Episode, slot_date: date) -> PostingSlot:
        if slot_date < self.today:
            raise SlotInPast(f"{slot_date} is in the past")
        slot = PostingSlot(slot_date=slot_date, episode_id=episode.id)
        self.db.add(slot)
        try:
            self.db.flush()
        except IntegrityError as e:
            self.db.rollback()
            raise SlotTaken(f"{slot_date} already has an episode") from e

        episode.publish_on = slot_date
        return slot

    def next_free_slot(self, cadence_days: int = 14, after: date | None = None) -> date:
        candidate = (after or self.today) + timedelta(days=cadence_days)
        taken = {s.slot_date for s in self.db.query(PostingSlot).all()}
        while candidate in taken:
            candidate += timedelta(days=cadence_days)
        return candidate

    def countdown(self, episode: Episode) -> Countdown | None:
        if episode.publish_on is None:
            return None
        if episode.published_at is not None:
            return Countdown(episode.publish_on, 0, "published")
        days = (episode.publish_on - self.today).days
        status = "overdue" if days < 0 else "due_soon" if days <= 3 else "on_track"
        return Countdown(episode.publish_on, days, status)
