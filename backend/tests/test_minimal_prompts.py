"""Phase 5 — minimal prompts, supplemental cap, and utility routing."""

from unittest.mock import MagicMock

import pytest

from ai.prompts.builders.prompt_builder import (
    build_batch_system_prompt,
    build_merge_system_prompt,
    build_vision_system_prompt,
    estimate_prompt_tokens,
    prompt_strategy_label,
)
from ai.prompts.shared.examples import GOLDEN_EXAMPLES
from config import settings
from core.document_categories import DocumentCategory
from services.invoice_extraction_service import (
    InvoiceExtractionService,
    _cap_vision_supplemental_text,
)


def test_generic_vision_prompt_is_minimal():
    prompt = build_vision_system_prompt(DocumentCategory.GENERIC)
    assert "Field rules" in prompt
    assert GOLDEN_EXAMPLES not in prompt
    assert "Example (shape only" not in prompt
    assert "Utility bill document types" not in prompt
    assert len(prompt) < 4000


def test_utility_vision_prompt_includes_utility_rules():
    prompt = build_vision_system_prompt(DocumentCategory.UTILITY)
    assert "Utility bill document types" in prompt
    assert GOLDEN_EXAMPLES not in prompt


def test_generic_batch_prompt_excludes_golden_examples():
    prompt = build_batch_system_prompt(DocumentCategory.GENERIC)
    assert "Batch rules" in prompt
    assert GOLDEN_EXAMPLES not in prompt
    assert "Utility bill document types" not in prompt


def test_utility_batch_prompt_includes_utility_rules():
    prompt = build_batch_system_prompt(DocumentCategory.UTILITY)
    assert "Utility bill document types" in prompt
    assert GOLDEN_EXAMPLES not in prompt


def test_merge_prompt_is_minimal():
    prompt = build_merge_system_prompt()
    assert "Merge rules" in prompt
    assert GOLDEN_EXAMPLES not in prompt
    assert "Field rules" not in prompt
    assert len(prompt) < 2500


def test_prompt_strategy_labels():
    assert prompt_strategy_label(mode="vision") == "minimal"
    assert (
        prompt_strategy_label(mode="vision", document_category=DocumentCategory.UTILITY)
        == "minimal+utility"
    )
    assert prompt_strategy_label(mode="batch") == "minimal+batch"
    assert prompt_strategy_label(mode="merge") == "minimal+merge"


def test_estimate_prompt_tokens():
    assert estimate_prompt_tokens("") == 0
    assert estimate_prompt_tokens("abcd") == 1
    assert estimate_prompt_tokens("a" * 800) == 200


def test_cap_vision_supplemental_text(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "openai_vision_supplemental_text_max_chars", 12000)
    text = "x" * 20000
    capped, chars = _cap_vision_supplemental_text(text)
    assert capped is not None
    assert len(capped) == 12000
    assert chars == 12000
    assert _cap_vision_supplemental_text(None) == (None, 0)


@pytest.mark.asyncio
async def test_merge_fallback_uses_minimal_prompt(monkeypatch: pytest.MonkeyPatch):
    from unittest.mock import AsyncMock

    from services.ai_validation_service import AIValidationService

    monkeypatch.setattr(settings, "openai_deterministic_merge_enabled", True)
    service = InvoiceExtractionService(
        upload_repo=MagicMock(),
        invoice_repo=MagicMock(),
        invoice_access_repo=MagicMock(),
        audit_repo=MagicMock(),
        ai_validation=AIValidationService(),
        openai_client=AsyncMock(),
    )
    captured: dict = {}

    async def fake_chat(**kwargs):
        captured.update(kwargs)
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

    from schemas.invoice import ExtractionResult

    partials = [
        ExtractionResult(
            invoice_number="INV-A",
            invoice_date="2026-01-01",
            name_of_company="Acme",
            amount=50.0,
            confidence_score=0.9,
        ),
        ExtractionResult(
            invoice_number="INV-B",
            invoice_date="2026-01-01",
            name_of_company="Acme",
            amount=50.0,
            confidence_score=0.9,
        ),
    ]
    await service._merge_partial_extractions(
        partials,
        total_pages=4,
        model="gpt-4o-mini",
    )
    system_content = captured["messages"][0]["content"]
    assert GOLDEN_EXAMPLES not in system_content
    assert "Merge rules" in system_content
    assert service._last_merge_meta.get("merge_strategy") == "llm"
    assert service._last_merge_meta.get("prompt_strategy") == "minimal+merge"


def test_json_schema_keys_unchanged():
    prompt = build_vision_system_prompt()
    for key in (
        "document_type",
        "invoice_date",
        "name_of_company",
        "invoice_number",
        "amount",
        "field_confidences",
        "needs_review",
    ):
        assert key in prompt
