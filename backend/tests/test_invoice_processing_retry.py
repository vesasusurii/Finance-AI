from unittest.mock import AsyncMock

import pytest

from core.rate_limiter import RateLimitExceeded
from services import invoice_processing_service


@pytest.mark.asyncio
async def test_inline_ocr_retry_catches_openai_rate_lease_limit(monkeypatch):
    process_upload = AsyncMock(
        side_effect=[
            RateLimitExceeded("OpenAI RPS limit reached", retry_after_seconds=3),
            None,
        ]
    )
    sleep = AsyncMock()
    released: list[tuple[str, str]] = []

    monkeypatch.setattr(invoice_processing_service, "process_invoice_upload", process_upload)
    monkeypatch.setattr(invoice_processing_service.asyncio, "sleep", sleep)
    monkeypatch.setattr(invoice_processing_service.settings, "task_max_retries", 1)
    monkeypatch.setattr(
        invoice_processing_service,
        "acquire_ocr_lock",
        lambda upload_id, owner: f"lock:{upload_id}:{owner}",
    )
    monkeypatch.setattr(
        invoice_processing_service,
        "release_lock",
        lambda lock_key, owner: released.append((lock_key, owner)),
    )

    await invoice_processing_service._run_with_retries(42, 7, content=b"pdf")

    assert process_upload.await_count == 2
    process_upload.assert_any_await(42, 7, content=b"pdf")
    sleep.assert_awaited_once_with(3)
    assert len(released) == 2
