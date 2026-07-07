"""PDF text-layer extraction for hybrid invoice OCR (pdfplumber)."""

from __future__ import annotations

import io
import re
from dataclasses import dataclass

from core.debug_logger import debug_trace, get_logger

logger = get_logger(__name__)

MIN_PDF_TEXT_CHARS = 80

CRITICAL_HINT_FIELDS = (
    "invoice_number",
    "invoice_date",
    "amount",
    "name_of_company",
)

SUPPORTING_HINT_FIELDS = (
    "account_details",
    "due_date",
    "vat_amount",
    "payment_reference",
)


@dataclass(frozen=True)
class TextLayerHints:
    """Structured hints parsed from a PDF text layer."""

    raw_text: str
    invoice_number: str | None = None
    invoice_date: str | None = None
    amount: float | None = None
    name_of_company: str | None = None
    account_details: str | None = None
    due_date: str | None = None
    vat_amount: float | None = None
    payment_reference: str | None = None

    @property
    def has_usable_text(self) -> bool:
        return len(self.raw_text.strip()) >= MIN_PDF_TEXT_CHARS

    def critical_hint_count(self) -> int:
        count = 0
        for field in CRITICAL_HINT_FIELDS:
            value = getattr(self, field)
            if value is not None and value != "":
                count += 1
        return count

    def missing_critical_fields(self) -> list[str]:
        missing: list[str] = []
        for field in CRITICAL_HINT_FIELDS:
            value = getattr(self, field)
            if value is None or value == "":
                missing.append(field)
        return missing

    def total_hint_count(self) -> int:
        count = self.critical_hint_count()
        for field in SUPPORTING_HINT_FIELDS:
            value = getattr(self, field)
            if value is not None and value != "":
                count += 1
        return count


_AMOUNT = r"(\d{1,3}(?:[.,]\d{3})*[.,]\d{2}|\d+[.,]\d{2})"
_CURRENCY = r"(?:EUR|USD|GBP|CHF|€|\$|£)?"
_RE_INVOICE_TITLE = re.compile(
    r"(?:FATURA\s*[-/]?\s*INVOICE|RECHNUNG)"
    r"\s*(?:(?:NO\.?|NR\.?|#)\s*[:#\-]?\s*)?([A-Z0-9][\w./-]{1,40})",
    re.IGNORECASE,
)
_RE_INVOICE_INLINE = re.compile(
    r"(?:^|\n)\s*INVOICE\s+(?!(?:number|no\.?)\b)([A-Z0-9][\w./-]{1,40})",
    re.IGNORECASE | re.MULTILINE,
)
_RE_INVOICE_LABEL = re.compile(
    r"(?:Numri i fatur(?:e|ë|es|ës|s)|Nr\.?\s*(?:i\s*)?fatur(?:e|ë|es|ës|s)|Fatura Nr\.?|"
    r"Invoice\s*(?:number|no\.?|#)|Inv(?:oice)?\s*No\.?|Bill\s*(?:number|no\.?)|"
    r"Belegnummer|Rechnungs(?:nummer|nr\.?)|Rechnung\s*Nr\.?|Dokument\s*Nr\.?|"
    r"Nr\.?\s*Ref\.?|Reference|Referenca|Document\s*(?:no\.?|#))\s*[:#\-]?\s*"
    r"([A-Z0-9][\w./-]{1,40})",
    re.IGNORECASE,
)
_RE_INVOICE_LONG_NUMERIC = re.compile(
    r"(?:^|\n)\s*(?:Invoice|Fatura)\s*(?:#|Nr\.?)?\s*([0-9]{8,20})\s*(?:\n|$)",
    re.IGNORECASE | re.MULTILINE,
)
_RE_DATE = re.compile(
    r"(?:Data\s*e\s*fatur[eëë]s?|Data\s*e\s*faturës|Data|Invoice\s*date|Issue\s*date|"
    r"Date\s*of\s*issue|Billing\s*date|Date|Datum|Rechnungsdatum)\s*[:#\-]?\s*"
    r"(\d{1,2}[./-]\d{1,2}[./-]\d{2,4}|\d{4}-\d{1,2}-\d{1,2})",
    re.IGNORECASE,
)
_RE_DUE_DATE = re.compile(
    r"(?:Due\s*date|Payment\s*due|Pay\s*by|Zahlbar\s*bis|Afati i pageses|"
    r"Data e pageses|Afati|Due)\s*[:#\-]?\s*"
    r"(\d{1,2}[./-]\d{1,2}[./-]\d{2,4}|\d{4}-\d{1,2}-\d{1,2})",
    re.IGNORECASE,
)
_RE_AMOUNT_WITH_VAT = re.compile(
    rf"(?:Vlera\s*me\s*TVSH|Vlera\s*totale|Shuma\s*totale|Gjith(?:e|ë|esejt)\s*vlerat|"
    rf"Gjithsej\s*(?:borxhi|per\s*pagese|p(?:e|ë)r\s*pages(?:e|en))|Totali|"
    rf"Total\s*(?:Amount\s*)?(?:Due|Payable)?|Grand\s*Total|Amount\s*with\s*VAT|"
    rf"Bruttobetrag|Zahlbetrag|Gesamt(?:betrag|summe)|Total\s+incl\.?\s+VAT|"
    rf"Total\s+{_CURRENCY}\s*)"
    rf"[^\d]{{0,80}}{_AMOUNT}",
    re.IGNORECASE,
)
_RE_AMOUNT_DUE = re.compile(
    rf"(?:Amount\s*Due|Total\s*Due|Balance\s*due|Payable|Per\s*pagese|T[eë]\s*pagese|"
    rf"Subtotal|Net\s*amount)\s*(?:\([^)]+\))?\s*[:#\-]?\s*{_CURRENCY}\s*{_AMOUNT}",
    re.IGNORECASE,
)
_RE_VAT = re.compile(
    rf"(?:VAT|TVSH|MwSt\.?|Tax\s*amount|Sales\s*tax)\s*(?:amount)?\s*[:#\-]?\s*"
    rf"{_CURRENCY}\s*{_AMOUNT}",
    re.IGNORECASE,
)
_RE_IBAN = re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b", re.IGNORECASE)
_RE_PAYMENT_REF = re.compile(
    r"(?:Payment\s*reference|Referenca e pageses|Kodi i pageses|Payment\s*ref\.?|"
    r"Reference\s*(?:number|no\.?)?)\s*[:#\-]?\s*([A-Z0-9][\w./-]{3,40})",
    re.IGNORECASE,
)
_RE_ISSUER = re.compile(
    r"([A-Z][\w\s.&\"'-]{2,80}"
    r"(?:SH\.?P\.?K\.?|LLC|L\.?L\.?C\.?|GmbH|AG|S\.?A\.?|S\.?R\.?L\.?|OpCo|Inc\.?))",
    re.IGNORECASE,
)
_BLOCKED_ISSUER_LINE = re.compile(
    r"(invoice|fatura|date|datum|total|amount|client|customer|buyer|bill\s*to|iban|bank)",
    re.IGNORECASE,
)


