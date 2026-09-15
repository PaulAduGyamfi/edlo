import os
import tempfile
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from apps.api.app.deps import ActorDep, SessionDep
from edlo.config import get_settings
from edlo.domain.roles import Role
from edlo.logging import log
from edlo.models import AudioFile, Episode, Transcript
from edlo.storage import get_storage
from edlo.transcription.engine import (
    AudioDecodeError,
    TranscriptTooShort,
    transcribe_file,
)

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


@router.post("/{episode_id}/audio/complete", status_code=201)
def complete_upload(
    episode_id: str, body: CompleteRequest, db: SessionDep, actor: ActorDep
):
    """
    The browser calls this after S3 accepts the bytes.

    Never trust it. `head_object` is the authority on whether the upload
    actually happened -- a client could call complete for a key it never
    uploaded, or for someone else's key.
    """
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
    if row.status == "ready":
        return {"audio_file_id": row.id, "replayed": True}  # idempotent

    checksum = obj.checksum_sha256 or body.checksum_sha256
    row.status = "ready"
    row.size_bytes = obj.size_bytes
    row.checksum = checksum
    row.uploaded_at = datetime.now(UTC)
    db.commit()

    # Transcribe right here. Simplest thing that works.
    fd, scratch = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    try:
        get_storage().download_to_path(key=body.key, dest=scratch)
        artifact = transcribe_file(scratch, checksum)
    except (AudioDecodeError, TranscriptTooShort) as e:
        # The audio is stored and ready; only the transcript is missing.
        log.warning("transcription_failed", episode_id=episode_id, error=str(e))
        return {
            "audio_file_id": row.id,
            "replayed": False,
            "transcript_id": None,
            "transcript_error": str(e),
        }
    finally:
        os.unlink(scratch)  # the Protocol docstring said so

    # Artifact in object storage, pointer in the database.
    art_key = f"episodes/{episode_id}/transcript/{checksum[:32]}.json"
    fd, tmp = tempfile.mkstemp(suffix=".json")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(artifact.model_dump_json())
        get_storage().upload_from_path(
            key=art_key, src=tmp, content_type="application/json"
        )
    finally:
        os.unlink(tmp)
    transcript = Transcript(
        audio_file_id=row.id,
        episode_id=episode_id,
        storage_key=art_key,
        engine=artifact.engine,
        model_version=artifact.model_version,
        language=artifact.language,
        duration_ms=artifact.duration_ms,
        segment_count=len(artifact.segments),
        audio_checksum=checksum,
    )
    db.add(transcript)
    db.commit()
    log.info(
        "transcription_complete",
        episode_id=episode_id,
        transcript_id=transcript.id,
        segments=len(artifact.segments),
        duration_ms=artifact.duration_ms,
    )
    return {
        "audio_file_id": row.id,
        "replayed": False,
        "transcript_id": transcript.id,
        "transcript_error": None,
    }


@router.get("/{episode_id}/audio/{kind}/download-url")
def download_url(episode_id: str, kind: str, db: SessionDep, actor: ActorDep):
    row = (
        db.query(AudioFile)
        .filter_by(episode_id=episode_id, kind=kind, status="ready")
        .order_by(AudioFile.uploaded_at.desc())
        .first()
    )
    if row is None:
        raise HTTPException(404, "no audio of that kind")
    if row.first_downloaded_at is None:
        row.first_downloaded_at = datetime.now(UTC)
        db.commit()
        # SQLite hands back naive datetimes; they were written as UTC.
        uploaded = row.uploaded_at.replace(tzinfo=row.uploaded_at.tzinfo or UTC)
        log.info(
            "handoff_completed",
            episode_id=episode_id,
            hours=(row.first_downloaded_at - uploaded).total_seconds() / 3600,
        )
    return {
        "url": get_storage().presign_download(
            key=row.storage_key, filename=f"{kind}.wav", expires_in=900
        )
    }
