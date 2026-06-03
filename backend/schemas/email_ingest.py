"""Outlook / n8n email ingestion API responses."""

from pydantic import BaseModel, Field


class EmailIngestResponse(BaseModel):
    """n8n-friendly response; extraction fields fill after async OCR completes."""

    supplier: str | None = Field(
        default=None,
        description="Maps to name_of_company when invoice row exists.",
    )
    invoice_number: str | None = None
    invoice_date: str | None = None
    amount: float | None = None
    currency: str | None = None
    confidence: float | None = None
    status: str = Field(
        description="queued | processing | completed | linked | failed",
    )
    duplicate: bool = False
    upload_id: int
    invoice_id: int | None = None
    message_id: str | None = None
    attachment_name: str | None = None
    sender_email: str | None = None
    error: str | None = None
