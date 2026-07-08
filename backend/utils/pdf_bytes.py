"""PDF byte inspection helpers for serve-path validation and diagnostics."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

_PDF_MAGIC = b"%PDF"
_EOF_MARKER = b"%%EOF"


@dataclass(frozen=True)
class PdfByteReport:
    size: int
    sha256: str
    starts_with_pdf: bool
    has_eof_marker: bool
    pdf_start_offset: int
    leading_prefix_len: int
    first_16_hex: str
    last_16_hex: str

    @property
    def looks_like_pdf(self) -> bool:
        return self.starts_with_pdf and self.size > 0

    @property
    def likely_truncated(self) -> bool:
        return (
            self.starts_with_pdf
            and self.size > 0
            and not self.has_eof_marker
        )


def find_pdf_start(data: bytes, *, scan_limit: int = 4096) -> int:
    """Return byte offset of the first %PDF header, or -1 if not found."""
    if not data:
        return -1
    window = data[:scan_limit]
    idx = window.find(_PDF_MAGIC)
    return idx if idx >= 0 else -1


def has_pdf_eof_marker(data: bytes) -> bool:
    """Return True when %%EOF appears anywhere in the file (PDFs may have multiple)."""
    if not data:
        return False
    if _EOF_MARKER in data:
        return True
    tail = data[-4096:] if len(data) > 4096 else data
    return b"%EOF" in tail


def has_pdf_tail_markers(data: bytes) -> bool:
    """Return True when the file tail looks like a finished PDF."""
    if not data:
        return False
    if has_pdf_eof_marker(data):
        return True
    tail = data[-8192:] if len(data) > 8192 else data
    return b"startxref" in tail


def normalize_pdf_bytes(data: bytes) -> bytes:
    """Strip leading non-PDF bytes (BOM, HTTP wrapper text, etc.)."""
    offset = find_pdf_start(data)
    if offset <= 0:
        return data
    return data[offset:]


def inspect_pdf_bytes(data: bytes) -> PdfByteReport:
    offset = find_pdf_start(data)
    normalized = data if offset <= 0 else data[offset:]
    first = normalized[:16]
    last = normalized[-16:] if normalized else b""
    return PdfByteReport(
        size=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
        starts_with_pdf=normalized.startswith(_PDF_MAGIC),
        has_eof_marker=has_pdf_eof_marker(normalized),
        pdf_start_offset=offset,
        leading_prefix_len=max(offset, 0),
        first_16_hex=first.hex(),
        last_16_hex=last.hex(),
    )


def format_pdf_report(report: PdfByteReport) -> str:
    return (
        f"size={report.size} sha256={report.sha256[:16]}… "
        f"pdf_offset={report.pdf_start_offset} eof={report.has_eof_marker} "
        f"first16={report.first_16_hex} last16={report.last_16_hex}"
    )


def looks_like_html_or_json(data: bytes) -> bool:
    head = data[:256].lstrip()
    if not head:
        return False
    if head.startswith((b"{", b"[", b"<")):
        text = head.decode("utf-8", errors="ignore").lower()
        return bool(
            re.search(r"<!doctype\s+html|<html\b|application/json", text)
            or text.startswith("{")
        )
    return False
