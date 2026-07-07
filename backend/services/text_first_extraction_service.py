"""Text-first invoice extraction for digital PDFs (skip Vision when text is sufficient)."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from config import settings
from core.debug_logger import debug_trace, get_logger
from schemas.invoice import ExtractionResult
from services.ai_validation_service import AIValidationService
from services.ocr.pdf_text_extractor import (
    MIN_PDF_TEXT_CHARS,
    TextLayerHints,
    text_quality_score,
)

if TYPE_CHECKING:
    from openai import AsyncOpenAI

logger = get_logger(__name__)

_TEXT_LLM_MIN_CONFIDENCE = 0.75
_TEXT_LLM_PARTIAL_HINT_CONFIDENCE = 0.65
_PARTIAL_HINT_LLM_THRESHOLD = 1


@dataclass(frozen=True)
class TextFirstRoute:
    """Routing decision for text-first extraction."""

    use_text_first: bool
    mode: str | None
    reason: str
    text_chars: int
    hints_found_count: int
    missing_hint_fields: tuple[str, ...]
    text_quality_score: float

    def metadata(self) -> dict[str, object]:
        return {
            "text_first_reason": self.reason,
            "text_chars": self.text_chars,
            "hints_found_count": self.hints_found_count,
            "missing_hint_fields": list(self.missing_hint_fields),
            "text_quality_score": self.text_quality_score,
        }


class TextFirstExtractionService:
    def __init__(
        self,
        openai_client: AsyncOpenAI | None,
        ai_validation: AIValidationService | None = None,
    ) -> None:
        self._openai = openai_client
        self._ai_validation = ai_validation or AIValidationService()
        self.last_route: TextFirstRoute | None = None

    def evaluate_route(
        self,
        *,
        total_pages: int,
        hints: TextLayerHints,
    ) -> TextFirstRoute:
        text_chars = len(hints.raw_text.strip())
        hints_found = hints.critical_hint_count()
        missing = tuple(hints.missing_critical_fields())
        quality = text_quality_score(hints)

        base = TextFirstRoute(
            use_text_first=False,
            mode=None,
            reason="vision_fallback",
            text_chars=text_chars,
            hints_found_count=hints_found,
            missing_hint_fields=missing,
            text_quality_score=quality,
        )

        if not settings.openai_text_first_enabled:
            return replace(base, reason="disabled")

        if total_pages > settings.openai_text_first_max_pages:
            return replace(base, reason="too_many_pages")

        min_chars = settings.openai_text_first_min_chars
        has_enough_text = text_chars >= min_chars
        has_minimal_text = text_chars >= MIN_PDF_TEXT_CHARS
        has_partial_hints = hints_found >= _PARTIAL_HINT_LLM_THRESHOLD

        if not has_enough_text and not (has_minimal_text and has_partial_hints):
            return replace(base, reason="text_too_short")

        if self._hints_have_all_critical(hints):
            return TextFirstRoute(
                use_text_first=True,
                mode="text_hints",
                reason="all_hints_complete",
                text_chars=text_chars,
                hints_found_count=hints_found,
                missing_hint_fields=missing,
                text_quality_score=quality,
            )

        if has_partial_hints and has_minimal_text:
            return TextFirstRoute(
                use_text_first=True,
                mode="text_llm",
                reason="partial_hints",
                text_chars=text_chars,
                hints_found_count=hints_found,
                missing_hint_fields=missing,
                text_quality_score=quality,
            )

        if quality < 0.15 and hints_found == 0:
            return replace(base, reason="low_quality")

        if has_enough_text:
            return TextFirstRoute(
                use_text_first=True,
                mode="text_llm",
                reason="sufficient_text",
                text_chars=text_chars,
                hints_found_count=hints_found,
                missing_hint_fields=missing,
                text_quality_score=quality,
            )

        if quality < 0.15 and hints_found == 0:
            return replace(base, reason="low_quality")

        return replace(base, reason="low_quality")

    def can_attempt(
        self,
        *,
        total_pages: int,
        hints: TextLayerHints,
    ) -> bool:
        route = self.evaluate_route(total_pages=total_pages, hints=hints)
        self.last_route = route
        return route.use_text_first

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
            account_details=self._ai_validation._clean_text(hints.account_details or ""),
            confidence_score=0.88,
            needs_review=False,
            field_confidences={
                "invoice_number": 0.9,
                "invoice_date": 0.9,
                "amount": 0.88,
                "name_of_company": 0.82,
                "account_details": 0.8 if hints.account_details else 0.0,
            },
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
        hints: TextLayerHints | None = None,
        partial_hint_count: int = 0,
    ) -> ExtractionResult | None:
        """Single text-only LLM call (no images)."""
        if self._openai is None:
            return None

        truncated = raw_text[: settings.openai_max_supplemental_chars]
        hint_block = self._format_hint_block(hints) if hints is not None else ""
        user_parts = [
            "Extract structured invoice JSON from this PDF text layer.",
            f"Filename: {filename}",
        ]
        if hint_block:
            user_parts += ["", "Regex hints detected in the text (verify and correct):", hint_block]
        user_parts += ["", truncated]

        response = await chat_completion(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": "\n".join(user_parts)},
            ],
            timeout_seconds=min(60.0, float(settings.openai_timeout_seconds)),
        )
        result = parse_response(response.choices[0].message.content or "{}")
        result = self._ai_validation.sanitize_and_validate(result)
        if self._ai_validation.validate_required_fields(result):
            return None
        min_confidence = (
            _TEXT_LLM_PARTIAL_HINT_CONFIDENCE
            if partial_hint_count >= _PARTIAL_HINT_LLM_THRESHOLD
            else _TEXT_LLM_MIN_CONFIDENCE
        )
        if result.confidence_score < min_confidence:
            return None
        return result

    def _format_hint_block(self, hints: TextLayerHints) -> str:
        lines: list[str] = []
        mapping = {
            "invoice_number": hints.invoice_number,
            "invoice_date": hints.invoice_date,
            "due_date": hints.due_date,
            "amount": hints.amount,
            "vat_amount": hints.vat_amount,
            "name_of_company": hints.name_of_company,
            "account_details": hints.account_details,
            "payment_reference": hints.payment_reference,
        }
        for key, value in mapping.items():
            if value is not None and value != "":
                lines.append(f"- {key}: {value}")
        return "\n".join(lines)

    def _hints_have_all_critical(self, hints: TextLayerHints) -> bool:
        return hints.critical_hint_count() == 4
