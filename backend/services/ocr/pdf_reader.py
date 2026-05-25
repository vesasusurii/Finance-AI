"""PDF page rendering for OpenAI Vision — no text/OCR outside OpenAI (doc 8)."""

from __future__ import annotations

import io

import pypdfium2 as pdfium


def pdf_page_count(content: bytes) -> int:
    doc = pdfium.PdfDocument(content)
    try:
        return len(doc)
    finally:
        doc.close()


def pdf_is_encrypted(content: bytes) -> bool:
    """Return True only when the PDF genuinely requires a password to open.

    Previous implementation caught *every* exception and returned True, which
    meant any rendering hiccup (memory, codec, unusual PDF variant) would
    silently reject a valid document as "encrypted".  Now we only return True
    when pypdfium2 signals a password/encryption problem.
    """
    try:
        doc = pdfium.PdfDocument(content)
        doc.close()
        return False
    except Exception as exc:
        msg = str(exc).lower()
        # pypdfium2 / PDFium surfaces password problems via error messages
        if any(k in msg for k in ("password", "encrypt", "locked", "protected")):
            return True
        # Any other exception (corrupt page, codec issue, etc.) — not our
        # concern here; let the render step surface the real error.
        return False


def render_pdf_pages_as_images(
    content: bytes,
    *,
    max_pages: int | None = None,
    scale: float = 2.5,
    max_dimension: int = 2048,
    jpeg_quality: int = 92,
) -> list[tuple[bytes, str]]:
    """Rasterise PDF pages to JPEG for OpenAI Vision."""
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
