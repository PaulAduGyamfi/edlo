"""
Between the model's draft and any human seeing it, deterministic policy runs.
A sponsor the model invented is a legal problem, not a typo.
"""

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from edlo.ai.grounding import normalize

ALLOWED_LINK_DOMAINS = {"sozzledpod.com", "youtube.com", "spotify.com"}


@dataclass(frozen=True)
class Violation:
    rule: str
    detail: str

    def as_dict(self) -> dict[str, str]:
        return {"rule": self.rule, "detail": self.detail}


def check_pack(
    *, links: list[str], sponsors: list[str], chapters: list[Any], transcript_text: str
) -> list[Violation]:
    v: list[Violation] = []
    for url in links:
        host = urlparse(url).netloc.lower().removeprefix("www.")
        if not any(host == d or host.endswith("." + d) for d in ALLOWED_LINK_DOMAINS):
            v.append(Violation("invented_link", url))
    full = normalize(transcript_text)
    for name in sponsors:
        if normalize(name) not in full:
            v.append(Violation("unverified_sponsor", name))
    starts = [c["start_ms"] if isinstance(c, dict) else c.start_ms for c in chapters]
    if starts != sorted(starts):
        v.append(Violation("chapters_not_monotonic", ""))
    return v
