"""Bank-statement-scoped purchase invoice export."""

from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from sqlalchemy.dialects import postgresql

from api.controllers.export_controller import ExportController
from models.bank_statement import BankStatement
from repositories.invoice_repository import InvoiceRepository
from schemas.auth import UserContext
from services.excel_service import ExcelService
from services.export_service import ExportService


def _user() -> UserContext:
    return UserContext(user_id=7, email="f@borek.com", role="finance")


@pytest.fixture
def export_controller() -> ExportController:
    return ExportController(
        excel_service=ExcelService(),
        export_service=AsyncMock(spec=ExportService),
        invoice_repo=AsyncMock(),
        statement_repo=AsyncMock(),
    )


@pytest.mark.asyncio
async def test_purchase_invoices_excel_404_when_statement_missing(
    export_controller: ExportController,
):
    export_controller._statement_repo.get.return_value = None

    with pytest.raises(HTTPException) as exc_info:
        await export_controller.purchase_invoices_excel(
            _user(),
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            99,
        )

    assert exc_info.value.status_code == 404
    export_controller._invoice_repo.list_invoices_for_export.assert_not_awaited()


@pytest.mark.asyncio
async def test_purchase_invoices_excel_passes_bank_statement_filter(
    export_controller: ExportController,
):
    export_controller._statement_repo.get.return_value = BankStatement(
        id=12,
        statement_date=date(2026, 3, 1),
        statement_month=date(2026, 3, 1),
        source_file_id=1,
        uploaded_by=7,
        row_count=10,
        processing_status="processed",
    )
    export_controller._invoice_repo.list_invoices_for_export.return_value = []

    response = await export_controller.purchase_invoices_excel(
        _user(),
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        12,
    )

    export_controller._invoice_repo.list_invoices_for_export.assert_awaited_once_with(
        {"bank_statement_id": 12},
        owner_user_id=None,
    )
    assert (
        response.headers["Content-Disposition"]
        == 'attachment; filename="purchase_invoices_statement_12_'
        f'{date.today().isoformat()}.xlsx"'
    )


@pytest.mark.asyncio
async def test_list_invoices_for_export_query_scopes_by_statement_and_confirmed_matches():
    session = AsyncMock()
    repo = InvoiceRepository(session)

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    session.execute = AsyncMock(return_value=mock_result)

    await repo.list_invoices_for_export({"bank_statement_id": 5})

    query = session.execute.await_args.args[0]
    compiled = query.compile(
        dialect=postgresql.dialect(),
        compile_kwargs={"literal_binds": True},
    )
    sql = str(compiled).lower()

    assert "invoice_payment_matches" in sql
    assert "bank_transactions" in sql
    assert "bank_statement_id" in sql
    assert "distinct" in sql
    assert "matched" in sql
    assert "approved" in sql
    assert "rejected" not in sql
    assert "suggested" not in sql
