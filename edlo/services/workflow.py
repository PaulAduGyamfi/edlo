from sqlalchemy.orm import Session

from edlo.domain.roles import Actor, Role
from edlo.logging import log
from edlo.models import Episode, StageTransition

STAGES = (
    "registered",
    "mixing",
    "plan_ready",
    "editing",
    "review",
    "published",
    "blocked",
)

# The whole workflow, in one readable structure. If a move is not listed
# here it cannot happen, anywhere in the codebase.
LEGAL: dict[str, set[str]] = {
    "registered": {"mixing", "blocked"},
    "mixing": {"plan_ready", "blocked"},
    "plan_ready": {"editing", "mixing", "blocked"},
    "editing": {"review", "plan_ready", "blocked"},
    "review": {"published", "editing", "blocked"},
    "published": set(),
    "blocked": {"registered", "mixing", "plan_ready", "editing", "review"},
}

# Who may move an episode INTO each stage.
OWNERS: dict[str, set[Role]] = {
    "mixing": {Role.AUDIO_EDITOR, Role.OWNER},
    "plan_ready": {Role.VIDEO_EDITOR, Role.OWNER},
    "editing": {Role.VIDEO_EDITOR, Role.OWNER},
    "review": {Role.VIDEO_EDITOR, Role.OWNER},
    "published": {Role.OWNER},  # only Paul publishes
    "blocked": set(Role),
}


class IllegalTransition(Exception): ...


class NotPermitted(Exception): ...


class WorkflowService:
    def __init__(self, db: Session):
        self.db = db

    def transition(
        self,
        ep: Episode,
        to_stage: str,
        actor: Actor,
        reason: str | None = None,
        trace_id: str | None = None,
    ) -> Episode:
        if to_stage not in STAGES:
            raise IllegalTransition(f"unknown stage {to_stage!r}")
        if to_stage not in LEGAL[ep.stage]:
            raise IllegalTransition(f"cannot move from {ep.stage} to {to_stage}")
        if actor.role not in OWNERS.get(to_stage, set()):
            raise NotPermitted(
                f"{actor.role.value} may not move an episode to {to_stage}"
            )

        self.db.add(
            StageTransition(
                episode_id=ep.id,
                from_stage=ep.stage,
                to_stage=to_stage,
                actor_id=actor.id,
                actor_role=actor.role.value,
                reason=reason,
                trace_id=trace_id,
            )
        )
        log.info(
            "stage_transition",
            episode_id=ep.id,
            from_stage=ep.stage,
            to_stage=to_stage,
            actor=actor.id,
        )
        ep.stage = to_stage
        return ep

    def history(self, episode_id: str) -> list[StageTransition]:
        return (
            self.db.query(StageTransition)
            .filter_by(episode_id=episode_id)
            .order_by(StageTransition.happened_at)
            .all()
        )
