from datetime import date

from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from apps.api.app.deps import ActorDep, SessionDep
from edlo.domain.roles import Role
from edlo.logging import log
from edlo.models import Episode
from edlo.services.deletion import CannotDelete, delete_episode
from edlo.services.schedule import ScheduleService, SlotInPast, SlotTaken
from edlo.services.workflow import IllegalTransition, NotPermitted, WorkflowService
from edlo.storage import get_storage

router = APIRouter(prefix="/episodes", tags=["episodes"])


class EpisodeCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    recorded_on: date


class EpisodeView(BaseModel):
    id: str
    title: str
    recorded_on: date
    publish_on: date | None = None
    days_remaining: int | None = None
    schedule_status: str | None = None


def _view(ep: Episode, svc: ScheduleService) -> EpisodeView:
    c = svc.countdown(ep)
    return EpisodeView(
        id=ep.id,
        title=ep.title,
        recorded_on=ep.recorded_on,
        publish_on=ep.publish_on,
        days_remaining=c.days_remaining if c else None,
        schedule_status=c.status if c else None,
    )


@router.post("", status_code=status.HTTP_201_CREATED, response_model=EpisodeView)
def create_episode(body: EpisodeCreate, db: SessionDep, actor: ActorDep) -> EpisodeView:
    if actor.role not in (Role.AUDIO_EDITOR, Role.OWNER):
        raise HTTPException(403, "only the audio editor registers episodes")
    svc = ScheduleService(db)
    ep = Episode(title=body.title, recorded_on=body.recorded_on)
    db.add(ep)
    db.flush()
    svc.assign(ep, svc.next_free_slot(after=body.recorded_on))
    db.commit()
    log.info("episode_registered", episode_id=ep.id, publish_on=str(ep.publish_on))
    return _view(ep, svc)


class StageChange(BaseModel):
    to_stage: str
    reason: str | None = None


@router.post("/{episode_id}/stage", response_model=EpisodeView)
def change_stage(
    episode_id: str,
    body: StageChange,
    request: Request,
    db: SessionDep,
    actor: ActorDep,
) -> EpisodeView:
    ep = db.get(Episode, episode_id)
    if ep is None:
        raise HTTPException(404, "episode not found")
    try:
        WorkflowService(db).transition(
            ep, body.to_stage, actor, body.reason, request.state.trace_id
        )
    except IllegalTransition as e:
        raise HTTPException(409, str(e))
    except NotPermitted as e:
        raise HTTPException(403, str(e))
    db.commit()
    return _view(ep, ScheduleService(db))


@router.get("/{episode_id}/history")
def history(episode_id: str, db: SessionDep, actor: ActorDep):
    return [
        {
            "from": t.from_stage,
            "to": t.to_stage,
            "actor": t.actor_id,
            "role": t.actor_role,
            "at": t.happened_at,
            "reason": t.reason,
        }
        for t in WorkflowService(db).history(episode_id)
    ]


class SlotAssign(BaseModel):
    publish_on: date


@router.put("/{episode_id}/slot", response_model=EpisodeView)
def set_slot(episode_id: str, body: SlotAssign, db: SessionDep) -> EpisodeView:
    ep = db.get(Episode, episode_id)
    if ep is None:
        raise HTTPException(404, "episode not found")
    svc = ScheduleService(db)
    try:
        svc.assign(ep, body.publish_on)
    except SlotTaken as e:
        raise HTTPException(409, str(e))
    except SlotInPast as e:
        raise HTTPException(422, str(e))
    db.commit()
    return _view(ep, svc)


@router.get("", response_model=list[EpisodeView])
def list_episodes(db: SessionDep) -> list[EpisodeView]:
    svc = ScheduleService(db)
    eps = (
        db.query(Episode)
        .order_by(Episode.publish_on.is_(None), Episode.publish_on)
        .all()
    )
    return [_view(e, svc) for e in eps]


@router.delete("/{episode_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_episode(episode_id: str, db: SessionDep, actor: ActorDep) -> Response:
    """Gone for good: rows, slot, history, and the objects in storage."""
    if actor.role not in (Role.AUDIO_EDITOR, Role.OWNER):
        raise HTTPException(403, "only the audio editor or the owner deletes episodes")
    ep = db.get(Episode, episode_id)
    if ep is None:
        raise HTTPException(404, "episode not found")
    title = ep.title
    try:
        keys = delete_episode(db, ep)
    except CannotDelete as e:
        raise HTTPException(409, str(e))

    storage = get_storage()
    for key in keys:
        try:
            storage.delete(key)
        except Exception as e:  # noqa: BLE001 - the rows are gone; an orphan is a cost, not a bug
            log.warning("orphaned_object", key=key, error=f"{type(e).__name__}: {e}")
    log.info(
        "episode_deleted",
        episode_id=episode_id,
        title=title,
        actor=actor.id,
        objects=len(keys),
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
