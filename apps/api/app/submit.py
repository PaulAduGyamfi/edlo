"""
One way to create a job from a route: idempotency lookup, row committed
FIRST, enqueue AFTER, response remembered. Every job-creating route uses it.
"""

from typing import Any

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from apps.api.app.idempotency import fingerprint, lookup, remember
from edlo.logging import log
from edlo.models import Job
from edlo.queue import enqueue


def replay(
    db: Session, key: str | None, route: str, body: bytes
) -> tuple[str, str, JSONResponse | None]:
    """Validate the key and return (fingerprint, route, stored response or None)."""
    if not key:
        raise HTTPException(400, "Idempotency-Key header required")
    fp = fingerprint(body)
    try:
        stored = lookup(db, key, route, fp)
    except ValueError as e:
        raise HTTPException(409, str(e))
    if stored is None:
        return fp, route, None
    return (
        fp,
        route,
        JSONResponse(stored, status_code=202, headers={"Idempotency-Replayed": "true"}),
    )


def submit_job(
    db: Session,
    request: Request,
    *,
    kind: str,
    episode_id: str,
    payload: dict[str, Any],
    job_key: str,
    idempotency_key: str,
    route: str,
    fp: str,
    extra: dict[str, Any] | None = None,
) -> JSONResponse:
    """Create (or find) the job for `job_key`, enqueue it once, answer 202."""
    job = Job(
        kind=kind,
        episode_id=episode_id,
        payload=payload,
        idempotency_key=job_key,
        trace_id=request.state.trace_id,
    )
    db.add(job)
    created = True
    try:
        db.commit()  # job row committed FIRST
    except IntegrityError:
        db.rollback()
        created = False
        job = db.query(Job).filter_by(kind=kind, idempotency_key=job_key).one()
    if created:
        # Enqueue AFTER the commit. The reverse order lets a worker receive a
        # message for a row that was never committed.
        enqueue(kind, {"job_id": job.id, **payload})
        log.info("job_submitted", kind=kind, job_id=job.id, episode_id=episode_id)
    response = {
        **(extra or {}),
        "replayed": not created,
        "job_id": job.id,
        "poll_url": f"/jobs/{job.id}",
    }
    remember(db, idempotency_key, route, fp, response)
    db.commit()
    return JSONResponse(response, status_code=202)
