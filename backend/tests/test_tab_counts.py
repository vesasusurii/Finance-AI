"""Tests for aggregated tab-count endpoints (Documents + Matching)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.controllers.invoice_controller import InvoiceController
from api.controllers.reconciliation_controller import ReconciliationController
from schemas.auth import UserContext
from schemas.invoice import InvoiceTabCountsResponse
from schemas.reconciliation import MatchingTabCountsResponse


def _user() -> UserContext:
    return UserContext(user_id=7, email="f@borek.com", role="finance")


@pytest.fixture
def invoice_controller() -> InvoiceController:
    return InvoiceController(
        extraction_service=AsyncMock(),
        invoice_repo=AsyncMock(),
        invoice_access_repo=AsyncMock(),
        audit_repo=AsyncMock(),
        upload_repo=AsyncMock(),
        match_repo=AsyncMock(),
    )


@pytest.fixture
def reconciliation_controller() -> ReconciliationController:
    return ReconciliationController(
        matching_service=AsyncMock(),
        match_repo=AsyncMock(),
        invoice_repo=AsyncMock(),
        statement_repo=AsyncMock(),
        bank_txn_repo=AsyncMock(),
        audit_repo=AsyncMock(),
    )


@pytest.mark.asyncio
async def test_invoice_tab_counts_returns_aggregated_counts(
    invoice_controller: InvoiceController,
):
    invoice_controller._invoice_repo.count_by_tabs.return_value = {
        "all": 42,
        "needs_review": 5,
        "unmatched": 12,
    }
    with patch("api.controllers.invoice_controller.cache") as cache_mock:
        cache_mock.get_model.return_value = None
        result = await invoice_controller.tab_counts(_user(), search="acme")

    assert result == InvoiceTabCountsResponse(
        all=42,
        needs_review=5,
        unmatched=12,
    )
    invoice_controller._invoice_repo.count_by_tabs.assert_awaited_once_with(
        {"search": "acme"},
        owner_user_id=None,
    )
    cache_mock.set_model.assert_called_once()


@pytest.mark.asyncio
async def test_invoice_tab_counts_uses_cache_when_present(
    invoice_controller: InvoiceController,
):
    cached = InvoiceTabCountsResponse(all=1, needs_review=0, unmatched=0)
    with patch("api.controllers.invoice_controller.cache") as cache_mock:
        cache_mock.get_model.return_value = cached
        result = await invoice_controller.tab_counts(_user(), search=None)

    assert result is cached
    invoice_controller._invoice_repo.count_by_tabs.assert_not_awaited()


@pytest.mark.asyncio
async def test_matching_tab_counts_returns_aggregated_counts(
    reconciliation_controller: ReconciliationController,
):
    reconciliation_controller._match_repo.count_matches.return_value = 3
    reconciliation_controller._invoice_repo.count_by_match_status.side_effect = [
        2,
        8,
    ]
    reconciliation_controller._bank_txn_repo.count_transactions.side_effect = [
        4,
        1,
    ]
    reconciliation_controller._invoice_repo.count_by_match_statuses.return_value = 9

    with patch("api.controllers.reconciliation_controller.cache") as cache_mock:
        cache_mock.get_model.return_value = None
        result = await reconciliation_controller.tab_counts(_user(), bank_statement_id=15)

    assert result == MatchingTabCountsResponse(
        matched=3,
        partially_matched=2,
        unmatched_invoices=8,
        unmatched_transactions=4,
        needs_review=9,
        multi_invoice=1,
    )
    reconciliation_controller._match_repo.count_matches.assert_awaited_once_with(
        None,
        15,
        owner_user_id=None,
        confirmed_only=True,
    )
    reconciliation_controller._invoice_repo.count_by_match_statuses.assert_awaited_once_with(
        ["unmatched", "needs_review"],
        owner_user_id=None,
    )
    cache_mock.set_model.assert_called_once()


@pytest.mark.asyncio
async def test_matching_tab_counts_uses_cache_when_present(
    reconciliation_controller: ReconciliationController,
):
    cached = MatchingTabCountsResponse(
        matched=0,
        partially_matched=0,
        unmatched_invoices=0,
        unmatched_transactions=0,
        needs_review=0,
        multi_invoice=0,
    )
    with patch("api.controllers.reconciliation_controller.cache") as cache_mock:
        cache_mock.get_model.return_value = cached
        result = await reconciliation_controller.tab_counts(_user(), bank_statement_id=None)

    assert result is cached
    reconciliation_controller._match_repo.count_matches.assert_not_awaited()


@pytest.mark.asyncio
async def test_matching_tab_counts_with_shared_db_session():
    """Regression: parallel gather on one AsyncSession raises ISCE (500 in prod)."""
    from db.pool import async_session
    from api.controllers.reconciliation_controller import ReconciliationController
    from repositories.audit_repository import AuditRepository
    from repositories.bank_statement_repository import BankStatementRepository
    from repositories.bank_transaction_repository import BankTransactionRepository
    from repositories.invoice_repository import InvoiceRepository
    from repositories.match_repository import MatchRepository
    from repositories.review_repository import ReviewRepository
    from services.matching_service import MatchingService

    async with async_session() as session:
        match_repo = MatchRepository(session)
        invoice_repo = InvoiceRepository(session)
        statement_repo = BankStatementRepository(session)
        bank_txn_repo = BankTransactionRepository(session)
        audit_repo = AuditRepository(session)
        review_repo = ReviewRepository(session)
        matching = MatchingService(
            invoice_repo,
            bank_txn_repo,
            match_repo,
            review_repo,
            audit_repo,
            comment_extractor=None,
        )
        ctrl = ReconciliationController(
            matching,
            match_repo,
            invoice_repo,
            statement_repo,
            bank_txn_repo,
            audit_repo,
        )
        with patch("api.controllers.reconciliation_controller.cache") as cache_mock:
            cache_mock.get_model.return_value = None
            result = await ctrl.tab_counts(_user(), bank_statement_id=None)

    assert isinstance(result, MatchingTabCountsResponse)
    assert result.matched >= 0
