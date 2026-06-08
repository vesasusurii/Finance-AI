"""PDF text-layer extraction for hybrid invoice OCR (pdfplumber)."""

from __future__ import annotations

import io
import re
from dataclasses import dataclass

from core.debug_logger import debug_trace, get_logger

logger = get_logger(__name__)

MIN_PDF_TEXT_CHARS = 80


@dataclass(frozen=True)
class TextLayerHints:
    """Structured hints parsed from PDF text layer."""

    raw_text: str
    invoice_number: str | None = None
    invoice_date: str | None = None
    amount: float | None = None
    name_of_company: str | None = None

    @property
    def has_usable_text(self) -> bool:
        return len(self.raw_text.strip()) >= MIN_PDF_TEXT_CHARS


_RE_INVOICE_TITLE = re.compile(
    r"(?:FATURA\s*[-/]?\s*INVOICE|INVOICE)\s+([A-Z0-9][\w./-]{1,20})",
    re.IGNORECASE,
)
_RE_INVOICE_LABEL = re.compile(
    r"(?:Numri i faturës|Invoice number|Fatura Nr\.?|Belegnummer)\s*[:\s]+([A-Z0-9][\w./-]{1,20})",
    re.IGNORECASE,
)
_RE_DATE = re.compile(
    r"(?:Data e faturës|Invoice date|Datum|Date)\s*[:\s]+(\d{1,2}[./]\d{1,2}[./]\d{2,4})",
    re.IGNORECASE,
)
_RE_AMOUNT_WITH_VAT = re.compile(
    r"(?:Vlera me TVSH|Amount with VAT|Total Amount Due|Gjithësejt vlerat|Gjithsejt vlerat)"
    r"[^\d]{0,40}(\d{1,3}(?:[.,]\d{3})*[.,]\d{2})",
    re.IGNORECASE,
)
_RE_ISSUER_SHPK = re.compile(
    r"([A-ZÀ-Ÿ][\w\s.&\"'-]+SH\.?P\.?K\.?)",
    re.IGNORECASE,
)


@debug_trace
def extract_pdf_text(content: bytes) -> str:
    """Extract concatenated text from all PDF pages."""
    try:
        import pdfplumber
    except ImportError:
        logger.warning("pdfplumber not installed — text-layer extraction disabled")
        return ""

    chunks: list[str] = []
    try:
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text() or ""
                if page_text.strip():
                    chunks.append(page_text)
    except Exception as exc:
        logger.warning("PDF text extraction failed: %s", exc)
        return ""

    return "\n".join(chunks)


def _parse_amount(raw: str) -> float | None:
    text = raw.strip().replace(" ", "")
    if re.search(r",\d{2}$", text) and "." in text:
        text = text.replace(".", "").replace(",", ".")
    elif re.search(r",\d{2}$", text):
        text = text.replace(",", ".")
    else:
        text = text.replace(",", "")
    try:
        value = float(text)
    except ValueError:
        return None
    return value if value > 0 else None


@debug_trace
def parse_text_layer_hints(text: str) -> TextLayerHints:
    """Parse invoice_number, date, amount, issuer from extracted PDF text."""
    if not text.strip():
        return TextLayerHints(raw_text="")

    invoice_number: str | None = None
    for pattern in (_RE_INVOICE_TITLE, _RE_INVOICE_LABEL):
        match = pattern.search(text)
        if match:
            invoice_number = match.group(1).strip()
            break

    invoice_date: str | None = None
    date_match = _RE_DATE.search(text)
    if date_match:
        invoice_date = date_match.group(1).strip()

    amount: float | None = None
    amount_match = _RE_AMOUNT_WITH_VAT.search(text)
    if amount_match:
        amount = _parse_amount(amount_match.group(1))

    name_of_company: str | None = None
    issuer_match = _RE_ISSUER_SHPK.search(text)
    if issuer_match:
        name_of_company = issuer_match.group(1).strip()

    return TextLayerHints(
        raw_text=text,
        invoice_number=invoice_number,
        invoice_date=invoice_date,
        amount=amount,
        name_of_company=name_of_company,
    )
