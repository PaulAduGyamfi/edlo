from datetime import datetime

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
    finished_at: datetime | None = None


def job_view(job: Job) -> JobView:
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
        created_at=job.created_at,
        finished_at=job.finished_at,
    )


@router.get("/{job_id}", response_model=JobView)
def get_job(job_id: str, db: SessionDep, actor: ActorDep) -> JobView:
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(404, "job not found")
    return job_view(job)
