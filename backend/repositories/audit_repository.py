from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from models.audit_log import AuditLog


class AuditRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def log(
        self,
        user_id: int | None,
        action: str,
        entity_type: str,
        entity_id: int,
        before: dict[str, Any] | None,
        after: dict[str, Any] | None,
    ) -> AuditLog:
        row = AuditLog(
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            before=before,
            after=after,
        )
        self._session.add(row)
        await self._session.flush()
        return row
