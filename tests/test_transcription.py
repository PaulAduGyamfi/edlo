import hashlib
from datetime import date
from urllib.parse import unquote

import pytest
from pydantic import ValidationError

from apps.worker.main import process
from edlo.models import AudioFile, Episode, Job, Transcript
from edlo.transcription.engine import AudioDecodeError
from edlo.transcription.schema import TranscriptArtifact, TranscriptSegment

ALBERT = {"Authorization": "Bearer albert-token"}
CHRIS = {"Authorization": "Bearer chris-token"}
DATA = b"RIFF" + bytes(range(256)) * 8
CHECKSUM = hashlib.sha256(DATA).hexdigest()


def seg(i, start, end, text="words here"):
    return TranscriptSegment(index=i, start_ms=start, end_ms=end, text=text)


def artifact(segments, duration_ms=10_000, checksum=CHECKSUM):
    return TranscriptArtifact(
        audio_checksum=checksum,
        engine="fake",
        model_version="v0",
        language="en",
        duration_ms=duration_ms,
        segments=segments,
    )


# ---- schema: the shape the rest of the system trusts ----


def test_segment_must_end_after_it_starts():
    with pytest.raises(ValidationError, match="end_ms must be after start_ms"):
        seg(0, 2000, 1000)


def test_out_of_order_and_overlap_are_distinct_errors():
    with pytest.raises(ValidationError, match="out of order"):
        artifact([seg(0, 5000, 6000), seg(1, 1000, 2000)])
    with pytest.raises(ValidationError, match="overlap"):
        artifact([seg(0, 1000, 3000), seg(1, 2000, 4000)])


def test_last_segment_inside_duration():
    with pytest.raises(ValidationError, match="beyond the declared audio duration"):
        artifact([seg(0, 0, 1000), seg(1, 1000, 20_000)], duration_ms=10_000)


def test_text_between_uses_the_stored_segments():
    a = artifact(
        [seg(0, 0, 1000, "one"), seg(1, 1000, 2000, "two"), seg(2, 2000, 3000, "three")]
    )
    assert a.text_between(900, 2100) == "one two three"
    assert a.text_between(1000, 2000) == "two"


# ---- the routes and the worker, end to end on local storage ----


def _episode(db) -> Episode:
    ep = Episode(title="Test", recorded_on=date(2026, 3, 1))
    db.add(ep)
    db.commit()
    return ep


def _upload(client, episode_id, filename="rough mix v2.wav", data=DATA) -> dict:
    target = client.post(
        f"/episodes/{episode_id}/audio/upload-target",
        json={
            "kind": "rough",
            "filename": filename,
            "content_type": "audio/wav",
            "size_bytes": 1,
        },
        headers=ALBERT,
    ).json()
    assert (
        client.put(target["url"], content=data, headers=target["headers"]).status_code
        == 204
    )
    return target


def _complete(client, episode_id, target, checksum=CHECKSUM, key=None):
    return client.post(
        f"/episodes/{episode_id}/audio/complete",
        json={"key": target["key"], "checksum_sha256": checksum},
        headers={**ALBERT, "Idempotency-Key": key or target["key"]},
    )


FAKE = artifact(
    [seg(0, 0, 1000, "hello"), seg(1, 1000, 2000, "sozzled"), seg(2, 2000, 3000, "pod")]
)


def test_complete_queues_a_transcribe_job(client, db, local_storage, queue):
    ep = _episode(db)
    target = _upload(client, ep.id)

    r = _complete(client, ep.id, target)
    assert r.status_code == 202, r.text
    body = r.json()
    assert body["replayed"] is False and body["poll_url"] == f"/jobs/{body['job_id']}"

    job = db.get(Job, body["job_id"])
    assert (job.kind, job.status, job.attempt) == ("transcribe", "queued", 0)
    assert job.payload == {"audio_file_id": body["audio_file_id"]}
    assert job.trace_id  # the request's trace id travels with the job
    assert queue.depth() == 1

    assert client.get(f"/jobs/{job.id}", headers=CHRIS).json()["status"] == "queued"
    pending = client.get(f"/episodes/{ep.id}/transcript", headers=CHRIS)
    assert pending.status_code == 202
    assert pending.json()["job"]["id"] == job.id


