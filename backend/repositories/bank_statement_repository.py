from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.bank_statement import BankStatement
from models.uploaded_file import UploadedFile
from schemas.bank_statement import BankStatementListItem


def _apply_owner_scope(query, owner_user_id: int | None):
    if owner_user_id is not None:
        return query.where(BankStatement.uploaded_by == owner_user_id)
    return query


class BankStatementRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        source_file_id: int,
        uploaded_by: int,
        row_count: int,
        processing_status: str = "processed",
    ) -> BankStatement:
        row = BankStatement(
            source_file_id=source_file_id,
            uploaded_by=uploaded_by,
            row_count=row_count,
            processing_status=processing_status,
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return row

    async def get(
        self,
        statement_id: int,
        *,
        owner_user_id: int | None = None,
    ) -> BankStatement | None:
        query = select(BankStatement).where(BankStatement.id == statement_id)
        query = _apply_owner_scope(query, owner_user_id)
        result = await self._session.execute(query)
        return result.scalar_one_or_none()

    async def update_status(
        self, statement_id: int, status: str, row_count: int | None = None
    ) -> None:
        row = await self.get(statement_id)
        if row:
            row.processing_status = status
            if row_count is not None:
                row.row_count = row_count
            await self._session.flush()

    async def list_statements(
        self,
        page: int,
        limit: int,
        *,
        owner_user_id: int | None = None,
    ) -> tuple[list[BankStatementListItem], int]:
        count_q = select(func.count()).select_from(BankStatement)
        count_q = _apply_owner_scope(count_q, owner_user_id)
        total = (await self._session.execute(count_q)).scalar_one()

        offset = (page - 1) * limit
        q = (
            select(BankStatement, UploadedFile.original_filename)
            .join(UploadedFile, BankStatement.source_file_id == UploadedFile.id)
            .order_by(BankStatement.uploaded_at.desc())
            .offset(offset)
            .limit(limit)
        )
        q = _apply_owner_scope(q, owner_user_id)
        result = await self._session.execute(q)
        items = [
            BankStatementListItem(
                id=stmt.id,
                original_filename=filename,
                uploaded_at=stmt.uploaded_at,
                uploaded_by=stmt.uploaded_by,
                row_count=stmt.row_count,
                processing_status=stmt.processing_status,
            )
            for stmt, filename in result.all()
        ]
        return items, total
