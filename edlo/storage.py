"""
Local filesystem storage.
"""

import hashlib
import re
from pathlib import Path, PurePosixPath
from uuid import uuid4

CHUNK = 1024 * 1024
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


class LocalStorage:
    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def path(self, key: str) -> Path:
        assert_safe_key(key)
        p = (self.root / key).resolve()
        if not p.is_relative_to(self.root):
            raise UnsafeKey("resolved path escaped the storage root")
        return p

    def save_stream(self, key: str, chunks) -> tuple[int, str]:
        """Write while hashing. One pass over the bytes, constant memory."""
        p = self.path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        h, size = hashlib.sha256(), 0
        with p.open("wb") as f:
            for chunk in chunks:
                h.update(chunk)
                size += len(chunk)
                f.write(chunk)
        return size, h.hexdigest()

    def open(self, key: str):
        return self.path(key).open("rb")

    def exists(self, key: str) -> bool:
        return self.path(key).exists()
