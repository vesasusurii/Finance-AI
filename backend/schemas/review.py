from datetime import datetime

from pydantic import BaseModel, ConfigDict

from schemas.bank_statement import BankTransactionResponse
from schemas.invoice import InvoiceResponse


class ReviewTaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    task_type: str
    invoice_id: int | None
    bank_transaction_id: int | None
    reason: str
    status: str
    payload: dict | None
    created_at: datetime
    resolved_at: datetime | None
    invoice: InvoiceResponse | None = None
    bank_transaction: BankTransactionResponse | None = None


class ReviewTaskListResponse(BaseModel):
    items: list[ReviewTaskResponse]
    total: int
    page: int
    limit: int


class ReviewDecisionRequest(BaseModel):
    reason: str | None = None


class ReviewTaskDecisionResponse(BaseModel):
    review_task_id: int
    status: str
    resolved_at: datetime
