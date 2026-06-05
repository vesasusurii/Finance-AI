from fastapi import APIRouter, Depends, Query

from api.controllers.review_controller import ReviewController
from api.dependencies import get_current_user, get_review_controller
from schemas.auth import UserContext
from schemas.review import (
    ReviewDecisionRequest,
    ReviewTaskDecisionResponse,
    ReviewTaskListResponse,
)

router = APIRouter(prefix="/review", tags=["review"])


@router.get("", response_model=ReviewTaskListResponse)
async def list_review_tasks(
    task_type: str | None = None,
    has_invoice: bool | None = Query(
        None,
        description="When true, only tasks with a linked purchase invoice (invoice-centric queue).",
    ),
    reasons: list[str] | None = Query(
        None,
        description="When set, only tasks whose reason is in this list.",
    ),
    enrich: bool = Query(
        True,
        description="When false, skip loading linked invoice and bank transaction details.",
    ),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    user: UserContext = Depends(get_current_user),
    ctrl: ReviewController = Depends(get_review_controller),
):
    return await ctrl.list_open(
        user, task_type, page, limit, has_invoice, reasons, enrich=enrich
    )


@router.post("/{task_id}/approve", response_model=ReviewTaskDecisionResponse)
async def approve_review_task(
    task_id: int,
    user: UserContext = Depends(get_current_user),
    ctrl: ReviewController = Depends(get_review_controller),
):
    return await ctrl.approve(task_id, user)


@router.post("/{task_id}/reject", response_model=ReviewTaskDecisionResponse)
async def reject_review_task(
    task_id: int,
    body: ReviewDecisionRequest,
    user: UserContext = Depends(get_current_user),
    ctrl: ReviewController = Depends(get_review_controller),
):
    return await ctrl.reject(task_id, body, user)
