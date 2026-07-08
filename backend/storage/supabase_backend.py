import asyncio

import httpx

from config import settings
from core.debug_logger import get_logger
from storage.base import StorageBackend
from storage.helpers import encode_storage_path
logger = get_logger(__name__)

# Downloads occasionally get cut short mid-stream (seen intermittently on the
# Azure-hosted backend's outbound path to Supabase, not locally) while still
# reporting HTTP 200 — httpx does not always raise when a chunked response is
# terminated early. When the server told us how many bytes to expect via
# Content-Length, cross-check the body we actually received and retry.
_MAX_READ_ATTEMPTS = 3
_RETRY_BACKOFF_SECONDS = 0.3


class SupabaseStorageBackend(StorageBackend):
    def __init__(self, http_client: httpx.AsyncClient) -> None:
        self._client = http_client
        self._base = settings.supabase_url.rstrip("/")
        self._bucket = settings.supabase_storage_bucket

    def _object_url(self, storage_path: str) -> str:
        path = encode_storage_path(storage_path)
        return f"{self._base}/storage/v1/object/{self._bucket}/{path}"

    def _headers(self, content_type: str | None = None) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {settings.supabase_service_role_key}",
            "apikey": settings.supabase_service_role_key,
        }
        if content_type:
            headers["Content-Type"] = content_type
        return headers

    async def save(
        self,
        storage_path: str,
        content: bytes,
        *,
        content_type: str | None = None,
    ) -> None:
        url = self._object_url(storage_path)
        headers = self._headers(content_type or "application/octet-stream")
        headers["x-upsert"] = "true"
        resp = await self._client.post(url, content=content, headers=headers)
        if resp.status_code not in (200, 201):
            logger.error(
                "Supabase upload failed: status=%s body=%s path=%s",
                resp.status_code,
                resp.text[:500],
                storage_path,
            )
            raise RuntimeError(
                "Storage upload failed. Check Supabase bucket and credentials."
            )
        logger.debug(
            "Supabase storage saved: %s (%d bytes)", storage_path, len(content)
        )

    async def read(self, storage_path: str) -> bytes:
        url = self._object_url(storage_path)
        last_mismatch: str | None = None
        for attempt in range(1, _MAX_READ_ATTEMPTS + 1):
            resp = await self._client.get(url, headers=self._headers())
            if resp.status_code == 404:
                raise FileNotFoundError(storage_path)
            if resp.status_code != 200:
                raise RuntimeError(
                    f"Storage download failed ({resp.status_code}): {resp.text[:200]}"
                )

            content = resp.content
            declared = resp.headers.get("content-length")
            declared_len = int(declared) if declared and declared.isdigit() else None
            if declared_len is not None and len(content) != declared_len:
                last_mismatch = (
                    f"declared={declared_len} received={len(content)} "
                    f"path={storage_path} attempt={attempt}"
                )
                logger.warning("Supabase storage download truncated: %s", last_mismatch)
                if attempt < _MAX_READ_ATTEMPTS:
                    await asyncio.sleep(_RETRY_BACKOFF_SECONDS * attempt)
                    continue
                raise RuntimeError(f"Storage download truncated: {last_mismatch}")
            return content

        raise RuntimeError(f"Storage download truncated: {last_mismatch}")

    async def delete(self, storage_path: str) -> None:
        url = self._object_url(storage_path)
        resp = await self._client.delete(url, headers=self._headers())
        if resp.status_code in (200, 204, 404):
            return
        # Supabase sometimes returns HTTP 400 with a not_found payload.
        if resp.status_code == 400 and "not_found" in resp.text.lower():
            logger.debug(
                "Supabase storage delete: object already absent at %s",
                storage_path,
            )
            return
        raise RuntimeError(
            f"Storage delete failed ({resp.status_code}): {resp.text[:200]}"
        )

    async def exists(self, storage_path: str) -> bool:
        url = self._object_url(storage_path)
        resp = await self._client.head(url, headers=self._headers())
        return resp.status_code == 200
