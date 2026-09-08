# edlo/models.py
import enum
from datetime import UTC, date, datetime
from uuid import uuid4

from sqlalchemy import (
    Date,
    DateTime,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from edlo.db import Base


def uid() -> str:
    return uuid4().hex


def utcnow() -> datetime:
    return datetime.now(UTC)


class Stage(str, enum.Enum):
    REGISTERED = "registered"
    MIXING = "mixing"
    PLAN_READY = "plan_ready"
    EDITING = "editing"
    REVIEW = "review"
    PUBLISHED = "published"


class Episode(Base):
    __tablename__ = "episodes"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    title: Mapped[str] = mapped_column(String(300))
    recorded_on: Mapped[date] = mapped_column(Date)
    publish_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )


class PostingSlot(Base):
    """
    A calendar date that can hold at most one episode.
    """

    __tablename__ = "posting_slots"
    __table_args__ = (UniqueConstraint("slot_date", name="uq_posting_slots_slot_date"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    slot_date: Mapped[date] = mapped_column(Date)
    episode_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
