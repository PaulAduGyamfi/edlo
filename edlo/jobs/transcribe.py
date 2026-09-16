import os
import tempfile
import time

from edlo.db import get_sessionmaker
from edlo.domain.roles import SYSTEM_ACTOR
from edlo.jobs import PermanentFailure, progress
from edlo.logging import log
from edlo.models import AudioFile, Episode, Job, Transcript
from edlo.services.workflow import WorkflowService
from edlo.storage import get_storage
from edlo.transcription.engine import (
    ENGINE,
    MODEL_VERSION,
    AudioDecodeError,
    TranscriptTooShort,
    model_loaded,
    transcribe_file,
)

SCRATCH_DIR = tempfile.gettempdir()


def transcribe_audio(payload: dict) -> None:
    audio_file_id = payload["audio_file_id"]
    job_id = payload.get("job_id")
    Session = get_sessionmaker()
    storage = get_storage()

    with Session() as db:
        # GUARD 1 -- idempotency. At-least-once delivery means we WILL see this
        # message again after a crash. If the work already succeeded, stop.
        job = db.get(Job, job_id) if job_id else None
        if job and job.status == "succeeded":
            log.info("job_already_done", job_id=job_id)
            return

        audio = db.get(AudioFile, audio_file_id)
        if audio is None or audio.status != "ready" or not audio.checksum:
            raise PermanentFailure(f"audio_file {audio_file_id} is not ready")
        key, checksum, episode_id = audio.storage_key, audio.checksum, audio.episode_id

        # GUARD 2 -- content-addressed cache. Keyed by the audio checksum plus
        # engine and model version: re-uploading identical bytes is free, and
        # a model version bump invalidates everything automatically because
        # nothing matches the new key.
        cached = (
            db.query(Transcript)
            .filter_by(
                audio_checksum=checksum, engine=ENGINE, model_version=MODEL_VERSION
            )
            .order_by(Transcript.created_at.desc())
            .first()
        )
        if cached is not None:
            if cached.audio_file_id != audio_file_id:
                _persist(
                    db,
                    audio,
                    cached.storage_key,
                    language=cached.language,
                    duration_ms=cached.duration_ms,
                    segment_count=cached.segment_count,
                )
            log.info(
                "transcript_cache_hit",
                audio_file_id=audio_file_id,
                checksum=checksum[:12],
            )
            return

    scratch = None
    try:
        fd, scratch = tempfile.mkstemp(
            prefix="edlo-audio-", suffix=".wav", dir=SCRATCH_DIR
        )
        os.close(fd)
        progress(job_id, stage="downloading the audio")
        storage.download_to_path(key=key, dest=scratch)
        log.info(
            "audio_downloaded",
            audio_file_id=audio_file_id,
            size_mb=round(os.path.getsize(scratch) / 1024**2, 1),
        )
        progress(
            job_id,
            stage="transcribing"
            if model_loaded()
            else "loading the speech model (about 15s, once per worker), then transcribing",
        )
        last_report = 0.0

        def report(done_ms: int, total_ms: int) -> None:
            # One row write every few seconds, not one per segment.
            nonlocal last_report
            if time.monotonic() - last_report < 5:
                return
            last_report = time.monotonic()
            progress(
                job_id, stage="transcribing", audio_done_ms=done_ms, audio_ms=total_ms
            )

        try:
            artifact = transcribe_file(scratch, checksum, on_progress=report)
        except (AudioDecodeError, TranscriptTooShort) as e:
            # A corrupt file is still corrupt on attempt three.
            raise PermanentFailure(str(e)) from e
    finally:
        # UNCONDITIONAL. A worker task runs hundreds of jobs over its life.
        # Leaking a 200 MB scratch file per job fills Fargate's 20 GB
        # ephemeral volume in about a hundred jobs, and every job after that
        # fails with ENOSPC -- which looks like a storage bug and is not.
        if scratch and os.path.exists(scratch):
            os.unlink(scratch)

    progress(job_id, stage="saving the transcript")
    art_key = f"episodes/{episode_id}/transcript/{checksum[:32]}.json"
    fd, tmp = tempfile.mkstemp(
        prefix="edlo-transcript-", suffix=".json", dir=SCRATCH_DIR
    )
    try:
        with os.fdopen(fd, "w") as f:
            f.write(artifact.model_dump_json())
        storage.upload_from_path(key=art_key, src=tmp, content_type="application/json")
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)

    with Session() as db:
        audio = db.get(AudioFile, audio_file_id)
        if audio is None:
            raise PermanentFailure(
                "audio file was deleted while it was being transcribed"
            )
        _persist(
            db,
            audio,
            art_key,
            language=artifact.language,
            duration_ms=artifact.duration_ms,
            segment_count=len(artifact.segments),
        )
    log.info(
        "transcription_complete",
        audio_file_id=audio_file_id,
        episode_id=episode_id,
        segments=len(artifact.segments),
        duration_ms=artifact.duration_ms,
    )


def _persist(
    db,
    audio: AudioFile,
    storage_key: str,
    *,
    language: str,
    duration_ms: int,
    segment_count: int,
) -> None:
    """Pointer row, then the stage move, in one transaction."""
    assert audio.checksum is not None
    db.add(
        Transcript(
            audio_file_id=audio.id,
            episode_id=audio.episode_id,
            storage_key=storage_key,
            engine=ENGINE,
            model_version=MODEL_VERSION,
            language=language,
            duration_ms=duration_ms,
            segment_count=segment_count,
            audio_checksum=audio.checksum,
        )
    )
    ep = db.get(Episode, audio.episode_id)
    if ep and ep.stage == "registered":
        WorkflowService(db).transition(
            ep, "mixing", SYSTEM_ACTOR, reason="transcription complete"
        )
    db.commit()
