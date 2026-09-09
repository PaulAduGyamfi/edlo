# edlo/models.py
import enum
from datetime import UTC, date, datetime
from uuid import uuid4

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    Integer,
    String,
    Text,
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
    stage: Mapped[str] = mapped_column(String(32), default="registered", index=True)


class PostingSlot(Base):
    """
    A calendar date that can hold at most one episode.
    """

    __tablename__ = "posting_slots"
    __table_args__ = (UniqueConstraint("slot_date", name="uq_posting_slots_slot_date"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    slot_date: Mapped[date] = mapped_column(Date)
    episode_id: Mapped[str | None] = mapped_column(String(32), nullable=True)


class StageTransition(Base):
    """
    Append-only history. Never updated, never deleted.
    """

    __tablename__ = "stage_transitions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    episode_id: Mapped[str] = mapped_column(String(32), index=True)
    from_stage: Mapped[str] = mapped_column(String(32))
    to_stage: Mapped[str] = mapped_column(String(32))
    actor_id: Mapped[str] = mapped_column(String(64))
    actor_role: Mapped[str] = mapped_column(String(32))
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    trace_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    happened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )


class PlanStep(Base):
    """The one fixed editing checklist, same every episode."""

    __tablename__ = "plan_steps"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    episode_id: Mapped[str] = mapped_column(String(32), index=True)
    position: Mapped[int] = mapped_column(Integer)
    label: Mapped[str] = mapped_column(String(200))
    done_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class AudioFile(Base):
    __tablename__ = "audio_files"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    episode_id: Mapped[str] = mapped_column(String(32), index=True)
    kind: Mapped[str] = mapped_column(String(16))  # rough | final
    storage_key: Mapped[str] = mapped_column(String(300))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    checksum: Mapped[str] = mapped_column(String(64))
    uploaded_by: Mapped[str] = mapped_column(String(64))
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    first_downloaded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
