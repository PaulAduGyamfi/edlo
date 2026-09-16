"""The plan and the pack, end to end: routes, jobs, triage, export, approval."""

import hashlib
from datetime import date

from apps.worker.main import process
from edlo.ai.gateway import MockGateway
from edlo.ai.schemas import (
    Candidate,
    ColdOpenCandidate,
    ColdOpenProposal,
    CutProposal,
    PublishingPackDraft,
)
from edlo.config import get_settings
from edlo.jobs.plan import CHECKLIST
from edlo.models import AudioFile, Episode, Job, Transcript
from tests.test_ai import LINES, transcript

ALBERT = {"Authorization": "Bearer albert-token"}
CHRIS = {"Authorization": "Bearer chris-token"}
PAUL = {"Authorization": "Bearer paul-token"}


def episode_with_transcript(db, local_storage, stage="mixing") -> Episode:
    ep = Episode(title="Planned", recorded_on=date(2026, 3, 1), stage=stage)
    db.add(ep)
    db.flush()
    art = transcript()
    key = f"episodes/{ep.id}/transcript/{'c' * 32}.json"
    p = local_storage.path(key)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(art.model_dump_json())
    audio_key = local_storage.new_key(episode_id=ep.id, kind="rough", filename="a.wav")
    db.add(
        AudioFile(
            episode_id=ep.id,
            kind="rough",
            storage_key=audio_key,
            status="ready",
            size_bytes=1,
            checksum=hashlib.sha256(b"x").hexdigest(),
            uploaded_by="u_albert",
        )
    )
    db.add(
        Transcript(
            audio_file_id="x" * 32,
            episode_id=ep.id,
            storage_key=key,
            engine="fake",
            model_version="v0",
            language="en",
            duration_ms=art.duration_ms,
            segment_count=len(art.segments),
            audio_checksum="a" * 64,
        )
    )
    db.commit()
    return ep


def ai_on(monkeypatch, responses):
    s = get_settings()
    monkeypatch.setattr(s, "ai_enabled", True)
    monkeypatch.setattr(s, "model_provider", "mock")
    gw = MockGateway(responses)
    monkeypatch.setattr("edlo.jobs.plan.get_gateway", lambda: gw)
    monkeypatch.setattr("edlo.jobs.pack.get_gateway", lambda: gw)
    return gw


def run_next(queue):
    (message,) = queue.receive(wait_seconds=0)
    process(queue, message)


def test_plan_needs_a_transcript_and_an_editor(client, db, local_storage, queue):
    ep = Episode(title="Bare", recorded_on=date(2026, 3, 1))
    db.add(ep)
    db.commit()
    h = {**CHRIS, "Idempotency-Key": "p-0"}
    assert client.post(f"/episodes/{ep.id}/plan", headers=h).status_code == 409
    planned = episode_with_transcript(db, local_storage)
    assert (
        client.post(
            f"/episodes/{planned.id}/plan", headers={**ALBERT, "Idempotency-Key": "p-1"}
        ).status_code
        == 403
    )
    assert (
        client.post(f"/episodes/{planned.id}/plan", headers=CHRIS).status_code == 400
    )  # no key
    assert client.get(f"/episodes/{planned.id}/plan", headers=CHRIS).status_code == 404


