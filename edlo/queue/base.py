from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


@dataclass
class Message:
    id: str
    kind: str
    payload: dict[str, Any]
    receive_count: int  # how many times this message has been delivered
    raw: Any = None  # backend handle used to ack


@runtime_checkable
class JobQueue(Protocol):
    def enqueue(
        self, kind: str, payload: dict[str, Any], *, delay_seconds: int = 0
    ) -> str: ...

    def receive(
        self, *, max_messages: int = 1, wait_seconds: int = 20
    ) -> list[Message]: ...

    def ack(self, message: Message) -> None:
        """Delete. Call ONLY after the work is durably committed."""

    def extend_lease(self, message: Message, seconds: int) -> None:
        """Heartbeat for long jobs. Without this, transcription longer than
        the visibility timeout is delivered twice and processed twice."""

    def depth(self) -> int:
        """Approximate messages waiting. Drives autoscaling and the dashboard."""
