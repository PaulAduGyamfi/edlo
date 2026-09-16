"""
Test the failure, not the success. At-least-once delivery means every one of
these paths WILL happen in production.
"""

import hashlib
import threading
from datetime import UTC, datetime, timedelta

from edlo.jobs import claim_job, claim_next_job
from edlo.models import AudioFile, Episode, Job, Transcript
from tests.test_transcription import (
    ALBERT,
    CHECKSUM,
    DATA,
    FAKE,
    _complete,
    _episode,
    _upload,
)


def make_job(db, **overrides) -> Job:
    fields: dict = {
        "kind": "transcribe",
        "episode_id": "e" * 32,
        "payload": {},
        "idempotency_key": "k",
    }
    fields.update(overrides)
    job = Job(**fields)
    db.add(job)
    db.commit()
    return job


def _ready_audio(db, local_storage, ep, data=DATA):
    key = local_storage.new_key(episode_id=ep.id, kind="rough", filename="a.wav")
    p = local_storage.path(key)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)
    audio = AudioFile(
        episode_id=ep.id,
        kind="rough",
        storage_key=key,
        status="ready",
        size_bytes=len(data),
        checksum=hashlib.sha256(data).hexdigest(),
        uploaded_by="u_albert",
    )
    db.add(audio)
    db.commit()
    return audio


def test_duplicate_delivery_does_not_duplicate_work(
    db, local_storage, queue, monkeypatch
):
    """The single most important test in the async system."""
    from edlo.jobs.transcribe import transcribe_audio

    calls = []
    monkeypatch.setattr(
        "edlo.jobs.transcribe.transcribe_file", lambda *a, **k: calls.append(a) or FAKE
    )
    ep = _episode(db)
    audio = _ready_audio(db, local_storage, ep)
    job = make_job(
        db,
        episode_id=ep.id,
        payload={"audio_file_id": audio.id},
        idempotency_key=audio.id,
    )

    transcribe_audio({"job_id": job.id, "audio_file_id": audio.id})
    transcribe_audio({"job_id": job.id, "audio_file_id": audio.id})

    assert len(calls) == 1
    assert db.query(Transcript).filter_by(audio_file_id=audio.id).count() == 1


def test_identical_bytes_reuse_the_transcript(db, local_storage, queue, monkeypatch):
    """Content-addressed: the second upload of the same audio never hits the model."""
    from edlo.jobs.transcribe import transcribe_audio

    calls = []
    monkeypatch.setattr(
        "edlo.jobs.transcribe.transcribe_file", lambda *a, **k: calls.append(a) or FAKE
    )
    first, second = _episode(db), _episode(db)
    a1 = _ready_audio(db, local_storage, first)
    a2 = _ready_audio(db, local_storage, second)

    transcribe_audio({"audio_file_id": a1.id})
    transcribe_audio({"audio_file_id": a2.id})

    assert len(calls) == 1
    rows = {t.audio_file_id: t for t in db.query(Transcript).all()}
    assert (
        rows[a2.id].storage_key == rows[a1.id].storage_key
    )  # one artifact, two pointers
    db.expire_all()  # the worker wrote through its own session
    assert db.get(Episode, second.id).stage == "mixing"


def test_expired_lease_is_reclaimable(pg_db):
    """Requires Postgres: SKIP LOCKED does not exist on SQLite."""
    job = make_job(
        pg_db,
        status="running",
        lease_owner="dead-worker",
        lease_expires_at=datetime.now(UTC) - timedelta(minutes=1),
    )
    claimed = claim_next_job(pg_db, worker_id="new-worker")
    assert claimed is not None and claimed.id == job.id
    assert claimed.lease_owner == "new-worker" and claimed.attempt == 1


def test_two_workers_never_claim_the_same_job(pg_db):
    make_job(pg_db, status="queued")
    a = claim_next_job(pg_db, "w1")
    b = claim_next_job(pg_db, "w2")
    assert a is not None and b is None


def test_concurrent_claims_hand_out_each_job_once(pg_db):
    """Four workers, two jobs, one race: SKIP LOCKED gives every job exactly one owner."""
    from sqlalchemy.orm import sessionmaker

    for i in range(2):
        make_job(pg_db, idempotency_key=f"k{i}")
    factory = sessionmaker(pg_db.get_bind(), expire_on_commit=False)
    start = threading.Barrier(4)
    winners: list[str] = []
    lock = threading.Lock()

    def worker(name: str) -> None:
        with factory() as db:
            start.wait()
            job = claim_next_job(db, name)
            if job is not None:
                with lock:
                    winners.append(job.id)

    threads = [threading.Thread(target=worker, args=(f"w{i}",)) for i in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(winners) == 2 and len(set(winners)) == 2


def test_claim_job_refuses_a_live_lease_and_a_finished_job(db):
    job = make_job(
        db,
        status="running",
        lease_owner="w1",
        lease_expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )
    assert claim_job(db, job.id, "w2") is None
    done = make_job(db, idempotency_key="done", status="succeeded")
    assert claim_job(db, done.id, "w2") is None
    spent = make_job(db, idempotency_key="spent", status="failed", attempt=3)
    assert claim_job(db, spent.id, "w2") is None


def test_replay_returns_the_same_job(client, db, local_storage, queue):
    ep = _episode(db)
    target = _upload(client, ep.id)
    first = _complete(client, ep.id, target, key="k-1")
    second = _complete(client, ep.id, target, key="k-1")
    assert first.status_code == second.status_code == 202
    assert first.json()["job_id"] == second.json()["job_id"]
    assert second.headers["Idempotency-Replayed"] == "true"
    assert queue.depth() == 1  # one message, not two


def test_same_key_different_body_is_rejected(client, db, local_storage, queue):
    ep = _episode(db)
    target = _upload(client, ep.id)
    assert _complete(client, ep.id, target, key="k-2").status_code == 202
    r = _complete(client, ep.id, target, key="k-2", checksum="0" * 64)
    assert r.status_code == 409


def test_complete_requires_an_idempotency_key(client, db, local_storage, queue):
    ep = _episode(db)
    target = _upload(client, ep.id)
    r = client.post(
        f"/episodes/{ep.id}/audio/complete",
        json={"key": target["key"], "checksum_sha256": CHECKSUM},
        headers=ALBERT,
    )
    assert r.status_code == 400


def test_a_second_complete_with_a_new_key_still_yields_one_job(
    client, db, local_storage, queue
):
    """The unique constraint on (kind, idempotency_key) is the backstop."""
    ep = _episode(db)
    target = _upload(client, ep.id)
    a = _complete(client, ep.id, target, key="k-3").json()
    b = _complete(client, ep.id, target, key="k-4").json()
    assert a["job_id"] == b["job_id"] and b["replayed"] is True
    assert db.query(Job).count() == 1 and queue.depth() == 1
