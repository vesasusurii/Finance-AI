"""Tests for bank statement upload merge behavior."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from io import BytesIO
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.datastructures import UploadFile

from models.bank_statement import BankStatement
from models.bank_transaction import BankTransaction
from schemas.auth import UserContext
from services.bank_statement_service import BankStatementService
from utils.bank_excel_parser import (
    ParsedBankRow,
    statement_month_from_date,
    transaction_dedupe_key,
)


def _parsed_row(**kwargs) -> ParsedBankRow:
    defaults = {
        "transaction_date": date(2026, 7, 1),
        "debited_amount": Decimal("100.00"),
        "credited_amount": None,
        "transaction_type": "Transfer",
        "comment": "Invoice 123",
        "detected_invoice_numbers": ["123"],
    }
    defaults.update(kwargs)
    return ParsedBankRow(**defaults)


def _stored_txn(**kwargs) -> BankTransaction:
    defaults = {
        "id": 42,
        "bank_statement_id": 1,
        "transaction_date": date(2026, 7, 1),
        "debited_amount": Decimal("100.00"),
        "credited_amount": None,
        "transaction_type": "Transfer",
        "comment": "Invoice 123",
        "detected_invoice_numbers": ["123"],
        "reconciliation_status": "matched",
        "created_at": datetime.now(timezone.utc),
    }
    defaults.update(kwargs)
    return BankTransaction(**defaults)


def _existing_statement(*, uploaded_by: int = 1) -> BankStatement:
    stmt_date = date(2026, 7, 7)
    stmt_month = statement_month_from_date(stmt_date)
    return BankStatement(
        id=1,
        statement_date=stmt_date,
        statement_month=stmt_month,
        source_file_id=10,
        uploaded_by=uploaded_by,
        row_count=1,
        processing_status="processed",
    )


@pytest.fixture
def service() -> BankStatementService:
    return BankStatementService(
        upload_repo=AsyncMock(),
        statement_repo=AsyncMock(),
        transaction_repo=AsyncMock(),
        review_repo=AsyncMock(),
    )


@pytest.fixture
def user_b() -> UserContext:
    return UserContext(user_id=2, email="b@b.com", role="finance")


async def _upload_with_rows(
    service: BankStatementService,
    user: UserContext,
    parsed_rows: list[ParsedBankRow],
    *,
    statement_date: date = date(2026, 7, 7),
    existing_statement: BankStatement | None = None,
    existing_txns: list[BankTransaction] | None = None,
    filename: str = "statement_20260707.xlsx",
):
    upload_row = MagicMock(id=99)
    service._upload_repo.create.return_value = upload_row
    service._statement_repo.get_by_month.return_value = existing_statement
    service._transaction_repo.list_for_statement.return_value = existing_txns or []

    statement_month = statement_month_from_date(statement_date)
    created_statement = BankStatement(
        id=2,
        statement_date=statement_date,
        statement_month=statement_month,
        source_file_id=99,
        uploaded_by=user.user_id,
        row_count=len(parsed_rows),
        processing_status="processed",
    )
    service._statement_repo.create.return_value = created_statement

    file = UploadFile(
        filename=filename,
        file=BytesIO(b"fake-xlsx"),
    )

    with (
        patch(
            "services.bank_statement_service.save_bytes",
            new_callable=AsyncMock,
            return_value=("/tmp/fake.xlsx", 12),
        ),
        patch(
            "services.bank_statement_service.read_bytes",
            new_callable=AsyncMock,
            return_value=b"fake-xlsx",
        ),
        patch(
            "services.bank_statement_service.parse_bank_statement_excel",
            return_value=parsed_rows,
        ),
        patch(
            "services.bank_statement_service.dedupe_parsed_rows",
            return_value=(parsed_rows, 0),
        ),
        patch(
            "services.bank_statement_service.extract_statement_date",
            return_value=statement_date,
        ),
    ):
        return await service.upload(file, user)


@pytest.mark.asyncio
async def test_first_upload_creates_statement(service: BankStatementService, user_b):
    rows = [_parsed_row(), _parsed_row(comment="Invoice 456")]

    result = await _upload_with_rows(service, user_b, rows)

    service._statement_repo.create.assert_awaited_once()
    service._transaction_repo.create_bulk.assert_awaited_once()
    service._statement_repo.update_after_merge.assert_not_awaited()
    assert result.merged_into_existing is False
    assert result.new_rows_added == 2
    assert result.existing_rows_kept == 0
    assert result.row_count == 2
    assert result.statement_month == date(2026, 7, 1)


@pytest.mark.asyncio
async def test_merge_adds_only_new_rows(service: BankStatementService, user_b):
    existing = _existing_statement(uploaded_by=1)
    existing_txn = _stored_txn()
    new_row = _parsed_row(comment="Invoice 999", debited_amount=Decimal("50.00"))
    parsed = [_parsed_row(), new_row]

    result = await _upload_with_rows(
        service,
        user_b,
        parsed,
        existing_statement=existing,
        existing_txns=[existing_txn],
    )

    service._statement_repo.create.assert_not_awaited()
    service._transaction_repo.create_bulk.assert_awaited_once()
    add_args = service._transaction_repo.create_bulk.await_args
    assert add_args.args[0] == existing.id
    assert len(add_args.args[1]) == 1
    assert add_args.args[1][0]["comment"] == "Invoice 999"

    service._statement_repo.update_after_merge.assert_awaited_once_with(
        existing.id,
        row_count=2,
        source_file_id=99,
        statement_date=date(2026, 7, 7),
    )

    assert result.merged_into_existing is True
    assert result.new_rows_added == 1
    assert result.existing_rows_kept == 1
    assert result.row_count == 2
    assert result.bank_statement_id == existing.id


@pytest.mark.asyncio
async def test_merge_from_different_user_succeeds(service: BankStatementService, user_b):
    existing = _existing_statement(uploaded_by=1)
    existing_txn = _stored_txn()
    new_row = _parsed_row(comment="Invoice 999", debited_amount=Decimal("50.00"))

    result = await _upload_with_rows(
        service,
        user_b,
        [_parsed_row(), new_row],
        existing_statement=existing,
        existing_txns=[existing_txn],
    )

    service._statement_repo.create.assert_not_awaited()
    assert result.merged_into_existing is True
    assert result.new_rows_added == 1
    assert result.existing_rows_kept == 1


@pytest.mark.asyncio
async def test_merge_with_no_new_rows_updates_source_only(
    service: BankStatementService, user_b
):
    existing = _existing_statement(uploaded_by=1)
    existing_txn = _stored_txn()
    duplicate_only = [_parsed_row()]

    result = await _upload_with_rows(
        service,
        user_b,
        duplicate_only,
        existing_statement=existing,
        existing_txns=[existing_txn],
    )

    service._transaction_repo.create_bulk.assert_not_awaited()
    service._statement_repo.update_after_merge.assert_awaited_once_with(
        existing.id,
        row_count=1,
        source_file_id=99,
        statement_date=date(2026, 7, 7),
    )
    assert result.merged_into_existing is True
    assert result.new_rows_added == 0
    assert result.existing_rows_kept == 1
    assert result.row_count == 1


@pytest.mark.asyncio
async def test_merge_partial_then_full_month_statement(service: BankStatementService, user_b):
    partial_date = date(2026, 5, 15)
    full_date = date(2026, 5, 31)
    partial_rows = [
        _parsed_row(
            transaction_date=date(2026, 5, 1),
            comment="Invoice partial-1",
        ),
        _parsed_row(
            transaction_date=date(2026, 5, 15),
            comment="Invoice partial-2",
        ),
    ]
    full_rows = partial_rows + [
        _parsed_row(
            transaction_date=date(2026, 5, 31),
            comment="Invoice full-only",
        ),
    ]

    partial_result = await _upload_with_rows(
        service,
        user_b,
        partial_rows,
        statement_date=partial_date,
        filename="XK051110343587000119_20260501-20260515.xls",
    )
    assert partial_result.merged_into_existing is False
    assert partial_result.statement_month == date(2026, 5, 1)

    existing = BankStatement(
        id=partial_result.bank_statement_id,
        statement_date=partial_date,
        statement_month=date(2026, 5, 1),
        source_file_id=99,
        uploaded_by=user_b.user_id,
        row_count=len(partial_rows),
        processing_status="processed",
    )
    existing_txns = [
        _stored_txn(
            id=idx + 1,
            bank_statement_id=existing.id,
            transaction_date=row.transaction_date,
            comment=row.comment,
        )
        for idx, row in enumerate(partial_rows)
    ]

    full_result = await _upload_with_rows(
        service,
        user_b,
        full_rows,
        statement_date=full_date,
        existing_statement=existing,
        existing_txns=existing_txns,
        filename="XK051110343587000119_20260501-20260531.xls",
    )

    service._statement_repo.create.assert_awaited_once()
    service._statement_repo.update_after_merge.assert_awaited_once_with(
        existing.id,
        row_count=3,
        source_file_id=99,
        statement_date=full_date,
    )
    assert full_result.merged_into_existing is True
    assert full_result.new_rows_added == 1
    assert full_result.existing_rows_kept == 2
    assert full_result.row_count == 3
    assert full_result.statement_month == date(2026, 5, 1)


@pytest.mark.asyncio
async def test_merge_full_then_partial_month_statement(service: BankStatementService, user_b):
    partial_date = date(2026, 5, 15)
    full_date = date(2026, 5, 31)
    partial_rows = [
        _parsed_row(
            transaction_date=date(2026, 5, 1),
            comment="Invoice partial-1",
        ),
        _parsed_row(
            transaction_date=date(2026, 5, 15),
            comment="Invoice partial-2",
        ),
    ]
    full_rows = partial_rows + [
        _parsed_row(
            transaction_date=date(2026, 5, 31),
            comment="Invoice full-only",
        ),
    ]

    full_result = await _upload_with_rows(
        service,
        user_b,
        full_rows,
        statement_date=full_date,
        filename="XK051110343587000119_20260501-20260531.xls",
    )
    assert full_result.merged_into_existing is False
    assert full_result.row_count == 3

    existing = BankStatement(
        id=full_result.bank_statement_id,
        statement_date=full_date,
        statement_month=date(2026, 5, 1),
        source_file_id=99,
        uploaded_by=user_b.user_id,
        row_count=len(full_rows),
        processing_status="processed",
    )
    existing_txns = [
        _stored_txn(
            id=idx + 1,
            bank_statement_id=existing.id,
            transaction_date=row.transaction_date,
            comment=row.comment,
        )
        for idx, row in enumerate(full_rows)
    ]

    partial_result = await _upload_with_rows(
        service,
        user_b,
        partial_rows,
        statement_date=partial_date,
        existing_statement=existing,
        existing_txns=existing_txns,
        filename="XK051110343587000119_20260501-20260515.xls",
    )

    service._statement_repo.create.assert_awaited_once()
    service._statement_repo.update_after_merge.assert_awaited_once_with(
        existing.id,
        row_count=3,
        source_file_id=99,
        statement_date=full_date,
    )
    assert partial_result.merged_into_existing is True
    assert partial_result.new_rows_added == 0
    assert partial_result.existing_rows_kept == 3
    assert partial_result.row_count == 3


def test_transaction_dedupe_key_matches_parsed_and_stored_rows():
    parsed = _parsed_row()
    stored = _stored_txn()
    assert transaction_dedupe_key(parsed) == transaction_dedupe_key(stored)
