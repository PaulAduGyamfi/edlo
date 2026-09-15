from functools import lru_cache
from typing import Any

from edlo.config import get_settings
from edlo.queue.base import JobQueue, Message


@lru_cache(maxsize=1)
def get_queue() -> JobQueue:
    s = get_settings()
    if s.queue_backend == "sqs":
        if not s.sqs_queue_url:
            raise RuntimeError("queue_backend=sqs requires sqs_queue_url")
        from edlo.queue.sqs_queue import SQSQueue

        return SQSQueue(
            s.sqs_queue_url,
            s.s3_region,
            visibility_timeout=s.sqs_visibility_timeout_seconds,
            wait_seconds=s.sqs_wait_time_seconds,
        )
    from edlo.queue.rq_queue import RQQueue

    return RQQueue(s.redis_url, visibility_timeout=s.sqs_visibility_timeout_seconds)


def enqueue(kind: str, payload: dict[str, Any]) -> str:
    return get_queue().enqueue(kind, payload)


__all__ = ["JobQueue", "Message", "enqueue", "get_queue"]
