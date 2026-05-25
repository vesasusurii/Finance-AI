from fastapi import APIRouter, Depends, File, Query, UploadFile

from api.controllers.bank_statement_controller import BankStatementController
from api.dependencies import get_bank_statement_controller, get_current_user
from schemas.auth import UserContext
from schemas.bank_statement import (
    BankStatementListResponse,
    BankStatementUploadResponse,
    BankTransactionListResponse,
)

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
    user: UserContext = Depends(get_current_user),
    ctrl: BankStatementController = Depends(get_bank_statement_controller),
):
    return await ctrl.list_statements(page, limit)


@router.get("/bank-transactions", response_model=BankTransactionListResponse)
async def list_bank_transactions(
    bank_statement_id: int | None = None,
    reconciliation_status: str | None = None,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    user: UserContext = Depends(get_current_user),
    ctrl: BankStatementController = Depends(get_bank_statement_controller),
):
    return await ctrl.list_transactions(
        bank_statement_id, reconciliation_status, page, limit
    )
