"""Supabase/local storage setup for RQ workers (no FastAPI lifespan)."""

from __future__ import annotations

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

import httpx

from config import settings
from storage.factory import reset_storage_backend
from utils.file_storage import bind_http_client


@asynccontextmanager
async def worker_storage_session() -> AsyncIterator[None]:
    """
    Bind an HTTP client for Supabase Storage for the duration of a worker job.

    The API sets this in FastAPI lifespan; RQ workers run in a separate process.
    """
    reset_storage_backend()
    if settings.storage_backend != "supabase":
        try:
            yield
        finally:
            reset_storage_backend()
        return

    async with httpx.AsyncClient(timeout=120.0) as http_client:
        bind_http_client(http_client)
        try:
            yield
        finally:
            bind_http_client(None)
            reset_storage_backend()
