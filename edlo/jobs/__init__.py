"""
Job rows are the durable truth about background work; queue messages are only
wake-ups. Everything here is plain database state, shared by the API (which
creates jobs) and the worker (which claims and finishes them).
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from edlo import db as _db
from edlo.logging import log
from edlo.models import Job

LEASE_SECONDS = 300


class PermanentFailure(Exception):
    """
    Retrying cannot help: corrupt audio, unsupported format, schema violation.
    Ack it and surface to a human rather than burning three attempts and
    polluting the dead-letter queue with noise, so that a DLQ message
    genuinely means "something unexpected happened."
    """


def _claimable(now: datetime):
    return and_(
        Job.attempt < Job.max_attempts,
        or_(
            Job.status.in_(["queued", "failed"]),
            and_(Job.status == "running", Job.lease_expires_at < now),
        ),
    )


def _take(
    db: Session, job: Job, worker_id: str, lease_seconds: int, now: datetime
) -> Job:
    job.status = "running"
    job.lease_owner = worker_id
    job.lease_expires_at = now + timedelta(seconds=lease_seconds)
    job.attempt += 1
    job.started_at = job.started_at or now
    db.commit()
    return job


def claim_job(
    db: Session, job_id: str, worker_id: str, lease_seconds: int = LEASE_SECONDS
) -> Job | None:
    """
    Take a lease on the job a message named. None means it is finished, or
    another worker holds a live lease on it: either way, not ours to run.
    """
    now = datetime.now(UTC)
    job = (
        db.query(Job)
        .filter(Job.id == job_id, _claimable(now))
        .with_for_update(skip_locked=True)
        .one_or_none()
    )
    if job is None:
        db.rollback()
        return None
    return _take(db, job, worker_id, lease_seconds, now)


def claim_next_job(
    db: Session, worker_id: str, lease_seconds: int = LEASE_SECONDS
) -> Job | None:
    """
    The oldest claimable job. FOR UPDATE SKIP LOCKED makes this race-free on
    Postgres with no lock service: N workers each get a different row.
    """
    now = datetime.now(UTC)
    job = (
        db.query(Job)
        .filter(_claimable(now))
        .order_by(Job.created_at)
        .with_for_update(skip_locked=True)
        .first()
    )
    if job is None:
        db.rollback()
        return None
    return _take(db, job, worker_id, lease_seconds, now)


def extend_job_lease(
    db: Session, job_id: str, worker_id: str, seconds: int = LEASE_SECONDS
) -> None:
    job = db.get(Job, job_id)
    if job and job.status == "running" and job.lease_owner == worker_id:
        job.lease_expires_at = datetime.now(UTC) + timedelta(seconds=seconds)
        db.commit()


def mark_succeeded(db: Session, job_id: str) -> None:
    job = db.get(Job, job_id)
    if job is None:
        return
    job.status = "succeeded"
    job.finished_at = datetime.now(UTC)
    job.lease_owner = None
    job.lease_expires_at = None
    job.error_class = None
    job.error_message = None
    db.commit()


def _record_error(job: Job, exc: BaseException) -> None:
    # A PermanentFailure wraps the real cause; that is the class a user
    # message is keyed on.
    job.error_class = type(exc.__cause__ or exc).__name__
    job.error_message = str(exc)[:2000]


def mark_failed(
    db: Session, job_id: str, exc: BaseException, receive_count: int
) -> None:
    """Transient: the message comes back. After the last attempt it is dead."""
    job = db.get(Job, job_id)
    if job is None:
        return
    _record_error(job, exc)
    exhausted = max(receive_count, job.attempt) >= job.max_attempts
    job.status = "dead" if exhausted else "failed"
    if exhausted:
        job.finished_at = datetime.now(UTC)
    job.lease_owner = None
    job.lease_expires_at = None
    db.commit()


def mark_dead(db: Session, job_id: str, exc: BaseException) -> None:
    job = db.get(Job, job_id)
    if job is None:
        return
    _record_error(job, exc)
    job.status = "dead"
    job.finished_at = datetime.now(UTC)
    job.lease_owner = None
    job.lease_expires_at = None
    db.commit()


def stale_queued_jobs(
    db: Session, older_than: timedelta = timedelta(minutes=2)
) -> list[Job]:
    """
    Commit-then-enqueue can lose the enqueue (the network is not reliable).
    Rather than a full transactional outbox, a reconciler re-enqueues any job
    still `queued` after two minutes; the idempotent claim makes a duplicate
    message harmless.
    """
    cutoff = datetime.now(UTC) - older_than
    return (
        db.query(Job)
        .filter(Job.status == "queued", Job.attempt == 0, Job.created_at < cutoff)
        .order_by(Job.created_at)
        .limit(100)
        .all()
    )


def progress(job_id: str | None, **fields: object) -> None:
    """Handlers call this as they go; the job view shows it. Never raises."""
    if not job_id:
        return
    try:
        with _db.get_sessionmaker()() as db:
            job = db.get(Job, job_id)
            if job is not None:
                job.progress = {**(job.progress or {}), **fields}
                db.commit()
    except Exception as e:  # noqa: BLE001 - progress is a courtesy, not the work
        log.warning("progress_not_saved", job_id=job_id, error=type(e).__name__)
