"""Image storage behind an adapter interface.

Only a local-filesystem implementation exists. An S3-compatible backend would be a new
class implementing the same protocol and a change to `get_storage()` - no caller
changes. Binary image data never goes into the database; rows hold keys only.
"""

from __future__ import annotations

import hashlib
from functools import lru_cache
from pathlib import Path
from typing import Protocol

from app.core.config import settings
from app.core.errors import StorageUnavailableError
from app.core.logging import get_logger

logger = get_logger(__name__)


class Storage(Protocol):
    def put(self, key: str, data: bytes) -> None: ...
    def get(self, key: str) -> bytes: ...
    def delete(self, key: str) -> None: ...
    def exists(self, key: str) -> bool: ...


class LocalStorage:
    """Filesystem storage rooted outside the web root.

    Keys are UUID-based and served only through an authorising endpoint, so files are
    never publicly addressable.
    """

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()

    def _path(self, key: str) -> Path:
        # Resolve and confirm containment: a key must never escape the storage root,
        # even though keys are generated internally rather than supplied by clients.
        candidate = (self.root / key).resolve()
        if not candidate.is_relative_to(self.root):
            raise StorageUnavailableError("Invalid storage key.")
        return candidate

    def put(self, key: str, data: bytes) -> None:
        try:
            path = self._path(key)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        except OSError as exc:
            logger.error("storage_write_failed", extra={"error": type(exc).__name__})
            raise StorageUnavailableError() from exc

    def get(self, key: str) -> bytes:
        try:
            return self._path(key).read_bytes()
        except OSError as exc:
            logger.error("storage_read_failed", extra={"error": type(exc).__name__})
            raise StorageUnavailableError() from exc

    def delete(self, key: str) -> None:
        try:
            self._path(key).unlink(missing_ok=True)
        except OSError as exc:
            logger.error("storage_delete_failed", extra={"error": type(exc).__name__})
            raise StorageUnavailableError() from exc

    def exists(self, key: str) -> bool:
        try:
            return self._path(key).is_file()
        except StorageUnavailableError:
            return False


@lru_cache
def get_storage() -> Storage:
    """Resolve the storage backend from configuration, not from the import site."""
    return LocalStorage(settings.STORAGE_LOCAL_PATH)


def checksum(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
