from fastapi import HTTPException, UploadFile

from core.cache import cache
from core.debug_logger import debug_trace, get_logger
from core.exceptions import ExcelParseError
from core.invoice_access import upload_owner_user_id
from repositories.bank_statement_repository import BankStatementRepository
from repositories.bank_transaction_repository import BankTransactionRepository
from schemas.auth import UserContext
from schemas.bank_statement import (
    BankStatementListResponse,
    BankStatementReparseResponse,
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
            response = await self._service.upload(file, user)
            cache.delete_pattern("bank_tx:*")
            return response
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
        self,
        user: UserContext,
        page: int,
        limit: int,
        uploaded_by: int | None = None,
    ) -> BankStatementListResponse:
        owner = upload_owner_user_id(user)
        filter_user_id = uploaded_by if owner is None else None
        items, total = await self._statement_repo.list_statements(
            page,
            limit,
            owner_user_id=owner,
            uploaded_by=filter_user_id,
        )
        return BankStatementListResponse(
            items=items, total=total, page=page, limit=limit
        )

    @debug_trace
    async def list_transactions(
        self,
        user: UserContext,
        bank_statement_id: int | None,
        reconciliation_status: str | None,
        page: int,
        limit: int,
        multi_invoice: bool = False,
    ) -> BankTransactionListResponse:
        owner = upload_owner_user_id(user)
        cache_key = (
            f"bank_tx:{owner}:{bank_statement_id}:{reconciliation_status}:"
            f"multi={multi_invoice}:{page}:{limit}"
        )
        cached = cache.get_model(cache_key, BankTransactionListResponse)
        if cached is not None:
            return cached
        items, total = await self._transaction_repo.list_transactions(
            bank_statement_id,
            reconciliation_status,
            page,
            limit,
            owner_user_id=owner,
            multi_invoice=multi_invoice,
        )
        response = BankTransactionListResponse(
            items=items, total=total, page=page, limit=limit
        )
        cache.set_model(cache_key, response, ttl_seconds=30)
        return response

    @debug_trace
    async def reparse_statement(
        self, statement_id: int, user: UserContext
    ) -> BankStatementReparseResponse:
        try:
            response = await self._service.reparse_statement(statement_id, user)
            cache.delete_pattern("bank_tx:*")
            cache.delete_pattern("review:*")
            return response
        except ExcelParseError as exc:
            raise HTTPException(
                status_code=400,
                detail={"error": "parse_error", "message": str(exc)},
            ) from exc

    @debug_trace
    async def delete_statement(
        self, statement_id: int, user: UserContext
    ) -> None:
        await self._service.delete_statement(statement_id, user)
        cache.delete_pattern("bank_tx:*")
