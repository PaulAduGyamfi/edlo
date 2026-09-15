import hashlib
from datetime import date

import pytest
from pydantic import ValidationError

from edlo.models import AudioFile, Episode, Transcript
from edlo.transcription.engine import AudioDecodeError
from edlo.transcription.schema import TranscriptArtifact, TranscriptSegment

ALBERT = {"Authorization": "Bearer albert-token"}
CHRIS = {"Authorization": "Bearer chris-token"}
DATA = b"RIFF" + bytes(range(256)) * 8
CHECKSUM = hashlib.sha256(DATA).hexdigest()


def seg(i, start, end, text="words here"):
    return TranscriptSegment(index=i, start_ms=start, end_ms=end, text=text)


def artifact(segments, duration_ms=10_000):
    return TranscriptArtifact(
        audio_checksum=CHECKSUM,
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


# ---- the route: transcribe when the upload completes ----


def _episode(db) -> Episode:
    ep = Episode(title="Test", recorded_on=date(2026, 3, 1))
    db.add(ep)
    db.commit()
    return ep


def _upload(client, episode_id) -> dict:
    target = client.post(
        f"/episodes/{episode_id}/audio/upload-target",
        json={
            "kind": "rough",
            "filename": "a.wav",
            "content_type": "audio/wav",
            "size_bytes": 1,
        },
        headers=ALBERT,
    ).json()
    assert (
        client.put(target["url"], content=DATA, headers=target["headers"]).status_code
        == 204
    )
    return target


def test_complete_transcribes_and_serves_the_transcript(
    client, db, local_storage, monkeypatch
):
    fake = artifact(
        [
            seg(0, 0, 1000, "hello"),
            seg(1, 1000, 2000, "sozzled"),
            seg(2, 2000, 3000, "pod"),
        ]
    )
    seen = []
    monkeypatch.setattr(
        "apps.api.app.routes.audio.transcribe_file",
        lambda path, checksum: seen.append(checksum) or fake,
    )
    ep = _episode(db)
    target = _upload(client, ep.id)

    r = client.post(
        f"/episodes/{ep.id}/audio/complete",
        json={"key": target["key"], "checksum_sha256": CHECKSUM},
        headers=ALBERT,
    )
    assert r.status_code == 201, r.text
    assert r.json()["transcript_error"] is None
    assert seen == [CHECKSUM]

    row = db.query(Transcript).filter_by(episode_id=ep.id).one()
    assert row.id == r.json()["transcript_id"]
    assert (row.segment_count, row.duration_ms, row.engine) == (3, 10_000, "fake")
    assert local_storage.head(row.storage_key) is not None  # the artifact is in storage

    t = client.get(f"/episodes/{ep.id}/transcript", headers=CHRIS)
    assert t.status_code == 200
    assert t.json()["id"] == row.id
    assert [s["text"] for s in t.json()["segments"]] == ["hello", "sozzled", "pod"]


def test_transcription_failure_keeps_the_audio(client, db, local_storage, monkeypatch):
    def boom(path, checksum):
        raise AudioDecodeError("could not decode audio: Nope")

    monkeypatch.setattr("apps.api.app.routes.audio.transcribe_file", boom)
    ep = _episode(db)
    target = _upload(client, ep.id)

    r = client.post(
        f"/episodes/{ep.id}/audio/complete",
        json={"key": target["key"], "checksum_sha256": CHECKSUM},
        headers=ALBERT,
    )
    assert r.status_code == 201
    assert r.json()["transcript_id"] is None
    assert "could not decode" in r.json()["transcript_error"]
    assert db.get(AudioFile, r.json()["audio_file_id"]).status == "ready"
    assert client.get(f"/episodes/{ep.id}/transcript", headers=CHRIS).status_code == 404


def test_transcript_requires_a_bearer(client):
    assert client.get("/episodes/x/transcript").status_code == 401
