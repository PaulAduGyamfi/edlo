from typing import Annotated, Literal

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel, Field

from apps.api.app.deps import ActorDep, SessionDep
from apps.api.app.routes.jobs import job_view
from apps.api.app.submit import replay, submit_job
from edlo.config import get_settings
from edlo.domain.roles import Role
from edlo.models import ColdOpen, CutItem, Episode, Job, Plan, PlanStep, Transcript

router = APIRouter(prefix="/episodes", tags=["plans"])

EDITORS = (Role.VIDEO_EDITOR, Role.OWNER)


def _editor(actor) -> None:
    if actor.role not in EDITORS:
        raise HTTPException(403, "only the video editor or the owner works the plan")


def _stamp(ms: int) -> str:
    s, frac = divmod(ms, 1000)
    return f"{s // 60}:{s % 60:02d}.{frac:03d}"


def item_view(i: CutItem) -> dict:
    return {
        "id": i.id,
        "source": i.source,
        "flag_id": i.flag_id,
        "position": i.position,
        "start_ms": i.start_ms,
        "end_ms": i.end_ms,
        "edited_start_ms": i.edited_start_ms,
        "edited_end_ms": i.edited_end_ms,
        "quote": i.quote,
        "reason": i.reason,
        "confidence": i.confidence,
        "decision": i.decision,
    }


def cold_view(c: ColdOpen) -> dict:
    return {
        "id": c.id,
        "position": c.position,
        "start_ms": c.start_ms,
        "end_ms": c.end_ms,
        "quote": c.quote,
        "why": c.why,
        "confidence": c.confidence,
        "picked": c.picked,
    }


@router.post("/{episode_id}/plan")
def generate(
    episode_id: str,
    request: Request,
    db: SessionDep,
    actor: ActorDep,
    idempotency_key: Annotated[str | None, Header()] = None,
):
    """202: a worker builds the plan. With AI off it is the flags and the checklist."""
    _editor(actor)
    if db.get(Episode, episode_id) is None:
        raise HTTPException(404, "episode not found")
    if not db.query(Transcript).filter_by(episode_id=episode_id).count():
        raise HTTPException(409, "no transcript yet; the plan is built from it")
    fp, route, stored = replay(
        db, idempotency_key, f"POST /episodes/{episode_id}/plan", b""
    )
    if stored is not None:
        return stored
    return submit_job(
        db,
        request,
        kind="plan",
        episode_id=episode_id,
        payload={"episode_id": episode_id},
        job_key=idempotency_key or "",
        idempotency_key=idempotency_key or "",
        route=route,
        fp=fp,
        extra={"ai_enabled": get_settings().ai_enabled},
    )


@router.get("/{episode_id}/plan")
def get_plan(episode_id: str, db: SessionDep, actor: ActorDep):
    plan = (
        db.query(Plan)
        .filter_by(episode_id=episode_id)
        .order_by(Plan.generated_at.desc())
        .first()
    )
    job = (
        db.query(Job)
        .filter_by(episode_id=episode_id, kind="plan")
        .order_by(Job.created_at.desc())
        .first()
    )
    if (
        job is not None
        and job.status not in ("succeeded",)
        and (plan is None or job.created_at > plan.generated_at)
    ):
        return JSONResponse(
            {"status": "pending", "job": job_view(job).model_dump(mode="json")},
            status_code=202,
        )
    if plan is None:
        raise HTTPException(404, "no plan yet")
    items = (
        db.query(CutItem).filter_by(plan_id=plan.id).order_by(CutItem.position).all()
    )
    colds = (
        db.query(ColdOpen).filter_by(plan_id=plan.id).order_by(ColdOpen.position).all()
    )
    steps = (
        db.query(PlanStep)
        .filter_by(episode_id=episode_id)
        .order_by(PlanStep.position)
        .all()
    )
    return {
        "id": plan.id,
        "status": plan.status,
        "prompt_version": plan.prompt_version,
        "model": plan.model,
        "windows": plan.windows,
        "proposed": plan.proposed,
        "rejections": plan.rejections,
        "generated_at": plan.generated_at,
        "items": [item_view(i) for i in items],
        "cold_opens": [cold_view(c) for c in colds],
        "steps": [
            {"id": s.id, "position": s.position, "label": s.label, "done_at": s.done_at}
            for s in steps
        ],
    }


