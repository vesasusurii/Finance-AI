"""Batch payment matching — multi-invoice payments and amount-combination suggestions."""

from __future__ import annotations

from decimal import Decimal
from itertools import combinations

from utils.invoice_number_parser import comment_suggests_invoice_payment

REASON_NO_NUMBERS = "no_invoice_numbers_detected"
REASON_NOT_VISIBLE = "invoice_numbers_not_visible"
REASON_BATCH_INCOMPLETE = "batch_payment_incomplete"
REASON_BATCH_AMOUNT_SUGGESTED = "batch_amount_suggested"


def no_candidates_reason(comment: str | None) -> str:
    """
    When no invoice numbers were extracted: distinguish payment-like comments
    (manual review) from generic transfers.
    """
    if comment_suggests_invoice_payment(comment):
        return REASON_NOT_VISIBLE
    return REASON_NO_NUMBERS


def reconcile_batch_status(
    *,
    candidate_count: int,
    matched_invoice_count: int,
    not_in_db_count: int,
    ambiguous_count: int,
) -> tuple[str, str | None]:
    """
    Decide bank transaction reconciliation status after matching visible numbers.

    Returns (status, optional_review_reason).
    """
    if matched_invoice_count <= 0:
        return "needs_review", None

    unresolved = not_in_db_count + ambiguous_count
    if unresolved == 0:
        return "matched", None

    if candidate_count > 1:
        return "partial", REASON_BATCH_INCOMPLETE

    if not_in_db_count > 0:
        return "partial", "no_invoice_in_db"

    return "partial", "duplicate_invoice_in_db"


def amounts_close(a: Decimal, b: Decimal, tolerance: Decimal) -> bool:
    return abs(a - b) <= tolerance


def find_invoice_amount_combination(
    invoices: list[tuple[int, Decimal, str]],
    target: Decimal,
    tolerance: Decimal,
    *,
    max_combo_size: int = 6,
) -> list[int] | None:
    """
    Find a subset of unpaid invoices whose amounts sum to the bank debit (± tolerance).

    Prefers smaller combinations when multiple fit. Returns invoice ids or None.
    """
    if not invoices or target <= 0:
        return None

    capped = max(2, min(max_combo_size, len(invoices)))
    for size in range(2, capped + 1):
        for combo in combinations(invoices, size):
            total = sum(row[1] for row in combo)
            if amounts_close(total, target, tolerance):
                return [row[0] for row in combo]

    for row in invoices:
        if amounts_close(row[1], target, tolerance):
            return [row[0]]

    return None


def normalize_supplier_key(name: str | None) -> str:
    if not name:
        return ""
    return " ".join(name.lower().split())
