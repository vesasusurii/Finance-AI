from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.invoice_access import InvoiceAccess


class InvoiceAccessRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def grant(
        self,
        invoice_id: int,
        user_id: int,
        *,
        grant_reason: str = "duplicate_upload",
    ) -> bool:
        """Grant access; returns True if a new row was created."""
        if await self.has_access(invoice_id, user_id):
            return False
        self._session.add(
            InvoiceAccess(
                invoice_id=invoice_id,
                user_id=user_id,
                grant_reason=grant_reason,
            )
        )
        await self._session.flush()
        return True

    async def has_access(self, invoice_id: int, user_id: int) -> bool:
        q = select(InvoiceAccess.id).where(
            InvoiceAccess.invoice_id == invoice_id,
            InvoiceAccess.user_id == user_id,
        )
        row = (await self._session.execute(q)).scalar_one_or_none()
        return row is not None

    async def revoke(self, invoice_id: int, user_id: int) -> bool:
        """Remove shared access for a user. Returns True if a row was deleted."""
        q = select(InvoiceAccess).where(
            InvoiceAccess.invoice_id == invoice_id,
            InvoiceAccess.user_id == user_id,
        )
        row = (await self._session.execute(q)).scalar_one_or_none()
        if row is None:
            return False
        await self._session.delete(row)
        await self._session.flush()
        return True
