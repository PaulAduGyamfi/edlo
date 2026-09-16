"""
The most important code in the system. Everything after the model is
deterministic: the model has no path to the database that does not pass
through code that can reject it.
"""

import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from edlo.ai.schemas import Candidate, Grounded
from edlo.transcription.schema import TranscriptArtifact

RULES = (
    "timecode_out_of_range",
    "timecode_inverted",
    "quote_too_short",
    "quote_not_in_transcript",
    "quote_not_at_timecode",
    "span_too_long",
    "over_cap",
)


@dataclass(frozen=True)
class Rejection:
    candidate: Any
    rule: str
    detail: str


def normalize(s: str) -> str:
    """
    Match on meaning, not bytes. A model returning a smart apostrophe where
    the transcript has a straight one is NOT hallucinating -- rejecting it
    would train you to loosen the rule later, which is far worse.
    """
    s = unicodedata.normalize("NFKD", s)
    s = s.replace("’", "'").replace("“", '"').replace("”", '"')
    s = re.sub(r"[^\w\s']", " ", s.lower())
    return re.sub(r"\s+", " ", s).strip()


def validate[G: Grounded](
    candidates: Sequence[G],
    transcript: TranscriptArtifact,
    *,
    max_items: int,
    max_span_ms: int = 120_000,
) -> tuple[list[G], list[Rejection]]:
    kept: list[G] = []
    rejected: list[Rejection] = []
    full = normalize(" ".join(s.text for s in transcript.segments))

    for c in candidates:
        # RULE 1 -- timecodes inside the episode
        if c.end_ms > transcript.duration_ms:
            rejected.append(
                Rejection(c, "timecode_out_of_range", f"ends at {c.end_ms}")
            )
            continue
        if c.start_ms >= c.end_ms:
            rejected.append(
                Rejection(c, "timecode_inverted", f"{c.start_ms} >= {c.end_ms}")
            )
            continue

        # RULE 2 -- the quote exists SOMEWHERE
        q = normalize(c.exact_quote)
        if len(q) < 8:
            rejected.append(Rejection(c, "quote_too_short", q))
            continue
        if q not in full:
            rejected.append(Rejection(c, "quote_not_in_transcript", q[:80]))
            continue

        # RULE 3 -- the quote exists AT THE TIMECODE CITED.
        # A real quote from minute 4 tagged at minute 40 is useless even
        # though it is not fabricated. THIS is the rule people miss.
        local = normalize(transcript.text_between(c.start_ms - 2000, c.end_ms + 2000))
        if q not in local:
            rejected.append(Rejection(c, "quote_not_at_timecode", q[:80]))
            continue

        # RULE 4 -- length sanity
        if c.end_ms - c.start_ms > max_span_ms:
            rejected.append(
                Rejection(c, "span_too_long", f"{c.end_ms - c.start_ms} ms")
            )
            continue

        kept.append(c)

    kept.sort(key=lambda c: c.confidence, reverse=True)
    rejected += [Rejection(c, "over_cap", "") for c in kept[max_items:]]
    return kept[:max_items], rejected


@dataclass(frozen=True)
class Proposed:
    """A cut on its way to the plan: a human flag, or a model candidate that survived."""

    source: str  # human | model
    start_ms: int
    end_ms: int
    quote: str
    reason: str | None
    confidence: float | None
    flag_id: str | None = None


def merge(
    human_flags: Sequence[Any],
    model_candidates: Sequence[Candidate],
    transcript: TranscriptArtifact,
    cap: int,
) -> tuple[list[Proposed], list[Rejection]]:
    """Human flags never enter validate(). They are kept first, and the cap
    applies to what the model adds after them."""
    kept, rejected = validate(
        model_candidates, transcript, max_items=max(0, cap - len(human_flags))
    )
    items = [
        Proposed(
            source="human",
            start_ms=f.start_ms,
            end_ms=f.end_ms,
            quote=transcript.text_between(f.start_ms, f.end_ms),
            reason=f.note,
            confidence=None,
            flag_id=f.id,
        )
        for f in human_flags
    ] + [
        Proposed(
            source="model",
            start_ms=c.start_ms,
            end_ms=c.end_ms,
            quote=c.exact_quote,
            reason=c.reason,
            confidence=c.confidence,
        )
        for c in kept
    ]
    return items, rejected