class Decision(BaseModel):
    decision: Literal["pending", "accepted", "rejected"] | None = None
    start_ms: int | None = Field(default=None, ge=0)
    end_ms: int | None = Field(default=None, gt=0)


@router.post("/{episode_id}/plan/items/{item_id}")
def decide(
    episode_id: str, item_id: str, body: Decision, db: SessionDep, actor: ActorDep
):
    """Accept, reject, or edit the span. Editing keeps what was proposed."""
    _editor(actor)
    item = db.get(CutItem, item_id)
    if item is None or item.episode_id != episode_id:
        raise HTTPException(404, "cut not found")
    if body.decision is not None:
        item.decision = body.decision
    if body.start_ms is not None or body.end_ms is not None:
        start = (
            body.start_ms
            if body.start_ms is not None
            else (item.edited_start_ms or item.start_ms)
        )
        end = (
            body.end_ms
            if body.end_ms is not None
            else (item.edited_end_ms or item.end_ms)
        )
        if end <= start:
            raise HTTPException(422, "end_ms must be after start_ms")
        item.edited_start_ms, item.edited_end_ms = start, end
    db.commit()
    return item_view(item)


class Pick(BaseModel):
    picked: bool = True


@router.post("/{episode_id}/plan/cold-opens/{cold_id}")
def pick_cold_open(
    episode_id: str, cold_id: str, body: Pick, db: SessionDep, actor: ActorDep
):
    _editor(actor)
    cold = db.get(ColdOpen, cold_id)
    if cold is None or cold.episode_id != episode_id:
        raise HTTPException(404, "cold open not found")
    if body.picked:
        db.query(ColdOpen).filter_by(plan_id=cold.plan_id).update({"picked": False})
    cold.picked = body.picked
    db.commit()
    return cold_view(cold)


class StepDone(BaseModel):
    done: bool


@router.post("/{episode_id}/plan/steps/{step_id}")
def tick_step(
    episode_id: str, step_id: str, body: StepDone, db: SessionDep, actor: ActorDep
):
    from datetime import UTC, datetime

    _editor(actor)
    step = db.get(PlanStep, step_id)
    if step is None or step.episode_id != episode_id:
        raise HTTPException(404, "step not found")
    step.done_at = datetime.now(UTC) if body.done else None
    db.commit()
    return {
        "id": step.id,
        "position": step.position,
        "label": step.label,
        "done_at": step.done_at,
    }


@router.get("/{episode_id}/plan/export", response_class=PlainTextResponse)
def export(episode_id: str, db: SessionDep, actor: ActorDep) -> str:
    """The accepted cuts as timecodes Chris can work from. Plain text on purpose."""
    plan = (
        db.query(Plan)
        .filter_by(episode_id=episode_id)
        .order_by(Plan.generated_at.desc())
        .first()
    )
    if plan is None:
        raise HTTPException(404, "no plan yet")
    ep = db.get(Episode, episode_id)
    items = (
        db.query(CutItem)
        .filter_by(plan_id=plan.id, decision="accepted")
        .order_by(CutItem.start_ms)
        .all()
    )
    lines = [f"# {ep.title if ep else episode_id} -- cut list", ""]
    for i in items:
        start = i.edited_start_ms if i.edited_start_ms is not None else i.start_ms
        end = i.edited_end_ms if i.edited_end_ms is not None else i.end_ms
        lines.append(f"{_stamp(start)} - {_stamp(end)}  [{i.source}]  {i.quote}")
        if i.reason:
            lines.append(f"    {i.reason}")
    picked = db.query(ColdOpen).filter_by(plan_id=plan.id, picked=True).first()
    lines += ["", "# cold open"]
    lines.append(
        f"{_stamp(picked.start_ms)} - {_stamp(picked.end_ms)}  {picked.quote}"
        if picked
        else "(none picked)"
    )
    return "\n".join(lines) + "\n"
