from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class ReconciliationRunRequest(BaseModel):
    bank_statement_id: int | None = None


class ReconciliationSummary(BaseModel):
    matched: int
    unmatched_invoices: int
    unmatched_transactions: int
    review_tasks_created: int
    run_at: str


class MatchResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    invoice_id: int
    bank_transaction_id: int
    invoice_number: str
    match_type: str
    match_confidence: float
    status: str
    paid_at_date: date
    created_at: datetime


class MatchListResponse(BaseModel):
    items: list[MatchResultResponse]
    total: int
    page: int
    limit: int


class ManualMatchRequest(BaseModel):
    invoice_id: int = Field(..., ge=1)
    bank_transaction_id: int = Field(..., ge=1)
    review_task_id: int | None = Field(default=None, ge=1)


class ManualMatchResponse(BaseModel):
    match_id: int
    status: str
    invoice_id: int
    bank_transaction_id: int
    review_task_id: int | None = None


class ApproveMatchRequest(BaseModel):
    match_id: int = Field(..., ge=1)


class RejectMatchRequest(BaseModel):
    match_id: int = Field(..., ge=1)
    reason: str | None = None


class MatchActionResponse(BaseModel):
    match_id: int
    status: str
