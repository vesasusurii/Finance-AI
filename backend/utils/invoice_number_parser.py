"""
Extract invoice number candidates from bank comment text (doc 9).

Two-tier strategy:
  1. Hardened regex (this file)            - cheap, deterministic, deployed today
  2. LLM fallback                          - see services.bank_comment_extraction_service
     gated by `needs_llm_fallback(comment, regex_candidates)`

Real-world false positives this module deliberately rejects:
  - IBANs           e.g. MK07210701001870650, DE86270325000000013671, XK051234567890123456
  - Bank accounts   long pure-digit strings (>= 13 digits, e.g. 118900228600017)
  - Approval codes  tokens right after APROVAL:/AUTH:/TERM:/RRN:/REF:
  - Date fragments  DD/YYYY pairs inside timestamps like "11/02/2026"
  - 4-digit years   bare "2026" / "1999" with no other context
  - Tax IDs         Albanian fiscal IDs starting with 811 or 330 (utils.normalization)
  - Sub-tokens      digit runs that sit inside a larger token already captured
                    (e.g. "00114712" inside "FDP25-00114712")
"""

from __future__ import annotations

import re

from core.debug_logger import debug_trace, get_logger
from utils.normalization import is_tax_or_client_id, normalize_invoice_number

logger = get_logger(__name__)

PATTERNS = [
    r"\b(?:invoices?|fatur[aëe]?|fatures?|faturat?)\s+([\d\s,./-]+)",
    r"\b(\d{1,4}/\d{4}/\d{2,6})\b",
    r"\bpagesa\b(?:\s+(?:per|për|par))?(?:\s+(?:invoice|fatur[aëe]?))?\s*[:#]?\s*([A-Z0-9][\w./-]{2,})",
    r"\b(?:invoice|fatur[aëe]?|inv|ref|nr\.?)\b\s*[:#]?\s*([A-Z0-9][\w./-]{2,})",
    r"\b([A-Z0-9]{4,}[-/][A-Z0-9]{2,})\b",
    r"\b(\d{4,})\b",
]


# ─────────────────────────────────────────────────────────────────────────────
# Patterns — ordered by confidence (highest first). Each captures group(1).
# Lower-tier matches that overlap an already-captured range are suppressed.
# ─────────────────────────────────────────────────────────────────────────────

# Tier 1 — anchored by an invoice keyword (English / Albanian / abbreviations).
# Handles chained keywords like "Pagesa fature ...", "Pagese per fat. ...".
# Examples captured:
#   "Pagese per fat. FDP25-00114712"  ->  FDP25-00114712
#   "Inv 26-0103"                     ->  26-0103
#   "Pagesa fature 1/2026/0048"       ->  1/2026/0048
#   "Payment for invoice 26063"       ->  26063
KEYWORD_ANCHORED = re.compile(
    r"""(?ix)
    (?:                                   # primary keyword
        invoices? |
        fatur (?: at | es | a | e )? |
        fat \.? |
        inv \.? |
        pagesa | pagese |
        payment \s+ for (?: \s+ invoices? )?
    )
    (?:                                   # optional chained keywords
        \s+
        (?:
            per \s+ fat \.? |
            fatur (?: at | es | a | e )? |
            fat \.? |
            inv \.? |
            nr \.? |
            no \.?
        )
    )*
    \s* [:#]? \s*
    ( [A-Z0-9][\w./-]{2,} )               # the candidate
    """
)

# Tier 2 — slash-serials anywhere (e.g. 1/2026/0048).
SLASH_SERIAL = re.compile(r"\b(\d{1,4}/\d{4}/\d{2,6})\b")

# Tier 3 — alphanumeric serial with dash/slash separator.
# Either letters+digits then -dddd  (FDP25-00114712, ABC-2024-1),
# OR digits-dddd where the right side is NOT a 4-digit year (26-0103, not 02/2026).
DASHED_SERIAL = re.compile(
    r"""(?ix)
    \b (
        [A-Z]{2,}\d{1,6} [-/] \d{3,} |
        \d{1,4} [-/] (?! 19\d{2}\b | 20\d{2}\b ) \d{3,}
    ) \b
    """
)

# Tier 4 — bare numeric fallback (4-12 digits, bounded to skip IBANs/accounts).
BARE_NUMERIC = re.compile(r"\b(\d{4,12})\b")


# ─────────────────────────────────────────────────────────────────────────────
# Rejection filters
# ─────────────────────────────────────────────────────────────────────────────

# IBAN: 2 country letters + 2 check digits + 11-30 alphanumerics (BBAN).
IBAN_RE = re.compile(r"^[A-Z]{2}\d{2}[A-Z0-9]{11,30}$", re.IGNORECASE)

# Pure-digit string of 13+ chars => bank account or unanchored IBAN body.
LONG_ACCOUNT_RE = re.compile(r"^\d{13,}$")

# Standalone 4-digit year — never an invoice number on its own.
YEAR_ONLY_RE = re.compile(r"^(19|20)\d{2}$")

