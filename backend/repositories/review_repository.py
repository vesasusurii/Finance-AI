from datetime import datetime

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.invoice_access import invoice_visible_to_user_clause
from models.bank_statement import BankStatement
from models.bank_transaction import BankTransaction
from models.invoice import Invoice
from models.review_task import ReviewTask
from schemas.review import ReviewTaskResponse


def _to_response(row: ReviewTask) -> ReviewTaskResponse:
    return ReviewTaskResponse.model_validate(row)


def _owner_visibility_filter(owner_user_id: int):
    """Tasks visible to a finance user (invoice access or bank statement owner)."""
    return or_(
        invoice_visible_to_user_clause(owner_user_id),
        BankStatement.uploaded_by == owner_user_id,
    )


class ReviewRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_bank_unmatched(
        self,
        bank_transaction_id: int,
        invoice_number: str,
        reason: str,
        payload: dict | None = None,
    ) -> ReviewTask:
        row = ReviewTask(
            task_type="bank_match",
            bank_transaction_id=bank_transaction_id,
            invoice_id=None,
            reason=reason,
            status="open",
            payload=payload
            if payload is not None
            else ({"invoice_number": invoice_number} if invoice_number else None),
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return row

    async def create_extraction_failure(
        self,
        invoice_id: int,
        reason: str,
        payload: dict | None,
    ) -> ReviewTask:
        row = ReviewTask(
            task_type="extraction",
            invoice_id=invoice_id,
            bank_transaction_id=None,
            reason=reason,
            status="open",
            payload=payload,
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return row

    async def list_open(
        self,
        task_type: str | None,
        page: int,
        limit: int,
        *,
        owner_user_id: int | None = None,
        reasons: list[str] | None = None,
    ) -> tuple[list[ReviewTaskResponse], int]:
        query = select(ReviewTask).where(ReviewTask.status == "open")
        count_q = (
            select(func.count(func.distinct(ReviewTask.id)))
            .select_from(ReviewTask)
            .where(ReviewTask.status == "open")
        )
        if task_type:
            query = query.where(ReviewTask.task_type == task_type)
            count_q = count_q.where(ReviewTask.task_type == task_type)
        if reasons:
            query = query.where(ReviewTask.reason.in_(reasons))
            count_q = count_q.where(ReviewTask.reason.in_(reasons))

        if owner_user_id is not None:
            owner_filter = _owner_visibility_filter(owner_user_id)
            query = (
                query.outerjoin(Invoice, ReviewTask.invoice_id == Invoice.id)
                .outerjoin(
                    BankTransaction,
                    ReviewTask.bank_transaction_id == BankTransaction.id,
                )
                .outerjoin(
                    BankStatement,
                    BankTransaction.bank_statement_id == BankStatement.id,
                )
                .where(owner_filter)
                .distinct()
            )
            count_q = (
                count_q.outerjoin(Invoice, ReviewTask.invoice_id == Invoice.id)
                .outerjoin(
                    BankTransaction,
                    ReviewTask.bank_transaction_id == BankTransaction.id,
                )
                .outerjoin(
                    BankStatement,
                    BankTransaction.bank_statement_id == BankStatement.id,
                )
                .where(owner_filter)
            )
        total = (await self._session.execute(count_q)).scalar_one()
        offset = (page - 1) * limit
        query = query.order_by(ReviewTask.created_at.desc()).offset(offset).limit(limit)
        rows = (await self._session.execute(query)).scalars().all()
        return [_to_response(r) for r in rows], int(total)

    async def get(self, task_id: int) -> ReviewTask | None:
        return await self._session.get(ReviewTask, task_id)

    async def is_visible_to_user(
        self, task_id: int, owner_user_id: int
    ) -> bool:
        """True when the task is in scope for a finance user (not admin)."""
        q = (
            select(ReviewTask.id)
            .where(ReviewTask.id == task_id)
            .outerjoin(Invoice, ReviewTask.invoice_id == Invoice.id)
            .outerjoin(
                BankTransaction,
                ReviewTask.bank_transaction_id == BankTransaction.id,
            )
            .outerjoin(
                BankStatement,
                BankTransaction.bank_statement_id == BankStatement.id,
            )
            .where(_owner_visibility_filter(owner_user_id))
            .limit(1)
        )
        row = (await self._session.execute(q)).scalar_one_or_none()
        return row is not None

    async def resolve(
        self, task_id: int, status: str, resolved_at: datetime
    ) -> ReviewTask | None:
        row = await self.get(task_id)
        if not row:
            return None
        row.status = status
        row.resolved_at = resolved_at
        await self._session.flush()
        await self._session.refresh(row)
        return row

    async def has_open_bank_task(
        self,
        bank_transaction_id: int,
        reason: str,
        invoice_number: str | None = None,
    ) -> bool:
        """Check if an open bank_match review task already exists for this txn.

        Used by matching service to avoid creating duplicate tasks on re-runs.
        """
        q = select(ReviewTask.id).where(
            ReviewTask.task_type == "bank_match",
            ReviewTask.bank_transaction_id == bank_transaction_id,
            ReviewTask.reason == reason,
            ReviewTask.status == "open",
        )
        rows = (await self._session.execute(q)).scalars().all()
        if not invoice_number:
            return len(rows) > 0
        for tid in rows:
            row = await self._session.get(ReviewTask, tid)
            if row and row.payload and row.payload.get("invoice_number") == invoice_number:
                return True
        return False

    async def resolve_open_bank_tasks_for_txn(
        self,
        bank_transaction_id: int,
        matched_invoice_numbers: list[str],
        resolved_at: datetime,
    ) -> int:
        """Auto-resolve open bank_match tasks for a txn whose invoice now exists.

        Called after a re-run match succeeds for a previously failed candidate.
        Returns the number of tasks resolved.
        """
        q = select(ReviewTask).where(
            ReviewTask.task_type == "bank_match",
            ReviewTask.bank_transaction_id == bank_transaction_id,
            ReviewTask.status == "open",
        )
        rows = (await self._session.execute(q)).scalars().all()
        count = 0
        for row in rows:
            payload_num = (row.payload or {}).get("invoice_number")
            if not payload_num:
                continue
            if payload_num in matched_invoice_numbers:
                row.status = "approved"
                row.resolved_at = resolved_at
                count += 1
        if count:
            await self._session.flush()
        return count

    async def resolve_missing_transaction_date_tasks(
        self, bank_transaction_id: int, resolved_at: datetime
    ) -> int:
        q = select(ReviewTask).where(
            ReviewTask.task_type == "bank_match",
            ReviewTask.bank_transaction_id == bank_transaction_id,
            ReviewTask.reason == "missing_transaction_date",
            ReviewTask.status == "open",
        )
        rows = (await self._session.execute(q)).scalars().all()
        for row in rows:
            row.status = "approved"
            row.resolved_at = resolved_at
        if rows:
            await self._session.flush()
        return len(rows)
