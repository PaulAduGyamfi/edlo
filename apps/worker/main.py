"""
The worker loop.

The five lines that carry this file: ack AFTER the commit, not before;
permanent failures get acked; the heartbeat thread; SIGTERM drains rather than
aborts; and the lease claim that makes redelivery safe.
"""

import glob
import os
import signal
import socket
import tempfile
import threading

from edlo.config import get_settings
from edlo.db import get_sessionmaker
from edlo.jobs import (
    LEASE_SECONDS,
    PermanentFailure,
    claim_job,
    extend_job_lease,
    mark_dead,
    mark_failed,
    mark_succeeded,
)
from edlo.jobs.transcribe import transcribe_audio
from edlo.logging import configure_logging, log
from edlo.queue import get_queue
from edlo.queue.base import JobQueue, Message

HANDLERS = {"transcribe": transcribe_audio}
WORKER_ID = f"{socket.gethostname()}-{os.getpid()}"
_shutdown = threading.Event()


def _sigterm(*_) -> None:
    # ECS sends SIGTERM, waits stopTimeout, then SIGKILL. Stop taking NEW
    # work but let the current job finish. If it cannot finish in time, the
    # visibility timeout returns the message and the idempotent handler
    # makes the retry safe. This is what makes rolling deploys safe.
    log.info("worker_draining", worker=WORKER_ID)
    _shutdown.set()


def sweep_scratch() -> None:
    """For the case where the process was SIGKILLed before a finally could run."""
    for stale in glob.glob(os.path.join(tempfile.gettempdir(), "edlo-*")):
        try:
            os.unlink(stale)
            log.info("swept_stale_scratch", path=stale)
        except OSError:
            pass


def heartbeat(
    queue: JobQueue,
    message: Message,
    job_id: str | None,
    stop: threading.Event,
    every: int = 60,
) -> None:
    while not stop.wait(every):
        try:
            queue.extend_lease(message, seconds=LEASE_SECONDS)
            if job_id:
                with get_sessionmaker()() as db:
                    extend_job_lease(db, job_id, WORKER_ID, LEASE_SECONDS)
        except Exception as e:  # noqa: BLE001 - a missed heartbeat must not kill the job
            log.warning("lease_extend_failed", error=type(e).__name__)


def process(queue: JobQueue, message: Message) -> None:
    job_id = message.payload.get("job_id")
    Session = get_sessionmaker()
    handler = HANDLERS.get(message.kind)
    if handler is None:
        log.error("unknown_job_kind", kind=message.kind, message_id=message.id)
        if job_id:
            with Session() as db:
                mark_dead(
                    db, job_id, PermanentFailure(f"unknown job kind {message.kind!r}")
                )
        queue.ack(message)
        return

    if job_id:
        with Session() as db:
            claimed = claim_job(db, job_id, WORKER_ID)
        if claimed is None:
            # Finished already, or another worker holds a live lease. A
            # redelivered message for done work is the normal case here.
            log.info("job_not_claimable", job_id=job_id, worker=WORKER_ID)
            queue.ack(message)
            return

    stop = threading.Event()
    threading.Thread(
        target=heartbeat, args=(queue, message, job_id, stop), daemon=True
    ).start()
    log.info(
        "job_started", job_id=job_id, kind=message.kind, attempt=message.receive_count
    )
    try:
        handler(message.payload)
        if job_id:
            with Session() as db:
                mark_succeeded(db, job_id)
        queue.ack(message)  # ack LAST, after a durable commit
        log.info("job_succeeded", job_id=job_id, kind=message.kind)
    except PermanentFailure as e:
        # A corrupt WAV will still be corrupt on attempt three. Ack it so it
        # does NOT reach the DLQ -- keeping the DLQ clean is what makes a
        # `depth > 0` alarm actionable instead of noise you learn to ignore.
        if job_id:
            with Session() as db:
                mark_dead(db, job_id, e)
        queue.ack(message)
        log.warning("job_dead", job_id=job_id, kind=message.kind, error=str(e))
    except Exception as e:  # noqa: BLE001 - anything else is transient by definition
        # Transient. Do NOT ack. Visibility expires, the queue redelivers,
        # and after maxReceiveCount the message lands in the DLQ.
        if job_id:
            with Session() as db:
                mark_failed(db, job_id, e, message.receive_count)
        log.error(
            "job_failed",
            job_id=job_id,
            kind=message.kind,
            attempt=message.receive_count,
            error=f"{type(e).__name__}: {e}",
        )
    finally:
        stop.set()


def main() -> None:
    configure_logging()
    signal.signal(signal.SIGTERM, _sigterm)
    signal.signal(signal.SIGINT, _sigterm)
    queue = get_queue()
    sweep_scratch()
    log.info("worker_started", worker=WORKER_ID, backend=get_settings().queue_backend)
    while not _shutdown.is_set():
        try:
            messages = queue.receive(max_messages=1, wait_seconds=20)
        except Exception as e:  # noqa: BLE001 - the loop outlives any single failed poll
            log.warning("receive_failed", error=f"{type(e).__name__}: {e}")
            _shutdown.wait(5)
            continue
        for m in messages:
            if _shutdown.is_set():
                break  # do not start new work while draining
            process(queue, m)
    log.info("worker_stopped", worker=WORKER_ID)


if __name__ == "__main__":
    main()
