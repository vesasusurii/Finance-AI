"""PDF page rendering for OpenAI Vision — no text/OCR outside OpenAI (doc 8)."""

from __future__ import annotations

import io
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Literal

import pypdfium2 as pdfium

from config import settings
from core.debug_logger import debug_trace, get_logger

logger = get_logger(__name__)

RenderStrategy = Literal["sequential", "parallel"]


@dataclass(frozen=True)
class PdfRenderResult:
    images: list[tuple[bytes, str]]
    page_numbers: list[int]
    render_strategy: RenderStrategy
    render_ms: float
    render_parallel_ms: float | None
    rendered_page_count: int
    render_scale_strategy: str = "fixed"
    page_render_scales: dict[int, float] = field(default_factory=dict)
    page_render_reason: dict[int, str] = field(default_factory=dict)
    average_render_scale: float | None = None
    estimated_image_bytes: int | None = None
    actual_image_bytes: int | None = None
    skipped_page_numbers: tuple[int, ...] = ()


@debug_trace
def pdf_page_count(content: bytes) -> int:
    doc = pdfium.PdfDocument(content)
    try:
        return len(doc)
    finally:
        doc.close()


@debug_trace
def pdf_is_encrypted(content: bytes) -> bool:
    """Return True only when the PDF genuinely requires a password to open."""
    try:
        doc = pdfium.PdfDocument(content)
        doc.close()
        return False
    except Exception as exc:
        msg = str(exc).lower()
        if any(k in msg for k in ("password", "encrypt", "locked", "protected")):
            return True
        return False


def _page_to_jpeg(
    page,
    *,
    scale: float,
    max_dimension: int,
    jpeg_quality: int,
) -> bytes:
    bitmap = page.render(scale=scale)
    pil_image = bitmap.to_pil()
    pil_image.thumbnail((max_dimension, max_dimension))
    buffer = io.BytesIO()
    pil_image.convert("RGB").save(buffer, format="JPEG", quality=jpeg_quality)
    return buffer.getvalue()


def _render_page_at_index(
    content: bytes,
    index: int,
    *,
    scale: float,
    max_dimension: int,
    jpeg_quality: int,
) -> tuple[int, bytes, str]:
    """Render one PDF page — opens its own document handle (thread-safe)."""
    doc = pdfium.PdfDocument(content)
    try:
        jpeg_bytes = _page_to_jpeg(
            doc[index],
            scale=scale,
            max_dimension=max_dimension,
            jpeg_quality=jpeg_quality,
        )
        logger.debug("  rendered page %d: %d bytes scale=%.2f", index + 1, len(jpeg_bytes), scale)
        return index, jpeg_bytes, "image/jpeg"
    finally:
        doc.close()


def _render_sequential_indices(
    content: bytes,
    page_indices: list[int],
    *,
    default_scale: float,
    page_scales: dict[int, float],
    max_dimension: int,
    jpeg_quality: int,
) -> list[tuple[int, tuple[bytes, str]]]:
    doc = pdfium.PdfDocument(content)
    try:
        out: list[tuple[int, tuple[bytes, str]]] = []
        for index in page_indices:
            page_num = index + 1
            scale = page_scales.get(page_num, default_scale)
            jpeg_bytes = _page_to_jpeg(
                doc[index],
                scale=scale,
                max_dimension=max_dimension,
                jpeg_quality=jpeg_quality,
            )
            logger.debug(
                "  rendered page %d/%d: %d bytes scale=%.2f",
                page_num,
                len(doc),
                len(jpeg_bytes),
                scale,
            )
            out.append((index, (jpeg_bytes, "image/jpeg")))
        return out
    finally:
        doc.close()


def _render_parallel_indices(
    content: bytes,
    page_indices: list[int],
    *,
    default_scale: float,
    page_scales: dict[int, float],
    max_dimension: int,
    jpeg_quality: int,
    max_workers: int,
) -> tuple[list[tuple[int, tuple[bytes, str]]], float]:
    workers = max(1, min(max_workers, len(page_indices)))
    ordered: list[tuple[int, tuple[bytes, str]] | None] = [None] * len(page_indices)
    index_positions = {index: pos for pos, index in enumerate(page_indices)}
    parallel_t0 = time.perf_counter()

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(
                _render_page_at_index,
                content,
                index,
                scale=page_scales.get(index + 1, default_scale),
                max_dimension=max_dimension,
                jpeg_quality=jpeg_quality,
            ): index
            for index in page_indices
        }
        for future in as_completed(futures):
            index, jpeg_bytes, mime = future.result()
            pos = index_positions[index]
            ordered[pos] = (index, (jpeg_bytes, mime))

    if any(item is None for item in ordered):
        raise RuntimeError("Parallel PDF render returned incomplete page set")

    parallel_ms = round((time.perf_counter() - parallel_t0) * 1000, 1)
    return [item for item in ordered if item is not None], parallel_ms


