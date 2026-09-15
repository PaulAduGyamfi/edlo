"""
Redis-backed queue for development.

A list holds waiting messages; a sorted set holds in-flight messages keyed by
their visibility deadline. Ack removes the entry; an expired deadline puts the
message back at the front. That gives the same at-least-once, visibility-timeout
semantics as SQS, so the worker loop is identical in both environments.
"""

import json
import time
from typing import Any
from uuid import uuid4

from redis import Redis
from redis.exceptions import TimeoutError as RedisTimeout

from edlo.queue.base import Message


class RQQueue:
    def __init__(
        self,
        url: str,
        *,
        connection: Redis | None = None,
        name: str = "edlo",
        visibility_timeout: int = 300,
        max_receive_count: int = 3,
    ):
        # redis-py's return types are unions of bytes/str/list; we only use
        # it with decode_responses off, so treat the client as untyped.
        # A blocking pop waits up to `wait_seconds`; the socket timeout has to
        # outlast it or the client gives up on Redis while Redis is still fine.
        self.redis: Any = connection or Redis.from_url(url, socket_timeout=60)
        self.ready = f"{name}:ready"
        self.inflight = f"{name}:inflight"
        self.dead = f"{name}:dead"  # the dead-letter list
        self.visibility_timeout = visibility_timeout
        self.max_receive_count = max_receive_count

    def enqueue(
        self, kind: str, payload: dict[str, Any], *, delay_seconds: int = 0
    ) -> str:
        msg: dict[str, Any] = {
            "id": uuid4().hex,
            "kind": kind,
            "payload": payload,
            "receive_count": 0,
        }
        if delay_seconds:
            # A delayed message is an in-flight message nobody holds.
            self.redis.zadd(
                self.inflight, {json.dumps(msg): time.time() + delay_seconds}
            )
        else:
            self.redis.lpush(self.ready, json.dumps(msg))
        return msg["id"]

    def _requeue_expired(self) -> None:
        now = time.time()
        for raw in self.redis.zrangebyscore(self.inflight, 0, now):
            if self.redis.zrem(self.inflight, raw):  # we won the race for it
                self.redis.rpush(self.ready, raw)  # back at the front

    def receive(
        self, *, max_messages: int = 1, wait_seconds: int = 20
    ) -> list[Message]:
        self._requeue_expired()
        out: list[Message] = []
        while len(out) < max_messages:
            if not out and wait_seconds > 0:
                try:
                    popped = self.redis.brpop(
                        [self.ready], timeout=min(wait_seconds, 30)
                    )
                except RedisTimeout:
                    popped = None  # nothing arrived; the caller polls again
                raw = popped[1] if popped else None
            else:
                raw = self.redis.rpop(self.ready)
            if raw is None:
                break
            msg = json.loads(raw)
            msg["receive_count"] += 1
            if msg["receive_count"] > self.max_receive_count:
                self.redis.lpush(self.dead, json.dumps(msg))
                continue
            packed = json.dumps(msg)
            self.redis.zadd(
                self.inflight, {packed: time.time() + self.visibility_timeout}
            )
            out.append(
                Message(
                    id=msg["id"],
                    kind=msg["kind"],
                    payload=msg["payload"],
                    receive_count=msg["receive_count"],
                    raw=packed,
                )
            )
        return out

    def ack(self, message: Message) -> None:
        self.redis.zrem(self.inflight, message.raw)

    def extend_lease(self, message: Message, seconds: int) -> None:
        self.redis.zadd(self.inflight, {message.raw: time.time() + seconds}, xx=True)

    def depth(self) -> int:
        return int(self.redis.llen(self.ready))
