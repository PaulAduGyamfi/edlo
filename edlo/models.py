# edlo/models.py
import enum
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from edlo.db import Base


def uid() -> str:
    return str(uuid.uuid4())


def now() -> datetime:
    return datetime.now(timezone.utc)


class Stage(str, enum.Enum):
    REGISTERED = "registered"
    MIXING = "mixing"
    PLAN_READY = "plan_ready"
    EDITING = "editing"
    REVIEW = "review"
    PUBLISHED = "published"


class Episode(Base):
    __tablename__ = "episodes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    title: Mapped[str] = mapped_column(String(140))
    recorded_on: Mapped[date] = mapped_column(Date)
    publish_on: Mapped[date] = mapped_column(Date, index=True)
    stage: Mapped[Stage] = mapped_column(Enum(Stage), default=Stage.REGISTERED)
    idempotency_key: Mapped[str] = mapped_column(String(100), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class StageTransition(Base):
    __tablename__ = "stage_transitions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    episode_id: Mapped[str] = mapped_column(ForeignKey("episodes.id"), index=True)
    from_stage: Mapped[Stage] = mapped_column(Enum(Stage))
    to_stage: Mapped[Stage] = mapped_column(Enum(Stage))
    actor: Mapped[str] = mapped_column(String(30))
    reason: Mapped[str] = mapped_column(String(240))
    happened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class AudioFile(Base):
    __tablename__ = "audio_files"
    __table_args__ = (UniqueConstraint("episode_id", "kind", "checksum"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    episode_id: Mapped[str] = mapped_column(ForeignKey("episodes.id"), index=True)
    kind: Mapped[str] = mapped_column(String(10))  # rough or final
    original_name: Mapped[str] = mapped_column(String(255))
    storage_key: Mapped[str] = mapped_column(String(255), unique=True)
    checksum: Mapped[str] = mapped_column(String(64), index=True)
    size_bytes: Mapped[int] = mapped_column(Integer)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    first_downloaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PlanStep(Base):
    __tablename__ = "plan_steps"
    __table_args__ = (UniqueConstraint("episode_id", "position"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    episode_id: Mapped[str] = mapped_column(ForeignKey("episodes.id"), index=True)
    position: Mapped[int] = mapped_column(Integer)
    label: Mapped[str] = mapped_column(String(100))
    completed_by: Mapped[str | None] = mapped_column(String(30))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))