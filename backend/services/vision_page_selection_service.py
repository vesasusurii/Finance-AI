"""Lightweight page scoring and selection before OpenAI Vision."""

from __future__ import annotations

from dataclasses import dataclass

from config import settings
from services.ocr.pdf_text_extractor import parse_text_layer_hints

# Keyword hits on extracted page text (case-insensitive substring match).
_KEYWORD_WEIGHTS: tuple[tuple[str, int], ...] = (
    ("invoice number", 4),
    ("invoice no", 4),
    ("rechnungsnummer", 4),
    ("fatura", 3),
    ("rechnung", 3),
    ("total", 2),
    ("grand total", 3),
    ("amount due", 4),
    ("balance due", 3),
    ("vat", 3),
    ("mwst", 3),
    ("tvsh", 3),
    ("iban", 5),
    ("bank", 2),
    ("due date", 3),
    ("payment due", 3),
    ("supplier", 2),
    ("customer", 2),
    ("bill to", 2),
    ("ship to", 1),
    ("zahlbetrag", 3),
    ("gesamtbetrag", 3),
)

# Middle pages must reach this score to be included beyond first/last.
_MIDDLE_PAGE_SCORE_THRESHOLD = 6

# Position bonuses applied before keyword scoring.
_FIRST_PAGE_BONUS = 100.0
_LAST_PAGE_BONUS = 90.0


@dataclass(frozen=True)
class VisionPageSelection:
    """Result of dynamic Vision page selection."""

    selected_pages: tuple[int, ...]
    skipped_pages: tuple[int, ...]
    page_scores: dict[int, float]
    strategy: str

    def metadata(self) -> dict[str, object]:
        return {
            "page_selection_strategy": self.strategy,
            "selected_vision_pages": list(self.selected_pages),
            "skipped_vision_pages": list(self.skipped_pages),
            "page_scores": {str(k): v for k, v in self.page_scores.items()},
        }


def score_page(page_num: int, total_pages: int, page_text: str) -> float:
    """Score a 1-based page for invoice-critical content likelihood."""
    score = 0.0

    if page_num == 1:
        score += _FIRST_PAGE_BONUS
    elif page_num == total_pages and total_pages > 1:
        score += _LAST_PAGE_BONUS

    text = page_text.strip()
    if not text:
        return round(score, 2)

    lowered = text.lower()
    for keyword, weight in _KEYWORD_WEIGHTS:
        if keyword in lowered:
            score += weight

    hints = parse_text_layer_hints(text)
    score += hints.critical_hint_count() * 5
    if hints.account_details:
        score += 4
    if hints.due_date:
        score += 3
    if hints.vat_amount is not None:
        score += 3

    return round(score, 2)


def select_vision_pages(
    *,
    total_pages: int,
    page_texts: list[str] | None = None,
    max_pages: int | None = None,
) -> VisionPageSelection:
    """
    Select pages for Vision extraction.

    Always includes page 1. For multi-page PDFs, always includes the last page.
    Middle pages are added in score order while capacity remains.
    """
    if total_pages <= 0:
        return VisionPageSelection(
            selected_pages=(),
            skipped_pages=(),
            page_scores={},
            strategy="dynamic_empty",
        )

    cap = max(1, max_pages or settings.openai_dynamic_page_selection_max_pages)
    texts = page_texts or [""] * total_pages
    if len(texts) < total_pages:
        texts = list(texts) + [""] * (total_pages - len(texts))

    page_scores = {
        page_num: score_page(page_num, total_pages, texts[page_num - 1])
        for page_num in range(1, total_pages + 1)
    }

    selected: list[int] = [1]
    if total_pages > 1:
        selected.append(total_pages)

    middle_pages = [
        page_num
        for page_num in range(2, total_pages)
        if page_num not in selected
    ]
    middle_pages.sort(
        key=lambda p: page_scores[p],
        reverse=True,
    )

    for page_num in middle_pages:
        if len(selected) >= cap:
            break
        if page_scores[page_num] >= _MIDDLE_PAGE_SCORE_THRESHOLD:
            selected.append(page_num)

    selected_sorted = tuple(sorted(set(selected)))
    skipped = tuple(
        page_num
        for page_num in range(1, total_pages + 1)
        if page_num not in selected_sorted
    )

    if len(selected_sorted) == total_pages:
        strategy = "dynamic_all_pages"
    elif len(selected_sorted) <= 2 and total_pages > 2:
        strategy = "dynamic_first_last"
    else:
        strategy = "dynamic_scored"

    return VisionPageSelection(
        selected_pages=selected_sorted,
        skipped_pages=skipped,
        page_scores=page_scores,
        strategy=strategy,
    )
