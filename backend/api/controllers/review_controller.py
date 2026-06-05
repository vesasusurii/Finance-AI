from core.debug_logger import debug_trace, get_logger
from core.invoice_access import upload_owner_user_id
from schemas.auth import UserContext
from schemas.review import (
    ReviewDecisionRequest,
    ReviewTaskDecisionResponse,
    ReviewTaskListResponse,
)
from services.review_service import ReviewService

logger = get_logger(__name__)


class ReviewController:
    def __init__(self, review_service: ReviewService) -> None:
        self._service = review_service

    @debug_trace
    async def list_open(
        self,
        user: UserContext,
        task_type: str | None,
        page: int,
        limit: int,
        has_invoice: bool | None,
        reasons: list[str] | None = None,
        *,
        enrich: bool = True,
    ) -> ReviewTaskListResponse:
        return await self._service.list_open(
            task_type,
            page,
            limit,
            owner_user_id=upload_owner_user_id(user),
            has_invoice=has_invoice,
            reasons=reasons,
            enrich=enrich,
        )

    @debug_trace
    async def approve(
        self, task_id: int, user: UserContext
    ) -> ReviewTaskDecisionResponse:
        return await self._service.approve(task_id, user)

    @debug_trace
    async def reject(
        self,
        task_id: int,
        request: ReviewDecisionRequest,
        user: UserContext,
    ) -> ReviewTaskDecisionResponse:
        return await self._service.reject(task_id, request.reason, user)
