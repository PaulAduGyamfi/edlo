from functools import lru_cache

from edlo.config import get_settings
from edlo.storage.base import Storage, StoredObject, UploadTarget


@lru_cache(maxsize=1)
def get_storage() -> Storage:
    s = get_settings()
    if s.storage_backend == "s3":
        if not s.s3_bucket:
            raise RuntimeError("storage_backend=s3 requires s3_bucket")
        from edlo.storage.s3 import S3Storage

        return S3Storage(s.s3_bucket, s.s3_region, s.s3_endpoint_url)
    from edlo.storage.local import LocalStorage

    return LocalStorage(s.upload_dir)


__all__ = ["Storage", "StoredObject", "UploadTarget", "get_storage"]
