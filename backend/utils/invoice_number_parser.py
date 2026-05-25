"""Extract invoice number candidates from bank comment text (doc 9)."""

import re

from utils.normalization import is_tax_or_client_id, normalize_invoice_number

PATTERNS = [
    r"(?:invoice|fatura|inv|ref|nr\.?|pagesa)\s*[:#]?\s*([A-Z0-9][\w./-]{2,})",
    r"\b(\d{1,4}/\d{4}/\d{2,6})\b",
    r"(?:invoices?|faturat?|fatures?)\s+([\d\s,.-/]+)",
    r"\b([A-Z0-9]{4,}[-/][A-Z0-9]{2,})\b",
    r"\b(\d{4,})\b",
]


def extract_invoice_numbers(comment: str | None) -> list[str]:
    if not comment or not str(comment).strip():
        return []

    text = str(comment).strip()
    candidates: list[str] = []

    for pattern in PATTERNS:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            chunk = match.group(1) if match.lastindex else match.group(0)
            for part in re.split(r"[,;]\s*", chunk):
                part = part.strip()
                if not part:
                    continue
                norm = normalize_invoice_number(part)
                if (
                    norm
                    and norm not in candidates
                    and not is_tax_or_client_id(norm)
                ):
                    candidates.append(norm)

    return candidates
