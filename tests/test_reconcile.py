from datetime import UTC, datetime, timedelta

from apps.worker import main as worker
from edlo.models import Job
from tests.test_worker import StubQueue


class RecordingQueue(StubQueue):
    def __init__(self):
        super().__init__()
        self.sent: list[tuple[str, dict]] = []

    def enqueue(self, kind, payload, *, delay_seconds=0):
        self.sent.append((kind, payload))
        return "m"


def test_reconciler_reenqueues_only_old_untouched_queued_jobs(db, engine):
    old = datetime.now(UTC) - timedelta(minutes=5)
    stale = Job(
        kind="transcribe",
        episode_id="e",
        payload={"audio_file_id": "a"},
        idempotency_key="1",
        created_at=old,
    )
    fresh = Job(kind="transcribe", episode_id="e", payload={}, idempotency_key="2")
    tried = Job(
        kind="transcribe",
        episode_id="e",
        payload={},
        idempotency_key="3",
        attempt=1,
        status="failed",
        created_at=old,
    )
    done = Job(
        kind="transcribe",
        episode_id="e",
        payload={},
        idempotency_key="4",
        status="succeeded",
        created_at=old,
    )
    db.add_all([stale, fresh, tried, done])
    db.commit()

    q = RecordingQueue()
    assert worker.reconcile(q) == 1
    assert q.sent == [("transcribe", {"job_id": stale.id, "audio_file_id": "a"})]
