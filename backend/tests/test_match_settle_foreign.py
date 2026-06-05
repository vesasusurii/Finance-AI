"""Match confirmation settles invoice amount from bank transaction."""

from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from schemas.auth import UserContext
from schemas.invoice import InvoiceResponse
from services.matching_service import MatchingService


def _user() -> UserContext:
    return UserContext(user_id=1, email="f@b.com", role="finance")


def _usd_invoice_normalized() -> InvoiceResponse:
    now = datetime.now(timezone.utc)
    return InvoiceResponse(
        id=1,
        invoice_number="INV-USD",
        name_of_company="Vendor",
        address_of_company=None,
        amount=Decimal("26.19"),
        currency="EUR",
        original_amount=Decimal("30.11"),
        original_currency="USD",
        exchange_rate=Decimal("0.869809"),
        exchange_rate_date=date(2026, 1, 15),
        invoice_date=date(2026, 1, 15),
        paid_at_date=None,
        debt=Decimal("26.19"),
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
async def test_manual_match_full_settlement_uses_transaction_amount(
    matching_service: MatchingService,
):
    from models.bank_transaction import BankTransaction

    invoice = _usd_invoice_normalized()
    txn = BankTransaction(
        id=10,
        bank_statement_id=1,
        transaction_date=date(2026, 2, 1),
        comment="Payment",
        debited_amount=None,
        credited_amount=Decimal("26.19"),
        detected_invoice_numbers=[],
        reconciliation_status="needs_review",
        created_at=datetime.now(timezone.utc),
    )
    match_row = MagicMock()
    match_row.id = 50
    match_row.status = "approved"

    matching_service._invoice_repo.get.return_value = invoice
    matching_service._bank_txn_repo.get.return_value = txn
    matching_service._match_repo.active_for_transaction.return_value = None
    matching_service._match_repo.get_pair.return_value = None
    matching_service._match_repo.create.return_value = match_row
    matching_service._match_repo.sum_paid_for_invoice.return_value = Decimal("26.19")

    await matching_service.manual_match(1, 10, _user())

    matching_service._invoice_repo.settle_invoice_from_transaction.assert_awaited_once_with(
        1, Decimal("26.19")
    )
