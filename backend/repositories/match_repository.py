from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.invoice_access import invoice_visible_to_user_clause
from models.bank_statement import BankStatement
from models.bank_transaction import BankTransaction
from models.invoice import Invoice
from models.invoice_payment_match import InvoicePaymentMatch
from schemas.reconciliation import MatchResultResponse


def _to_response(row: InvoicePaymentMatch) -> MatchResultResponse:
    return MatchResultResponse(
        id=row.id,
        invoice_id=row.invoice_id,
        bank_transaction_id=row.bank_transaction_id,
        invoice_number=row.invoice_number,
        match_type=row.match_type,
        match_confidence=float(row.match_confidence),
        status=row.status,
        paid_at_date=row.paid_at_date,
        created_at=row.created_at,
    )


class MatchRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        invoice_id: int,
        bank_transaction_id: int,
        invoice_number: str,
        match_type: str,
        match_confidence: float,
        paid_at_date: date,
        status: str = "matched",
    ) -> InvoicePaymentMatch:
        row = InvoicePaymentMatch(
            invoice_id=invoice_id,
            bank_transaction_id=bank_transaction_id,
            invoice_number=invoice_number,
            match_type=match_type,
            match_confidence=Decimal(str(match_confidence)),
            paid_at_date=paid_at_date,
            status=status,
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return row

    async def get(self, match_id: int) -> InvoicePaymentMatch | None:
        return await self._session.get(InvoicePaymentMatch, match_id)

    async def get_response(self, match_id: int) -> MatchResultResponse | None:
        row = await self.get(match_id)
        return _to_response(row) if row else None

    async def approve(self, match_id: int) -> MatchResultResponse | None:
        row = await self.get(match_id)
        if not row:
            return None
        row.status = "approved"
        await self._session.flush()
        await self._session.refresh(row)
        return _to_response(row)

    async def reject(self, match_id: int) -> InvoicePaymentMatch | None:
        row = await self.get(match_id)
        if not row:
            return None
        row.status = "rejected"
        await self._session.flush()
        await self._session.refresh(row)
        return row

    async def list_matches(
        self,
        status: str | None,
        bank_statement_id: int | None,
        page: int,
        limit: int,
        *,
        owner_user_id: int | None = None,
    ) -> tuple[list[MatchResultResponse], int]:
        query = select(InvoicePaymentMatch)
        count_q = select(func.count()).select_from(InvoicePaymentMatch)
        txn_joined = False

        if owner_user_id is not None:
            visible = invoice_visible_to_user_clause(owner_user_id)
            query = query.join(
                Invoice, InvoicePaymentMatch.invoice_id == Invoice.id
            ).where(visible)
            count_q = count_q.join(
                Invoice, InvoicePaymentMatch.invoice_id == Invoice.id
            ).where(visible)
            query = query.join(
                BankTransaction,
                InvoicePaymentMatch.bank_transaction_id == BankTransaction.id,
            )
            count_q = count_q.join(
                BankTransaction,
                InvoicePaymentMatch.bank_transaction_id == BankTransaction.id,
            )
            txn_joined = True
            query = query.join(
                BankStatement,
                BankTransaction.bank_statement_id == BankStatement.id,
            ).where(BankStatement.uploaded_by == owner_user_id)
            count_q = count_q.join(
                BankStatement,
                BankTransaction.bank_statement_id == BankStatement.id,
            ).where(BankStatement.uploaded_by == owner_user_id)

        if status:
            query = query.where(InvoicePaymentMatch.status == status)
            count_q = count_q.where(InvoicePaymentMatch.status == status)

        if bank_statement_id is not None:
            if not txn_joined:
                query = query.join(
                    BankTransaction,
                    InvoicePaymentMatch.bank_transaction_id == BankTransaction.id,
                )
                count_q = count_q.join(
                    BankTransaction,
                    InvoicePaymentMatch.bank_transaction_id == BankTransaction.id,
                )
            query = query.where(BankTransaction.bank_statement_id == bank_statement_id)
            count_q = count_q.where(
                BankTransaction.bank_statement_id == bank_statement_id
            )

        total = (await self._session.execute(count_q)).scalar_one()
        offset = (page - 1) * limit
        query = (
            query.order_by(InvoicePaymentMatch.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        rows = (await self._session.execute(query)).scalars().all()
        return [_to_response(r) for r in rows], int(total)

    async def exists(
        self, invoice_id: int, bank_transaction_id: int
    ) -> bool:
        q = select(InvoicePaymentMatch.id).where(
            InvoicePaymentMatch.invoice_id == invoice_id,
            InvoicePaymentMatch.bank_transaction_id == bank_transaction_id,
        )
        row_id = (await self._session.execute(q)).scalar_one_or_none()
        return row_id is not None

    async def get_pair(
        self, invoice_id: int, bank_transaction_id: int
    ) -> InvoicePaymentMatch | None:
        q = select(InvoicePaymentMatch).where(
            InvoicePaymentMatch.invoice_id == invoice_id,
            InvoicePaymentMatch.bank_transaction_id == bank_transaction_id,
        )
        return (await self._session.execute(q)).scalar_one_or_none()

    async def active_for_invoice(
        self, invoice_id: int, *, exclude_bank_transaction_id: int | None = None
    ) -> InvoicePaymentMatch | None:
        q = select(InvoicePaymentMatch).where(
            InvoicePaymentMatch.invoice_id == invoice_id,
            InvoicePaymentMatch.status.in_(("matched", "approved")),
        )
        if exclude_bank_transaction_id is not None:
            q = q.where(
                InvoicePaymentMatch.bank_transaction_id != exclude_bank_transaction_id
            )
        return (await self._session.execute(q)).scalar_one_or_none()

    async def active_for_transaction(
        self, bank_transaction_id: int, *, exclude_invoice_id: int | None = None
    ) -> InvoicePaymentMatch | None:
        q = select(InvoicePaymentMatch).where(
            InvoicePaymentMatch.bank_transaction_id == bank_transaction_id,
            InvoicePaymentMatch.status.in_(("matched", "approved")),
        )
        if exclude_invoice_id is not None:
            q = q.where(InvoicePaymentMatch.invoice_id != exclude_invoice_id)
        return (await self._session.execute(q)).scalar_one_or_none()