def test_worker_transcribes_and_moves_the_episode(
    client, db, local_storage, queue, monkeypatch
):
    monkeypatch.setattr(
        "edlo.jobs.transcribe.transcribe_file", lambda path, checksum: FAKE
    )
    ep = _episode(db)
    target = _upload(client, ep.id)
    job_id = _complete(client, ep.id, target).json()["job_id"]

    (message,) = queue.receive(wait_seconds=0)
    process(queue, message)

    job = db.get(Job, job_id)
    db.refresh(job)
    assert job.status == "succeeded" and job.lease_owner is None and job.attempt == 1
    assert queue.depth() == 0 and queue.receive(wait_seconds=0) == []  # acked
    t = client.get(f"/episodes/{ep.id}/transcript", headers=CHRIS)
    assert t.status_code == 200
    assert [s["text"] for s in t.json()["segments"]] == ["hello", "sozzled", "pod"]
    history = client.get(f"/episodes/{ep.id}/history", headers=CHRIS).json()
    assert history[-1]["to"] == "mixing" and history[-1]["actor"] == "system"


def test_corrupt_audio_is_a_dead_job_with_a_user_message(
    client, db, local_storage, queue, monkeypatch
):
    def boom(path, checksum):
        raise AudioDecodeError("could not decode audio: Nope")

    monkeypatch.setattr("edlo.jobs.transcribe.transcribe_file", boom)
    ep = _episode(db)
    target = _upload(client, ep.id)
    job_id = _complete(client, ep.id, target).json()["job_id"]

    (message,) = queue.receive(wait_seconds=0)
    process(queue, message)

    view = client.get(f"/jobs/{job_id}", headers=CHRIS).json()
    assert view["status"] == "dead" and view["error_class"] == "AudioDecodeError"
    assert "could not be read" in view["user_message"]
    assert queue.receive(wait_seconds=0) == []  # acked: a retry cannot help
    assert client.get(f"/episodes/{ep.id}/transcript", headers=CHRIS).status_code == 202
    assert (
        db.get(AudioFile, view and db.get(Job, job_id).payload["audio_file_id"]).status
        == "ready"
    )


def test_download_keeps_the_uploaded_filename(client, db, local_storage, queue):
    ep = _episode(db)
    target = _upload(client, ep.id, filename="../Ep 42 rough mix.wav")
    _complete(client, ep.id, target)

    dl = client.get(f"/episodes/{ep.id}/audio/rough/download-url", headers=CHRIS).json()
    assert dl["filename"] == "Ep 42 rough mix.wav"  # directories stripped, name kept
    got = client.get(dl["url"])
    assert got.status_code == 200
    # Starlette writes non-token names RFC 5987 style; browsers decode it.
    assert "Ep 42 rough mix.wav" in unquote(got.headers["content-disposition"])


def test_playback_url_does_not_stamp_the_handoff(client, db, local_storage, queue):
    ep = _episode(db)
    target = _upload(client, ep.id)
    done = _complete(client, ep.id, target).json()

    play = client.get(
        f"/episodes/{ep.id}/audio/rough/download-url?stamp=false", headers=CHRIS
    )
    assert play.status_code == 200 and play.json()["url"]
    assert db.get(AudioFile, done["audio_file_id"]).first_downloaded_at is None

    client.get(f"/episodes/{ep.id}/audio/rough/download-url", headers=CHRIS)
    assert db.get(AudioFile, done["audio_file_id"]).first_downloaded_at is not None


def test_transcript_requires_a_bearer(client):
    assert client.get("/episodes/x/transcript").status_code == 401
    assert client.get("/jobs/x").status_code == 401


def test_transcript_row_is_written_by_the_worker(db, local_storage, queue, monkeypatch):
    monkeypatch.setattr(
        "edlo.jobs.transcribe.transcribe_file", lambda path, checksum: FAKE
    )
    ep = _episode(db)
    key = local_storage.new_key(episode_id=ep.id, kind="rough", filename="a.wav")
    p = local_storage.path(key)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(DATA)
    audio = AudioFile(
        episode_id=ep.id,
        kind="rough",
        storage_key=key,
        status="ready",
        size_bytes=len(DATA),
        checksum=CHECKSUM,
        uploaded_by="u_albert",
    )
    db.add(audio)
    db.commit()

    from edlo.jobs.transcribe import transcribe_audio

    transcribe_audio({"audio_file_id": audio.id})
    row = db.query(Transcript).filter_by(audio_file_id=audio.id).one()
    assert (row.segment_count, row.duration_ms) == (3, 10_000)
    assert local_storage.head(row.storage_key) is not None
