import time

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from core.debug_logger import get_logger
from models.bank_statement import BankStatement
from models.bank_transaction import BankTransaction
from schemas.bank_statement import BankTransactionResponse

logger = get_logger(__name__)


def _to_response(row: BankTransaction) -> BankTransactionResponse:
    numbers = row.detected_invoice_numbers
    if isinstance(numbers, list):
        detected = [str(n) for n in numbers]
    else:
        detected = []
    return BankTransactionResponse(
        id=row.id,
        bank_statement_id=row.bank_statement_id,
        transaction_date=row.transaction_date,
        debited_amount=row.debited_amount,
        credited_amount=row.credited_amount,
        transaction_type=row.transaction_type,
        comment=row.comment,
        detected_invoice_numbers=detected,
        reconciliation_status=row.reconciliation_status,
        created_at=row.created_at,
    )


class BankTransactionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _apply_statement_owner(
        self,
        query,
        *,
        owner_user_id: int | None,
        joined: bool,
    ):
        if owner_user_id is None:
            return query, joined
        if not joined:
            query = query.join(
                BankStatement,
                BankTransaction.bank_statement_id == BankStatement.id,
            )
            joined = True
        return query.where(BankStatement.uploaded_by == owner_user_id), joined

    async def create_bulk(
        self, bank_statement_id: int, rows: list[dict]
    ) -> list[BankTransaction]:
        entities = [
            BankTransaction(
                bank_statement_id=bank_statement_id,
                transaction_date=r.get("transaction_date"),
                debited_amount=r.get("debited_amount"),
                credited_amount=r.get("credited_amount"),
                transaction_type=r.get("transaction_type"),
                comment=r.get("comment"),
                detected_invoice_numbers=r.get("detected_invoice_numbers") or [],
                reconciliation_status="pending",
            )
            for r in rows
        ]
        self._session.add_all(entities)
        await self._session.flush()
        for entity in entities:
            await self._session.refresh(entity)
        return entities

    async def get(self, transaction_id: int) -> BankTransactionResponse | None:
        row = await self._session.get(BankTransaction, transaction_id)
        return _to_response(row) if row else None

    async def get_many(
        self, transaction_ids: list[int]
    ) -> dict[int, BankTransactionResponse]:
        ids = sorted(set(transaction_ids))
        if not ids:
            return {}
        q = select(BankTransaction).where(BankTransaction.id.in_(ids))
        result = await self._session.execute(q)
        return {row.id: _to_response(row) for row in result.scalars().all()}

    async def list_transactions(
        self,
        bank_statement_id: int | None,
        reconciliation_status: str | None,
        page: int,
        limit: int,
        *,
        owner_user_id: int | None = None,
        multi_invoice: bool = False,
    ) -> tuple[list[BankTransactionResponse], int]:
        base = select(BankTransaction)
        count_q = select(func.count()).select_from(BankTransaction)

        if owner_user_id is not None:
            join_condition = BankTransaction.bank_statement_id == BankStatement.id
            base = base.join(BankStatement, join_condition)
            count_q = count_q.join(BankStatement, join_condition)
            base = base.where(BankStatement.uploaded_by == owner_user_id)
            count_q = count_q.where(BankStatement.uploaded_by == owner_user_id)

        if bank_statement_id is not None:
            base = base.where(BankTransaction.bank_statement_id == bank_statement_id)
            count_q = count_q.where(
                BankTransaction.bank_statement_id == bank_statement_id
            )
        if reconciliation_status:
            base = base.where(
                BankTransaction.reconciliation_status == reconciliation_status
            )
            count_q = count_q.where(
                BankTransaction.reconciliation_status == reconciliation_status
            )
        if multi_invoice:
            multi_filter = func.jsonb_array_length(
                BankTransaction.detected_invoice_numbers
            ) > 1
            base = base.where(multi_filter)
            count_q = count_q.where(multi_filter)

        db_t0 = time.perf_counter()
        total = (await self._session.execute(count_q)).scalar_one()

        offset = (page - 1) * limit
        q = base.order_by(BankTransaction.id.asc()).offset(offset).limit(limit)
        result = await self._session.execute(q)
        rows = result.scalars().all()
        db_query_ms = round((time.perf_counter() - db_t0) * 1000, 1)
        if db_query_ms >= settings.slow_route_ms:
            logger.warning(
                "Slow bank transaction list query db_query_ms=%s statement_id=%s status=%s page=%d limit=%d total=%d",
                db_query_ms,
                bank_statement_id,
                reconciliation_status,
                page,
                limit,
                int(total),
            )
        return [_to_response(r) for r in rows], total

    async def list_for_statement(
        self, bank_statement_id: int
    ) -> list[BankTransaction]:
        q = (
            select(BankTransaction)
            .where(BankTransaction.bank_statement_id == bank_statement_id)
            .order_by(BankTransaction.id.asc())
        )
        result = await self._session.execute(q)
        return list(result.scalars().all())

    async def list_pending(
        self,
        bank_statement_id: int | None = None,
        *,
        owner_user_id: int | None = None,
    ) -> list[BankTransaction]:
        q = select(BankTransaction).where(
            BankTransaction.reconciliation_status == "pending"
        )
        joined = False
        if bank_statement_id is not None:
            q = q.where(BankTransaction.bank_statement_id == bank_statement_id)
        q, joined = self._apply_statement_owner(
            q, owner_user_id=owner_user_id, joined=joined
        )
        db_t0 = time.perf_counter()
        result = await self._session.execute(q)
        rows = list(result.scalars().all())
        db_query_ms = round((time.perf_counter() - db_t0) * 1000, 1)
        if db_query_ms >= settings.slow_route_ms:
            logger.warning(
                "Slow unresolved transaction query db_query_ms=%s statement_id=%s rows=%d owner_scoped=%s",
                db_query_ms,
                bank_statement_id,
                len(rows),
                owner_user_id is not None,
            )
        return rows

    async def list_unresolved(
        self,
        bank_statement_id: int | None = None,
        *,
        owner_user_id: int | None = None,
    ) -> list[BankTransaction]:
        """Transactions still eligible for matching: pending, needs_review, partial.

        `matched` rows are excluded — they're finalised. This lets re-runs pick up
        previously failed rows after the user edits invoice numbers.
        """
        q = select(BankTransaction).where(
            BankTransaction.reconciliation_status.in_(
                ("pending", "needs_review", "partial")
            )
        )
        joined = False
        if bank_statement_id is not None:
            q = q.where(BankTransaction.bank_statement_id == bank_statement_id)
        q, joined = self._apply_statement_owner(
            q, owner_user_id=owner_user_id, joined=joined
        )
        result = await self._session.execute(q)
        return list(result.scalars().all())

    async def save_detected_numbers(
        self, transaction_id: int, numbers: list[str]
    ) -> None:
        row = await self._session.get(BankTransaction, transaction_id)
        if row:
            row.detected_invoice_numbers = numbers
            await self._session.flush()

    async def update_reconciliation_status(
        self, transaction_id: int, status: str
    ) -> None:
        row = await self._session.get(BankTransaction, transaction_id)
        if row:
            row.reconciliation_status = status
            await self._session.flush()

    async def list_needs_review(
        self,
        bank_statement_id: int | None = None,
        *,
        owner_user_id: int | None = None,
    ) -> list[BankTransactionResponse]:
        q = select(BankTransaction).where(
            BankTransaction.reconciliation_status == "needs_review"
        )
        joined = False
        if bank_statement_id is not None:
            q = q.where(BankTransaction.bank_statement_id == bank_statement_id)
        q, joined = self._apply_statement_owner(
            q, owner_user_id=owner_user_id, joined=joined
        )
        result = await self._session.execute(q)
        return [_to_response(r) for r in result.scalars().all()]

    async def list_multi_invoice_matches(
        self,
        bank_statement_id: int | None = None,
        *,
        owner_user_id: int | None = None,
    ) -> list[BankTransactionResponse]:
        """Transactions with more than one detected invoice number."""
        q = select(BankTransaction).where(
            BankTransaction.reconciliation_status.in_(("matched", "partial"))
        )
        joined = False
        if bank_statement_id is not None:
            q = q.where(BankTransaction.bank_statement_id == bank_statement_id)
        q, joined = self._apply_statement_owner(
            q, owner_user_id=owner_user_id, joined=joined
        )
        result = await self._session.execute(q)
        rows = []
        for r in result.scalars().all():
            nums = r.detected_invoice_numbers
            if isinstance(nums, list) and len(nums) > 1:
                rows.append(_to_response(r))
        return rows
