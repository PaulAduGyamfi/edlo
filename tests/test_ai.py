"""Gateway, windows, grounding, policy: the deterministic wall around the model."""

import asyncio
from types import SimpleNamespace

import pytest
from pydantic import BaseModel

from edlo.ai import windows as W
from edlo.ai.gateway import (
    AIDisabled,
    MockGateway,
    ModelInvalidOutput,
    ModelUnavailable,
    OpenAICompatibleGateway,
    get_gateway,
)
from edlo.ai.grounding import merge, normalize, validate
from edlo.ai.schemas import Candidate, CutProposal
from edlo.config import get_settings
from edlo.services.policy import check_pack
from edlo.transcription.schema import TranscriptArtifact, TranscriptSegment

LINES = [
    "Welcome back to the Sozzled Pod, it's good to be here.",
    "This week we are talking about the ATEM Mini Pro and why it matters.",
    "Chris, you said the posting slot changed everything for you.",
    "It did, the first episode we scheduled went out on time.",
    "Then Albert uploaded the rough mix on the same day we recorded it.",
    "We still argue about the cold open, but we argue in one place now.",
]


def transcript(lines=LINES, seconds_each=5) -> TranscriptArtifact:
    ms = seconds_each * 1000
    return TranscriptArtifact(
        audio_checksum="a" * 64,
        engine="fake",
        model_version="v0",
        language="en",
        duration_ms=ms * len(lines),
        segments=[
            TranscriptSegment(index=i, start_ms=i * ms, end_ms=(i + 1) * ms, text=t)
            for i, t in enumerate(lines)
        ],
    )


def cand(start, end, quote, confidence=0.9):
    return Candidate(
        start_ms=start, end_ms=end, exact_quote=quote, reason="x", confidence=confidence
    )


# ---- grounding (chapter 20)


def test_fabricated_quote_is_dropped():
    fake = cand(1000, 5000, "I have never said this sentence")
    kept, rejected = validate([fake], transcript(), max_items=12)
    assert kept == [] and rejected[0].rule == "quote_not_in_transcript"


def test_real_quote_wrong_timecode_is_dropped():
    t = transcript()
    c = cand(25_000, 30_000, t.segments[0].text)  # said at 0:00, cited at 0:25
    _, rejected = validate([c], t, max_items=12)
    assert rejected[0].rule == "quote_not_at_timecode"


def test_smart_quotes_are_not_a_rejection():
    t = transcript()
    seg = t.segments[0]
    c = cand(seg.start_ms, seg.end_ms, seg.text.replace("'", "’"))
    assert len(validate([c], t, max_items=12)[0]) == 1


def test_timecodes_and_span_are_checked_before_quotes():
    t = transcript()
    out = cand(0, t.duration_ms + 1, t.segments[0].text)
    inverted = cand(5000, 4000, t.segments[0].text)
    _, rejected = validate([out, inverted], t, max_items=12)
    assert [r.rule for r in rejected] == ["timecode_out_of_range", "timecode_inverted"]
    long = cand(0, 30_000, t.segments[0].text)
    _, rejected = validate([long], t, max_items=12, max_span_ms=10_000)
    assert rejected[0].rule == "span_too_long"


def test_cap_keeps_the_most_confident():
    t = transcript()
    cs = [
        cand(s.start_ms, s.end_ms, s.text, confidence=0.1 * (i + 1))
        for i, s in enumerate(t.segments)
    ]
    kept, rejected = validate(cs, t, max_items=2)
    assert [c.confidence for c in kept] == [pytest.approx(0.6), pytest.approx(0.5)]
    assert sum(r.rule == "over_cap" for r in rejected) == 4


class FakeFlag:
    def __init__(self, id, start_ms, end_ms, note=None):
        self.id, self.start_ms, self.end_ms, self.note = id, start_ms, end_ms, note


def test_human_flags_survive_total_model_failure():
    t = transcript()
    flags = [FakeFlag("f1", 1000, 3000, "mic pop"), FakeFlag("f2", 20_000, 22_000)]
    garbage = [
        cand(0, 999_999, "nothing"),
        cand(5000, 4000, "never said"),
        cand(0, 5000, "x"),
    ]
    items, rejected = merge(flags, garbage, t, cap=12)
    assert [i.source for i in items] == ["human", "human"]
    assert {i.flag_id for i in items} == {"f1", "f2"}
    assert items[0].reason == "mic pop" and "Sozzled" in items[0].quote
    assert len(rejected) == 3


def test_cap_counts_human_flags_first():
    t = transcript()
    flags = [FakeFlag(f"f{i}", i * 5000, i * 5000 + 1000) for i in range(3)]
    model = [cand(s.start_ms, s.end_ms, s.text) for s in t.segments]
    items, _rejected = merge(flags, model, t, cap=4)
    assert sum(i.source == "human" for i in items) == 3
    assert sum(i.source == "model" for i in items) == 1


