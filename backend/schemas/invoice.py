from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class ExtractionResult(BaseModel):
    invoice_date: str | None = None
    name_of_company: str | None = None
    address_of_company: str | None = None
    invoice_number: str | None = None
    amount: float | None = None
    currency: str | None = None
    account_details: str | None = None
    internal_note_description: str | None = None
    client_employee_related: str | None = None
    category: str | None = None
    confidence_score: float = 0.0
    needs_review: bool = False


class InvoiceUpdate(BaseModel):
    invoice_date: date | None = None
    name_of_company: str | None = None
    address_of_company: str | None = None
    invoice_number: str | None = None
    amount: Decimal | None = None
    currency: str | None = None
    account_details: str | None = None
    internal_note_description: str | None = None
    client_employee_related: str | None = None
    paid_by: str | None = None
    fixed_status: str | None = None
    category: str | None = None


class InvoiceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    invoice_date: date | None
    name_of_company: str | None
    address_of_company: str | None
    invoice_number: str | None
    amount: Decimal | None
    currency: str | None
    account_details: str | None
    internal_note_description: str | None
    client_employee_related: str | None
    paid_at_date: date | None
    paid_by: str | None
    fixed_status: str | None
    category: str | None
    extraction_confidence: Decimal | None
    review_status: str
    match_status: str
    source_file_id: int | None
    created_at: datetime
    updated_at: datetime


class InvoiceListResponse(BaseModel):
    items: list[InvoiceResponse]
    total: int
    page: int
    limit: int


class UploadItemResponse(BaseModel):
    upload_id: int
    original_filename: str
    processing_status: str
    invoice_id: int | None = None
    error: str | None = None


class InvoiceUploadResponse(BaseModel):
    uploaded: int
    items: list[UploadItemResponse]


class InvoiceApproveResponse(BaseModel):
    id: int
    review_status: str
