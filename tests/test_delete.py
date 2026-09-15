from datetime import date

from apps.worker.main import process
from edlo.models import (
    AudioFile,
    Episode,
    Job,
    PostingSlot,
    StageTransition,
    Transcript,
)
from tests.test_transcription import ALBERT, CHRIS, FAKE, _complete, _upload

PAUL = {"Authorization": "Bearer paul-token"}


def _registered(client, title="Doomed") -> dict:
    return client.post(
        "/episodes", json={"title": title, "recorded_on": "2026-09-01"}, headers=ALBERT
    ).json()


def _transcribed(client, db, queue, monkeypatch, title="Doomed") -> dict:
    """An episode with audio, a finished job, a transcript and a history."""
    monkeypatch.setattr(
        "edlo.jobs.transcribe.transcribe_file", lambda path, checksum: FAKE
    )
    ep = _registered(client, title)
    target = _upload(client, ep["id"])
    _complete(client, ep["id"], target)
    (message,) = queue.receive(wait_seconds=0)
    process(queue, message)
    return ep


def test_delete_removes_everything_the_episode_owned(
    client, db, local_storage, queue, monkeypatch
):
    ep = _transcribed(client, db, queue, monkeypatch)
    audio_key = db.query(AudioFile).filter_by(episode_id=ep["id"]).one().storage_key
    transcript_key = (
        db.query(Transcript).filter_by(episode_id=ep["id"]).one().storage_key
    )
    assert local_storage.head(audio_key) and local_storage.head(transcript_key)
    slot_date = date.fromisoformat(ep["publish_on"])

    r = client.delete(f"/episodes/{ep['id']}", headers=ALBERT)
    assert r.status_code == 204

    db.expire_all()
    assert db.get(Episode, ep["id"]) is None
    for model in (AudioFile, Transcript, Job, StageTransition, PostingSlot):
        assert db.query(model).filter_by(episode_id=ep["id"]).count() == 0, (
            model.__name__
        )
    assert (
        local_storage.head(audio_key) is None
        and local_storage.head(transcript_key) is None
    )
    assert ep["id"] not in {e["id"] for e in client.get("/episodes").json()}
    assert client.get(f"/episodes/{ep['id']}/history", headers=CHRIS).json() == []
    # the posting slot is free again
    again = client.post(
        "/episodes", json={"title": "Next", "recorded_on": "2026-09-01"}, headers=ALBERT
    ).json()
    assert date.fromisoformat(again["publish_on"]) == slot_date


def test_delete_keeps_a_transcript_artifact_another_episode_shares(
    client, db, local_storage, queue, monkeypatch
):
    first = _transcribed(client, db, queue, monkeypatch, "First")
    second = _transcribed(
        client, db, queue, monkeypatch, "Second"
    )  # same bytes: cache hit
    keys = {t.episode_id: t.storage_key for t in db.query(Transcript).all()}
    assert keys[first["id"]] == keys[second["id"]]

    assert client.delete(f"/episodes/{first['id']}", headers=PAUL).status_code == 204

    assert local_storage.head(keys[second["id"]]) is not None
    assert (
        client.get(f"/episodes/{second['id']}/transcript", headers=CHRIS).status_code
        == 200
    )


def test_delete_is_gated(client, db, local_storage, queue):
    ep = _registered(client)
    assert client.delete(f"/episodes/{ep['id']}").status_code == 401
    assert client.delete(f"/episodes/{ep['id']}", headers=CHRIS).status_code == 403
    assert client.delete("/episodes/nope", headers=ALBERT).status_code == 404

    published = Episode(title="Out", recorded_on=date(2026, 3, 1), stage="published")
    db.add(published)
    db.commit()
    r = client.delete(f"/episodes/{published.id}", headers=PAUL)
    assert r.status_code == 409 and db.get(Episode, published.id) is not None


def test_a_queued_job_for_a_deleted_episode_is_dropped_cleanly(
    client, db, local_storage, queue, monkeypatch
):
    ran = []
    monkeypatch.setattr(
        "edlo.jobs.transcribe.transcribe_file",
        lambda path, checksum: ran.append(1) or FAKE,
    )
    ep = _registered(client)
    target = _upload(client, ep["id"])
    _complete(client, ep["id"], target)  # message waiting, job row queued

    assert client.delete(f"/episodes/{ep['id']}", headers=ALBERT).status_code == 204

    (message,) = queue.receive(wait_seconds=0)
    process(queue, message)  # the row is gone: nothing to claim, ack and move on
    assert ran == [] and queue.receive(wait_seconds=0) == []
