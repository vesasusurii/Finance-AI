from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from models.bank_statement import BankStatement
from models.uploaded_file import UploadedFile
from schemas.bank_statement import BankStatementListItem


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

    async def get(self, statement_id: int) -> BankStatement | None:
        return await self._session.get(BankStatement, statement_id)

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
        self, page: int, limit: int
    ) -> tuple[list[BankStatementListItem], int]:
        count_q = select(func.count()).select_from(BankStatement)
        total = (await self._session.execute(count_q)).scalar_one()

        offset = (page - 1) * limit
        q = (
            select(BankStatement, UploadedFile.original_filename)
            .join(UploadedFile, BankStatement.source_file_id == UploadedFile.id)
            .order_by(BankStatement.uploaded_at.desc())
            .offset(offset)
            .limit(limit)
        )
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
