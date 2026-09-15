import os
import tempfile
from pathlib import Path

from fastapi import APIRouter, HTTPException

from apps.api.app.deps import ActorDep, SessionDep
from edlo.models import Transcript
from edlo.storage import get_storage
from edlo.transcription.schema import TranscriptArtifact

router = APIRouter(prefix="/episodes", tags=["transcripts"])


@router.get("/{episode_id}/transcript")
def get_transcript(episode_id: str, db: SessionDep, actor: ActorDep):
    """The latest transcript for the episode, segments and all."""
    row = (
        db.query(Transcript)
        .filter_by(episode_id=episode_id)
        .order_by(Transcript.created_at.desc())
        .first()
    )
    if row is None:
        raise HTTPException(404, "no transcript yet")

    fd, scratch = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    try:
        get_storage().download_to_path(key=row.storage_key, dest=scratch)
        artifact = TranscriptArtifact.model_validate_json(Path(scratch).read_text())
    finally:
        os.unlink(scratch)
    return {
        "id": row.id,
        "audio_file_id": row.audio_file_id,
        "created_at": row.created_at,
        **artifact.model_dump(),
    }
