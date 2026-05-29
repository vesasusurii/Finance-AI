from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class BankTransactionPreview(BaseModel):
    transaction_date: date | None
    debited_amount: Decimal | None
    credited_amount: Decimal | None
    transaction_type: str | None
    comment: str | None
    detected_invoice_numbers: list[str] = Field(default_factory=list)


class BankStatementUploadResponse(BaseModel):
    bank_statement_id: int
    statement_date: date
    row_count: int
    processing_status: str
    unparsed_date_rows: int = 0
    duplicate_rows_skipped: int = 0
    preview: list[BankTransactionPreview]


class BankStatementListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    statement_date: date | None
    original_filename: str
    uploaded_at: datetime
    uploaded_by: int
    row_count: int
    processing_status: str


class BankStatementListResponse(BaseModel):
    items: list[BankStatementListItem]
    total: int
    page: int
    limit: int


class BankTransactionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    bank_statement_id: int
    transaction_date: date | None
    debited_amount: Decimal | None
    credited_amount: Decimal | None
    transaction_type: str | None
    comment: str | None
    detected_invoice_numbers: list[str]
    reconciliation_status: str
    created_at: datetime


class BankTransactionListResponse(BaseModel):
    items: list[BankTransactionResponse]
    total: int
    page: int
    limit: int
