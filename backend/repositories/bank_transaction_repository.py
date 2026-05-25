from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.bank_transaction import BankTransaction
from schemas.bank_statement import BankTransactionResponse


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

    async def list_transactions(
        self,
        bank_statement_id: int | None,
        reconciliation_status: str | None,
        page: int,
        limit: int,
    ) -> tuple[list[BankTransactionResponse], int]:
        filters = []
        if bank_statement_id is not None:
            filters.append(BankTransaction.bank_statement_id == bank_statement_id)
        if reconciliation_status:
            filters.append(
                BankTransaction.reconciliation_status == reconciliation_status
            )

        count_q = select(func.count()).select_from(BankTransaction)
        if filters:
            count_q = count_q.where(*filters)
        total = (await self._session.execute(count_q)).scalar_one()

        offset = (page - 1) * limit
        q = select(BankTransaction).order_by(BankTransaction.id.asc())
        if filters:
            q = q.where(*filters)
        q = q.offset(offset).limit(limit)
        result = await self._session.execute(q)
        rows = result.scalars().all()
        return [_to_response(r) for r in rows], total

    async def list_pending(
        self, bank_statement_id: int | None = None
    ) -> list[BankTransaction]:
        q = select(BankTransaction).where(
            BankTransaction.reconciliation_status == "pending"
        )
        if bank_statement_id is not None:
            q = q.where(BankTransaction.bank_statement_id == bank_statement_id)
        result = await self._session.execute(q)
        return list(result.scalars().all())

    async def save_detected_numbers(
        self, transaction_id: int, numbers: list[str]
    ) -> None:
        row = await self._session.get(BankTransaction, transaction_id)
        if row:
            row.detected_invoice_numbers = numbers
            await self._session.flush()
