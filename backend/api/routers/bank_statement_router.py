from fastapi import APIRouter, Depends, File, Query, UploadFile, status

from api.controllers.bank_statement_controller import BankStatementController
from api.dependencies import get_bank_statement_controller, get_current_user
from schemas.auth import UserContext
from schemas.bank_statement import (
    BankStatementListResponse,
    BankStatementReparseResponse,
    BankStatementUploadResponse,
    BankTransactionListResponse,
)
from utils.pagination import normalize_pagination

router = APIRouter(tags=["bank"])


@router.post(
    "/bank-statements/upload",
    response_model=BankStatementUploadResponse,
)
async def upload_bank_statement(
    file: UploadFile = File(...),
    user: UserContext = Depends(get_current_user),
    ctrl: BankStatementController = Depends(get_bank_statement_controller),
):
    return await ctrl.upload(file, user)


@router.get("/bank-statements", response_model=BankStatementListResponse)
async def list_bank_statements(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    uploaded_by: int | None = Query(
        None,
        description="Admin only: filter statements by uploader user id.",
    ),
    user: UserContext = Depends(get_current_user),
    ctrl: BankStatementController = Depends(get_bank_statement_controller),
):
    return await ctrl.list_statements(user, page, limit, uploaded_by)


@router.delete("/bank-statements/{statement_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_bank_statement(
    statement_id: int,
    user: UserContext = Depends(get_current_user),
    ctrl: BankStatementController = Depends(get_bank_statement_controller),
):
    await ctrl.delete_statement(statement_id, user)


@router.post(
    "/bank-statements/{statement_id}/reparse",
    response_model=BankStatementReparseResponse,
)
async def reparse_bank_statement(
    statement_id: int,
    user: UserContext = Depends(get_current_user),
    ctrl: BankStatementController = Depends(get_bank_statement_controller),
):
    return await ctrl.reparse_statement(statement_id, user)


@router.get("/bank-transactions", response_model=BankTransactionListResponse)
async def list_bank_transactions(
    bank_statement_id: int | None = None,
    reconciliation_status: str | None = None,
    multi_invoice: bool = Query(
        False,
        description="When true, only transactions with more than one detected invoice number.",
    ),
    page: int = Query(1),
    limit: int = Query(50),
    user: UserContext = Depends(get_current_user),
    ctrl: BankStatementController = Depends(get_bank_statement_controller),
):
    page, limit = normalize_pagination(page, limit)
    if reconciliation_status is not None:
        reconciliation_status = reconciliation_status.strip() or None
    return await ctrl.list_transactions(
        user, bank_statement_id, reconciliation_status, page, limit, multi_invoice
    )
