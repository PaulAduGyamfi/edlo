"""The publishing pack: the model drafts, policy checks, a human approves."""

import asyncio

from edlo.ai import windows as W
from edlo.ai.gateway import get_gateway
from edlo.ai.prompts import pack_v1
from edlo.ai.schemas import PublishingPackDraft
from edlo.config import get_settings
from edlo.db import get_sessionmaker
from edlo.jobs import PermanentFailure
from edlo.jobs.plan import load_transcript
from edlo.logging import log
from edlo.models import Episode, PublishingPack
from edlo.services.policy import check_pack


def generate_pack(payload: dict) -> None:
    episode_id = payload["episode_id"]
    s = get_settings()
    Session = get_sessionmaker()
    with Session() as db:
        ep = db.get(Episode, episode_id)
    if ep is None:
        raise PermanentFailure("episode is gone")
    _, artifact = load_transcript(episode_id)

    if s.ai_enabled:
        text = "\n".join(W.render(w) for w in W.make_windows(artifact, overlap_ms=0))
        draft = asyncio.run(
            get_gateway().structured(
                system=pack_v1.SYSTEM,
                user=pack_v1.user(ep.title, text),
                output_type=PublishingPackDraft,
                prompt_version=s.prompt_pack_version,
            )
        )
        status, model = "ready", s.model_name or s.model_provider
    else:
        draft = PublishingPackDraft(title=ep.title, description="")
        status, model = "ai_disabled", ""

    violations = check_pack(
        links=draft.links,
        sponsors=draft.sponsors,
        chapters=draft.chapters,
        transcript_text=" ".join(seg.text for seg in artifact.segments),
    )
    with Session() as db:
        db.query(PublishingPack).filter_by(episode_id=episode_id).delete(
            synchronize_session=False
        )
        db.add(
            PublishingPack(
                episode_id=episode_id,
                status=status,
                prompt_version=s.prompt_pack_version,
                model=model,
                title=draft.title[:300],
                description=draft.description,
                chapters=[c.model_dump() for c in draft.chapters],
                links=draft.links,
                sponsors=draft.sponsors,
                violations=[v.as_dict() for v in violations],
            )
        )
        db.commit()
    log.info(
        "pack_generated",
        episode_id=episode_id,
        status=status,
        chapters=len(draft.chapters),
        violations=[v.rule for v in violations],
    )
