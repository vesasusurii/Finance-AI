"""Partial payment and debt recalculation behaviour."""

from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from models.bank_transaction import BankTransaction
from models.invoice import Invoice
from schemas.auth import UserContext
from schemas.invoice import InvoiceResponse
from services.matching_service import MatchingService


def _user() -> UserContext:
    return UserContext(user_id=1, email="f@b.com", role="finance")


def _invoice(amount: str = "1000.00", debt: str | None = "1000.00") -> InvoiceResponse:
    now = datetime.now(timezone.utc)
    return InvoiceResponse(
        id=1,
        invoice_number="INV-001",
        name_of_company="Acme",
        address_of_company=None,
        amount=Decimal(amount),
        currency="EUR",
        original_amount=Decimal(amount),
        original_currency="EUR",
        exchange_rate=Decimal("1"),
        exchange_rate_date=date(2026, 1, 15),
        invoice_date=date(2026, 1, 15),
        paid_at_date=None,
        debt=Decimal(debt) if debt is not None else None,
        account_details=None,
        internal_note_description=None,
        client_employee_related=None,
        paid_by=None,
        fixed_status=None,
        category=None,
        extraction_confidence=None,
        field_confidences=None,
        review_reasons=None,
        match_status="unmatched",
        review_status="approved",
        uploaded_by=1,
        source_file_id=1,
        created_at=now,
        updated_at=now,
    )


def _txn(amount: str = "400.00") -> BankTransaction:
    return BankTransaction(
        id=10,
        bank_statement_id=1,
        transaction_date=date(2026, 2, 1),
        comment="Payment INV-001",
        debited_amount=None,
        credited_amount=Decimal(amount),
        detected_invoice_numbers=[],
        reconciliation_status="needs_review",
        created_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def matching_service() -> MatchingService:
    return MatchingService(
        invoice_repo=AsyncMock(),
        bank_txn_repo=AsyncMock(),
        match_repo=AsyncMock(),
        review_repo=AsyncMock(),
        audit_repo=AsyncMock(),
        comment_extractor=None,
    )


@pytest.mark.asyncio
async def test_manual_match_partial_payment_sets_debt_and_status(
    matching_service: MatchingService,
):
    invoice = _invoice()
    txn = _txn("400.00")
    match_row = MagicMock()
    match_row.id = 99
    match_row.status = "approved"

    matching_service._invoice_repo.get.return_value = invoice
    matching_service._bank_txn_repo.get.return_value = txn
    matching_service._match_repo.active_for_transaction.return_value = None
    matching_service._match_repo.get_pair.return_value = None
    matching_service._match_repo.create.return_value = match_row
    matching_service._match_repo.sum_paid_for_invoice.return_value = Decimal("400.00")

    result = await matching_service.manual_match(1, 10, _user(), paid_amount=Decimal("400"))

    assert result.status == "approved"
    matching_service._invoice_repo.update_debt.assert_awaited_once_with(
        1, Decimal("600.00")
    )
    matching_service._invoice_repo.update_match_status.assert_awaited_once_with(
        1, "partially_matched"
    )
    matching_service._match_repo.create.assert_awaited_once()
    create_kwargs = matching_service._match_repo.create.await_args.kwargs
    assert create_kwargs["paid_amount"] == Decimal("400")


@pytest.mark.asyncio
async def test_manual_match_full_payment_sets_matched_status(
    matching_service: MatchingService,
):
    invoice = _invoice()
    txn = _txn("1000.00")
    match_row = MagicMock()
    match_row.id = 100
    match_row.status = "approved"

    matching_service._invoice_repo.get.return_value = invoice
    matching_service._bank_txn_repo.get.return_value = txn
    matching_service._match_repo.active_for_transaction.return_value = None
    matching_service._match_repo.get_pair.return_value = None
    matching_service._match_repo.create.return_value = match_row
    matching_service._match_repo.sum_paid_for_invoice.return_value = Decimal("1000.00")

    result = await matching_service.manual_match(1, 10, _user())

    assert result.status == "approved"
    matching_service._invoice_repo.settle_invoice_from_transaction.assert_awaited_once_with(
        1, Decimal("1000.00")
    )


@pytest.mark.asyncio
async def test_manual_match_rejects_fully_paid_invoice(
    matching_service: MatchingService,
):
    invoice = _invoice(debt="0")
    txn = _txn()

    matching_service._invoice_repo.get.return_value = invoice
    matching_service._bank_txn_repo.get.return_value = txn
    matching_service._match_repo.active_for_transaction.return_value = None

    with pytest.raises(HTTPException) as exc:
        await matching_service.manual_match(1, 10, _user())
    assert exc.value.status_code == 409
    assert exc.value.detail["error"] == "invoice_fully_paid"
