from core.debug_logger import debug_trace, get_logger
from core.invoice_access import upload_owner_user_id
from repositories.review_repository import ReviewRepository
from schemas.auth import UserContext
from schemas.review import ReviewTaskListResponse

logger = get_logger(__name__)


class ReviewController:
    def __init__(self, review_repo: ReviewRepository) -> None:
        self._review_repo = review_repo

    @debug_trace
    async def list_open(
        self,
        user: UserContext,
        task_type: str | None,
        page: int,
        limit: int,
    ) -> ReviewTaskListResponse:
        items, total = await self._review_repo.list_open(
            task_type,
            page,
            limit,
            owner_user_id=upload_owner_user_id(user),
        )
        return ReviewTaskListResponse(
            items=items, total=total, page=page, limit=limit
        )
