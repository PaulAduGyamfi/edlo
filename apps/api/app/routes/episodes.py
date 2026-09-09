from datetime import date

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from apps.api.app.deps import SessionDep
from edlo.logging import log
from edlo.models import Episode
from edlo.services.schedule import ScheduleService, SlotInPast, SlotTaken

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
def create_episode(body: EpisodeCreate, db: SessionDep) -> EpisodeView:
    svc = ScheduleService(db)
    ep = Episode(title=body.title, recorded_on=body.recorded_on)
    db.add(ep)
    db.flush()
    svc.assign(ep, svc.next_free_slot(after=body.recorded_on))
    db.commit()
    log.info("episode_registered", episode_id=ep.id, publish_on=str(ep.publish_on))
    return _view(ep, svc)


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
