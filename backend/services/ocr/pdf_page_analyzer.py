"""Lightweight per-page PDF content analysis for adaptive render scale."""

from __future__ import annotations

import io
import re
from dataclasses import dataclass

from core.debug_logger import debug_trace, get_logger
from services.ocr.pdf_text_extractor import parse_text_layer_hints

logger = get_logger(__name__)

_RE_SIGNATURE = re.compile(
    r"\b(signature|signed|unterschrift|firm|stamp)\b",
    re.IGNORECASE,
)
_RE_LINE_ITEM = re.compile(
    r"\b(qty|quantity|description|unit price|line total|pos\.?)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class PageContentAnalysis:
    """Heuristic signals extracted from a PDF page text layer."""

    page_num: int
    text_length: int
    text_density: float
    whitespace_ratio: float
    avg_font_size: float | None
    text_block_count: int
    has_totals: bool
    has_invoice_number: bool
    has_vat: bool
    has_bank_details: bool
    has_signature: bool
    mostly_line_items: bool
    mostly_whitespace: bool


def _analysis_from_text(page_num: int, text: str, *, page_area: float) -> PageContentAnalysis:
    stripped = text.strip()
    text_length = len(stripped)
    hints = parse_text_layer_hints(stripped) if stripped else None

    lines = [line.strip() for line in stripped.splitlines() if line.strip()]
    text_block_count = max(1, len(lines)) if stripped else 0
    text_density = round((text_length / max(page_area, 1.0)) * 1000.0, 3)

    char_estimate = max(text_length, 1)
    whitespace_ratio = round(
        max(0.0, 1.0 - min(1.0, text_length / max(page_area * 0.15, 1.0))),
        3,
    )

    lowered = stripped.lower()
    has_totals = any(
        token in lowered
        for token in (
            "total",
            "amount due",
            "grand total",
            "zahlbetrag",
            "gesamtbetrag",
            "balance due",
        )
    )
    has_invoice_number = bool(hints and hints.invoice_number)
    has_vat = bool(hints and hints.vat_amount is not None) or any(
        token in lowered for token in ("vat", "mwst", "tvsh")
    )
    has_bank_details = bool(hints and hints.account_details) or "iban" in lowered
    has_signature = bool(_RE_SIGNATURE.search(stripped))
    mostly_line_items = bool(_RE_LINE_ITEM.search(stripped)) and not has_totals
    mostly_whitespace = text_length < 40 or whitespace_ratio >= 0.92

    avg_font_size: float | None = None

    return PageContentAnalysis(
        page_num=page_num,
        text_length=text_length,
        text_density=text_density,
        whitespace_ratio=whitespace_ratio,
        avg_font_size=avg_font_size,
        text_block_count=text_block_count,
        has_totals=has_totals,
        has_invoice_number=has_invoice_number,
        has_vat=has_vat,
        has_bank_details=has_bank_details,
        has_signature=has_signature,
        mostly_line_items=mostly_line_items,
        mostly_whitespace=mostly_whitespace,
    )


@debug_trace
def analyze_pdf_pages(content: bytes) -> list[PageContentAnalysis]:
    """Analyse every PDF page using inexpensive text-layer heuristics."""
    try:
        import pdfplumber
    except ImportError:
        logger.warning("pdfplumber not installed - PDF page analysis disabled")
        return []

    analyses: list[PageContentAnalysis] = []
    try:
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            for index, page in enumerate(pdf.pages, start=1):
                text = page.extract_text() or ""
                width = float(page.width or 612.0)
                height = float(page.height or 792.0)
                page_area = max(width * height, 1.0)

                analysis = _analysis_from_text(index, text, page_area=page_area)
                chars = page.chars or []
                if chars:
                    sizes = [
                        float(ch.get("size") or 0.0)
                        for ch in chars
                        if ch.get("size")
                    ]
                    if sizes:
                        avg_size = round(sum(sizes) / len(sizes), 2)
                        analysis = PageContentAnalysis(
                            page_num=analysis.page_num,
                            text_length=analysis.text_length,
                            text_density=round(
                                len(chars) / max(page_area, 1.0) * 1000.0,
                                3,
                            ),
                            whitespace_ratio=analysis.whitespace_ratio,
                            avg_font_size=avg_size,
                            text_block_count=analysis.text_block_count,
                            has_totals=analysis.has_totals,
                            has_invoice_number=analysis.has_invoice_number,
                            has_vat=analysis.has_vat,
                            has_bank_details=analysis.has_bank_details,
                            has_signature=analysis.has_signature,
                            mostly_line_items=analysis.mostly_line_items,
                            mostly_whitespace=analysis.mostly_whitespace,
                        )
                analyses.append(analysis)
    except Exception as exc:
        logger.warning("PDF page analysis failed: %s", exc)
        return []

    return analyses
