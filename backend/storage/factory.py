import httpx

from config import settings
from storage.base import StorageBackend

_backend: StorageBackend | None = None


def get_storage_backend(http_client: httpx.AsyncClient | None = None) -> StorageBackend:
    """Return the configured storage backend singleton."""
    global _backend
    if _backend is not None:
        return _backend

    if settings.storage_backend == "supabase":
        if http_client is None:
            raise RuntimeError("HTTP client required for Supabase storage backend")
        from storage.supabase_backend import SupabaseStorageBackend

        _backend = SupabaseStorageBackend(http_client)
    else:
        from storage.local_backend import LocalStorageBackend

        _backend = LocalStorageBackend()
    return _backend


def reset_storage_backend() -> None:
    """Test helper — clear cached backend."""
    global _backend
    _backend = None
