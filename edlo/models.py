# edlo/models.py
import enum
from datetime import UTC, date, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    Index,
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
    filename: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )  # as uploaded
    status: Mapped[str] = mapped_column(
        String(16), default="pending"
    )  # pending | ready
    size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    checksum: Mapped[str | None] = mapped_column(String(64), nullable=True)
    uploaded_by: Mapped[str] = mapped_column(String(64))
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    first_downloaded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class Transcript(Base):
    """Pointer to the transcript artifact in object storage. Rows stay small."""

    __tablename__ = "transcripts"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    audio_file_id: Mapped[str] = mapped_column(String(32), index=True)
    episode_id: Mapped[str] = mapped_column(String(32), index=True)
    storage_key: Mapped[str] = mapped_column(String(300))
    engine: Mapped[str] = mapped_column(String(64))
    model_version: Mapped[str] = mapped_column(String(64))
    language: Mapped[str] = mapped_column(String(16))
    duration_ms: Mapped[int] = mapped_column(Integer)
    segment_count: Mapped[int] = mapped_column(Integer)
    audio_checksum: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )


class Job(Base):
    """
    A unit of background work. The row is the durable record; the queue
    message is only the wake-up. Idempotency is enforced by the DATABASE
    (kind + idempotency_key), not by application logic that can race.
    """

    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    kind: Mapped[str] = mapped_column(String(64))
    episode_id: Mapped[str] = mapped_column(String(32), index=True)
    status: Mapped[str] = mapped_column(String(32), default="queued", index=True)
    # queued | running | succeeded | failed | dead
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    trace_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_class: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    # What the worker is doing right now, for the person waiting on it.
    progress: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(128))
    attempt: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    # A worker owns the job until this passes; a dead worker's job becomes claimable.
    lease_owner: Mapped[str | None] = mapped_column(String(64), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        UniqueConstraint(
            "kind", "idempotency_key", name="uq_jobs_kind_idempotency_key"
        ),
        Index("ix_jobs_status_created", "status", "created_at"),
    )


class IdempotencyRecord(Base):
    """
    Stored responses for job-creating requests. A table, not a dict: with two
    API tasks behind a load balancer a retry lands on the other process.
    """

    __tablename__ = "idempotency_records"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    route: Mapped[str] = mapped_column(String(200), primary_key=True)
    request_fingerprint: Mapped[str] = mapped_column(String(64))
    response_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )


class Flag(Base):
    """
    A moment a human marked. Never subject to grounding, never dropped by a
    model rule (ADR-004): a person heard it, and there may be no transcript
    text at all -- a mic pop, a laugh, a dog.
    """

    __tablename__ = "flags"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    episode_id: Mapped[str] = mapped_column(String(32), index=True)
    start_ms: Mapped[int] = mapped_column(Integer)
    end_ms: Mapped[int] = mapped_column(Integer)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )


class Plan(Base):
    """One generation of cuts and cold opens. Regenerating replaces it."""

    __tablename__ = "plans"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    episode_id: Mapped[str] = mapped_column(String(32), index=True)
    status: Mapped[str] = mapped_column(
        String(32), default="ready"
    )  # ready | ai_disabled
    prompt_version: Mapped[str] = mapped_column(String(64))
    model: Mapped[str] = mapped_column(String(128), default="")
    windows: Mapped[int] = mapped_column(Integer, default=0)
    proposed: Mapped[int] = mapped_column(
        Integer, default=0
    )  # model candidates before validation
    rejections: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict
    )  # rule -> count
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )


class CutItem(Base):
    __tablename__ = "cut_items"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    plan_id: Mapped[str] = mapped_column(String(32), index=True)
    episode_id: Mapped[str] = mapped_column(String(32), index=True)
    source: Mapped[str] = mapped_column(String(16))  # human | model
    flag_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    position: Mapped[int] = mapped_column(Integer)
    start_ms: Mapped[int] = mapped_column(Integer)
    end_ms: Mapped[int] = mapped_column(Integer)
    quote: Mapped[str] = mapped_column(Text, default="")
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    decision: Mapped[str] = mapped_column(
        String(16), default="pending"
    )  # pending | accepted | rejected
    # Chris can edit the span without losing what was proposed.
    edited_start_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    edited_end_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)


class ColdOpen(Base):
    __tablename__ = "cold_opens"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    plan_id: Mapped[str] = mapped_column(String(32), index=True)
    episode_id: Mapped[str] = mapped_column(String(32), index=True)
    position: Mapped[int] = mapped_column(Integer)
    start_ms: Mapped[int] = mapped_column(Integer)
    end_ms: Mapped[int] = mapped_column(Integer)
    quote: Mapped[str] = mapped_column(Text)
    why: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    picked: Mapped[bool] = mapped_column(Boolean, default=False)


class PublishingPack(Base):
    """The model's draft copy, with the policy check's findings stored beside it."""

    __tablename__ = "publishing_packs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    episode_id: Mapped[str] = mapped_column(String(32), index=True)
    status: Mapped[str] = mapped_column(
        String(32), default="ready"
    )  # ready | ai_disabled
    prompt_version: Mapped[str] = mapped_column(String(64))
    model: Mapped[str] = mapped_column(String(128), default="")
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(Text, default="")
    chapters: Mapped[list[Any]] = mapped_column(
        JSON, default=list
    )  # [{start_ms, title}]
    links: Mapped[list[Any]] = mapped_column(JSON, default=list)
    sponsors: Mapped[list[Any]] = mapped_column(JSON, default=list)
    violations: Mapped[list[Any]] = mapped_column(
        JSON, default=list
    )  # [{rule, detail}]
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
