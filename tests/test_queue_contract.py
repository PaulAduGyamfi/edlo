"""ONE suite, run against BOTH backends. Same rule as the storage contract."""

import boto3
import fakeredis
import pytest
from moto import mock_aws

from edlo.queue.rq_queue import RQQueue
from edlo.queue.sqs_queue import SQSQueue


@pytest.fixture(params=["rq", "sqs"])
def queue(request):
    if request.param == "rq":
        yield RQQueue(
            "redis://unused", connection=fakeredis.FakeRedis(), visibility_timeout=30
        )
    else:
        with mock_aws():
            url = boto3.client("sqs", region_name="us-east-1").create_queue(
                QueueName="test"
            )["QueueUrl"]
            yield SQSQueue(url, "us-east-1", visibility_timeout=30)


def test_roundtrip(queue):
    assert queue.depth() == 0
    queue.enqueue("transcribe", {"audio_file_id": "a3"})
    assert queue.depth() == 1
    (m,) = queue.receive(wait_seconds=0)
    assert (m.kind, m.payload, m.receive_count) == (
        "transcribe",
        {"audio_file_id": "a3"},
        1,
    )
    queue.ack(m)
    assert queue.depth() == 0
    assert queue.receive(wait_seconds=0) == []  # acked: never comes back


def test_unacked_message_redelivers(queue):
    """The at-least-once contract, asserted rather than assumed."""
    queue.enqueue("transcribe", {"audio_file_id": "a3"})
    m = queue.receive(wait_seconds=0)[0]
    assert queue.receive(wait_seconds=0) == []  # invisible while leased
    queue.extend_lease(m, seconds=0)  # expire the lease immediately
    again = queue.receive(wait_seconds=0)
    assert again, "message should be redelivered"
    assert again[0].receive_count == 2


def test_receive_respects_the_batch_cap(queue):
    for i in range(3):
        queue.enqueue("transcribe", {"i": i})
    assert len(queue.receive(max_messages=2, wait_seconds=0)) == 2
    assert queue.depth() == 1


def test_a_zero_lease_hands_the_message_straight_back(queue):
    """What a draining worker does with a message it received but will not run."""
    queue.enqueue("plan", {"job_id": "j1"})
    (m,) = queue.receive(wait_seconds=0)
    assert queue.receive(wait_seconds=0) == []  # in flight: invisible to others
    queue.extend_lease(m, 0)
    (again,) = queue.receive(wait_seconds=0)
    assert again.payload == {"job_id": "j1"}
