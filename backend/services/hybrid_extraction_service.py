"""Merge PDF text-layer hints with Vision extraction results."""

from __future__ import annotations

from core.debug_logger import debug_trace, get_logger
from schemas.invoice import ExtractionResult
from services.ai_validation_service import AIValidationService
from services.ocr.pdf_text_extractor import TextLayerHints

logger = get_logger(__name__)

# Fields where deterministic text-layer reads are preferred over Vision
_TEXT_PREFERRED_FIELDS = ("invoice_number", "invoice_date", "amount", "name_of_company")


class HybridExtractionService:
    def __init__(self, ai_validation: AIValidationService | None = None) -> None:
        self._ai_validation = ai_validation or AIValidationService()

    @debug_trace
    def merge(
        self,
        vision: ExtractionResult,
        hints: TextLayerHints,
    ) -> ExtractionResult:
        """Prefer text-layer values for critical fields when Vision left them empty."""
        if not hints.has_usable_text:
            return vision

        data = vision.model_dump()
        merged_fields: list[str] = []

        if hints.invoice_number and not data.get("invoice_number"):
            cleaned = self._ai_validation._clean_invoice_number(hints.invoice_number)
            if cleaned:
                data["invoice_number"] = cleaned
                merged_fields.append("invoice_number")

        if hints.invoice_date and not data.get("invoice_date"):
            normalised = self._ai_validation._normalize_date(hints.invoice_date)
            if normalised:
                data["invoice_date"] = normalised
                merged_fields.append("invoice_date")

        if hints.amount is not None and data.get("amount") is None:
            data["amount"] = hints.amount
            merged_fields.append("amount")

        if hints.name_of_company and not data.get("name_of_company"):
            data["name_of_company"] = self._ai_validation._clean_text(
                hints.name_of_company
            )
            merged_fields.append("name_of_company")

        if merged_fields:
            logger.info(
                "Hybrid merge applied text-layer hints for: %s",
                ", ".join(merged_fields),
            )

        return self._ai_validation.sanitize_and_validate(
            ExtractionResult.model_validate(data)
        )
