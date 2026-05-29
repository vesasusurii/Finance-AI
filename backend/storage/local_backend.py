from pathlib import Path

from config import settings
from core.debug_logger import get_logger
from storage.base import StorageBackend

logger = get_logger(__name__)


class LocalStorageBackend(StorageBackend):
    def _path(self, storage_path: str) -> Path:
        return Path(settings.storage_path) / storage_path

    async def save(
        self,
        storage_path: str,
        content: bytes,
        *,
        content_type: str | None = None,
    ) -> None:
        dest = self._path(storage_path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(content)
        logger.debug("Local storage saved: %s (%d bytes)", storage_path, len(content))

    async def read(self, storage_path: str) -> bytes:
        path = self._path(storage_path)
        if not path.is_file():
            raise FileNotFoundError(storage_path)
        return path.read_bytes()

    async def delete(self, storage_path: str) -> None:
        path = self._path(storage_path)
        if path.is_file():
            path.unlink()

    async def exists(self, storage_path: str) -> bool:
        return self._path(storage_path).is_file()
