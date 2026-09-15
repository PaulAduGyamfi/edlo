from datetime import UTC, datetime
from pathlib import PurePosixPath
from typing import Annotated, Literal

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError

from apps.api.app.deps import ActorDep, SessionDep
from apps.api.app.idempotency import fingerprint, lookup, remember
from edlo.config import get_settings
from edlo.domain.roles import Role
from edlo.logging import log
from edlo.models import AudioFile, Episode, Job
from edlo.queue import enqueue
from edlo.storage import get_storage

router = APIRouter(prefix="/episodes", tags=["audio"])


class UploadRequest(BaseModel):
    kind: Literal["rough", "final"]
    filename: str = Field(min_length=1, max_length=255)
    content_type: str
    size_bytes: int = Field(gt=0)


@router.post("/{episode_id}/audio/upload-target")
def create_upload_target(
    episode_id: str, body: UploadRequest, db: SessionDep, actor: ActorDep
):
    """Authorize and sign. The bytes go straight from the browser to S3."""
    if actor.role not in (Role.AUDIO_EDITOR, Role.OWNER):
        raise HTTPException(403, "only the audio editor uploads")
    if db.get(Episode, episode_id) is None:
        raise HTTPException(404, "episode not found")
    s = get_settings()
    if body.size_bytes > s.max_upload_bytes:
        raise HTTPException(413, f"exceeds {s.max_upload_bytes // (1024**2)} MB")

    storage = get_storage()
    key = storage.new_key(episode_id=episode_id, kind=body.kind, filename=body.filename)
    target = storage.presign_upload(
        key=key, content_type=body.content_type, max_bytes=s.max_upload_bytes
    )

    # Row first, status `pending`. The object does not exist yet -- the browser
    # is about to create it. An abandoned `pending` row is cheap and sweepable.
    # An object with no row is a byte we pay for forever and cannot find.
    db.add(
        AudioFile(
            episode_id=episode_id,
            kind=body.kind,
            storage_key=key,
            filename=PurePosixPath(body.filename).name,  # what the download is called
            status="pending",
            uploaded_by=actor.id,
        )
    )
    db.commit()
    log.info("upload_target_issued", episode_id=episode_id, key=key, actor=actor.id)
    return target


class CompleteRequest(BaseModel):
    key: str
    checksum_sha256: str = Field(min_length=64, max_length=64)


@router.post("/{episode_id}/audio/complete", status_code=202)
def complete_upload(
    episode_id: str,
    body: CompleteRequest,
    request: Request,
    db: SessionDep,
    actor: ActorDep,
    idempotency_key: Annotated[str | None, Header()] = None,
):
    """
    The browser calls this after S3 accepts the bytes.

    Never trust it. `head_object` is the authority on whether the upload
    actually happened -- a client could call complete for a key it never
    uploaded, or for someone else's key.

    202: the transcript is produced by a worker; the response names the job.
    """
    if not idempotency_key:
        raise HTTPException(400, "Idempotency-Key header required")
    route = f"POST /episodes/{episode_id}/audio/complete"
    fp = fingerprint(body.model_dump_json().encode())
    try:
        stored = lookup(db, idempotency_key, route, fp)
    except ValueError as e:
        raise HTTPException(409, str(e))
    if stored is not None:
        return JSONResponse(
            stored, status_code=202, headers={"Idempotency-Replayed": "true"}
        )

    obj = get_storage().head(body.key)
    if obj is None:
        raise HTTPException(409, "object not found in storage; upload did not complete")
    if obj.checksum_sha256 and obj.checksum_sha256 != body.checksum_sha256:
        raise HTTPException(409, "checksum mismatch; the upload was corrupted")

    row = (
        db.query(AudioFile)
        .filter_by(episode_id=episode_id, storage_key=body.key)
        .one_or_none()
    )
    if row is None:
        raise HTTPException(404, "no pending upload for that key")

    if row.status != "ready":
        row.status = "ready"
        row.size_bytes = obj.size_bytes
        row.checksum = obj.checksum_sha256 or body.checksum_sha256
        row.uploaded_at = datetime.now(UTC)
        db.commit()

    # One transcribe job per audio file, enforced by the unique constraint.
    # Two concurrent completes produce one row and one IntegrityError; the
    # loser returns the existing job.
    job = Job(
        kind="transcribe",
        episode_id=episode_id,
        payload={"audio_file_id": row.id},
        idempotency_key=row.id,
        trace_id=request.state.trace_id,
    )
    db.add(job)
    created = True
    try:
        db.commit()  # job row committed FIRST
    except IntegrityError:
        db.rollback()
        created = False
        job = db.query(Job).filter_by(kind="transcribe", idempotency_key=row.id).one()
    if created:
        # Enqueue AFTER the commit. The reverse order lets a worker receive a
        # message for a row that was never committed.
        enqueue("transcribe", {"job_id": job.id, "audio_file_id": row.id})
        log.info(
            "audio_uploaded",
            episode_id=episode_id,
            kind=row.kind,
            job_id=job.id,
            actor=actor.id,
        )

    response = {
        "audio_file_id": row.id,
        "replayed": not created,
        "job_id": job.id,
        "poll_url": f"/jobs/{job.id}",
    }
    remember(db, idempotency_key, route, fp, response)
    db.commit()
    return JSONResponse(response, status_code=202)


@router.get("/{episode_id}/audio/{kind}/download-url")
def download_url(
    episode_id: str, kind: str, db: SessionDep, actor: ActorDep, stamp: bool = True
):
    """stamp=false is for in-browser playback, which is not the handoff."""
    row = (
        db.query(AudioFile)
        .filter_by(episode_id=episode_id, kind=kind, status="ready")
        .order_by(AudioFile.uploaded_at.desc())
        .first()
    )
    if row is None:
        raise HTTPException(404, "no audio of that kind")
    if stamp and row.first_downloaded_at is None:
        row.first_downloaded_at = datetime.now(UTC)
        db.commit()
        # SQLite hands back naive datetimes; they were written as UTC.
        uploaded = row.uploaded_at.replace(tzinfo=row.uploaded_at.tzinfo or UTC)
        log.info(
            "handoff_completed",
            episode_id=episode_id,
            hours=(row.first_downloaded_at - uploaded).total_seconds() / 3600,
        )
    filename = row.filename or f"{kind}{PurePosixPath(row.storage_key).suffix}"
    return {
        "url": get_storage().presign_download(
            key=row.storage_key, filename=filename, expires_in=900
        ),
        "filename": filename,
    }
