from datetime import date
from decimal import Decimal

from sqlalchemy import and_, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.invoice_access import invoice_visible_to_user_clause
from models.bank_statement import BankStatement
from models.bank_transaction import BankTransaction
from models.invoice import Invoice
from models.invoice_payment_match import InvoicePaymentMatch
from schemas.reconciliation import (
    MatchBankTransactionSnapshot,
    MatchInvoiceSnapshot,
    MatchResultResponse,
)


def _to_response(
    row: InvoicePaymentMatch,
    invoice: Invoice | None = None,
    txn: BankTransaction | None = None,
) -> MatchResultResponse:
    inv_snapshot = (
        MatchInvoiceSnapshot(
            id=invoice.id,
            invoice_number=invoice.invoice_number,
            name_of_company=invoice.name_of_company,
            amount=invoice.amount,
            currency=invoice.currency,
        )
        if invoice is not None
        else None
    )
    txn_snapshot = (
        MatchBankTransactionSnapshot(
            id=txn.id,
            transaction_date=txn.transaction_date,
            comment=txn.comment,
            debited_amount=txn.debited_amount,
            credited_amount=txn.credited_amount,
            detected_invoice_numbers=list(txn.detected_invoice_numbers),
            reconciliation_status=txn.reconciliation_status,
        )
        if txn is not None
        else None
    )
    return MatchResultResponse(
        id=row.id,
        invoice_id=row.invoice_id,
        bank_transaction_id=row.bank_transaction_id,
        invoice_number=row.invoice_number,
        match_type=row.match_type,
        match_confidence=float(row.match_confidence),
        status=row.status,
        paid_at_date=row.paid_at_date,
        paid_amount=row.paid_amount,
        created_at=row.created_at,
        invoice=inv_snapshot,
        bank_transaction=txn_snapshot,
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
        *,
        paid_amount: Decimal | None = None,
        flush: bool = True,
    ) -> InvoicePaymentMatch:
        row = InvoicePaymentMatch(
            invoice_id=invoice_id,
            bank_transaction_id=bank_transaction_id,
            invoice_number=invoice_number,
            match_type=match_type,
            match_confidence=Decimal(str(match_confidence)),
            paid_at_date=paid_at_date,
            status=status,
            paid_amount=paid_amount,
        )
        self._session.add(row)
        if flush:
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
        approved_last = case(
            (InvoicePaymentMatch.status == "approved", 1),
            else_=0,
        )
        query = (
            query.order_by(approved_last, InvoicePaymentMatch.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        rows = (await self._session.execute(query)).scalars().all()

        invoice_ids = list({r.invoice_id for r in rows})
        txn_ids = list({r.bank_transaction_id for r in rows})

        invoices: dict[int, Invoice] = {}
        txns: dict[int, BankTransaction] = {}

        if invoice_ids:
            inv_rows = (
                await self._session.execute(
                    select(Invoice).where(Invoice.id.in_(invoice_ids))
                )
            ).scalars().all()
            invoices = {inv.id: inv for inv in inv_rows}

        if txn_ids:
            txn_rows = (
                await self._session.execute(
                    select(BankTransaction).where(BankTransaction.id.in_(txn_ids))
                )
            ).scalars().all()
            txns = {txn.id: txn for txn in txn_rows}

        return [
            _to_response(r, invoice=invoices.get(r.invoice_id), txn=txns.get(r.bank_transaction_id))
            for r in rows
        ], int(total)

    async def list_pairs_for_transactions(
        self, bank_transaction_ids: list[int]
    ) -> set[tuple[int, int]]:
        if not bank_transaction_ids:
            return set()
        q = select(
            InvoicePaymentMatch.invoice_id,
            InvoicePaymentMatch.bank_transaction_id,
        ).where(
            InvoicePaymentMatch.bank_transaction_id.in_(bank_transaction_ids)
        )
        rows = (await self._session.execute(q)).all()
        return {(int(inv_id), int(txn_id)) for inv_id, txn_id in rows}

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

    async def sum_paid_for_invoice(self, invoice_id: int) -> Decimal:
        q = select(func.coalesce(func.sum(InvoicePaymentMatch.paid_amount), 0)).where(
            and_(
                InvoicePaymentMatch.invoice_id == invoice_id,
                InvoicePaymentMatch.status.in_(("matched", "approved")),
                InvoicePaymentMatch.paid_amount.isnot(None),
            )
        )
        result = (await self._session.execute(q)).scalar_one()
        return Decimal(str(result))

    async def list_active_for_invoice(
        self, invoice_id: int
    ) -> list[InvoicePaymentMatch]:
        """Return all active (matched/approved) match rows for an invoice."""
        q = select(InvoicePaymentMatch).where(
            InvoicePaymentMatch.invoice_id == invoice_id,
            InvoicePaymentMatch.status.in_(("matched", "approved")),
        )
        return list((await self._session.execute(q)).scalars().all())

    async def list_for_invoice(
        self, invoice_id: int
    ) -> list[MatchResultResponse]:
        """Active matches for an invoice with bank transaction snapshots."""
        rows = await self.list_active_for_invoice(invoice_id)
        if not rows:
            return []

        txn_ids = list({r.bank_transaction_id for r in rows})
        txns: dict[int, BankTransaction] = {}
        if txn_ids:
            txn_rows = (
                await self._session.execute(
                    select(BankTransaction).where(BankTransaction.id.in_(txn_ids))
                )
            ).scalars().all()
            txns = {t.id: t for t in txn_rows}

        invoice_row = await self._session.get(Invoice, invoice_id)

        return [
            _to_response(
                r,
                invoice=invoice_row,
                txn=txns.get(r.bank_transaction_id),
            )
            for r in sorted(rows, key=lambda m: m.created_at, reverse=True)
        ]

    async def set_paid_amount_if_missing(
        self, match_id: int, paid_amount: Decimal
    ) -> None:
        row = await self.get(match_id)
        if row is None or row.paid_amount is not None:
            return
        row.paid_amount = paid_amount
        await self._session.flush()
