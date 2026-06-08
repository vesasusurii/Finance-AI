"""Invoice number normalization for DB storage and matching (doc 9)."""

import os
import re

def is_tax_or_client_id(s: str) -> bool:
    if s.isdigit() and len(s) == 9 and s.startswith(("811", "330")):
        return True
    if s.isdigit() and len(s) >= 8 and s.startswith("330"):
        return True
    return False


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


def normalize_invoice_number(raw: str | None) -> str | None:
    """
    Canonical invoice number: uppercase alphanumeric only.

    Removes slashes, hyphens, and whitespace (and other punctuation).
    Returns None for tax/client IDs, years-only values, or values too short.
    """
    if not raw or not str(raw).strip():
        return None

    raw_stripped = str(raw).strip()
    s = _compact_alphanumeric(raw_stripped)

    prefixes = (
        r"^(FATURA|INVOICE|INV|REF|NR|NO|NUM|PAYMENTFORINVOICE(S)?|PAGESA|PAGESAPARFATURES)"
    )
    s = re.sub(prefixes, "", s, flags=re.IGNORECASE)

    if re.fullmatch(r"[\d.,]+", s.replace(",", ".")):
        s = s.replace(",", "").replace(".", "")
    elif not s:
        return None

    if is_tax_or_client_id(s):
        return None

    if re.fullmatch(r"20\d{2}", s):
        return None

    min_len = int(os.getenv("MATCH_MIN_DIGIT_LENGTH", "4"))
    if len(s) < min_len and s.isdigit():
        return None

    return s if s else None


def split_invoice_number(raw: str | None) -> tuple[str | None, str | None]:
    """Return (display, normalized) for DB storage."""
    if not raw or not str(raw).strip():
        return None, None
    display = str(raw).strip()
    return display, normalize_invoice_number(display)