def test_normalize_matches_on_meaning():
    assert normalize("It’s  GOOD, to be here!") == normalize("it's good to be here")


# ---- windows


def test_windows_overlap_and_cover():
    t = transcript([f"line {i}" for i in range(120)], seconds_each=5)  # 10 minutes
    wins = W.make_windows(t, window_ms=300_000, overlap_ms=30_000)
    assert [(w.start_ms, w.end_ms) for w in wins] == [
        (0, 300_000),
        (270_000, 570_000),
        (540_000, 600_000),
    ]
    assert "[0:00.000-0:05.000] line 0" in W.render(wins[0])
    covered = set()
    for w in wins:
        covered.update(s.index for s in w.segments)
    assert covered == set(range(120))


# ---- gateway (chapter 19)


def test_mock_gateway_returns_configured_or_empty():
    proposal = CutProposal(candidates=[cand(0, 1000, "abc def ghi")])
    g = MockGateway({"CutProposal": proposal})
    assert (
        asyncio.run(
            g.structured(
                system="", user="", output_type=CutProposal, prompt_version="v"
            )
        )
        is proposal
    )
    assert (
        asyncio.run(
            MockGateway().structured(
                system="", user="", output_type=CutProposal, prompt_version="v"
            )
        ).candidates
        == []
    )
    assert g.calls == [{"type": "CutProposal", "version": "v"}]


def test_kill_switch_and_provider_selection(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "ai_enabled", False)
    with pytest.raises(AIDisabled):
        get_gateway()
    monkeypatch.setattr(s, "ai_enabled", True)
    monkeypatch.setattr(s, "model_provider", "mock")
    assert isinstance(get_gateway(), MockGateway)


class Out(BaseModel):
    n: int


class FakeCompletions:
    def __init__(self, script):
        self.script = list(script)
        self.calls = 0

    async def create(self, **kwargs):
        self.calls += 1
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        message = SimpleNamespace(content=item)
        return SimpleNamespace(
            id="req", usage=None, choices=[SimpleNamespace(message=message)]
        )


def fake_client(script):
    return type(
        "Client",
        (),
        {"chat": type("Chat", (), {"completions": FakeCompletions(script)})()},
    )()


def _run(gw, out=Out):
    return asyncio.run(
        gw.structured(system="s", user="u", output_type=out, prompt_version="v")
    )


def test_invalid_output_gets_one_corrective_retry_then_fails(monkeypatch):
    monkeypatch.setattr("edlo.ai.gateway.random.uniform", lambda a, b: 0)
    client = fake_client(['{"n": "not a number"}', '{"n": "still not"}', '{"n": 1}'])
    gw = OpenAICompatibleGateway("", "k", "m", 1, client=client)
    with pytest.raises(ModelInvalidOutput):
        _run(gw)
    assert client.chat.completions.calls == 2  # never a third


def test_transient_status_is_retried_with_jitter(monkeypatch):
    monkeypatch.setattr("edlo.ai.gateway.random.uniform", lambda a, b: 0)
    rate_limited = type("RL", (Exception,), {"status_code": 429})()
    client = fake_client([rate_limited, '{"n": 7}'])
    gw = OpenAICompatibleGateway("", "k", "m", 1, client=client)
    assert _run(gw).n == 7
    client = fake_client([rate_limited, rate_limited])
    with pytest.raises(ModelUnavailable):
        _run(OpenAICompatibleGateway("", "k", "m", 1, client=client))


def test_non_retryable_status_is_structural():
    bad_request = type("BR", (Exception,), {"status_code": 400})()
    client = fake_client([bad_request, '{"n": 1}'])
    with pytest.raises(ModelInvalidOutput):
        _run(OpenAICompatibleGateway("", "k", "m", 1, client=client))
    assert client.chat.completions.calls == 1


# ---- policy (chapter 22)


def test_policy_flags_invented_links_sponsors_and_disordered_chapters():
    text = "Thanks to Acme Coffee for sponsoring. Find us at sozzledpod.com."
    v = check_pack(
        links=["https://www.sozzledpod.com/ep1", "https://evil.example/x"],
        sponsors=["Acme Coffee", "Definitely Real Cars"],
        chapters=[{"start_ms": 5000, "title": "b"}, {"start_ms": 1000, "title": "a"}],
        transcript_text=text,
    )
    assert [(x.rule, x.detail) for x in v] == [
        ("invented_link", "https://evil.example/x"),
        ("unverified_sponsor", "Definitely Real Cars"),
        ("chapters_not_monotonic", ""),
    ]
    assert check_pack(links=[], sponsors=[], chapters=[], transcript_text=text) == []
