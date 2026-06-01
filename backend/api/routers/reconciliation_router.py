from fastapi import APIRouter, Depends, Query

from api.controllers.reconciliation_controller import ReconciliationController
from api.dependencies import get_current_user, get_reconciliation_controller
from schemas.auth import UserContext
from schemas.reconciliation import (
    ApproveMatchRequest,
    ManualMatchRequest,
    ManualMatchResponse,
    MatchActionResponse,
    MatchListResponse,
    ReconciliationRunRequest,
    ReconciliationSummary,
    RejectMatchRequest,
)

router = APIRouter(prefix="/reconciliation", tags=["reconciliation"])


@router.post("/run", response_model=ReconciliationSummary)
async def run_reconciliation(
    body: ReconciliationRunRequest | None = None,
    user: UserContext = Depends(get_current_user),
    ctrl: ReconciliationController = Depends(get_reconciliation_controller),
):
    request = body or ReconciliationRunRequest()
    return await ctrl.run(request, user)


@router.get("/results", response_model=MatchListResponse)
async def reconciliation_results(
    status: str | None = None,
    bank_statement_id: int | None = None,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    user: UserContext = Depends(get_current_user),
    ctrl: ReconciliationController = Depends(get_reconciliation_controller),
):
    return await ctrl.results(user, status, bank_statement_id, page, limit)


@router.post("/manual-match", response_model=ManualMatchResponse)
async def manual_match(
    body: ManualMatchRequest,
    user: UserContext = Depends(get_current_user),
    ctrl: ReconciliationController = Depends(get_reconciliation_controller),
):
    return await ctrl.manual_match(body, user)


@router.post("/approve-match", response_model=MatchActionResponse)
async def approve_match(
    body: ApproveMatchRequest,
    user: UserContext = Depends(get_current_user),
    ctrl: ReconciliationController = Depends(get_reconciliation_controller),
):
    return await ctrl.approve_match(body, user)


@router.post("/reject-match", response_model=MatchActionResponse)
async def reject_match(
    body: RejectMatchRequest,
    user: UserContext = Depends(get_current_user),
    ctrl: ReconciliationController = Depends(get_reconciliation_controller),
):
    return await ctrl.reject_match(body, user)
