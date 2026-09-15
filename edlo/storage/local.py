"""
Local filesystem storage. Development and tests; S3 everywhere deployed.

Its "presigned URLs" point at the /dev/storage routes, which stand in for S3.
"""

import hashlib
import shutil
from pathlib import Path
from urllib.parse import urlencode

from edlo.storage.base import StoredObject, UploadTarget
from edlo.storage.keys import UnsafeKey, assert_safe_key, build_key

CHUNK = 1024 * 1024


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

    def new_key(self, *, episode_id: str, kind: str, filename: str) -> str:
        return build_key(episode_id=episode_id, kind=kind, filename=filename)

    def presign_upload(
        self, *, key: str, content_type: str, max_bytes: int
    ) -> UploadTarget:
        assert_safe_key(key)
        return UploadTarget(
            url=f"/dev/storage/{key}",
            method="PUT",
            fields={},
            headers={"Content-Type": content_type},
            key=key,
            expires_in=900,
        )

    def presign_download(self, *, key: str, filename: str, expires_in: int) -> str:
        assert_safe_key(key)
        return f"/dev/storage/{key}?{urlencode({'filename': filename})}"

    def head(self, key: str) -> StoredObject | None:
        p = self.path(key)
        if not p.exists():
            return None
        h = hashlib.sha256()
        with p.open("rb") as f:
            for chunk in iter(lambda: f.read(CHUNK), b""):
                h.update(chunk)
        return StoredObject(
            key=key,
            size_bytes=p.stat().st_size,
            checksum_sha256=h.hexdigest(),
            content_type="application/octet-stream",
        )

    def download_to_path(self, *, key: str, dest: str) -> str:
        shutil.copyfile(self.path(key), dest)
        return dest

    def upload_from_path(
        self, *, key: str, src: str, content_type: str
    ) -> StoredObject:
        p = self.path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, p)
        obj = self.head(key)
        assert obj is not None
        return obj

    def delete(self, key: str) -> None:
        self.path(key).unlink(missing_ok=True)
