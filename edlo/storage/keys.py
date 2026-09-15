"""
Storage keys. Shared by every backend; was inline in storage.py.
"""

import re
from pathlib import PurePosixPath
from uuid import uuid4

ALLOWED_EXTENSIONS = {".wav", ".mp3", ".m4a", ".aiff", ".flac"}
KEY_RE = re.compile(
    r"^episodes/[a-f0-9]{32}/(rough|final)/[a-f0-9]{32}\.[a-z0-9]{2,5}$"
)


class UnsafeKey(ValueError): ...


class UnsupportedMedia(ValueError): ...


def build_key(*, episode_id: str, kind: str, filename: str) -> str:
    ext = PurePosixPath(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise UnsupportedMedia(f"{ext!r} is not an accepted audio format")
    if kind not in {"rough", "final"}:
        raise UnsafeKey(f"unknown kind {kind!r}")
    return f"episodes/{episode_id}/{kind}/{uuid4().hex}{ext}"


def assert_safe_key(key: str) -> str:
    """
    Allowlist, never blocklist. A pattern describing exactly the keys we
    generate cannot be defeated by encoding tricks.
    """
    if not KEY_RE.match(key):
        raise UnsafeKey("storage key does not match the expected pattern")
    return key
