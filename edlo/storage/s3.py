import base64
import binascii
from typing import Any

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from edlo.storage.base import StoredObject, UploadTarget
from edlo.storage.keys import assert_safe_key, build_key


def _b64_to_hex(b64: str) -> str:
    """
    S3 returns SHA-256 checksums base64-encoded. LocalStorage returns hex.

    Normalising here is not cosmetic: in Chapter 14 the checksum becomes the
    transcription cache key. If the two backends disagreed on format, every
    cached transcript would silently miss after the migration and re-run.
    The contract test asserts this.
    """
    return binascii.hexlify(base64.b64decode(b64)).decode() if b64 else ""


class S3Storage:
    def __init__(self, bucket: str, region: str, endpoint_url: str | None = None):
        self.bucket = bucket
        # The bucket enforces AES256 by default (terraform/s3.tf). Asking per
        # request as well is belt and braces on AWS, but MinIO rejects it
        # without a KMS, so only send it to real S3.
        self._sse = {} if endpoint_url else {"x-amz-server-side-encryption": "AES256"}
        self.client = boto3.client(
            "s3",
            region_name=region,
            endpoint_url=endpoint_url,
            config=Config(
                signature_version="s3v4",
                retries={"max_attempts": 5, "mode": "adaptive"},
            ),
        )

    def new_key(self, *, episode_id, kind, filename) -> str:
        return build_key(episode_id=episode_id, kind=kind, filename=filename)

    def presign_upload(self, *, key, content_type, max_bytes) -> UploadTarget:
        assert_safe_key(key)
        conditions: list[Any] = [
            {"Content-Type": content_type},
            *({k: v} for k, v in self._sse.items()),
            {"x-amz-checksum-algorithm": "SHA256"},
            # The browser posts the digest it computed; S3 verifies it on
            # receipt and stores it, which is what head() reads back.
            ["starts-with", "$x-amz-checksum-sha256", ""],
            # S3 enforces this itself. A presigned PUT cannot.
            ["content-length-range", 1, max_bytes],
        ]
        p = self.client.generate_presigned_post(
            Bucket=self.bucket,
            Key=key,
            Fields={
                "Content-Type": content_type,
                **self._sse,
                "x-amz-checksum-algorithm": "SHA256",
            },
            Conditions=conditions,
            ExpiresIn=900,
        )
        return UploadTarget(
            url=p["url"],
            method="POST",
            fields=p["fields"],
            headers={},
            key=key,
            expires_in=900,
        )

    def presign_download(self, *, key, filename, expires_in) -> str:
        assert_safe_key(key)
        return self.client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": self.bucket,
                "Key": key,
                "ResponseContentDisposition": f'attachment; filename="{filename}"',
            },
            ExpiresIn=expires_in,
        )

    def head(self, key) -> StoredObject | None:
        assert_safe_key(key)
        try:
            r = self.client.head_object(
                Bucket=self.bucket, Key=key, ChecksumMode="ENABLED"
            )
        except ClientError as e:
            if e.response["Error"]["Code"] in ("404", "NoSuchKey", "NotFound"):
                return None
            raise
        return StoredObject(
            key=key,
            size_bytes=r["ContentLength"],
            checksum_sha256=_b64_to_hex(r.get("ChecksumSHA256", "")),
            content_type=r.get("ContentType", "application/octet-stream"),
        )

    def download_to_path(self, *, key, dest) -> str:
        assert_safe_key(key)
        # Managed multipart transfer: parallel ranged GETs, automatic retries,
        # constant memory. NEVER get_object()["Body"].read() on a 200 MB object
        # in a task with 1 GB of memory.
        self.client.download_file(self.bucket, key, dest)
        return dest

    def upload_from_path(self, *, key, src, content_type) -> StoredObject:
        assert_safe_key(key)
        self.client.upload_file(
            src,
            self.bucket,
            key,
            ExtraArgs={
                "ContentType": content_type,
                "ChecksumAlgorithm": "SHA256",
                **({"ServerSideEncryption": "AES256"} if self._sse else {}),
            },
        )
        obj = self.head(key)
        assert obj is not None
        return obj

    def delete(self, key) -> None:
        assert_safe_key(key)
        self.client.delete_object(Bucket=self.bucket, Key=key)
