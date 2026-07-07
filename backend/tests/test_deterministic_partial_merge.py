import os
from unittest.mock import AsyncMock, MagicMock

import pytest

os.environ["DEBUG"] = "false"

from config import settings
from schemas.invoice import ExtractionResult
from services.ai_validation_service import AIValidationService
from services.deterministic_partial_merge_service import DeterministicPartialMergeService
from services.invoice_extraction_service import InvoiceExtractionService


def _partial(**kwargs) -> ExtractionResult:
    base = {
        "invoice_number": None,
        "invoice_date": None,
        "amount": None,
        "name_of_company": None,
        "confidence_score": 0.9,
    }
    base.update(kwargs)
    return ExtractionResult.model_validate(base)


@pytest.fixture
def merge_service() -> DeterministicPartialMergeService:
    return DeterministicPartialMergeService(AIValidationService())


def test_non_conflicting_partials_merge_deterministically(
    merge_service: DeterministicPartialMergeService,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(settings, "openai_deterministic_merge_enabled", True)
    partials = [
        _partial(
            name_of_company="Acme LLC",
            address_of_company="Street 1",
            invoice_number="INV-100",
            invoice_date="2026-01-01",
            client_employee_related="Buyer Co",
            internal_note_description="Line A",
        ),
        _partial(
            amount=150.0,
            currency="EUR",
            account_details="XK051701010500018287",
            internal_note_description="Line B",
        ),
    ]
    outcome = merge_service.merge_partials(partials)
    assert not outcome.use_llm
    assert outcome.strategy == "deterministic"
    assert outcome.result is not None
    assert outcome.result.name_of_company == "Acme LLC"
    assert outcome.result.invoice_number == "INV-100"
    assert outcome.result.amount == 150.0
    assert outcome.result.account_details == "XK051701010500018287"
    assert "Line A" in (outcome.result.internal_note_description or "")
    assert "Line B" in (outcome.result.internal_note_description or "")


def test_conflicting_totals_prefer_last_page(
    merge_service: DeterministicPartialMergeService,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(settings, "openai_deterministic_merge_enabled", True)
    partials = [
        _partial(
            invoice_number="INV-1",
            invoice_date="2026-02-01",
            name_of_company="Acme",
            amount=50.0,
        ),
        _partial(amount=199.99, currency="EUR"),
    ]
    outcome = merge_service.merge_partials(partials)
    assert outcome.result is not None
    assert outcome.result.amount == 199.99


def test_conflicting_header_fields_prefer_first_page(
    merge_service: DeterministicPartialMergeService,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(settings, "openai_deterministic_merge_enabled", True)
    partials = [
        _partial(
            invoice_number="INV-FIRST",
            invoice_date="2026-01-01",
            name_of_company="Acme LLC",
            amount=10.0,
        ),
        _partial(
            invoice_number="INV-LAST",
            invoice_date="2026-02-01",
            name_of_company="Acme Limited",
            amount=10.0,
        ),
    ]
    outcome = merge_service.merge_partials(partials)
    assert outcome.use_llm
    assert outcome.result is not None
    assert outcome.result.invoice_number == "INV-FIRST"
    assert outcome.result.invoice_date == "2026-01-01"


def test_line_items_deduplicate_descriptions(
    merge_service: DeterministicPartialMergeService,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(settings, "openai_deterministic_merge_enabled", True)
    partials = [
        _partial(
            invoice_number="INV-1",
            invoice_date="2026-01-01",
            name_of_company="Acme",
            amount=10.0,
            internal_note_description="Widget x2 100.00",
        ),
        _partial(
            amount=10.0,
            internal_note_description="Widget x2 100.00\nSupport fee 10.00",
        ),
    ]
    outcome = merge_service.merge_partials(partials)
    assert outcome.result is not None
    notes = outcome.result.internal_note_description or ""
    assert notes.count("Widget x2 100.00") == 1
    assert "Support fee 10.00" in notes


def test_unresolved_invoice_number_conflict_falls_back_to_llm(
    merge_service: DeterministicPartialMergeService,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(settings, "openai_deterministic_merge_enabled", True)
    partials = [
        _partial(
            invoice_number="INV-AAA",
            invoice_date="2026-01-01",
            name_of_company="Acme",
            amount=10.0,
        ),
        _partial(
            invoice_number="INV-BBB",
            invoice_date="2026-01-01",
            name_of_company="Acme",
            amount=10.0,
        ),
    ]
    outcome = merge_service.merge_partials(partials)
    assert outcome.use_llm
    assert any("invoice_number_conflict" in c for c in outcome.conflicts)


def test_missing_required_fields_fall_back_to_llm(
    merge_service: DeterministicPartialMergeService,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(settings, "openai_deterministic_merge_enabled", True)
    partials = [
        _partial(invoice_number="INV-1", internal_note_description="Only header"),
        _partial(internal_note_description="Only body"),
    ]
    outcome = merge_service.merge_partials(partials)
    assert outcome.use_llm
    assert "invoice_date" in outcome.missing_fields
    assert "amount" in outcome.missing_fields


@pytest.mark.asyncio
async def test_merge_partial_extractions_skips_llm_when_deterministic(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(settings, "openai_deterministic_merge_enabled", True)
    service = InvoiceExtractionService(
        upload_repo=MagicMock(),
        invoice_repo=MagicMock(),
        invoice_access_repo=MagicMock(),
        audit_repo=MagicMock(),
        ai_validation=AIValidationService(),
        openai_client=AsyncMock(),
    )
    chat = AsyncMock()
    monkeypatch.setattr(service, "_chat_completion", chat)

    partials = [
        _partial(
            invoice_number="INV-1",
            invoice_date="2026-01-01",
            name_of_company="Acme",
        ),
        _partial(amount=50.0, currency="EUR"),
    ]
    merged = await service._merge_partial_extractions(
        partials,
        total_pages=12,
        model="gpt-4o-mini",
    )
    chat.assert_not_called()
    assert merged.amount == 50.0
    assert service._last_merge_meta.get("merge_strategy") == "deterministic"


@pytest.mark.asyncio
async def test_merge_partial_extractions_uses_llm_on_critical_conflict(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(settings, "openai_deterministic_merge_enabled", True)
    service = InvoiceExtractionService(
        upload_repo=MagicMock(),
        invoice_repo=MagicMock(),
        invoice_access_repo=MagicMock(),
        audit_repo=MagicMock(),
        ai_validation=AIValidationService(),
        openai_client=AsyncMock(),
    )

    async def fake_chat(**_kwargs):
        from types import SimpleNamespace

        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content=(
                            '{"invoice_number":"INV-OK","invoice_date":"2026-01-01",'
                            '"amount":50.0,"name_of_company":"Acme","confidence_score":0.9}'
                        )
                    )
                )
            ]
        )

    monkeypatch.setattr(service, "_chat_completion", fake_chat)

    partials = [
        _partial(
            invoice_number="INV-AAA",
            invoice_date="2026-01-01",
            name_of_company="Acme",
            amount=50.0,
        ),
        _partial(
            invoice_number="INV-BBB",
            invoice_date="2026-01-01",
            name_of_company="Acme",
            amount=50.0,
        ),
    ]
    merged = await service._merge_partial_extractions(
        partials,
        total_pages=12,
        model="gpt-4o-mini",
    )
    assert merged.invoice_number == "INV-OK"
    assert service._last_merge_meta.get("merge_strategy") == "llm"


def test_output_schema_unchanged(
    merge_service: DeterministicPartialMergeService,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(settings, "openai_deterministic_merge_enabled", True)
    partials = [
        _partial(
            invoice_number="INV-1",
            invoice_date="2026-01-01",
            name_of_company="Acme",
            amount=10.0,
            currency="EUR",
        ),
        _partial(amount=10.0),
    ]
    outcome = merge_service.merge_partials(partials)
    assert outcome.result is not None
    data = outcome.result.model_dump()
    assert set(data.keys()) == set(ExtractionResult.model_fields.keys())
