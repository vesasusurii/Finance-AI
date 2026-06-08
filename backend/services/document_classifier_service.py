"""Lightweight invoice document-type classifier (content-first, filename fallback)."""

from __future__ import annotations

from core.debug_logger import get_logger
from core.document_categories import DocumentCategory

logger = get_logger(__name__)


_UTILITY_MARKERS = (
    "kesco",
    "ujesjelles",
    "ujësjellës",
    "ujesjell",
    "regional water",
    "pastrimi",
    "mbeturinave",
    "nr. ref.",
    "shifra e konsumatorit",
    "borxhi kesco",
)

_ALBANIAN_RETAIL_MARKERS = (
    "fatura - invoice",
    "fatura-invoice",
    "numri i faturës",
    "invoice number",
    "detajet e blerësit",
    "buyer detail",
    "vlera me tvsh",
    "amount with vat",
    "gjithësejt vlerat",
    "gjithsejt vlerat",
    "sh.p.k.",
)

_FREELANCER_MARKERS = (
    "total hours worked",
    "hourly rate",
    "web development",
    "timesheet",
    "hours worked",
    "rate (€)",
    "rate (eur)",
)


class DocumentClassifierService:
    """Classify invoices before Vision extraction to select prompt blocks."""

    def classify(
        self,
        text: str | None,
        *,
        filename: str = "",
    ) -> DocumentCategory:
        blob = self._normalise_blob(text, filename)
        if not blob:
            return DocumentCategory.GENERIC

        if self._matches(blob, _UTILITY_MARKERS):
            category = DocumentCategory.UTILITY
        elif self._matches(blob, _ALBANIAN_RETAIL_MARKERS):
            category = DocumentCategory.ALBANIAN_RETAIL
        elif self._matches(blob, _FREELANCER_MARKERS):
            category = DocumentCategory.FREELANCER
        else:
            category = DocumentCategory.GENERIC

        logger.debug(
            "Document classified as %s (filename=%r text_len=%d)",
            category.value,
            filename,
            len(text or ""),
        )
        return category

    @staticmethod
    def _normalise_blob(text: str | None, filename: str) -> str:
        parts = [filename.lower()]
        if text:
            ascii_blob = (
                text.lower()
                .replace("ë", "e")
                .replace("ç", "c")
                .replace("ü", "u")
            )
            parts.append(ascii_blob)
        return " ".join(parts)

    @staticmethod
    def _matches(blob: str, markers: tuple[str, ...]) -> bool:
        return any(marker in blob for marker in markers)
