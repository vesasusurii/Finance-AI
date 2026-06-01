from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from utils.normalization import normalize_invoice_number


def _format_invoice_number(v: str | None) -> str | None:
    if v is None:
        return None
    text = str(v).strip()
    return normalize_invoice_number(text) if text else None


def _clean_paid_by(v: str | None) -> str | None:
    if v is None:
        return None
    text = str(v).strip()
    if not text:
        return None
    return text[:300]


class ExtractionResult(BaseModel):
    invoice_date: str | None = None
    name_of_company: str | None = None
    address_of_company: str | None = None
    invoice_number: str | None = None

    @field_validator("invoice_number", mode="before")
    @classmethod
    def _invoice_number_format(cls, v: str | None) -> str | None:
        return _format_invoice_number(v)
    amount: float | None = None
    debt: float | None = None
    currency: str | None = None
    # Set by Vision for utility routing; not stored on Invoice row
    document_type: str | None = None
    account_details: str | None = None
    internal_note_description: str | None = None
    client_employee_related: str | None = None
    category: str | None = None
    confidence_score: float = 0.0
    needs_review: bool = False
    # Per-field confidence scores, e.g. {"name_of_company": 0.95, "amount": 0.72}
    field_confidences: dict[str, float] | None = None


class InvoiceUpdate(BaseModel):
    invoice_date: date | None = None
    name_of_company: str | None = None
    address_of_company: str | None = None
    invoice_number: str | None = None

    @field_validator("invoice_number", mode="before")
    @classmethod
    def _invoice_number_format(cls, v: str | None) -> str | None:
        return _format_invoice_number(v)
    amount: Decimal | None = None
    debt: Decimal | None = None
    currency: str | None = None
    account_details: str | None = None
    internal_note_description: str | None = None
    client_employee_related: str | None = None
    paid_by: str | None = None
    fixed_status: str | None = None
    category: str | None = None

    @field_validator("paid_by", mode="before")
    @classmethod
    def _paid_by_format(cls, v: str | None) -> str | None:
        return _clean_paid_by(v)


class InvoiceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    invoice_date: date | None
    name_of_company: str | None
    address_of_company: str | None
    invoice_number: str | None
    amount: Decimal | None
    debt: Decimal | None
    currency: str | None
    account_details: str | None
    internal_note_description: str | None
    client_employee_related: str | None
    paid_at_date: date | None
    paid_by: str | None
    fixed_status: str | None
    category: str | None
    extraction_confidence: Decimal | None
    field_confidences: dict | None
    review_status: str
    match_status: str
    uploaded_by: int
    source_file_id: int | None
    source_filename: str | None = None
    source_mime_type: str | None = None
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
    # Set when processing_status is "linked" (duplicate file already in system).
    message: str | None = None
    original_uploader_email: str | None = None


class InvoiceUploadResponse(BaseModel):
    uploaded: int
    items: list[UploadItemResponse]


class InvoiceApproveResponse(BaseModel):
    id: int
    review_status: str
