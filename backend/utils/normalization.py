"""Invoice number normalization for DB storage and matching (doc 9)."""

import os
import re


def is_tax_or_client_id(s: str) -> bool:
    if s.isdigit() and len(s) == 9 and s.startswith(("811", "330")):
        return True
    if s.isdigit() and len(s) >= 8 and s.startswith("330"):
        return True
    return False


def normalize_invoice_number(raw: str | None) -> str | None:
    if not raw or not str(raw).strip():
        return None

    raw_stripped = str(raw).strip()

    if "/" in raw_stripped:
        parts = [p.strip() for p in raw_stripped.split("/") if p.strip()]
        if parts and all(p.isdigit() for p in parts):
            s = "".join(parts)
        else:
            s = re.sub(r"[^A-Z0-9]", "", raw_stripped.upper())
    else:
        s = re.sub(r"\s+", "", raw_stripped.upper())

    prefixes = (
        r"^(FATURA|INVOICE|INV|REF|NR|NO|NUM|PAYMENTFORINVOICE(S)?|PAGESA|PAGESAPARFATURES)"
    )
    s = re.sub(prefixes, "", s, flags=re.IGNORECASE)

    if re.fullmatch(r"[\d.,]+", s.replace(",", ".")):
        s = s.replace(",", "").replace(".", "")
    else:
        s = re.sub(r"[^A-Z0-9]", "", s)

    if is_tax_or_client_id(s):
        return None

    min_len = int(os.getenv("MATCH_MIN_DIGIT_LENGTH", "4"))
    if len(s) < min_len and s.isdigit():
        return None

    return s if s else None