def test_grounded_plan_with_flags_cold_opens_and_checklist(
    client, db, local_storage, queue, monkeypatch
):
    good = Candidate(
        start_ms=5000,
        end_ms=10_000,
        exact_quote=LINES[1],
        reason="tangent",
        confidence=0.8,
    )
    fake = Candidate(
        start_ms=5000,
        end_ms=10_000,
        exact_quote="we never said this thing",
        reason="x",
        confidence=0.9,
    )
    wrong_time = Candidate(
        start_ms=25_000, end_ms=30_000, exact_quote=LINES[0], reason="x", confidence=0.9
    )
    cold = ColdOpenCandidate(
        start_ms=15_000, end_ms=20_000, exact_quote=LINES[3], why="hook", confidence=0.7
    )
    gw = ai_on(
        monkeypatch,
        {
            "CutProposal": CutProposal(candidates=[good, fake, wrong_time]),
            "ColdOpenProposal": ColdOpenProposal(candidates=[cold]),
        },
    )
    ep = episode_with_transcript(db, local_storage)
    flag = client.post(
        f"/episodes/{ep.id}/flags",
        json={"start_ms": 20_000, "end_ms": 23_000, "note": "dog barks"},
        headers=ALBERT,
    ).json()

    r = client.post(
        f"/episodes/{ep.id}/plan", headers={**CHRIS, "Idempotency-Key": "p-2"}
    )
    assert r.status_code == 202 and r.json()["ai_enabled"] is True
    assert client.get(f"/episodes/{ep.id}/plan", headers=CHRIS).status_code == 202
    run_next(queue)

    plan = client.get(f"/episodes/{ep.id}/plan", headers=CHRIS).json()
    assert plan["status"] == "ready" and plan["windows"] == 1 and plan["proposed"] == 4
    assert plan["rejections"] == {
        "quote_not_in_transcript": 1,
        "quote_not_at_timecode": 1,
    }
    assert [(i["source"], i["start_ms"]) for i in plan["items"]] == [
        ("human", 20_000),
        ("model", 5000),
    ]
    assert (
        plan["items"][0]["flag_id"] == flag["id"]
        and plan["items"][0]["reason"] == "dog barks"
    )
    assert (
        plan["items"][0]["quote"] == LINES[4]
    )  # the flag's span, read from the transcript
    assert [c["quote"] for c in plan["cold_opens"]] == [LINES[3]]
    assert [s["label"] for s in plan["steps"]] == CHECKLIST
    assert gw.calls == [
        {"type": "CutProposal", "version": "cutlist-v1"},
        {"type": "ColdOpenProposal", "version": "cutlist-v1"},
    ]
    db.expire_all()
    assert db.get(Episode, ep.id).stage == "plan_ready"
    history = client.get(f"/episodes/{ep.id}/history", headers=CHRIS).json()
    assert history[-1] == {
        **history[-1],
        "to": "plan_ready",
        "actor": "system",
        "reason": "plan generated",
    }


def test_plan_with_ai_off_is_the_flags_and_the_checklist(
    client, db, local_storage, queue, monkeypatch
):
    monkeypatch.setattr(get_settings(), "ai_enabled", False)
    ep = episode_with_transcript(db, local_storage)
    client.post(
        f"/episodes/{ep.id}/flags", json={"start_ms": 0, "end_ms": 2000}, headers=CHRIS
    )
    r = client.post(
        f"/episodes/{ep.id}/plan", headers={**PAUL, "Idempotency-Key": "p-3"}
    )
    assert r.status_code == 202 and r.json()["ai_enabled"] is False
    run_next(queue)
    plan = client.get(f"/episodes/{ep.id}/plan", headers=PAUL).json()
    assert plan["status"] == "ai_disabled" and plan["model"] == ""
    assert [i["source"] for i in plan["items"]] == ["human"] and plan[
        "cold_opens"
    ] == []
    assert len(plan["steps"]) == len(CHECKLIST)
    assert db.get(Job, r.json()["job_id"]).status == "succeeded"


