from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from models.review_task import ReviewTask
from schemas.auth import UserContext
from schemas.invoice import InvoiceResponse
from schemas.review import ReviewTaskResponse
from services.review_service import ReviewService


def _user() -> UserContext:
    return UserContext(user_id=1, email="f@b.com", role="finance")


def _open_extraction_task() -> ReviewTask:
    return ReviewTask(
        id=10,
        task_type="extraction",
        invoice_id=5,
        bank_transaction_id=None,
        reason="low_confidence",
        status="open",
        payload={"missing_fields": ["invoice_number"]},
        created_at=datetime.now(timezone.utc),
        resolved_at=None,
    )


def _open_bank_task() -> ReviewTask:
    return ReviewTask(
        id=20,
        task_type="bank_match",
        invoice_id=None,
        bank_transaction_id=6,
        reason="no_invoice_in_db",
        status="open",
        payload={"invoice_number": "613260192"},
        created_at=datetime.now(timezone.utc),
        resolved_at=None,
    )


@pytest.fixture
def service() -> ReviewService:
    return ReviewService(
        review_repo=AsyncMock(),
        invoice_repo=AsyncMock(),
        bank_txn_repo=AsyncMock(),
        audit_repo=AsyncMock(),
    )


@pytest.mark.asyncio
async def test_list_open_enriches_invoice_and_bank(service: ReviewService):
    base = ReviewTaskResponse(
        id=1,
        task_type="bank_match",
        invoice_id=5,
        bank_transaction_id=6,
        reason="no_invoice_in_db",
        status="open",
        payload=None,
        created_at=datetime.now(timezone.utc),
        resolved_at=None,
    )
    service._review_repo.list_open.return_value = ([base], 1)
    service._invoice_repo.get.return_value = MagicMock(spec=InvoiceResponse)
    service._bank_txn_repo.get.return_value = MagicMock()

    result = await service.list_open(None, 1, 50)

    assert result.total == 1
    assert len(result.items) == 1
    service._invoice_repo.get.assert_awaited_once_with(5, owner_user_id=None)
    service._bank_txn_repo.get.assert_awaited_once_with(6)


@pytest.mark.asyncio
async def test_list_open_skips_enrich_when_disabled(service: ReviewService):
    base = ReviewTaskResponse(
        id=1,
        task_type="bank_match",
        invoice_id=5,
        bank_transaction_id=6,
        reason="no_invoice_in_db",
        status="open",
        payload=None,
        created_at=datetime.now(timezone.utc),
        resolved_at=None,
    )
    service._review_repo.list_open.return_value = ([base], 1)

    result = await service.list_open(None, 1, 50, enrich=False)

    assert result.total == 1
    assert result.items[0].invoice is None
    service._invoice_repo.get.assert_not_called()
    service._bank_txn_repo.get.assert_not_called()


@pytest.mark.asyncio
async def test_approve_extraction_sets_invoice_approved(service: ReviewService):
    task = _open_extraction_task()
    service._review_repo.get.return_value = task
    service._review_repo.is_visible_to_user.return_value = True
    service._invoice_repo.approve.return_value = MagicMock(spec=InvoiceResponse)
    service._review_repo.resolve.return_value = task

    result = await service.approve(10, _user())

    assert result.status == "approved"
    service._invoice_repo.approve.assert_awaited_once_with(
        5, owner_user_id=1, paid_by="f@b.com"
    )
    service._review_repo.resolve.assert_awaited_once()
    assert service._audit_repo.log.await_count == 2


@pytest.mark.asyncio
async def test_reject_bank_match_resolves_and_audits(service: ReviewService):
    task = _open_bank_task()
    service._review_repo.get.return_value = task
    service._review_repo.is_visible_to_user.return_value = True
    service._review_repo.resolve.return_value = task

    result = await service.reject(20, "Not our invoice", _user())

    assert result.status == "rejected"
    service._invoice_repo.approve.assert_not_called()
    service._review_repo.resolve.assert_awaited_once()
    resolve_args = service._review_repo.resolve.await_args.args
    assert resolve_args[0] == 20
    assert resolve_args[1] == "rejected"
    service._audit_repo.log.assert_awaited_once()
    log_args = service._audit_repo.log.await_args.args
    assert log_args[1] == "review_rejected"
    assert log_args[5]["reason"] == "Not our invoice"


@pytest.mark.asyncio
async def test_approve_already_resolved_raises_409(service: ReviewService):
    task = _open_extraction_task()
    task.status = "approved"
    service._review_repo.get.return_value = task
    service._review_repo.is_visible_to_user.return_value = True

    with pytest.raises(HTTPException) as exc:
        await service.approve(10, _user())
    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_approve_invisible_task_raises_404(service: ReviewService):
    task = _open_extraction_task()
    service._review_repo.get.return_value = task
    service._review_repo.is_visible_to_user.return_value = False

    with pytest.raises(HTTPException) as exc:
        await service.approve(10, _user())
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_reject_invisible_task_raises_404(service: ReviewService):
    task = _open_bank_task()
    service._review_repo.get.return_value = task
    service._review_repo.is_visible_to_user.return_value = False

    with pytest.raises(HTTPException) as exc:
        await service.reject(20, "reason", _user())
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_admin_skips_visibility_check(service: ReviewService):
    task = _open_extraction_task()
    admin = UserContext(user_id=99, email="a@b.com", role="admin")
    service._review_repo.get.return_value = task
    service._invoice_repo.approve.return_value = MagicMock(spec=InvoiceResponse)
    service._review_repo.resolve.return_value = task

    await service.approve(10, admin)

    service._review_repo.is_visible_to_user.assert_not_called()
    service._invoice_repo.approve.assert_awaited_once_with(
        5, owner_user_id=None, paid_by="a@b.com"
    )