@debug_trace
def render_pdf_pages(
    content: bytes,
    *,
    max_pages: int | None = None,
    scale: float | None = None,
    page_indices: list[int] | None = None,
    page_scales: dict[int, float] | None = None,
    page_render_reason: dict[int, str] | None = None,
    render_scale_strategy: str = "fixed",
    skipped_page_numbers: tuple[int, ...] = (),
    estimated_image_bytes: int | None = None,
    max_dimension: int = 2048,
    jpeg_quality: int = 92,
    parallel: bool | None = None,
    max_workers: int | None = None,
) -> PdfRenderResult:
    """Rasterise PDF pages to JPEG for OpenAI Vision."""
    render_t0 = time.perf_counter()
    default_scale = scale if scale is not None else settings.openai_pdf_render_scale
    scales = page_scales or {}

    doc = pdfium.PdfDocument(content)
    try:
        total = len(doc)
        capped_total = total if max_pages is None else min(total, max_pages)
    finally:
        doc.close()

    if capped_total == 0:
        return PdfRenderResult(
            images=[],
            page_numbers=[],
            render_strategy="sequential",
            render_ms=0.0,
            render_parallel_ms=None,
            rendered_page_count=0,
            render_scale_strategy=render_scale_strategy,
            skipped_page_numbers=skipped_page_numbers,
        )

    indices = page_indices if page_indices is not None else list(range(capped_total))
    indices = [index for index in indices if 0 <= index < capped_total]
    if not indices:
        return PdfRenderResult(
            images=[],
            page_numbers=[],
            render_strategy="sequential",
            render_ms=0.0,
            render_parallel_ms=None,
            rendered_page_count=0,
            render_scale_strategy=render_scale_strategy,
            skipped_page_numbers=skipped_page_numbers,
        )

    use_parallel = (
        settings.openai_parallel_pdf_rendering if parallel is None else parallel
    )
    workers = (
        settings.openai_pdf_render_workers if max_workers is None else max_workers
    )
    strategy: RenderStrategy = "sequential"
    render_parallel_ms: float | None = None
    rendered_pairs: list[tuple[int, tuple[bytes, str]]]

    if use_parallel and len(indices) > 1:
        try:
            rendered_pairs, render_parallel_ms = _render_parallel_indices(
                content,
                indices,
                default_scale=default_scale,
                page_scales=scales,
                max_dimension=max_dimension,
                jpeg_quality=jpeg_quality,
                max_workers=workers,
            )
            strategy = "parallel"
        except Exception as exc:
            logger.warning(
                "Parallel PDF render failed (%d pages), falling back to sequential: %s",
                len(indices),
                exc,
            )
            rendered_pairs = _render_sequential_indices(
                content,
                indices,
                default_scale=default_scale,
                page_scales=scales,
                max_dimension=max_dimension,
                jpeg_quality=jpeg_quality,
            )
    else:
        rendered_pairs = _render_sequential_indices(
            content,
            indices,
            default_scale=default_scale,
            page_scales=scales,
            max_dimension=max_dimension,
            jpeg_quality=jpeg_quality,
        )

    images = [pair[1] for pair in rendered_pairs]
    page_numbers = [index + 1 for index, _ in rendered_pairs]
    actual_image_bytes = sum(len(img) for img, _mime in images)
    average_scale = (
        round(sum(scales.get(p, default_scale) for p in page_numbers) / len(page_numbers), 3)
        if page_numbers
        else None
    )

    render_ms = round((time.perf_counter() - render_t0) * 1000, 1)
    logger.debug(
        "Rendered PDF pages: count=%d strategy=%s render_ms=%s parallel_ms=%s bytes=%d",
        len(images),
        strategy,
        render_ms,
        render_parallel_ms,
        actual_image_bytes,
    )
    return PdfRenderResult(
        images=images,
        page_numbers=page_numbers,
        render_strategy=strategy,
        render_ms=render_ms,
        render_parallel_ms=render_parallel_ms,
        rendered_page_count=len(images),
        render_scale_strategy=render_scale_strategy,
        page_render_scales={p: scales.get(p, default_scale) for p in page_numbers},
        page_render_reason=page_render_reason or {},
        average_render_scale=average_scale,
        estimated_image_bytes=estimated_image_bytes,
        actual_image_bytes=actual_image_bytes,
        skipped_page_numbers=skipped_page_numbers,
    )


@debug_trace
def render_pdf_pages_as_images(
    content: bytes,
    *,
    max_pages: int | None = None,
    scale: float | None = None,
    max_dimension: int = 2048,
    jpeg_quality: int = 92,
) -> list[tuple[bytes, str]]:
    """Rasterise PDF pages to JPEG for OpenAI Vision (images only)."""
    return render_pdf_pages(
        content,
        max_pages=max_pages,
        scale=scale,
        max_dimension=max_dimension,
        jpeg_quality=jpeg_quality,
    ).images
