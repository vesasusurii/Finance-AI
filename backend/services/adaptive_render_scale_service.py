"""Choose per-page PDF render scale from lightweight content heuristics."""

from __future__ import annotations

from dataclasses import dataclass

from config import settings
from core.debug_logger import get_logger
from services.ocr.pdf_page_analyzer import PageContentAnalysis

logger = get_logger(__name__)

_SMALL_FONT_THRESHOLD = 8.5
_DENSE_TABLE_BLOCKS = 18
_DENSE_TABLE_DENSITY = 0.35


@dataclass(frozen=True)
class PageRenderPlan:
    page_num: int
    scale: float
    reason: str
    tier: str


@dataclass(frozen=True)
class AdaptiveRenderPlan:
    pages: tuple[PageRenderPlan, ...]
    skipped_pages: tuple[int, ...]
    strategy: str

    def metadata(self, *, actual_image_bytes: int, estimated_image_bytes: int) -> dict[str, object]:
        scales = {plan.page_num: plan.scale for plan in self.pages}
        reasons = {plan.page_num: plan.reason for plan in self.pages}
        rendered = [plan.page_num for plan in self.pages]
        average = (
            round(sum(scales.values()) / len(scales), 3) if scales else None
        )
        return {
            "render_scale_strategy": self.strategy,
            "page_render_scales": {str(k): v for k, v in scales.items()},
            "page_render_reason": {str(k): v for k, v in reasons.items()},
            "average_render_scale": average,
            "estimated_image_bytes": estimated_image_bytes,
            "actual_image_bytes": actual_image_bytes,
            "rendered_page_numbers": rendered,
            "skipped_render_pages": list(self.skipped_pages),
        }


def _scale_for_tier(tier: str) -> float:
    if tier == "high":
        return settings.openai_render_scale_high
    if tier == "low":
        return settings.openai_render_scale_low
    return settings.openai_render_scale_medium


def choose_render_tier(
    *,
    page_num: int,
    total_pages: int,
    analysis: PageContentAnalysis | None,
) -> tuple[str, str]:
    """Return (tier, reason) for a 1-based page index."""
    if page_num == 1:
        return "high", "invoice header"
    if total_pages > 1 and page_num == total_pages:
        return "high", "totals and payment details"

    if analysis is None or analysis.text_length == 0:
        if page_num == 1 or page_num == total_pages:
            return "high", "positional default"
        return "medium", "scanned page default"

    if analysis.has_totals or analysis.has_bank_details:
        return "high", "totals or bank details"
    if analysis.has_invoice_number:
        return "high", "invoice number"
    if analysis.avg_font_size is not None and analysis.avg_font_size < _SMALL_FONT_THRESHOLD:
        return "high", "small text"
    if (
        analysis.text_block_count >= _DENSE_TABLE_BLOCKS
        and analysis.text_density >= _DENSE_TABLE_DENSITY
    ):
        return "high", "dense table"

    if analysis.mostly_whitespace:
        return "low", "mostly whitespace"
    if analysis.mostly_line_items and (
        analysis.avg_font_size is None or analysis.avg_font_size >= 10.0
    ):
        return "low", "line items"
    if analysis.text_length < 80 and page_num not in (1, total_pages):
        return "low", "continuation page"

    return "medium", "normal content"


def build_adaptive_render_plan(
    *,
    total_pages: int,
    pages_to_render: list[int],
    analyses: list[PageContentAnalysis] | None,
    use_adaptive: bool | None = None,
) -> AdaptiveRenderPlan:
    """Build per-page render scales for the pages that will be rasterised."""
    adaptive = (
        settings.openai_adaptive_render_scale
        if use_adaptive is None
        else use_adaptive
    )
    analysis_by_page = {item.page_num: item for item in (analyses or [])}
    skipped = tuple(
        page_num
        for page_num in range(1, total_pages + 1)
        if page_num not in pages_to_render
    )

    if not adaptive:
        fixed = settings.openai_pdf_render_scale
        plans = tuple(
            PageRenderPlan(
                page_num=page_num,
                scale=fixed,
                reason="fixed scale",
                tier="fixed",
            )
            for page_num in sorted(pages_to_render)
        )
        return AdaptiveRenderPlan(
            pages=plans,
            skipped_pages=skipped,
            strategy="fixed",
        )

    plans: list[PageRenderPlan] = []
    for page_num in sorted(pages_to_render):
        tier, reason = choose_render_tier(
            page_num=page_num,
            total_pages=total_pages,
            analysis=analysis_by_page.get(page_num),
        )
        plans.append(
            PageRenderPlan(
                page_num=page_num,
                scale=_scale_for_tier(tier),
                reason=reason,
                tier=tier,
            )
        )

    return AdaptiveRenderPlan(
        pages=tuple(plans),
        skipped_pages=skipped,
        strategy="adaptive",
    )


def log_render_plan(
    *,
    total_pages: int,
    plan: AdaptiveRenderPlan,
) -> None:
    """Log render scale decisions for every page in the document."""
    rendered = {item.page_num: item for item in plan.pages}
    for page_num in range(1, total_pages + 1):
        if page_num in rendered:
            item = rendered[page_num]
            logger.info(
                "Page %d → scale %.2f (%s)",
                page_num,
                item.scale,
                item.reason,
            )
        else:
            logger.info("Page %d → skipped", page_num)


def estimate_image_bytes(
    *,
    page_count: int,
    average_scale: float,
    baseline_scale: float = 1.5,
    baseline_bytes_per_page: int = 180_000,
) -> int:
    """Rough JPEG size estimate from average render scale."""
    if page_count <= 0:
        return 0
    ratio = (average_scale / baseline_scale) ** 2
    return int(page_count * baseline_bytes_per_page * ratio)