def test_triage_edit_pick_tick_and_export(
    client, db, local_storage, queue, monkeypatch
):
    good = Candidate(
        start_ms=5000,
        end_ms=10_000,
        exact_quote=LINES[1],
        reason="tangent",
        confidence=0.8,
    )
    cold = ColdOpenCandidate(
        start_ms=15_000, end_ms=20_000, exact_quote=LINES[3], why="hook", confidence=0.7
    )
    ai_on(
        monkeypatch,
        {
            "CutProposal": CutProposal(candidates=[good]),
            "ColdOpenProposal": ColdOpenProposal(candidates=[cold]),
        },
    )
    ep = episode_with_transcript(db, local_storage)
    client.post(f"/episodes/{ep.id}/plan", headers={**CHRIS, "Idempotency-Key": "p-4"})
    run_next(queue)
    plan = client.get(f"/episodes/{ep.id}/plan", headers=CHRIS).json()
    item, cold_id, step = (
        plan["items"][0],
        plan["cold_opens"][0]["id"],
        plan["steps"][0],
    )

    assert (
        client.post(
            f"/episodes/{ep.id}/plan/items/{item['id']}",
            json={"decision": "accepted"},
            headers=ALBERT,
        ).status_code
        == 403
    )
    edited = client.post(
        f"/episodes/{ep.id}/plan/items/{item['id']}",
        json={"decision": "accepted", "start_ms": 5500, "end_ms": 9500},
        headers=CHRIS,
    ).json()
    assert (
        edited["decision"],
        edited["edited_start_ms"],
        edited["edited_end_ms"],
        edited["start_ms"],
    ) == ("accepted", 5500, 9500, 5000)
    assert (
        client.post(
            f"/episodes/{ep.id}/plan/items/{item['id']}",
            json={"start_ms": 9000, "end_ms": 8000},
            headers=CHRIS,
        ).status_code
        == 422
    )
    assert (
        client.post(
            f"/episodes/{ep.id}/plan/cold-opens/{cold_id}",
            json={"picked": True},
            headers=CHRIS,
        ).json()["picked"]
        is True
    )
    assert client.post(
        f"/episodes/{ep.id}/plan/steps/{step['id']}", json={"done": True}, headers=CHRIS
    ).json()["done_at"]

    text = client.get(f"/episodes/{ep.id}/plan/export", headers=CHRIS).text
    assert "0:05.500 - 0:09.500  [model]  " + LINES[1] in text
    assert "    tangent" in text and "# cold open\n0:15.000 - 0:20.000" in text


def test_regenerating_replaces_the_plan_and_is_idempotent_per_key(
    client, db, local_storage, queue, monkeypatch
):
    ai_on(monkeypatch, {})
    ep = episode_with_transcript(db, local_storage)
    first = client.post(
        f"/episodes/{ep.id}/plan", headers={**CHRIS, "Idempotency-Key": "p-5"}
    ).json()
    again = client.post(
        f"/episodes/{ep.id}/plan", headers={**CHRIS, "Idempotency-Key": "p-5"}
    )
    assert (
        again.json()["job_id"] == first["job_id"]
        and again.headers["Idempotency-Replayed"] == "true"
    )
    run_next(queue)
    second = client.post(
        f"/episodes/{ep.id}/plan", headers={**CHRIS, "Idempotency-Key": "p-6"}
    ).json()
    assert second["job_id"] != first["job_id"]
    assert (
        client.get(f"/episodes/{ep.id}/plan", headers=CHRIS).status_code == 202
    )  # newer job pending
    run_next(queue)
    assert client.get(f"/episodes/{ep.id}/plan", headers=CHRIS).status_code == 200
    assert db.query(Job).filter_by(kind="plan").count() == 2


# ---- the pack and the gate (chapter 22)


