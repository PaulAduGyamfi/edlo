from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from apps.api.app.deps import ActorDep, SessionDep
from apps.api.app.routes.jobs import job_view
from apps.api.app.submit import replay, submit_job
from edlo.config import get_settings
from edlo.domain.roles import Role
from edlo.jobs.plan import load_transcript
from edlo.logging import log
from edlo.models import Episode, Job, PublishingPack, Transcript
from edlo.services.policy import check_pack
from edlo.services.workflow import IllegalTransition, NotPermitted, WorkflowService

router = APIRouter(prefix="/episodes", tags=["publish"])


def pack_view(p: PublishingPack) -> dict:
    return {
        "id": p.id,
        "status": p.status,
        "prompt_version": p.prompt_version,
        "model": p.model,
        "title": p.title,
        "description": p.description,
        "chapters": p.chapters,
        "links": p.links,
        "sponsors": p.sponsors,
        "violations": p.violations,
        "generated_at": p.generated_at,
    }


@router.post("/{episode_id}/pack")
def generate_pack_route(
    episode_id: str,
    request: Request,
    db: SessionDep,
    actor: ActorDep,
    idempotency_key: Annotated[str | None, Header()] = None,
):
    if actor.role not in (Role.VIDEO_EDITOR, Role.OWNER):
        raise HTTPException(403, "only the video editor or the owner drafts the pack")
    if db.get(Episode, episode_id) is None:
        raise HTTPException(404, "episode not found")
    if not db.query(Transcript).filter_by(episode_id=episode_id).count():
        raise HTTPException(409, "no transcript yet; the pack is drafted from it")
    fp, route, stored = replay(
        db, idempotency_key, f"POST /episodes/{episode_id}/pack", b""
    )
    if stored is not None:
        return stored
    return submit_job(
        db,
        request,
        kind="pack",
        episode_id=episode_id,
        payload={"episode_id": episode_id},
        job_key=idempotency_key or "",
        idempotency_key=idempotency_key or "",
        route=route,
        fp=fp,
        extra={"ai_enabled": get_settings().ai_enabled},
    )


@router.get("/{episode_id}/pack")
def get_pack(episode_id: str, db: SessionDep, actor: ActorDep):
    pack = (
        db.query(PublishingPack)
        .filter_by(episode_id=episode_id)
        .order_by(PublishingPack.generated_at.desc())
        .first()
    )
    job = (
        db.query(Job)
        .filter_by(episode_id=episode_id, kind="pack")
        .order_by(Job.created_at.desc())
        .first()
    )
    if (
        job is not None
        and job.status != "succeeded"
        and (pack is None or job.created_at > pack.generated_at)
    ):
        return JSONResponse(
            {"status": "pending", "job": job_view(job).model_dump(mode="json")},
            status_code=202,
        )
    if pack is None:
        raise HTTPException(404, "no publishing pack yet")
    return pack_view(pack)


@router.post("/{episode_id}/approve")
def approve(episode_id: str, request: Request, db: SessionDep, actor: ActorDep):
    """
    The gate. Policy runs again on what is actually there, right now; then
    the only path into `published` opens.
    """
    if actor.role is not Role.OWNER:
        raise HTTPException(403, "only the owner approves")
    ep = db.get(Episode, episode_id)
    if ep is None:
        raise HTTPException(404, "episode not found")
    pack = (
        db.query(PublishingPack)
        .filter_by(episode_id=episode_id)
        .order_by(PublishingPack.generated_at.desc())
        .first()
    )
    if pack is None:
        raise HTTPException(409, "draft the publishing pack first")
    _, artifact = load_transcript(episode_id)
    violations = check_pack(
        links=list(pack.links),
        sponsors=list(pack.sponsors),
        chapters=list(pack.chapters),
        transcript_text=" ".join(s.text for s in artifact.segments),
    )
    if violations:
        pack.violations = [v.as_dict() for v in violations]
        db.commit()
        raise HTTPException(422, {"violations": [v.as_dict() for v in violations]})
    try:
        WorkflowService(db).transition(
            ep, "published", actor, reason="approved", trace_id=request.state.trace_id
        )
    except IllegalTransition as e:
        raise HTTPException(409, str(e))
    except NotPermitted as e:
        raise HTTPException(403, str(e))
    ep.published_at = datetime.now(UTC)
    db.commit()
    log.info("episode_published", episode_id=episode_id, actor=actor.id)
    return {"id": ep.id, "stage": ep.stage, "published_at": ep.published_at}
