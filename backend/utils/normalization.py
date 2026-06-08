"""Invoice number normalization for DB storage and matching (doc 9)."""

import os
import re

def is_tax_or_client_id(s: str) -> bool:
    # Kosovo / Albanian fiscal and business registration numbers (NUI, NRF, etc.)
    if s.isdigit() and len(s) == 9 and s.startswith(("810", "811", "330")):
        return True
    if s.isdigit() and len(s) >= 8 and s.startswith("330"):
        return True
    return False


def is_bank_account_number(s: str) -> bool:
    """Long pure-digit strings from bank-account lines are not invoice numbers."""
    return s.isdigit() and len(s) >= 13


_RE_IBAN_LIKE = re.compile(r"^[A-Z]{2}\d{2}[A-Z0-9]{11,30}$")
_RE_ISO_DATE_INVOICE = re.compile(r"^20\d{2}-\d{2}-\d{2}$")
_RE_COMPACT_DATE = re.compile(r"^20\d{6}$")


def is_date_like_invoice_number(s: str) -> bool:
    """Reject ISO dates and YYYYMMDD values misread as invoice numbers."""
    upper = s.upper()
    return bool(
        _RE_ISO_DATE_INVOICE.fullmatch(upper)
        or _RE_COMPACT_DATE.fullmatch(upper)
    )


def is_iban_like(s: str) -> bool:
    return bool(_RE_IBAN_LIKE.fullmatch(s.upper()))


def is_invalid_invoice_number_candidate(s: str) -> bool:
    """True when a normalised value must not be stored as invoice_number."""
    if not s:
        return True
    return (
        is_tax_or_client_id(s)
        or is_bank_account_number(s)
        or is_iban_like(s)
        or is_date_like_invoice_number(s)
        or bool(re.fullmatch(r"20\d{2}", s))
    )


def _compact_alphanumeric(raw_stripped: str) -> str:
    """
    Collapse invoice number to continuous A–Z / 0–9.

    Slash-separated all-digit serials (e.g. 1/2026/0048) are joined;
    all other separators (/, -, whitespace) are removed.
    """
    if "/" in raw_stripped:
        parts = [p.strip() for p in raw_stripped.split("/") if p.strip()]
        if parts and all(p.isdigit() for p in parts):
            return "".join(parts)
    return re.sub(r"[^A-Z0-9]", "", raw_stripped.upper())


def normalize_invoice_number(
    raw: str | None,
    *,
    min_digit_length: int | None = None,
) -> str | None:
    """
    Canonical invoice number: uppercase alphanumeric only.

    Removes slashes, hyphens, and whitespace (and other punctuation).
    Returns None for tax/client IDs, years-only values, or values too short.

    ``min_digit_length`` applies only to pure-digit values. Bank-comment parsing
    keeps the default (``MATCH_MIN_DIGIT_LENGTH``, usually 4). Invoice extraction
    passes ``min_digit_length=1`` so short refs like ``007`` are kept.
    """
    if not raw or not str(raw).strip():
        return None

    raw_stripped = str(raw).strip()
    s = _compact_alphanumeric(raw_stripped)

    prefixes = (
        r"^(FATURA|INVOICE|INV|REF|NR|NO|NUM|PAYMENTFORINVOICE(S)?|PAGESA|PAGESAPARFATURES)"
    )
    while True:
        stripped = re.sub(prefixes, "", s, flags=re.IGNORECASE)
        if stripped == s:
            break
        s = stripped

    if re.fullmatch(r"[\d.,]+", s.replace(",", ".")):
        s = s.replace(",", "").replace(".", "")
    elif not s:
        return None

    if is_invalid_invoice_number_candidate(s):
        return None

    if min_digit_length is None:
        min_digit_length = int(os.getenv("MATCH_MIN_DIGIT_LENGTH", "4"))
    if len(s) < min_digit_length and s.isdigit():
        return None

    return s if s else None


def split_invoice_number(
    raw: str | None,
    *,
    min_digit_length: int = 1,
) -> tuple[str | None, str | None]:
    """Return (display, normalized) for DB storage."""
    if not raw or not str(raw).strip():
        return None, None
    display = str(raw).strip()
    normalized = normalize_invoice_number(
        display,
        min_digit_length=min_digit_length,
    )
    return display, normalized
