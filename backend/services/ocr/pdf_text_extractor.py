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
    """Structured hints parsed from a PDF text layer."""

    raw_text: str
    invoice_number: str | None = None
    invoice_date: str | None = None
    amount: float | None = None
    name_of_company: str | None = None
    account_details: str | None = None

    @property
    def has_usable_text(self) -> bool:
        return len(self.raw_text.strip()) >= MIN_PDF_TEXT_CHARS


_AMOUNT = r"(\d{1,3}(?:[.,]\d{3})*[.,]\d{2}|\d+[.,]\d{2})"
_RE_INVOICE_TITLE = re.compile(
    r"(?:FATURA\s*[-/]?\s*INVOICE|INVOICE|RECHNUNG)"
    r"\s*(?:(?:NO\.?|NR\.?|#)\s*[:#\-]?\s*)?([A-Z0-9][\w./-]{1,32})",
    re.IGNORECASE,
)
_RE_INVOICE_LABEL = re.compile(
    r"(?:Numri i fatur(?:e|es|s)|Nr\.?\s*(?:i\s*)?fatur(?:e|es|s)|Fatura Nr\.?|"
    r"Invoice\s*(?:number|no\.?|#)|Inv(?:oice)?\s*No\.?|Bill\s*(?:number|no\.?)|"
    r"Belegnummer|Rechnungs(?:nummer|nr\.?)|Rechnung\s*Nr\.?|Dokument\s*Nr\.?|"
    r"Nr\.?\s*Ref\.?|Reference|Referenca)\s*[:#\-]?\s*([A-Z0-9][\w./-]{1,40})",
    re.IGNORECASE,
)
_RE_DATE = re.compile(
    r"(?:Data\s*e\s*fatur(?:e|es|s)|Data|Invoice\s*date|Issue\s*date|Date|Datum|"
    r"Rechnungsdatum)\s*[:#\-]?\s*"
    r"(\d{1,2}[./-]\d{1,2}[./-]\d{2,4}|\d{4}-\d{1,2}-\d{1,2})",
    re.IGNORECASE,
)
_RE_AMOUNT_WITH_VAT = re.compile(
    rf"(?:Vlera\s*me\s*TVSH|Vlera\s*totale|Shuma\s*totale|Gjith(?:e|esejt)\s*vlerat|"
    rf"Gjithsej\s*(?:borxhi|per\s*pagese|p(?:e|er)\s*pages(?:e|en))|Totali|"
    rf"Total\s*(?:Amount\s*)?(?:Due|Payable)?|Grand\s*Total|Amount\s*with\s*VAT|"
    rf"Bruttobetrag|Zahlbetrag|Gesamt(?:betrag|summe)|Total\s+incl\.?\s+VAT)"
    rf"[^\d]{{0,80}}{_AMOUNT}",
    re.IGNORECASE,
)
_RE_IBAN = re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b", re.IGNORECASE)
_RE_ISSUER = re.compile(
    r"([A-Z][\w\s.&\"'-]{2,80}"
    r"(?:SH\.?P\.?K\.?|LLC|L\.?L\.?C\.?|GmbH|AG|S\.?A\.?|S\.?R\.?L\.?))",
    re.IGNORECASE,
)
_BLOCKED_ISSUER_LINE = re.compile(
    r"(invoice|fatura|date|datum|total|amount|client|customer|buyer|bill\s*to|iban|bank)",
    re.IGNORECASE,
)


@debug_trace
def extract_pdf_text(content: bytes) -> str:
    """Extract concatenated text from all PDF pages."""
    try:
        import pdfplumber
    except ImportError:
        logger.warning("pdfplumber not installed - text-layer extraction disabled")
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


def _clean_line(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip(" :-\t")


def _first_plausible_issuer(text: str) -> str | None:
    issuer_match = _RE_ISSUER.search(text)
    if issuer_match:
        return _clean_line(issuer_match.group(1))

    for line in (_clean_line(line) for line in text.splitlines()[:18]):
        if len(line) < 3 or len(line) > 90:
            continue
        if _BLOCKED_ISSUER_LINE.search(line):
            continue
        if sum(ch.isalpha() for ch in line) >= 3:
            return line
    return None


@debug_trace
def parse_text_layer_hints(text: str) -> TextLayerHints:
    """Parse invoice number, date, amount, issuer, and IBANs from PDF text."""
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

    ibans: list[str] = []
    for match in _RE_IBAN.finditer(text):
        value = match.group(0).upper()
        if value not in ibans:
            ibans.append(value)

    return TextLayerHints(
        raw_text=text,
        invoice_number=invoice_number,
        invoice_date=invoice_date,
        amount=amount,
        name_of_company=_first_plausible_issuer(text),
        account_details=", ".join(ibans) if ibans else None,
    )
