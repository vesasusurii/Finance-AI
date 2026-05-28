from core.debug_logger import debug_trace, get_logger
from repositories.review_repository import ReviewRepository
from schemas.review import ReviewTaskListResponse

logger = get_logger(__name__)


class ReviewController:
    def __init__(self, review_repo: ReviewRepository) -> None:
        self._review_repo = review_repo

    @debug_trace
    async def list_open(
        self,
        task_type: str | None,
        page: int,
        limit: int,
    ) -> ReviewTaskListResponse:
        items, total = await self._review_repo.list_open(task_type, page, limit)
        return ReviewTaskListResponse(
            items=items, total=total, page=page, limit=limit
        )
