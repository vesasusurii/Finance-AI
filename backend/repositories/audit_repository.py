from datetime import date
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.audit_log import AuditLog
from models.user import User
from schemas.audit_log import AuditLogEntry


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

    async def list_logs(
        self,
        *,
        page: int,
        limit: int,
        action: str | None = None,
        entity_type: str | None = None,
        user_id: int | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> tuple[list[AuditLogEntry], int]:
        filters = []
        if action:
            filters.append(AuditLog.action == action)
        if entity_type:
            filters.append(AuditLog.entity_type == entity_type)
        if user_id is not None:
            filters.append(AuditLog.user_id == user_id)
        if date_from is not None:
            filters.append(func.date(AuditLog.created_at) >= date_from)
        if date_to is not None:
            filters.append(func.date(AuditLog.created_at) <= date_to)

        count_q = select(func.count()).select_from(AuditLog)
        if filters:
            count_q = count_q.where(*filters)
        total = int((await self._session.execute(count_q)).scalar_one())

        offset = (page - 1) * limit
        q = (
            select(AuditLog, User.email)
            .outerjoin(User, AuditLog.user_id == User.id)
            .order_by(AuditLog.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        if filters:
            q = q.where(*filters)

        rows = (await self._session.execute(q)).all()
        items = [
            AuditLogEntry(
                id=log.id,
                user_id=log.user_id,
                user_email=email,
                action=log.action,
                entity_type=log.entity_type,
                entity_id=log.entity_id,
                before=log.before,
                after=log.after,
                created_at=log.created_at,
            )
            for log, email in rows
        ]
        return items, total