@debug_trace
def extract_pdf_page_texts(content: bytes) -> list[str]:
    """Extract text per PDF page (one string per page, empty when unreadable)."""
    try:
        import pdfplumber
    except ImportError:
        logger.warning("pdfplumber not installed - text-layer extraction disabled")
        return []

    try:
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            return [page.extract_text() or "" for page in pdf.pages]
    except Exception as exc:
        logger.warning("PDF text extraction failed: %s", exc)
        return []


@debug_trace
def extract_pdf_text(content: bytes) -> str:
    """Extract concatenated text from all PDF pages."""
    chunks = [text for text in extract_pdf_page_texts(content) if text.strip()]
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


def _first_match(pattern: re.Pattern[str], text: str) -> str | None:
    match = pattern.search(text)
    return match.group(1).strip() if match else None


def _first_amount(*patterns: re.Pattern[str], text: str) -> float | None:
    for pattern in patterns:
        match = pattern.search(text)
        if match:
            parsed = _parse_amount(match.group(1))
            if parsed is not None:
                return parsed
    return None


@debug_trace
def parse_text_layer_hints(text: str) -> TextLayerHints:
    """Parse invoice number, date, amount, issuer, and IBANs from PDF text."""
    if not text.strip():
        return TextLayerHints(raw_text="")

    invoice_number: str | None = None
    for pattern in (
        _RE_INVOICE_LABEL,
        _RE_INVOICE_INLINE,
        _RE_INVOICE_TITLE,
        _RE_INVOICE_LONG_NUMERIC,
    ):
        match = pattern.search(text)
        if match:
            invoice_number = match.group(1).strip()
            break

    invoice_date = _first_match(_RE_DATE, text)
    due_date = _first_match(_RE_DUE_DATE, text)
    amount = _first_amount(_RE_AMOUNT_WITH_VAT, _RE_AMOUNT_DUE, text=text)

    vat_amount: float | None = None
    vat_match = _RE_VAT.search(text)
    if vat_match:
        vat_amount = _parse_amount(vat_match.group(1))

    payment_reference = _first_match(_RE_PAYMENT_REF, text)

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
        due_date=due_date,
        vat_amount=vat_amount,
        payment_reference=payment_reference,
    )


def text_quality_score(hints: TextLayerHints) -> float:
    """Heuristic 0–1 score for PDF text-layer usability."""
    text = hints.raw_text.strip()
    if len(text) < MIN_PDF_TEXT_CHARS:
        return 0.0

    length_score = min(1.0, len(text) / 500.0)
    critical = hints.critical_hint_count()
    hint_score = critical / len(CRITICAL_HINT_FIELDS)
    supporting = sum(
        1
        for field in SUPPORTING_HINT_FIELDS
        if getattr(hints, field) not in (None, "")
    )
    supporting_score = min(0.15, supporting * 0.03)
    garble_ratio = text.count("\ufffd") / max(len(text), 1)
    garble_penalty = max(0.0, 1.0 - garble_ratio * 25)

    raw = (length_score * 0.35 + hint_score * 0.5 + supporting_score) * garble_penalty
    return round(min(1.0, max(0.0, raw)), 3)
