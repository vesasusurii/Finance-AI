from decimal import Decimal

from utils.batch_payment_matching import (
    REASON_NOT_VISIBLE,
    find_invoice_amount_combination,
    no_candidates_reason,
    reconcile_batch_status,
)
from utils.invoice_number_parser import comment_suggests_invoice_payment


def test_comment_suggests_invoice_payment():
    assert comment_suggests_invoice_payment("Pagesa fature 26063")
    assert comment_suggests_invoice_payment("Payment for invoice ABC123")
    assert not comment_suggests_invoice_payment("Card purchase APROVAL:12345")
    assert not comment_suggests_invoice_payment("")


def test_no_candidates_reason_with_keywords():
    assert (
        no_candidates_reason("Pagesa fature per furnitor")
        == REASON_NOT_VISIBLE
    )
    assert no_candidates_reason("Card payment") == "no_invoice_numbers_detected"


def test_reconcile_batch_all_matched():
    status, reason = reconcile_batch_status(
        candidate_count=3,
        matched_invoice_count=3,
        not_in_db_count=0,
        ambiguous_count=0,
    )
    assert status == "matched"
    assert reason is None


def test_reconcile_batch_partial():
    status, reason = reconcile_batch_status(
        candidate_count=3,
        matched_invoice_count=2,
        not_in_db_count=1,
        ambiguous_count=0,
    )
    assert status == "partial"
    assert reason == "batch_payment_incomplete"


def test_reconcile_single_not_in_db():
    status, reason = reconcile_batch_status(
        candidate_count=1,
        matched_invoice_count=0,
        not_in_db_count=1,
        ambiguous_count=0,
    )
    assert status == "needs_review"
    assert reason is None


def test_find_invoice_amount_combination():
    invoices = [
        (1, Decimal("100.00"), "A"),
        (2, Decimal("200.00"), "B"),
        (3, Decimal("150.00"), "C"),
    ]
    assert find_invoice_amount_combination(
        invoices, Decimal("300.00"), Decimal("0.02")
    ) == [1, 2]
    assert find_invoice_amount_combination(
        invoices, Decimal("150.00"), Decimal("0.02")
    ) == [3]
    assert find_invoice_amount_combination(
        invoices, Decimal("999.00"), Decimal("0.02")
    ) is None
