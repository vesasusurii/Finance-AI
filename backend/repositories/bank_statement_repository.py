from datetime import date

from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from models.bank_statement import BankStatement
from models.invoice_payment_match import InvoicePaymentMatch
from models.review_task import ReviewTask
from models.bank_transaction import BankTransaction
from models.uploaded_file import UploadedFile
from models.user import User
from schemas.bank_statement import BankStatementListItem
from utils.bank_excel_parser import statement_id_from_date


def _apply_owner_scope(
    query,
    owner_user_id: int | None,
    *,
    uploaded_by: int | None = None,
):
    if owner_user_id is not None:
        return query.where(BankStatement.uploaded_by == owner_user_id)
    if uploaded_by is not None:
        return query.where(BankStatement.uploaded_by == uploaded_by)
    return query


class BankStatementRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        source_file_id: int,
        uploaded_by: int,
        row_count: int,
        statement_date: date,
        processing_status: str = "processed",
    ) -> BankStatement:
        statement_id = statement_id_from_date(statement_date)
        existing_by_date = await self.get_by_date(uploaded_by, statement_date)
        if existing_by_date:
            await self.delete_statement(
                existing_by_date.id,
                owner_user_id=uploaded_by,
            )

        existing_id = await self.get(statement_id, owner_user_id=None)
        if existing_id and existing_id.uploaded_by != uploaded_by:
            raise ValueError(
                "A bank statement for this date already exists for another user."
            )
        if existing_id:
            await self.delete_statement(statement_id, owner_user_id=uploaded_by)

        row = BankStatement(
            id=statement_id,
            statement_date=statement_date,
            source_file_id=source_file_id,
            uploaded_by=uploaded_by,
            row_count=row_count,
            processing_status=processing_status,
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        await self._session.execute(
            text(
                "SELECT setval("
                "pg_get_serial_sequence('bank_statements', 'id'), "
                "(SELECT COALESCE(MAX(id), 1) FROM bank_statements)"
                ")"
            )
        )
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

    async def get_by_date(
        self,
        uploaded_by: int,
        statement_date: date,
    ) -> BankStatement | None:
        result = await self._session.execute(
            select(BankStatement).where(
                BankStatement.uploaded_by == uploaded_by,
                BankStatement.statement_date == statement_date,
            )
        )
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
        uploaded_by: int | None = None,
    ) -> tuple[list[BankStatementListItem], int]:
        count_q = select(func.count()).select_from(BankStatement)
        count_q = _apply_owner_scope(
            count_q, owner_user_id, uploaded_by=uploaded_by
        )
        total = (await self._session.execute(count_q)).scalar_one()

        offset = (page - 1) * limit
        q = (
            select(BankStatement, UploadedFile.original_filename, User.email)
            .join(UploadedFile, BankStatement.source_file_id == UploadedFile.id)
            .join(User, BankStatement.uploaded_by == User.id)
            .order_by(
                BankStatement.statement_date.desc().nullslast(),
                BankStatement.uploaded_at.desc(),
            )
            .offset(offset)
            .limit(limit)
        )
        q = _apply_owner_scope(q, owner_user_id, uploaded_by=uploaded_by)
        result = await self._session.execute(q)
        items = [
            BankStatementListItem(
                id=stmt.id,
                statement_date=stmt.statement_date,
                original_filename=filename,
                uploaded_at=stmt.uploaded_at,
                uploaded_by=stmt.uploaded_by,
                uploaded_by_email=uploader_email,
                row_count=stmt.row_count,
                processing_status=stmt.processing_status,
            )
            for stmt, filename, uploader_email in result.all()
        ]
        return items, total

    async def count_by_uploader(self) -> dict[int, int]:
        result = await self._session.execute(
            select(BankStatement.uploaded_by, func.count())
            .group_by(BankStatement.uploaded_by)
        )
        return {user_id: int(count) for user_id, count in result.all()}

    async def delete_statement(
        self,
        statement_id: int,
        *,
        owner_user_id: int | None,
    ) -> BankStatement | None:
        row = await self.get(statement_id, owner_user_id=owner_user_id)
        if row is None:
            return None

        txn_ids = select(BankTransaction.id).where(
            BankTransaction.bank_statement_id == statement_id
        )
        await self._session.execute(
            delete(InvoicePaymentMatch).where(
                InvoicePaymentMatch.bank_transaction_id.in_(txn_ids)
            )
        )
        await self._session.execute(
            delete(ReviewTask).where(ReviewTask.bank_transaction_id.in_(txn_ids))
        )
        await self._session.delete(row)
        await self._session.flush()
        return row
