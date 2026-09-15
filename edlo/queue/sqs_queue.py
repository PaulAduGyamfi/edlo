import json
from typing import Any

import boto3
from botocore.config import Config

from edlo.queue.base import Message


class SQSQueue:
    def __init__(
        self,
        queue_url: str,
        region: str,
        visibility_timeout: int = 300,
        wait_seconds: int = 20,
    ):
        self.queue_url = queue_url
        self.visibility_timeout = visibility_timeout
        self.default_wait = wait_seconds
        self.client = boto3.client(
            "sqs",
            region_name=region,
            config=Config(retries={"max_attempts": 5, "mode": "adaptive"}),
        )

    def enqueue(
        self, kind: str, payload: dict[str, Any], *, delay_seconds: int = 0
    ) -> str:
        return self.client.send_message(
            QueueUrl=self.queue_url,
            MessageBody=json.dumps({"kind": kind, "payload": payload}),
            DelaySeconds=min(delay_seconds, 900),  # SQS max delay: 15 min
        )["MessageId"]

    def receive(
        self, *, max_messages: int = 1, wait_seconds: int | None = None
    ) -> list[Message]:
        r = self.client.receive_message(
            QueueUrl=self.queue_url,
            MaxNumberOfMessages=min(max_messages, 10),  # SQS hard cap
            WaitTimeSeconds=self.default_wait if wait_seconds is None else wait_seconds,
            VisibilityTimeout=self.visibility_timeout,
            AttributeNames=["ApproximateReceiveCount"],
        )
        out = []
        for m in r.get("Messages", []):
            body = json.loads(m["Body"])
            out.append(
                Message(
                    id=m["MessageId"],
                    kind=body["kind"],
                    payload=body["payload"],
                    receive_count=int(m["Attributes"]["ApproximateReceiveCount"]),
                    raw=m["ReceiptHandle"],
                )
            )
        return out

    def ack(self, message: Message) -> None:
        self.client.delete_message(QueueUrl=self.queue_url, ReceiptHandle=message.raw)

    def extend_lease(self, message: Message, seconds: int) -> None:
        self.client.change_message_visibility(
            QueueUrl=self.queue_url,
            ReceiptHandle=message.raw,
            VisibilityTimeout=min(seconds, 43200),  # SQS max: 12 hours
        )

    def depth(self) -> int:
        r = self.client.get_queue_attributes(
            QueueUrl=self.queue_url, AttributeNames=["ApproximateNumberOfMessages"]
        )
        return int(r["Attributes"]["ApproximateNumberOfMessages"])
