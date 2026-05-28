"""Extract invoice number candidates from bank comment text (doc 9)."""

import re

from utils.normalization import is_tax_or_client_id, normalize_invoice_number

PATTERNS = [
    r"\b(?:invoices?|fatur[aëe]?|fatures?|faturat?)\s+([\d\s,./-]+)",
    r"\b(\d{1,4}/\d{4}/\d{2,6})\b",
    r"\bpagesa\b(?:\s+(?:per|për|par))?(?:\s+(?:invoice|fatur[aëe]?))?\s*[:#]?\s*([A-Z0-9][\w./-]{2,})",
    r"\b(?:invoice|fatur[aëe]?|inv|ref|nr\.?)\b\s*[:#]?\s*([A-Z0-9][\w./-]{2,})",
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
                    if any(
                        existing.isdigit() and norm.isdigit() and norm in existing
                        for existing in candidates
                    ):
                        continue
                    candidates = [
                        existing
                        for existing in candidates
                        if not (
                            existing.isdigit()
                            and norm.isdigit()
                            and existing in norm
                        )
                    ]
                    candidates.append(norm)

    return candidates
