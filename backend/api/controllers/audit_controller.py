from datetime import date

from core.debug_logger import debug_trace
from repositories.audit_repository import AuditRepository
from schemas.audit_log import AuditLogListResponse


class AuditController:
    def __init__(self, audit_repo: AuditRepository) -> None:
        self._audit_repo = audit_repo

    @debug_trace
    async def list_logs(
        self,
        page: int,
        limit: int,
        action: str | None,
        entity_type: str | None,
        user_id: int | None,
        date_from: date | None,
        date_to: date | None,
    ) -> AuditLogListResponse:
        items, total = await self._audit_repo.list_logs(
            page=page,
            limit=limit,
            action=action,
            entity_type=entity_type,
            user_id=user_id,
            date_from=date_from,
            date_to=date_to,
        )
        return AuditLogListResponse(
            items=items,
            total=total,
            page=page,
            limit=limit,
        )
