from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class UploadTarget:
    """Everything the browser needs to upload one object."""

    url: str
    method: str  # "POST" (S3 presigned) or "PUT" (dev route)
    fields: dict[str, str]  # form fields for POST; empty for PUT
    headers: dict[str, str]
    key: str
    expires_in: int


@dataclass(frozen=True)
class StoredObject:
    key: str
    size_bytes: int
    checksum_sha256: str  # HEX, always. See the note in s3.py.
    content_type: str


@runtime_checkable
class Storage(Protocol):
    """
    The one boundary between Edlo and where bytes live.

    Nothing outside edlo/storage/ may import boto3.
    Nothing inside edlo/storage/ may import Episode, AudioFile or any model.
    That bidirectional ignorance is what makes both sides testable.
    """

    def new_key(self, *, episode_id: str, kind: str, filename: str) -> str: ...

    def presign_upload(
        self, *, key: str, content_type: str, max_bytes: int
    ) -> UploadTarget: ...

    def presign_download(self, *, key: str, filename: str, expires_in: int) -> str: ...

    def head(self, key: str) -> StoredObject | None: ...

    def download_to_path(self, *, key: str, dest: str) -> str:
        """Copy the object to scratch disk. THE CALLER MUST DELETE `dest`."""
        ...

    def upload_from_path(
        self, *, key: str, src: str, content_type: str
    ) -> StoredObject: ...

    def delete(self, key: str) -> None: ...
