from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel, Field

from apps.api.app.deps import ActorDep, SessionDep
from edlo.models import Episode, Flag

router = APIRouter(prefix="/episodes", tags=["flags"])


class FlagIn(BaseModel):
    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)
    note: str | None = Field(default=None, max_length=500)


def flag_view(f: Flag) -> dict:
    return {
        "id": f.id,
        "start_ms": f.start_ms,
        "end_ms": f.end_ms,
        "note": f.note,
        "created_by": f.created_by,
        "created_at": f.created_at,
    }


@router.post("/{episode_id}/flags", status_code=status.HTTP_201_CREATED)
def add_flag(episode_id: str, body: FlagIn, db: SessionDep, actor: ActorDep):
    """A human heard something. No model rule ever removes it."""
    if db.get(Episode, episode_id) is None:
        raise HTTPException(404, "episode not found")
    if body.end_ms <= body.start_ms:
        raise HTTPException(422, "end_ms must be after start_ms")
    flag = Flag(
        episode_id=episode_id,
        start_ms=body.start_ms,
        end_ms=body.end_ms,
        note=body.note,
        created_by=actor.id,
    )
    db.add(flag)
    db.commit()
    return flag_view(flag)


@router.get("/{episode_id}/flags")
def list_flags(episode_id: str, db: SessionDep, actor: ActorDep):
    rows = db.query(Flag).filter_by(episode_id=episode_id).order_by(Flag.start_ms).all()
    return [flag_view(f) for f in rows]


@router.delete("/{episode_id}/flags/{flag_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_flag(
    episode_id: str, flag_id: str, db: SessionDep, actor: ActorDep
) -> Response:
    flag = db.get(Flag, flag_id)
    if flag is None or flag.episode_id != episode_id:
        raise HTTPException(404, "flag not found")
    db.delete(flag)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
