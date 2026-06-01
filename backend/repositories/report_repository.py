from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.bank_statement import BankStatement
from models.bank_transaction import BankTransaction
from models.invoice import Invoice
from schemas.report import CategorySummary


class ReportRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def invoice_period_stats(
        self,
        start: date,
        end: date,
        *,
        owner_user_id: int | None = None,
    ) -> dict:
        filters = [
            Invoice.invoice_date >= start,
            Invoice.invoice_date <= end,
        ]
        if owner_user_id is not None:
            filters.append(Invoice.uploaded_by == owner_user_id)

        base = select(
            func.count(Invoice.id).label("total"),
            func.coalesce(func.sum(Invoice.amount), 0).label("total_amount"),
            func.count(case((Invoice.paid_at_date.is_not(None), 1))).label("paid"),
            func.coalesce(
                func.sum(case((Invoice.paid_at_date.is_not(None), Invoice.amount))),
                0,
            ).label("paid_amount"),
            func.count(case((Invoice.match_status == "matched", 1))).label("matched"),
            func.count(case((Invoice.match_status == "unmatched", 1))).label(
                "unmatched"
            ),
            func.count(
                case(
                    (
                        Invoice.review_status.in_(("needs_review", "manual_review")),
                        1,
                    )
                )
            ).label("needs_review"),
        ).where(*filters)

        row = (await self._session.execute(base)).one()
        total = int(row.total or 0)
        paid = int(row.paid or 0)
        return {
            "total_invoices": total,
            "total_amount": Decimal(str(row.total_amount or 0)),
            "paid_invoices": paid,
            "unpaid_invoices": max(0, total - paid),
            "total_paid_amount": Decimal(str(row.paid_amount or 0)),
            "matched_invoices": int(row.matched or 0),
            "unmatched_invoices": int(row.unmatched or 0),
            "needs_review": int(row.needs_review or 0),
        }

    async def category_breakdown(
        self,
        start: date,
        end: date,
        *,
        owner_user_id: int | None = None,
    ) -> list[CategorySummary]:
        filters = [
            Invoice.invoice_date >= start,
            Invoice.invoice_date <= end,
        ]
        if owner_user_id is not None:
            filters.append(Invoice.uploaded_by == owner_user_id)

        category_label = func.coalesce(Invoice.category, "Uncategorised").label(
            "category"
        )
        q = (
            select(
                category_label,
                func.count(Invoice.id).label("count"),
                func.coalesce(func.sum(Invoice.amount), 0).label("total_amount"),
            )
            .where(*filters)
            .group_by(category_label)
            .order_by(func.coalesce(func.sum(Invoice.amount), 0).desc())
        )
        rows = (await self._session.execute(q)).all()
        return [
            CategorySummary(
                category=str(r.category),
                count=int(r.count),
                total_amount=Decimal(str(r.total_amount or 0)),
            )
            for r in rows
        ]

    async def bank_period_stats(
        self,
        start: date,
        end: date,
        *,
        owner_user_id: int | None = None,
    ) -> dict:
        filters = [
            BankTransaction.transaction_date >= start,
            BankTransaction.transaction_date <= end,
        ]
        q = select(
            func.count(BankTransaction.id).label("total"),
            func.count(
                case((BankTransaction.reconciliation_status == "matched", 1))
            ).label("matched"),
            func.count(
                case((BankTransaction.reconciliation_status == "needs_review", 1))
            ).label("needs_review"),
        ).where(*filters)

        if owner_user_id is not None:
            q = q.join(
                BankStatement,
                BankTransaction.bank_statement_id == BankStatement.id,
            ).where(BankStatement.uploaded_by == owner_user_id)

        row = (await self._session.execute(q)).one()
        return {
            "bank_transactions": int(row.total or 0),
            "bank_matched": int(row.matched or 0),
            "bank_needs_review": int(row.needs_review or 0),
        }
