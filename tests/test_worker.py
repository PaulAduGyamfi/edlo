"""The loop around the handler: what gets acked, what gets marked, what comes back."""

from apps.worker import main as worker
from edlo.jobs import PermanentFailure
from edlo.models import Job
from edlo.queue.base import Message


class StubQueue:
    def __init__(self):
        self.acked: list[str] = []
        self.leases: list[int] = []

    def ack(self, message):
        self.acked.append(message.id)

    def extend_lease(self, message, seconds):
        self.leases.append(seconds)


def _job(db, **overrides) -> Job:
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


def _msg(job, receive_count=1) -> Message:
    return Message(
        id="m1",
        kind="transcribe",
        payload={"job_id": job.id},
        receive_count=receive_count,
    )


def test_success_marks_then_acks(db, engine, monkeypatch):
    order: list[str] = []
    monkeypatch.setitem(
        worker.HANDLERS, "transcribe", lambda payload: order.append("ran")
    )
    q = StubQueue()
    job = _job(db)

    worker.process(q, _msg(job))

    db.refresh(job)
    assert (job.status, job.attempt, job.lease_owner) == ("succeeded", 1, None)
    assert order == ["ran"] and q.acked == ["m1"]


def test_permanent_failure_is_dead_and_acked(db, engine, monkeypatch):
    def handler(payload):
        try:
            raise ValueError("bad wav")
        except ValueError as e:
            raise PermanentFailure("could not decode") from e

    monkeypatch.setitem(worker.HANDLERS, "transcribe", handler)
    q = StubQueue()
    job = _job(db)

    worker.process(q, _msg(job))

    db.refresh(job)
    assert (
        job.status == "dead" and job.error_class == "ValueError"
    )  # the cause, not the wrapper
    assert q.acked == ["m1"]  # never reaches the DLQ


def test_transient_failure_is_not_acked_and_comes_back(db, engine, monkeypatch):
    calls: list[int] = []

    def flaky(payload):
        calls.append(1)
        raise ConnectionError("s3 hiccup")

    monkeypatch.setitem(worker.HANDLERS, "transcribe", flaky)
    q = StubQueue()
    job = _job(db)

    worker.process(q, _msg(job, receive_count=1))
    db.refresh(job)
    assert (
        job.status == "failed"
        and job.error_class == "ConnectionError"
        and q.acked == []
    )

    worker.process(q, _msg(job, receive_count=2))  # redelivered: claimable again
    db.refresh(job)
    assert job.status == "failed" and job.attempt == 2

    worker.process(q, _msg(job, receive_count=3))  # the last attempt
    db.refresh(job)
    assert job.status == "dead" and job.finished_at is not None and len(calls) == 3


def test_redelivery_of_finished_work_is_acked_without_running(db, engine, monkeypatch):
    ran: list[int] = []
    monkeypatch.setitem(worker.HANDLERS, "transcribe", lambda payload: ran.append(1))
    q = StubQueue()
    job = _job(db, status="succeeded")

    worker.process(q, _msg(job, receive_count=2))

    assert ran == [] and q.acked == ["m1"]


def test_unknown_kind_is_dead_and_acked(db, engine):
    q = StubQueue()
    job = _job(db, kind="mystery")
    worker.process(
        q, Message(id="m2", kind="mystery", payload={"job_id": job.id}, receive_count=1)
    )
    db.refresh(job)
    assert job.status == "dead" and q.acked == ["m2"]