def test_pack_policy_blocks_then_approval_publishes(
    client, db, local_storage, queue, monkeypatch
):
    draft = PublishingPackDraft(
        title="Ep 1",
        description="Two paragraphs.",
        chapters=[
            {"start_ms": 0, "title": "Intro"},
            {"start_ms": 15_000, "title": "Slots"},
        ],
        links=["https://sozzledpod.com/ep1", "https://scam.example/free-money"],
        sponsors=["Acme Cars"],
    )
    ai_on(monkeypatch, {"PublishingPackDraft": draft})
    ep = episode_with_transcript(db, local_storage, stage="review")
    assert (
        client.post(f"/episodes/{ep.id}/approve", headers=PAUL).status_code == 409
    )  # no pack yet

    r = client.post(
        f"/episodes/{ep.id}/pack", headers={**CHRIS, "Idempotency-Key": "k-1"}
    )
    assert r.status_code == 202
    run_next(queue)
    pack = client.get(f"/episodes/{ep.id}/pack", headers=PAUL).json()
    assert pack["title"] == "Ep 1" and [v["rule"] for v in pack["violations"]] == [
        "invented_link",
        "unverified_sponsor",
    ]

    denied = client.post(f"/episodes/{ep.id}/approve", headers=PAUL)
    assert denied.status_code == 422
    assert [v["rule"] for v in denied.json()["detail"]["violations"]] == [
        "invented_link",
        "unverified_sponsor",
    ]
    assert client.post(f"/episodes/{ep.id}/approve", headers=CHRIS).status_code == 403

    # the model behaves; a new draft passes and the owner publishes
    ai_on(
        monkeypatch,
        {
            "PublishingPackDraft": PublishingPackDraft(
                title="Ep 1", description="d", links=["https://sozzledpod.com/ep1"]
            )
        },
    )
    client.post(f"/episodes/{ep.id}/pack", headers={**CHRIS, "Idempotency-Key": "k-2"})
    run_next(queue)
    ok = client.post(f"/episodes/{ep.id}/approve", headers=PAUL)
    assert (
        ok.status_code == 200
        and ok.json()["stage"] == "published"
        and ok.json()["published_at"]
    )
    db.expire_all()
    assert db.get(Episode, ep.id).stage == "published"
    history = client.get(f"/episodes/{ep.id}/history", headers=PAUL).json()
    assert (
        history[-1]["to"] == "published"
        and history[-1]["actor"] == "u_paul"
        and history[-1]["reason"] == "approved"
    )


def test_published_is_only_reachable_through_approval(client, db, local_storage):
    ep = episode_with_transcript(db, local_storage, stage="review")
    r = client.post(
        f"/episodes/{ep.id}/stage", json={"to_stage": "published"}, headers=PAUL
    )
    assert r.status_code == 409 and "approve" in r.json()["detail"]


def test_pack_with_ai_off_is_the_title_and_no_violations(
    client, db, local_storage, queue, monkeypatch
):
    monkeypatch.setattr(get_settings(), "ai_enabled", False)
    ep = episode_with_transcript(db, local_storage, stage="review")
    client.post(f"/episodes/{ep.id}/pack", headers={**PAUL, "Idempotency-Key": "k-3"})
    run_next(queue)
    pack = client.get(f"/episodes/{ep.id}/pack", headers=PAUL).json()
    assert (
        pack["status"] == "ai_disabled"
        and pack["title"] == "Planned"
        and pack["violations"] == []
    )
    assert (
        client.post(f"/episodes/{ep.id}/approve", headers=PAUL).status_code == 200
    )  # the workflow still completes


def test_flags_crud(client, db, local_storage):
    ep = episode_with_transcript(db, local_storage)
    assert (
        client.post(
            f"/episodes/{ep.id}/flags",
            json={"start_ms": 5, "end_ms": 5},
            headers=ALBERT,
        ).status_code
        == 422
    )
    f = client.post(
        f"/episodes/{ep.id}/flags",
        json={"start_ms": 1000, "end_ms": 4000, "note": "laugh"},
        headers=ALBERT,
    ).json()
    assert f["created_by"] == "u_albert"
    assert [
        x["id"] for x in client.get(f"/episodes/{ep.id}/flags", headers=CHRIS).json()
    ] == [f["id"]]
    assert (
        client.delete(f"/episodes/{ep.id}/flags/{f['id']}", headers=CHRIS).status_code
        == 204
    )
    assert client.get(f"/episodes/{ep.id}/flags", headers=CHRIS).json() == []
    assert (
        client.post(
            "/episodes/nope/flags", json={"start_ms": 0, "end_ms": 1}, headers=ALBERT
        ).status_code
        == 404
    )
