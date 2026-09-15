"""
ONE suite, run against BOTH backends.

THE RULE: if this file ever needs `if isinstance(storage, S3Storage)`,
the abstraction has leaked and the migration will hurt.
"""

import boto3
import pytest
from moto import mock_aws

from edlo.storage.keys import UnsafeKey, UnsupportedMedia
from edlo.storage.local import LocalStorage
from edlo.storage.s3 import S3Storage

EP = "a" * 32


@pytest.fixture(params=["local", "s3"])
def storage(request, tmp_path):
    if request.param == "local":
        yield LocalStorage(tmp_path)
    else:
        with mock_aws():  # no AWS account, no network
            boto3.client("s3", region_name="us-east-1").create_bucket(Bucket="test")
            yield S3Storage("test", "us-east-1")


def test_roundtrip(storage, tmp_path):
    src = tmp_path / "in.wav"
    src.write_bytes(b"RIFF" + b"\0" * 2048)
    key = storage.new_key(episode_id=EP, kind="final", filename="mix.wav")
    stored = storage.upload_from_path(key=key, src=str(src), content_type="audio/wav")
    assert stored.size_bytes == 2052
    out = tmp_path / "out.wav"
    storage.download_to_path(key=key, dest=str(out))
    assert out.read_bytes() == src.read_bytes()


def test_checksum_is_hex_on_both_backends(storage, tmp_path):
    """The bug that would have silently invalidated every cache key."""
    src = tmp_path / "a.wav"
    src.write_bytes(b"\0" * 64)
    key = storage.new_key(episode_id=EP, kind="final", filename="a.wav")
    obj = storage.upload_from_path(key=key, src=str(src), content_type="audio/wav")
    assert len(obj.checksum_sha256) == 64
    assert all(c in "0123456789abcdef" for c in obj.checksum_sha256)


def test_missing_object_returns_none(storage):
    assert storage.head(f"episodes/{EP}/final/{'b' * 32}.wav") is None


def test_traversal_keys_rejected(storage):
    for bad in ["../../etc/passwd", f"episodes/{EP}/final/../../x.wav", "/etc/passwd"]:
        with pytest.raises((UnsafeKey, ValueError)):
            storage.head(bad)


def test_video_extension_rejected(storage):
    with pytest.raises(UnsupportedMedia):
        storage.new_key(episode_id=EP, kind="final", filename="sneaky.mov")


def test_delete_is_idempotent(storage):
    key = storage.new_key(episode_id=EP, kind="rough", filename="a.wav")
    storage.delete(key)
    storage.delete(key)  # must not raise
