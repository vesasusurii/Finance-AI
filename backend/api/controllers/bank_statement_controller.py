from fastapi import HTTPException, UploadFile

from core.debug_logger import debug_trace, get_logger
from core.exceptions import ExcelParseError
from repositories.bank_statement_repository import BankStatementRepository
from repositories.bank_transaction_repository import BankTransactionRepository
from schemas.auth import UserContext
from schemas.bank_statement import (
    BankStatementListResponse,
    BankStatementUploadResponse,
    BankTransactionListResponse,
)
from services.bank_statement_service import BankStatementService

logger = get_logger(__name__)


class BankStatementController:
    def __init__(
        self,
        service: BankStatementService,
        statement_repo: BankStatementRepository,
        transaction_repo: BankTransactionRepository,
    ) -> None:
        self._service = service
        self._statement_repo = statement_repo
        self._transaction_repo = transaction_repo

    @debug_trace
    async def upload(
        self, file: UploadFile, user: UserContext
    ) -> BankStatementUploadResponse:
        if not file.filename:
            raise HTTPException(
                status_code=400,
                detail={"error": "no_file", "message": "No file attached."},
            )
        try:
            return await self._service.upload(file, user)
        except ExcelParseError as exc:
            msg = str(exc).lower()
            if "header" in msg or "column" in msg or "komenti" in msg:
                code = "missing_required_columns"
            elif "no transaction" in msg or "no data" in msg:
                code = "empty_file"
            elif "unsupported" in msg:
                code = "unsupported_file_type"
            else:
                code = "parse_error"
            raise HTTPException(
                status_code=400,
                detail={"error": code, "message": str(exc)},
            ) from exc

    @debug_trace
    async def list_statements(
        self, page: int, limit: int
    ) -> BankStatementListResponse:
        items, total = await self._statement_repo.list_statements(page, limit)
        return BankStatementListResponse(
            items=items, total=total, page=page, limit=limit
        )

    @debug_trace
    async def list_transactions(
        self,
        bank_statement_id: int | None,
        reconciliation_status: str | None,
        page: int,
        limit: int,
    ) -> BankTransactionListResponse:
        items, total = await self._transaction_repo.list_transactions(
            bank_statement_id, reconciliation_status, page, limit
        )
        return BankTransactionListResponse(
            items=items, total=total, page=page, limit=limit
        )
