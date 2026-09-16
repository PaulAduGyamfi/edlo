from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from apps.api.app.deps import ActorDep, SessionDep
from edlo.models import Job

router = APIRouter(prefix="/jobs", tags=["jobs"])

# The raw exception must NEVER reach the browser -- it can contain file
# paths, connection strings or transcript fragments. Map a small set of
# known failures to sentences a podcast editor understands.
USER_MESSAGES = {
    "AudioDecodeError": "That audio file could not be read. Please export and upload it again.",
    "TranscriptTooShort": "The audio was too short to transcribe.",
}
DEAD_FALLBACK = (
    "Transcription failed after several attempts. Try uploading the mix again."
)


class JobView(BaseModel):
    id: str
    kind: str
    episode_id: str
    status: str
    attempt: int
    error_class: str | None = None
    user_message: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    worker: str | None = None  # who holds the lease
    progress: dict[str, Any] | None = None  # what the worker says it is doing
    queue_position: int | None = None  # backpressure, communicated


def _aware(dt: datetime | None) -> datetime | None:
    """SQLite hands back naive datetimes. They were written as UTC, and a
    browser parsing a naive ISO string would assume local time."""
    return dt if dt is None or dt.tzinfo else dt.replace(tzinfo=UTC)


def job_view(job: Job, position: int | None = None) -> JobView:
    message = None
    if job.status == "dead":
        message = USER_MESSAGES.get(job.error_class or "", DEAD_FALLBACK)
    return JobView(
        id=job.id,
        kind=job.kind,
        episode_id=job.episode_id,
        status=job.status,
        attempt=job.attempt,
        error_class=job.error_class,
        user_message=message,
        created_at=_aware(job.created_at) or job.created_at,
        started_at=_aware(job.started_at),
        finished_at=_aware(job.finished_at),
        worker=job.lease_owner,
        progress=job.progress,
        queue_position=position,
    )


@router.get("/{job_id}", response_model=JobView)
def get_job(job_id: str, db: SessionDep, actor: ActorDep) -> JobView:
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(404, "job not found")
    position = None
    if job.status == "queued":
        position = (
            db.query(Job)
            .filter(Job.status == "queued", Job.created_at <= job.created_at)
            .count()
        )
    return job_view(job, position)
