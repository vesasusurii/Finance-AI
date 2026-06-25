"""Text-first invoice extraction for digital PDFs (skip Vision when text is sufficient)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from config import settings
from core.debug_logger import debug_trace, get_logger
from schemas.invoice import ExtractionResult
from services.ai_validation_service import AIValidationService
from services.ocr.pdf_text_extractor import TextLayerHints

if TYPE_CHECKING:
    from openai import AsyncOpenAI

logger = get_logger(__name__)


class TextFirstExtractionService:
    def __init__(
        self,
        openai_client: AsyncOpenAI | None,
        ai_validation: AIValidationService | None = None,
    ) -> None:
        self._openai = openai_client
        self._ai_validation = ai_validation or AIValidationService()

    def can_attempt(
        self,
        *,
        total_pages: int,
        hints: TextLayerHints,
    ) -> bool:
        if not settings.openai_text_first_enabled:
            return False
        if total_pages > settings.openai_text_first_max_pages:
            return False
        return (
            hints.has_usable_text
            and len(hints.raw_text.strip()) >= settings.openai_text_first_min_chars
        )

    @debug_trace
    def result_from_hints(self, hints: TextLayerHints) -> ExtractionResult | None:
        """Regex-derived critical fields only — no API call."""
        if not self._hints_have_all_critical(hints):
            return None

        invoice_date = self._ai_validation._normalize_date(hints.invoice_date or "")
        invoice_number = self._ai_validation._clean_invoice_number(
            hints.invoice_number or ""
        )
        if not invoice_date or not invoice_number:
            return None

        result = ExtractionResult(
            invoice_date=invoice_date,
            invoice_number=invoice_number,
            amount=hints.amount,
            name_of_company=self._ai_validation._clean_text(hints.name_of_company or ""),
            confidence_score=0.88,
            needs_review=False,
        )
        return self._ai_validation.sanitize_and_validate(result)

    @debug_trace
    async def extract_from_text(
        self,
        *,
        raw_text: str,
        filename: str,
        system_prompt: str,
        model: str,
        chat_completion,
        parse_response,
    ) -> ExtractionResult | None:
        """Single text-only LLM call (no images)."""
        if self._openai is None:
            return None

        truncated = raw_text[: settings.openai_max_supplemental_chars]
        response = await chat_completion(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": (
                        f"Extract structured invoice JSON from this PDF text layer.\n"
                        f"Filename: {filename}\n\n"
                        f"{truncated}"
                    ),
                },
            ],
            timeout_seconds=min(60.0, float(settings.openai_timeout_seconds)),
        )
        result = parse_response(response.choices[0].message.content or "{}")
        result = self._ai_validation.sanitize_and_validate(result)
        if self._ai_validation.validate_required_fields(result):
            return None
        if result.confidence_score < 0.75:
            return None
        return result

    def _hints_have_all_critical(self, hints: TextLayerHints) -> bool:
        return bool(
            hints.invoice_number
            and hints.invoice_date
            and hints.amount is not None
            and hints.name_of_company
        )
