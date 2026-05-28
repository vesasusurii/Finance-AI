from fastapi import APIRouter, Depends, Query

from api.controllers.review_controller import ReviewController
from api.dependencies import get_current_user, get_review_controller
from schemas.auth import UserContext
from schemas.review import ReviewTaskListResponse

router = APIRouter(prefix="/review", tags=["review"])


@router.get("", response_model=ReviewTaskListResponse)
async def list_review_tasks(
    task_type: str | None = None,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    user: UserContext = Depends(get_current_user),
    ctrl: ReviewController = Depends(get_review_controller),
):
    return await ctrl.list_open(task_type, page, limit)
