"""
transcript -> WINDOW -> model per window -> VALIDATE -> REDUCE -> human

Everything after the model is deterministic. With AI_ENABLED=false the plan
still exists: the human flags, the fixed checklist, and a clear status.
"""

import asyncio
import os
import tempfile
from collections import Counter
from pathlib import Path

from edlo.ai import windows as W
from edlo.ai.gateway import ModelGateway, ModelInvalidOutput, get_gateway
from edlo.ai.grounding import merge, validate
from edlo.ai.prompts import coldopen_v1, cutlist_v1
from edlo.ai.schemas import Candidate, ColdOpenCandidate, ColdOpenProposal, CutProposal
from edlo.config import get_settings
from edlo.db import get_sessionmaker
from edlo.domain.roles import SYSTEM_ACTOR
from edlo.jobs import PermanentFailure
from edlo.logging import log
from edlo.models import ColdOpen, CutItem, Episode, Flag, Plan, PlanStep, Transcript
from edlo.services.workflow import WorkflowService
from edlo.storage import get_storage
from edlo.transcription.schema import TranscriptArtifact

# Chris's fixed editing checklist: the same every episode, on purpose.
# Replace the wording with his own from the discovery session.
CHECKLIST = [
    "Cut to the accepted list",
    "Drop in the picked cold open",
    "Balance the final mix against the rough",
    "Title card and end slate",
    "Export at the agreed settings",
    "Upload the final mix",
]


def load_transcript(episode_id: str) -> tuple[Transcript, TranscriptArtifact]:
    Session = get_sessionmaker()
    with Session() as db:
        row = (
            db.query(Transcript)
            .filter_by(episode_id=episode_id)
            .order_by(Transcript.created_at.desc())
            .first()
        )
    if row is None:
        raise PermanentFailure(
            "no transcript to plan from; transcribe the rough mix first"
        )
    fd, scratch = tempfile.mkstemp(prefix="edlo-transcript-", suffix=".json")
    os.close(fd)
    try:
        get_storage().download_to_path(key=row.storage_key, dest=scratch)
        return row, TranscriptArtifact.model_validate_json(Path(scratch).read_text())
    finally:
        os.unlink(scratch)


async def _propose(
    gateway: ModelGateway, wins: list[W.Window], prompt_version: str
) -> tuple[list[Candidate], list[ColdOpenCandidate]]:
    cuts: list[Candidate] = []
    colds: list[ColdOpenCandidate] = []
    for w in wins:
        text = W.render(w)
        try:
            cp = await gateway.structured(
                system=cutlist_v1.SYSTEM,
                user=cutlist_v1.user(text),
                output_type=CutProposal,
                prompt_version=prompt_version,
            )
            co = await gateway.structured(
                system=coldopen_v1.SYSTEM,
                user=coldopen_v1.user(text),
                output_type=ColdOpenProposal,
                prompt_version=prompt_version,
            )
        except ModelInvalidOutput as e:
            # One window of bad output does not sink the plan; it is counted.
            log.warning("window_skipped", window=w.index, error=str(e))
            continue
        cuts += cp.candidates
        colds += co.candidates
    return cuts, colds


def generate_plan(payload: dict) -> None:
    episode_id = payload["episode_id"]
    s = get_settings()
    Session = get_sessionmaker()
    _, artifact = load_transcript(episode_id)

    with Session() as db:
        flags = (
            db.query(Flag)
            .filter_by(episode_id=episode_id)
            .order_by(Flag.start_ms)
            .all()
        )

    wins = W.make_windows(artifact)
    if s.ai_enabled:
        cuts, colds = asyncio.run(
            _propose(get_gateway(), wins, s.prompt_cutlist_version)
        )
        status, model = "ready", s.model_name or s.model_provider
    else:
        cuts, colds, status, model = [], [], "ai_disabled", ""

    items, rejected = merge(flags, cuts, artifact, cap=s.max_cuts)
    kept_colds, rejected_colds = validate(
        colds, artifact, max_items=s.max_cold_opens, max_span_ms=60_000
    )
    rejections = Counter(r.rule for r in rejected + rejected_colds)

    with Session() as db:
        # Regenerating replaces the previous plan.
        for model_cls in (CutItem, ColdOpen, Plan):
            db.query(model_cls).filter_by(episode_id=episode_id).delete(
                synchronize_session=False
            )
        plan = Plan(
            episode_id=episode_id,
            status=status,
            prompt_version=s.prompt_cutlist_version,
            model=model,
            windows=len(wins),
            proposed=len(cuts) + len(colds),
            rejections=dict(rejections),
        )
        db.add(plan)
        db.flush()
        for i, it in enumerate(items):
            db.add(
                CutItem(
                    plan_id=plan.id,
                    episode_id=episode_id,
                    source=it.source,
                    flag_id=it.flag_id,
                    position=i,
                    start_ms=it.start_ms,
                    end_ms=it.end_ms,
                    quote=it.quote,
                    reason=it.reason,
                    confidence=it.confidence,
                )
            )
        for i, c in enumerate(kept_colds):
            db.add(
                ColdOpen(
                    plan_id=plan.id,
                    episode_id=episode_id,
                    position=i,
                    start_ms=c.start_ms,
                    end_ms=c.end_ms,
                    quote=c.exact_quote,
                    why=c.why,
                    confidence=c.confidence,
                )
            )
        if not db.query(PlanStep).filter_by(episode_id=episode_id).count():
            for i, label in enumerate(CHECKLIST):
                db.add(PlanStep(episode_id=episode_id, position=i, label=label))
        ep = db.get(Episode, episode_id)
        if ep and ep.stage == "mixing":
            WorkflowService(db).transition(
                ep, "plan_ready", SYSTEM_ACTOR, reason="plan generated"
            )
        db.commit()

    log.info(
        "plan_generated",
        episode_id=episode_id,
        status=status,
        windows=len(wins),
        human=sum(1 for i in items if i.source == "human"),
        model_kept=sum(1 for i in items if i.source == "model"),
        cold_opens=len(kept_colds),
        rejected=dict(rejections),  # by rule: the regression detector
    )
