import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

os.environ["DEBUG"] = "false"

from config import settings
from services.ai_validation_service import AIValidationService
from services.invoice_extraction_service import (
    InvoiceExtractionService,
    _image_detail_for_page,
    _image_detail_strategy_name,
)


@pytest.mark.parametrize(
    ("page_num", "total_pages", "expected"),
    [
        (1, 1, "high"),
        (1, 3, "high"),
        (3, 3, "high"),
        (2, 3, "low"),
        (2, 5, "low"),
        (4, 5, "low"),
    ],
)
def test_image_detail_adaptive_enabled(
    monkeypatch: pytest.MonkeyPatch,
    page_num: int,
    total_pages: int,
    expected: str,
):
    monkeypatch.setattr(settings, "openai_adaptive_image_detail", True)
    monkeypatch.setattr(settings, "openai_adaptive_image_detail_middle", "low")
    assert _image_detail_for_page(page_num, total_pages) == expected


def test_image_detail_single_page_always_high(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "openai_adaptive_image_detail", True)
    assert _image_detail_for_page(1, 1) == "high"


def test_image_detail_two_page_pdf_both_high(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "openai_adaptive_image_detail", True)
    assert _image_detail_for_page(1, 2) == "high"
    assert _image_detail_for_page(2, 2) == "high"


def test_image_detail_disabled_uses_all_high(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "openai_adaptive_image_detail", False)
    assert _image_detail_for_page(2, 5) == "high"
    assert _image_detail_strategy_name() == "all_high"


def test_image_detail_middle_auto(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "openai_adaptive_image_detail", True)
    monkeypatch.setattr(settings, "openai_adaptive_image_detail_middle", "auto")
    assert _image_detail_for_page(3, 5) == "auto"


def test_image_detail_invalid_middle_falls_back_to_low(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(settings, "openai_adaptive_image_detail", True)
    monkeypatch.setattr(settings, "openai_adaptive_image_detail_middle", "invalid")
    assert _image_detail_for_page(3, 5) == "low"


@pytest.fixture
def vision_service() -> InvoiceExtractionService:
    return InvoiceExtractionService(
        upload_repo=MagicMock(),
        invoice_repo=MagicMock(),
        invoice_access_repo=MagicMock(),
        audit_repo=MagicMock(),
        ai_validation=AIValidationService(),
        openai_client=AsyncMock(),
    )


@pytest.mark.asyncio
async def test_vision_extract_applies_adaptive_detail_to_payload(
    vision_service: InvoiceExtractionService,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(settings, "openai_adaptive_image_detail", True)
    monkeypatch.setattr(settings, "openai_adaptive_image_detail_middle", "low")

    captured: dict = {}

    async def fake_chat_completion(self, *, model, messages, timeout_seconds=None):
        captured["messages"] = messages
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content='{"invoice_number":"INV-1"}'),
                    finish_reason="stop",
                )
            ]
        )

    monkeypatch.setattr(
        vision_service,
        "_chat_completion",
        fake_chat_completion.__get__(vision_service, InvoiceExtractionService),
    )

    images = [(b"jpeg-bytes", "image/jpeg") for _ in range(3)]
    await vision_service._openai_vision_extract(
        images,
        filename="invoice.pdf",
        file_type="pdf",
        model="gpt-4o-mini",
        page_range=(1, 3),
        total_pages=3,
    )

    user_content = captured["messages"][1]["content"]
    details = [
        part["image_url"]["detail"]
        for part in user_content
        if part.get("type") == "image_url"
    ]
    assert details == ["high", "low", "high"]
    assert vision_service._image_detail_high_pages == {1, 3}
    assert vision_service._image_detail_low_pages == {2}


@pytest.mark.asyncio
async def test_vision_extract_disabled_keeps_all_high(
    vision_service: InvoiceExtractionService,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(settings, "openai_adaptive_image_detail", False)

    captured: dict = {}

    async def fake_chat_completion(self, *, model, messages, timeout_seconds=None):
        captured["messages"] = messages
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content='{"invoice_number":"INV-1"}'),
                    finish_reason="stop",
                )
            ]
        )

    monkeypatch.setattr(
        vision_service,
        "_chat_completion",
        fake_chat_completion.__get__(vision_service, InvoiceExtractionService),
    )

    images = [(b"jpeg-bytes", "image/jpeg") for _ in range(3)]
    await vision_service._openai_vision_extract(
        images,
        filename="invoice.pdf",
        file_type="pdf",
        model="gpt-4o-mini",
        page_range=(1, 3),
        total_pages=3,
    )

    user_content = captured["messages"][1]["content"]
    details = [
        part["image_url"]["detail"]
        for part in user_content
        if part.get("type") == "image_url"
    ]
    assert details == ["high", "high", "high"]
