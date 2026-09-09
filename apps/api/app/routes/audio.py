from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from apps.api.app.deps import ActorDep, SessionDep
from edlo.config import get_settings
from edlo.domain.roles import Role
from edlo.logging import log
from edlo.models import AudioFile, Episode
from edlo.storage import LocalStorage, UnsupportedMedia, build_key

router = APIRouter(prefix="/episodes", tags=["audio"])


def storage() -> LocalStorage:
    return LocalStorage(get_settings().upload_dir)


@router.post("/{episode_id}/audio", status_code=201)
async def upload_audio(
    episode_id: str,
    kind: str,
    db: SessionDep,
    actor: ActorDep,
    file: Annotated[UploadFile, File()],
):
    if actor.role not in (Role.AUDIO_EDITOR, Role.OWNER):
        raise HTTPException(403, "only the audio editor uploads")
    if db.get(Episode, episode_id) is None:
        raise HTTPException(404, "episode not found")

    settings = get_settings()
    try:
        key = build_key(episode_id=episode_id, kind=kind, filename=file.filename or "")
    except UnsupportedMedia as e:
        raise HTTPException(415, str(e))

    def chunks():
        total = 0
        while data := file.file.read(1024 * 1024):
            total += len(data)
            if total > settings.max_upload_bytes:
                raise HTTPException(413, "file too large")
            yield data

    size, checksum = storage().save_stream(key, chunks())

    row = AudioFile(
        episode_id=episode_id,
        kind=kind,
        storage_key=key,
        size_bytes=size,
        checksum=checksum,
        uploaded_by=actor.id,
    )
    db.add(row)
    db.commit()

    log.info(
        "audio_uploaded",
        episode_id=episode_id,
        kind=kind,
        size_bytes=size,
        checksum=checksum[:12],
        actor=actor.id,
    )
    return {"audio_file_id": row.id, "size_bytes": size, "checksum": checksum}


@router.get("/{episode_id}/audio/{kind}")
def download_audio(episode_id: str, kind: str, db: SessionDep, actor: ActorDep):
    row = (
        db.query(AudioFile)
        .filter_by(episode_id=episode_id, kind=kind)
        .order_by(AudioFile.uploaded_at.desc())
        .first()
    )
    if row is None:
        raise HTTPException(404, "no audio of that kind")

    if row.first_downloaded_at is None:
        row.first_downloaded_at = datetime.now(UTC)
        db.commit()
        log.info(
            "handoff_completed",
            episode_id=episode_id,
            hours=(row.first_downloaded_at - row.uploaded_at).total_seconds() / 3600,
        )

    return StreamingResponse(
        storage().open(row.storage_key),
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{kind}-{episode_id[:8]}.wav"'
        },
    )
