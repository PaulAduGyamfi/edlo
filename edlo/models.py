# edlo/models.py
import enum
import uuid
from datetime import UTC, date, datetime

from sqlalchemy import (
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from edlo.db import Base


def uid() -> str:
    return str(uuid.uuid4())


def now() -> datetime:
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

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    title: Mapped[str] = mapped_column(String(140))
    recorded_on: Mapped[date] = mapped_column(Date)
    publish_on: Mapped[date] = mapped_column(Date, index=True)
    stage: Mapped[Stage] = mapped_column(Enum(Stage), default=Stage.REGISTERED)
    idempotency_key: Mapped[str] = mapped_column(String(100), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

    stage_transitions: Mapped[list["StageTransition"]] = relationship(
        back_populates="episode", cascade="all, delete-orphan"
    )
    audio_files: Mapped[list["AudioFile"]] = relationship(
        back_populates="episode", cascade="all, delete-orphan"
    )
    plan_steps: Mapped[list["PlanStep"]] = relationship(
        back_populates="episode",
        cascade="all, delete-orphan",
        order_by="PlanStep.position",
    )


class StageTransition(Base):
    __tablename__ = "stage_transitions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    episode_id: Mapped[str] = mapped_column(ForeignKey("episodes.id"), index=True)
    from_stage: Mapped[Stage] = mapped_column(Enum(Stage))
    to_stage: Mapped[Stage] = mapped_column(Enum(Stage))
    actor: Mapped[str] = mapped_column(String(30))
    reason: Mapped[str] = mapped_column(String(240))
    happened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

    episode: Mapped["Episode"] = relationship(back_populates="stage_transitions")


class AudioFile(Base):
    __tablename__ = "audio_files"
    __table_args__ = (UniqueConstraint("episode_id", "kind", "checksum"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    episode_id: Mapped[str] = mapped_column(ForeignKey("episodes.id"), index=True)
    kind: Mapped[str] = mapped_column(String(10))
    original_name: Mapped[str] = mapped_column(String(255))
    storage_key: Mapped[str] = mapped_column(String(255), unique=True)
    checksum: Mapped[str] = mapped_column(String(64), index=True)
    size_bytes: Mapped[int] = mapped_column(Integer)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    first_downloaded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )

    episode: Mapped["Episode"] = relationship(back_populates="audio_files")


class PlanStep(Base):
    __tablename__ = "plan_steps"
    __table_args__ = (UniqueConstraint("episode_id", "position"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    episode_id: Mapped[str] = mapped_column(ForeignKey("episodes.id"), index=True)
    position: Mapped[int] = mapped_column(Integer)
    label: Mapped[str] = mapped_column(String(100))
    completed_by: Mapped[str | None] = mapped_column(String(30))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    episode: Mapped["Episode"] = relationship(back_populates="plan_steps")


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        UniqueConstraint(
            "kind", "idempotency_key", name="uq_jobs_kind_idempotency_key"
        ),
        Index("ix_jobs_status_created", "status", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    kind: Mapped[str] = mapped_column(String(64))
    episode_id: Mapped[str] = mapped_column(String(32), index=True)
    status: Mapped[str] = mapped_column(String(32), default="queued", index=True)

    idempotency_key: Mapped[str] = mapped_column(String(128))
    attempt: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)

    lease_owner: Mapped[str | None] = mapped_column(String(64), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    trace_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_class: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
