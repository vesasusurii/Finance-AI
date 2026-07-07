"""Lightweight document preclassification for faster OCR routing."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from config import settings
from core.document_categories import DocumentCategory
from services.ocr.pdf_text_extractor import (
    MIN_PDF_TEXT_CHARS,
    TextLayerHints,
    text_quality_score,
)
from services.vision_page_selection_service import score_page, select_vision_pages

IMAGE_MIMES = frozenset({"image/jpeg", "image/jpg", "image/png"})

_UTILITY_KEYWORDS = (
    "kesco",
    "ujesjelles",
    "ujësjellës",
    "pastrimi",
    "utility",
    "electricity",
    "water bill",
    "nr. ref.",
)

_RECEIPT_KEYWORDS = (
    "receipt",
    "kupon",
    "fiskal",
    "fiscal",
    "cash sale",
    "thank you for your purchase",
)

_LONG_INVOICE_PAGE_THRESHOLD = 3
_SHORT_INVOICE_PAGE_THRESHOLD = 2


@dataclass(frozen=True)
class PreclassificationResult:
    preclassification_type: str
    preclassification_reason: str
    routing_decision: str
    use_text_first: bool
    prefer_dynamic_vision: bool | None
    prefer_full_document_vision: bool | None
    utility_prompts: bool
    routing_fallback_used: bool = False

    def metadata(self) -> dict[str, object]:
        return {
            "preclassification_type": self.preclassification_type,
            "preclassification_reason": self.preclassification_reason,
            "routing_decision": self.routing_decision,
            "routing_fallback_used": self.routing_fallback_used,
        }

    def with_fallback(self) -> PreclassificationResult:
        return PreclassificationResult(
            preclassification_type=self.preclassification_type,
            preclassification_reason=self.preclassification_reason,
            routing_decision="safe_fallback",
            use_text_first=False,
            prefer_dynamic_vision=None,
            prefer_full_document_vision=None,
            utility_prompts=self.utility_prompts,
            routing_fallback_used=True,
        )


class DocumentPreclassificationService:
    """Cheap preclassification to pick the fastest safe extraction route."""

    def classify(
        self,
        *,
        mime: str,
        filename: str,
        total_pages: int,
        hints: TextLayerHints,
        document_category: DocumentCategory,
        page_texts: tuple[str, ...] = (),
    ) -> PreclassificationResult:
        if not settings.openai_preclassification_routing_enabled:
            return PreclassificationResult(
                preclassification_type="unknown",
                preclassification_reason="preclassification_disabled",
                routing_decision="safe_fallback",
                use_text_first=False,
                prefer_dynamic_vision=None,
                prefer_full_document_vision=None,
                utility_prompts=document_category == DocumentCategory.UTILITY,
            )

        if mime in IMAGE_MIMES:
            return PreclassificationResult(
                preclassification_type="image_upload",
                preclassification_reason="image_mime",
                routing_decision="vision_single",
                use_text_first=False,
                prefer_dynamic_vision=False,
                prefer_full_document_vision=False,
                utility_prompts=False,
            )

        extension = Path(filename or "").suffix.lower()
        if mime != "application/pdf" and extension not in {".pdf"}:
            return self._unknown("unsupported_mime")

        text_chars = len(hints.raw_text.strip())
        quality = text_quality_score(hints)
        hints_found = hints.critical_hint_count()
        keyword_blob = self._keyword_blob(hints, page_texts)
        page_scores = self._page_scores(total_pages, page_texts)

        if self._is_utility(document_category, keyword_blob):
            vision_route = self._vision_route_for_pages(total_pages)
            return PreclassificationResult(
                preclassification_type="utility_bill",
                preclassification_reason=self._utility_reason(document_category, keyword_blob),
                routing_decision=vision_route,
                use_text_first=False,
                prefer_dynamic_vision=vision_route == "vision_dynamic",
                prefer_full_document_vision=vision_route == "vision_full_document",
                utility_prompts=True,
            )

        if self._is_digital_pdf(text_chars, quality, hints_found, hints):
            return PreclassificationResult(
                preclassification_type="digital_pdf",
                preclassification_reason=self._digital_reason(
                    text_chars, quality, hints_found
                ),
                routing_decision="text_first",
                use_text_first=True,
                prefer_dynamic_vision=False,
                prefer_full_document_vision=False,
                utility_prompts=False,
            )

        if total_pages <= _SHORT_INVOICE_PAGE_THRESHOLD:
            doc_type = (
                "receipt_or_short_invoice"
                if self._looks_like_receipt(keyword_blob, total_pages)
                else "scanned_pdf"
            )
            return PreclassificationResult(
                preclassification_type=doc_type,
                preclassification_reason=self._scanned_reason(
                    text_chars, quality, total_pages
                ),
                routing_decision="vision_full_document",
                use_text_first=False,
                prefer_dynamic_vision=False,
                prefer_full_document_vision=True,
                utility_prompts=False,
            )

        if total_pages >= _LONG_INVOICE_PAGE_THRESHOLD:
            return PreclassificationResult(
                preclassification_type="long_invoice",
                preclassification_reason=self._long_invoice_reason(
                    text_chars, quality, total_pages, page_scores
                ),
                routing_decision="vision_dynamic",
                use_text_first=False,
                prefer_dynamic_vision=True,
                prefer_full_document_vision=False,
                utility_prompts=False,
            )

        return PreclassificationResult(
            preclassification_type="scanned_pdf",
            preclassification_reason=self._scanned_reason(text_chars, quality, total_pages),
            routing_decision="vision_full_document",
            use_text_first=False,
            prefer_dynamic_vision=False,
            prefer_full_document_vision=True,
            utility_prompts=False,
        )

    @staticmethod
    def _unknown(reason: str) -> PreclassificationResult:
        return PreclassificationResult(
            preclassification_type="unknown",
            preclassification_reason=reason,
            routing_decision="safe_fallback",
            use_text_first=False,
            prefer_dynamic_vision=None,
            prefer_full_document_vision=None,
            utility_prompts=False,
        )

    @staticmethod
    def _vision_route_for_pages(total_pages: int) -> str:
        if total_pages > _SHORT_INVOICE_PAGE_THRESHOLD:
            return "vision_dynamic"
        return "vision_full_document"

    @staticmethod
    def _keyword_blob(hints: TextLayerHints, page_texts: tuple[str, ...]) -> str:
        parts = [hints.raw_text.lower()]
        parts.extend(text.lower() for text in page_texts if text)
        return "\n".join(parts)

    @staticmethod
    def _page_scores(total_pages: int, page_texts: tuple[str, ...]) -> dict[int, float]:
        if total_pages <= 0:
            return {}
        texts = list(page_texts) if page_texts else [""] * total_pages
        if len(texts) < total_pages:
            texts.extend([""] * (total_pages - len(texts)))
        return {
            page_num: score_page(page_num, total_pages, texts[page_num - 1])
            for page_num in range(1, total_pages + 1)
        }

    @staticmethod
    def _is_utility(category: DocumentCategory, keyword_blob: str) -> bool:
        if category == DocumentCategory.UTILITY:
            return True
        return any(keyword in keyword_blob for keyword in _UTILITY_KEYWORDS)

    @staticmethod
    def _utility_reason(category: DocumentCategory, keyword_blob: str) -> str:
        if category == DocumentCategory.UTILITY:
            return "document_category_utility"
        return "utility_keywords"

    @staticmethod
    def _is_digital_pdf(
        text_chars: int,
        quality: float,
        hints_found: int,
        hints: TextLayerHints,
    ) -> bool:
        if not settings.openai_text_first_enabled:
            return False
        min_chars = settings.openai_text_first_min_chars
        if text_chars >= min_chars:
            return True
        if hints_found >= len(hints.missing_critical_fields()) and hints_found >= 3:
            return True
        if text_chars >= MIN_PDF_TEXT_CHARS and hints_found >= 2 and quality >= 0.35:
            return True
        if text_chars >= MIN_PDF_TEXT_CHARS and quality >= 0.55:
            return True
        return False

    @staticmethod
    def _digital_reason(text_chars: int, quality: float, hints_found: int) -> str:
        if text_chars >= settings.openai_text_first_min_chars:
            return f"digital_text_chars={text_chars}"
        if hints_found >= 3:
            return f"digital_hints={hints_found}"
        return f"digital_quality={quality:.3f}"

    @staticmethod
    def _scanned_reason(text_chars: int, quality: float, total_pages: int) -> str:
        return (
            f"scanned_text_chars={text_chars} quality={quality:.3f} pages={total_pages}"
        )

    @staticmethod
    def _long_invoice_reason(
        text_chars: int,
        quality: float,
        total_pages: int,
        page_scores: dict[int, float],
    ) -> str:
        selection = select_vision_pages(
            total_pages=total_pages,
            page_texts=None,
        )
        return (
            f"long_invoice_pages={total_pages} text_chars={text_chars} "
            f"quality={quality:.3f} selected={list(selection.selected_pages)}"
        )

    @staticmethod
    def _looks_like_receipt(keyword_blob: str, total_pages: int) -> bool:
        if total_pages > 1:
            return False
        return any(keyword in keyword_blob for keyword in _RECEIPT_KEYWORDS)