# A token sitting right after a card/auth keyword should never be an invoice number.
APPROVAL_CONTEXT_RE = re.compile(
    r"(?i)\b(?:APROVAL|APPROVAL|AUTH|AUTHCODE|TERM|TERMINAL|RRN|ARN|REF\.?|REFERENCE)"
    r"\s*[:#=]\s*([A-Z0-9\-]+)"
)

INVOICE_KEYWORDS_RE = re.compile(
    r"(?i)\b(?:invoice|fatur|fat\.|inv\.|inv\b|pagesa|pagese\s+per\s+fat|payment\s+for\s+invoice)"
)


def comment_suggests_invoice_payment(comment: str | None) -> bool:
    """True when the bank comment explicitly references invoice payment."""
    if not comment or not str(comment).strip():
        return False
    return bool(INVOICE_KEYWORDS_RE.search(str(comment)))


@debug_trace
def extract_invoice_numbers(comment: str | None) -> list[str]:
    """
    Regex-only extraction (sync, no I/O). Used at upload time for the preview
    and as the first tier of the matching pipeline.

    For LLM-assisted extraction see
    `services.bank_comment_extraction_service.BankCommentExtractionService`
    and `matching_service.MatchingService.run`.
    """
    if not comment or not str(comment).strip():
        return []

    text = str(comment).strip()
    blocked = _collect_blocked_tokens(text)

    candidates: list[str] = []
    covered: list[tuple[int, int]] = []

    for pattern in (KEYWORD_ANCHORED, SLASH_SERIAL, DASHED_SERIAL, BARE_NUMERIC):
        for match in pattern.finditer(text):
            span = match.span(1) if match.lastindex else match.span(0)
            if _overlaps(span, covered):
                continue
            chunk = match.group(1) if match.lastindex else match.group(0)
            chunk_yielded_valid_token = False
            for raw_part in _split_multi(chunk):
                part = raw_part.strip()
                if not part:
                    continue
                if part.upper() in blocked:
                    continue
                if _is_rejected_format(part):
                    continue
                norm = normalize_invoice_number(part)
                if not norm:
                    continue
                if norm.upper() in blocked:
                    continue
                if is_tax_or_client_id(norm):
                    continue
                if _is_rejected_format(norm) or YEAR_ONLY_RE.match(norm):
                    continue
                chunk_yielded_valid_token = True
                if norm not in candidates:
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
            if chunk_yielded_valid_token:
                covered.append(span)

    logger.debug(
        "extract_invoice_numbers: comment_len=%d candidates=%r blocked=%r",
        len(text),
        candidates,
        sorted(blocked),
    )
    return candidates


@debug_trace
def needs_llm_fallback(comment: str | None, regex_candidates: list[str]) -> bool:
    """
    Decide whether to call the LLM on this comment.

    True when:
      - Comment mentions invoice keywords but regex found nothing (unusual
        format we have no pattern for).
      - Regex returned >3 candidates (noisy comment, likely needs disambiguation).
      - Regex returned only short bare numerics AND the comment has no
        invoice keyword (the candidate is probably noise like an approval
        code or partial amount).
    """
    if comment is None:
        return False
    text = str(comment).strip()
    if not text:
        return False

    has_keywords = comment_suggests_invoice_payment(text)

    if has_keywords and not regex_candidates:
        return True
    if len(regex_candidates) > 3:
        return True
    if regex_candidates and not has_keywords:
        if all(c.isdigit() and len(c) <= 5 for c in regex_candidates):
            return True

    return False


# ─────────────────────────────────────────────────────────────────────────────
# Internals
# ─────────────────────────────────────────────────────────────────────────────


def _collect_blocked_tokens(text: str) -> set[str]:
    """
    Build a set of UPPER-cased tokens that MUST NOT be returned as invoice
    numbers. Covers IBANs, long account numbers, and tokens that sit right
    after card/auth keywords.
    """
    blocked: set[str] = set()

    for token in re.findall(r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b", text, re.IGNORECASE):
        upper = token.upper()
        blocked.add(upper)
        blocked.add(re.sub(r"[^0-9]", "", upper))

    for token in re.findall(r"\b\d{13,}\b", text):
        blocked.add(token)

    for match in APPROVAL_CONTEXT_RE.finditer(text):
        blocked.add(match.group(1).upper())

    return blocked


def _overlaps(span: tuple[int, int], covered: list[tuple[int, int]]) -> bool:
    """True if `span` lies entirely inside any already-covered range."""
    s, e = span
    for cs, ce in covered:
        if cs <= s and e <= ce:
            return True
    return False


def _split_multi(chunk: str) -> list[str]:
    """
    Split a captured chunk on common multi-invoice separators:
      ',' ';' ' dhe ' (Albanian and) ' and ' ' & ' ' + '
    """
    return re.split(r"[,;]\s*|\s+(?:dhe|and|&|\+)\s+", chunk, flags=re.IGNORECASE)


def _is_rejected_format(token: str) -> bool:
    """Token-level rejection rules (independent of context)."""
    compact = re.sub(r"[^A-Z0-9]", "", token.upper())
    if not compact:
        return True
    if IBAN_RE.match(compact):
        return True
    if LONG_ACCOUNT_RE.match(compact):
        return True
    return False
