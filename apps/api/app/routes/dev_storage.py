"""
Dev stand-in for S3. LocalStorage's upload targets and download URLs point
here so the browser follows the same steps it does against a presigned URL.
Mounted only when STORAGE_BACKEND=local (see main.py).
"""

from pathlib import PurePosixPath

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import FileResponse

from edlo.storage import get_storage
from edlo.storage.keys import UnsafeKey
from edlo.storage.local import LocalStorage

router = APIRouter(prefix="/dev/storage", tags=["dev"])


def _local() -> LocalStorage:
    storage = get_storage()
    if not isinstance(storage, LocalStorage):
        raise HTTPException(404, "not found")
    return storage


@router.put("/{key:path}", status_code=204)
async def put_object(key: str, request: Request) -> Response:
    try:
        path = _local().path(key)
    except UnsafeKey as e:
        raise HTTPException(400, str(e))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as f:
        async for chunk in request.stream():
            f.write(chunk)
    return Response(status_code=204)


@router.get("/{key:path}")
def get_object(key: str, filename: str | None = None) -> FileResponse:
    try:
        path = _local().path(key)
    except UnsafeKey as e:
        raise HTTPException(400, str(e))
    if not path.exists():
        raise HTTPException(404, "no such object")
    # Like S3's response-content-disposition: the download gets its uploaded name.
    return FileResponse(
        path, filename=PurePosixPath(filename).name if filename else path.name
    )
