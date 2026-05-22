"""PDF text extraction and page rendering for OpenAI Vision (doc 8)."""

from __future__ import annotations

import io
import logging

import pdfplumber
import pypdfium2 as pdfium
from pdfminer.pdfdocument import PDFPasswordIncorrect

logger = logging.getLogger(__name__)

MIN_PDF_TEXT_CHARS = 80
GARBLED_REPLACEMENT_RATIO = 0.02


def pdf_page_count(content: bytes) -> int:
    doc = pdfium.PdfDocument(content)
    try:
        return len(doc)
    finally:
        doc.close()


def pdf_is_encrypted(content: bytes) -> bool:
    try:
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            doc = getattr(pdf, "doc", None)
            if doc is not None and getattr(doc, "is_encrypted", False):
                return True
    except PDFPasswordIncorrect:
        return True
    except Exception:
        logger.debug("Could not determine PDF encryption via pdfplumber", exc_info=True)
    return False


def extract_pdf_text(content: bytes, max_pages: int | None = None) -> str:
    """Extract text with page markers for multi-page invoices."""
    parts: list[str] = []
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        pages = pdf.pages if max_pages is None else pdf.pages[:max_pages]
        for index, page in enumerate(pages, start=1):
            text = (page.extract_text() or "").strip()
            parts.append(f"--- Page {index} ---\n{text}")
    return "\n\n".join(parts)


def pdf_text_usable(text: str) -> bool:
    stripped = text.strip()
    if len(stripped) < MIN_PDF_TEXT_CHARS:
        return False
    if stripped.count("\ufffd") / max(len(stripped), 1) > GARBLED_REPLACEMENT_RATIO:
        return False
    return True


def render_pdf_pages_as_images(
    content: bytes,
    *,
    max_pages: int | None = None,
    scale: float = 2.5,
    max_dimension: int = 2048,
    jpeg_quality: int = 92,
) -> list[tuple[bytes, str]]:
    """Return (jpeg_bytes, mime) per page for Vision API."""
    doc = pdfium.PdfDocument(content)
    try:
        total = len(doc)
        page_count = total if max_pages is None else min(total, max_pages)
        out: list[tuple[bytes, str]] = []

        for index in range(page_count):
            page = doc[index]
            bitmap = page.render(scale=scale)
            pil_image = bitmap.to_pil()
            pil_image.thumbnail((max_dimension, max_dimension))
            buffer = io.BytesIO()
            pil_image.convert("RGB").save(buffer, format="JPEG", quality=jpeg_quality)
            out.append((buffer.getvalue(), "image/jpeg"))

        return out
    finally:
        doc.close()
