from abc import ABC, abstractmethod


class StorageBackend(ABC):
    @abstractmethod
    async def save(
        self,
        storage_path: str,
        content: bytes,
        *,
        content_type: str | None = None,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    async def read(self, storage_path: str) -> bytes:
        raise NotImplementedError

    @abstractmethod
    async def delete(self, storage_path: str) -> None:
        raise NotImplementedError

    @abstractmethod
    async def exists(self, storage_path: str) -> bool:
        raise NotImplementedError
