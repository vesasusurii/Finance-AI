from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field


class CategorySummary(BaseModel):
    category: str
    count: int
    total_amount: Decimal = Field(default=Decimal("0"))


class PeriodReportResponse(BaseModel):
    period: str
    period_label: str
    start_date: date
    end_date: date
    total_invoices: int
    total_amount: Decimal
    paid_invoices: int
    unpaid_invoices: int
    total_paid_amount: Decimal
    matched_invoices: int
    unmatched_invoices: int
    needs_review: int
    bank_transactions: int
    bank_matched: int
    bank_needs_review: int
    by_category: list[CategorySummary]
