"""PDF page rendering for OpenAI Vision — no text/OCR outside OpenAI (doc 8)."""

from __future__ import annotations

import io
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Literal

import pypdfium2 as pdfium

from config import settings
from core.debug_logger import debug_trace, get_logger

logger = get_logger(__name__)

RenderStrategy = Literal["sequential", "parallel"]


@dataclass(frozen=True)
class PdfRenderResult:
    images: list[tuple[bytes, str]]
    render_strategy: RenderStrategy
    render_ms: float
    render_parallel_ms: float | None
    rendered_page_count: int


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
        logger.debug("  rendered page %d: %d bytes", index + 1, len(jpeg_bytes))
        return index, jpeg_bytes, "image/jpeg"
    finally:
        doc.close()


def _render_sequential(
    content: bytes,
    page_count: int,
    *,
    scale: float,
    max_dimension: int,
    jpeg_quality: int,
) -> list[tuple[bytes, str]]:
    doc = pdfium.PdfDocument(content)
    try:
        out: list[tuple[bytes, str]] = []
        for index in range(page_count):
            jpeg_bytes = _page_to_jpeg(
                doc[index],
                scale=scale,
                max_dimension=max_dimension,
                jpeg_quality=jpeg_quality,
            )
            logger.debug(
                "  rendered page %d/%d: %d bytes",
                index + 1,
                page_count,
                len(jpeg_bytes),
            )
            out.append((jpeg_bytes, "image/jpeg"))
        return out
    finally:
        doc.close()


def _render_parallel(
    content: bytes,
    page_count: int,
    *,
    scale: float,
    max_dimension: int,
    jpeg_quality: int,
    max_workers: int,
) -> tuple[list[tuple[bytes, str]], float]:
    workers = max(1, min(max_workers, page_count))
    ordered: list[tuple[bytes, str] | None] = [None] * page_count
    parallel_t0 = time.perf_counter()

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [
            pool.submit(
                _render_page_at_index,
                content,
                index,
                scale=scale,
                max_dimension=max_dimension,
                jpeg_quality=jpeg_quality,
            )
            for index in range(page_count)
        ]
        for future in as_completed(futures):
            index, jpeg_bytes, mime = future.result()
            ordered[index] = (jpeg_bytes, mime)

    if any(item is None for item in ordered):
        raise RuntimeError("Parallel PDF render returned incomplete page set")

    parallel_ms = round((time.perf_counter() - parallel_t0) * 1000, 1)
    return [item for item in ordered if item is not None], parallel_ms


@debug_trace
def render_pdf_pages(
    content: bytes,
    *,
    max_pages: int | None = None,
    scale: float = 2.5,
    max_dimension: int = 2048,
    jpeg_quality: int = 92,
    parallel: bool | None = None,
    max_workers: int | None = None,
) -> PdfRenderResult:
    """Rasterise PDF pages to JPEG for OpenAI Vision."""
    render_t0 = time.perf_counter()
    doc = pdfium.PdfDocument(content)
    try:
        total = len(doc)
        page_count = total if max_pages is None else min(total, max_pages)
    finally:
        doc.close()

    if page_count == 0:
        return PdfRenderResult(
            images=[],
            render_strategy="sequential",
            render_ms=0.0,
            render_parallel_ms=None,
            rendered_page_count=0,
        )

    use_parallel = (
        settings.openai_parallel_pdf_rendering if parallel is None else parallel
    )
    workers = (
        settings.openai_pdf_render_workers if max_workers is None else max_workers
    )
    strategy: RenderStrategy = "sequential"
    render_parallel_ms: float | None = None
    images: list[tuple[bytes, str]]

    if use_parallel and page_count > 1:
        try:
            images, render_parallel_ms = _render_parallel(
                content,
                page_count,
                scale=scale,
                max_dimension=max_dimension,
                jpeg_quality=jpeg_quality,
                max_workers=workers,
            )
            strategy = "parallel"
        except Exception as exc:
            logger.warning(
                "Parallel PDF render failed (%d pages), falling back to sequential: %s",
                page_count,
                exc,
            )
            images = _render_sequential(
                content,
                page_count,
                scale=scale,
                max_dimension=max_dimension,
                jpeg_quality=jpeg_quality,
            )
    else:
        images = _render_sequential(
            content,
            page_count,
            scale=scale,
            max_dimension=max_dimension,
            jpeg_quality=jpeg_quality,
        )

    render_ms = round((time.perf_counter() - render_t0) * 1000, 1)
    logger.debug(
        "Rendered PDF pages: count=%d strategy=%s render_ms=%s parallel_ms=%s",
        len(images),
        strategy,
        render_ms,
        render_parallel_ms,
    )
    return PdfRenderResult(
        images=images,
        render_strategy=strategy,
        render_ms=render_ms,
        render_parallel_ms=render_parallel_ms,
        rendered_page_count=len(images),
    )


@debug_trace
def render_pdf_pages_as_images(
    content: bytes,
    *,
    max_pages: int | None = None,
    scale: float = 2.5,
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
