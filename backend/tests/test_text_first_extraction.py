import os
from unittest.mock import AsyncMock, MagicMock

import pytest

os.environ["DEBUG"] = "false"

from config import settings
from services.ocr.pdf_text_extractor import TextLayerHints, parse_text_layer_hints, text_quality_score
from services.text_first_extraction_service import TextFirstExtractionService


def test_can_attempt_requires_enough_text(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "openai_text_first_enabled", True)
    monkeypatch.setattr(settings, "openai_text_first_min_chars", 200)
    svc = TextFirstExtractionService(openai_client=None)
    hints = TextLayerHints(raw_text="short")
    route = svc.evaluate_route(total_pages=1, hints=hints)
    assert not route.use_text_first
    assert route.reason == "text_too_short"


def test_partial_hints_route_to_text_llm(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "openai_text_first_enabled", True)
    monkeypatch.setattr(settings, "openai_text_first_min_chars", 200)
    svc = TextFirstExtractionService(openai_client=None)
    hints = TextLayerHints(
        raw_text="x" * 120,
        invoice_number="INV-1",
        invoice_date=None,
        amount=10.0,
        name_of_company=None,
    )
    route = svc.evaluate_route(total_pages=1, hints=hints)
    assert route.use_text_first
    assert route.mode == "text_llm"
    assert route.reason == "partial_hints"
    assert route.hints_found_count == 2
    assert "invoice_date" in route.missing_hint_fields
    assert "name_of_company" in route.missing_hint_fields


def test_result_from_hints_when_all_critical_present():
    svc = TextFirstExtractionService(openai_client=None)
    hints = TextLayerHints(
        raw_text="x" * 300,
        invoice_number="INV-26063",
        invoice_date="15.05.2026",
        amount=220.66,
        name_of_company="ADIA Group SH.P.K.",
    )
    result = svc.result_from_hints(hints)
    assert result is not None
    assert result.invoice_number == "INV-26063"
    assert result.amount == 220.66
    assert result.confidence_score >= 0.85


def test_result_from_hints_returns_none_when_incomplete():
    svc = TextFirstExtractionService(openai_client=None)
    hints = TextLayerHints(
        raw_text="x" * 300,
        invoice_number="INV-1",
        invoice_date=None,
        amount=10.0,
        name_of_company="Acme",
    )
    assert svc.result_from_hints(hints) is None


def test_all_hints_complete_routes_to_text_hints(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "openai_text_first_enabled", True)
    svc = TextFirstExtractionService(openai_client=None)
    hints = TextLayerHints(
        raw_text="x" * 300,
        invoice_number="INV-1",
        invoice_date="2026-01-01",
        amount=99.0,
        name_of_company="Acme LLC",
    )
    route = svc.evaluate_route(total_pages=2, hints=hints)
    assert route.use_text_first
    assert route.mode == "text_hints"
    assert route.reason == "all_hints_complete"
    assert route.hints_found_count == 4


def test_scanned_pdf_no_text_skips_text_first(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "openai_text_first_enabled", True)
    svc = TextFirstExtractionService(openai_client=None)
    hints = TextLayerHints(raw_text="")
    route = svc.evaluate_route(total_pages=1, hints=hints)
    assert not route.use_text_first
    assert route.reason == "text_too_short"


def test_max_pages_10_respected(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "openai_text_first_enabled", True)
    monkeypatch.setattr(settings, "openai_text_first_max_pages", 10)
    svc = TextFirstExtractionService(openai_client=None)
    hints = TextLayerHints(raw_text="x" * 300, invoice_number="INV-1")
    assert svc.evaluate_route(total_pages=10, hints=hints).use_text_first
    route = svc.evaluate_route(total_pages=11, hints=hints)
    assert not route.use_text_first
    assert route.reason == "too_many_pages"


def test_sufficient_text_without_hints_uses_text_llm(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "openai_text_first_enabled", True)
    monkeypatch.setattr(settings, "openai_text_first_min_chars", 200)
    svc = TextFirstExtractionService(openai_client=None)
    hints = TextLayerHints(raw_text="x" * 250)
    route = svc.evaluate_route(total_pages=1, hints=hints)
    assert route.use_text_first
    assert route.mode == "text_llm"
    assert route.reason == "sufficient_text"


def test_low_quality_no_hints_skips_text_first(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "openai_text_first_enabled", True)
    monkeypatch.setattr(settings, "openai_text_first_min_chars", 200)
    svc = TextFirstExtractionService(openai_client=None)
    hints = TextLayerHints(raw_text="\ufffd" * 250)
    route = svc.evaluate_route(total_pages=1, hints=hints)
    assert not route.use_text_first
    assert route.reason == "low_quality"


def test_parse_text_layer_hints_common_labels_and_iban():
    text = """
    ADIA Group SH.P.K.
    Invoice No: INV-26063
    Invoice date: 15.05.2026
    Due date: 30.05.2026
    Grand Total EUR 220.66
    VAT amount EUR 36.78
    Payment reference PAY-9981
    IBAN XK051701010500018287
    """

    hints = parse_text_layer_hints(text)

    assert hints.invoice_number == "INV-26063"
    assert hints.invoice_date == "15.05.2026"
    assert hints.due_date == "30.05.2026"
    assert hints.amount == 220.66
    assert hints.vat_amount == 36.78
    assert hints.payment_reference == "PAY-9981"
    assert hints.name_of_company == "ADIA Group SH.P.K."
    assert hints.account_details == "XK051701010500018287"


@pytest.mark.asyncio
async def test_extract_from_text_accepts_lower_confidence_with_partial_hints():
    svc = TextFirstExtractionService(openai_client=AsyncMock())
    hints = TextLayerHints(
        raw_text="x" * 300,
        invoice_number="INV-1",
        amount=50.0,
    )

    async def fake_chat_completion(**_kwargs):
        return MagicMock(
            choices=[
                MagicMock(
                    message=MagicMock(
                        content=(
                            '{"invoice_date":"2026-01-01","invoice_number":"INV-1",'
                            '"amount":50.0,"name_of_company":"Acme","confidence_score":0.7}'
                        )
                    )
                )
            ]
        )

    def parse_response(raw: str):
        from schemas.invoice import ExtractionResult
        import json

        return ExtractionResult.model_validate(json.loads(raw))

    result = await svc.extract_from_text(
        raw_text=hints.raw_text,
        filename="invoice.pdf",
        system_prompt="extract",
        model="gpt-4o-mini",
        chat_completion=fake_chat_completion,
        parse_response=parse_response,
        hints=hints,
        partial_hint_count=2,
    )
    assert result is not None
    assert result.confidence_score == 0.7


def test_text_quality_score_increases_with_hints():
    sparse = TextLayerHints(raw_text="x" * 100)
    rich = TextLayerHints(
        raw_text="x" * 500,
        invoice_number="1",
        invoice_date="2026-01-01",
        amount=1.0,
        name_of_company="Acme",
        account_details="XK051701010500018287",
    )
    assert text_quality_score(rich) > text_quality_score(sparse)
