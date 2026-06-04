import mimetypes
from datetime import date

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from fastapi.responses import Response

from api.controllers.invoice_controller import InvoiceController
from api.dependencies import get_current_user, get_invoice_controller
from api.dependencies_email_ingest import verify_email_ingest_user
from schemas.auth import UserContext
from schemas.email_ingest import EmailIngestResponse
from schemas.invoice import (
    InvoiceApproveResponse,
    InvoiceListResponse,
    InvoiceResponse,
    InvoiceUpdate,
    InvoiceUploadResponse,
)
from schemas.reconciliation import MatchListResponse

router = APIRouter(prefix="/invoices", tags=["invoices"])


@router.post(
    "/upload",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=InvoiceUploadResponse,
)
async def upload_invoices(
    files: list[UploadFile] = File(...),
    user: UserContext = Depends(get_current_user),
    ctrl: InvoiceController = Depends(get_invoice_controller),
):
    return await ctrl.upload(files, user)


@router.post(
    "/email-upload",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=EmailIngestResponse,
)
async def email_upload_invoice(
    file: UploadFile = File(..., description="Invoice attachment (PDF, PNG, JPG, JPEG)"),
    source: str = Form(default="outlook_email"),
    sender_email: str | None = Form(default=None),
    sender_name: str | None = Form(default=None),
    email_subject: str | None = Form(default=None),
    message_id: str | None = Form(default=None),
    attachment_name: str | None = Form(default=None),
    user: UserContext = Depends(verify_email_ingest_user),
    ctrl: InvoiceController = Depends(get_invoice_controller),
) -> EmailIngestResponse:
    """n8n / Outlook ingestion — stores file and queues OCR (no extraction in n8n)."""
    return await ctrl.email_upload(
        file,
        user,
        source=source,
        sender_email=sender_email,
        sender_name=sender_name,
        email_subject=email_subject,
        message_id=message_id,
        attachment_name=attachment_name,
    )


@router.get("", response_model=InvoiceListResponse)
async def list_invoices(
    review_status: str | None = None,
    match_status: str | None = None,
    invoice_date_from: date | None = None,
    invoice_date_to: date | None = None,
    company: str | None = None,
    search: str | None = None,
    sort: str | None = None,
    upload_source: str | None = None,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    user: UserContext = Depends(get_current_user),
    ctrl: InvoiceController = Depends(get_invoice_controller),
):
    return await ctrl.list(
        user,
        review_status,
        match_status,
        invoice_date_from,
        invoice_date_to,
        company,
        search,
        sort,
        upload_source,
        page,
        limit,
    )


@router.get("/{invoice_id}", response_model=InvoiceResponse)
async def get_invoice(
    invoice_id: int,
    user: UserContext = Depends(get_current_user),
    ctrl: InvoiceController = Depends(get_invoice_controller),
):
    return await ctrl.get(invoice_id, user)


@router.put("/{invoice_id}", response_model=InvoiceResponse)
async def update_invoice(
    invoice_id: int,
    body: InvoiceUpdate,
    user: UserContext = Depends(get_current_user),
    ctrl: InvoiceController = Depends(get_invoice_controller),
):
    return await ctrl.update(invoice_id, body, user)


@router.delete("/{invoice_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_invoice(
    invoice_id: int,
    user: UserContext = Depends(get_current_user),
    ctrl: InvoiceController = Depends(get_invoice_controller),
):
    await ctrl.delete(invoice_id, user)


@router.post("/{invoice_id}/approve", response_model=InvoiceApproveResponse)
async def approve_invoice(
    invoice_id: int,
    user: UserContext = Depends(get_current_user),
    ctrl: InvoiceController = Depends(get_invoice_controller),
):
    return await ctrl.approve(invoice_id, user)


@router.get("/{invoice_id}/matches", response_model=MatchListResponse)
async def list_invoice_matches(
    invoice_id: int,
    user: UserContext = Depends(get_current_user),
    ctrl: InvoiceController = Depends(get_invoice_controller),
):
    return await ctrl.list_matches(invoice_id, user)


@router.get("/{invoice_id}/file")
async def get_invoice_file(
    invoice_id: int,
    user: UserContext = Depends(get_current_user),
    ctrl: InvoiceController = Depends(get_invoice_controller),
) -> Response:
    """Serve the original uploaded file for an invoice (PDF or image)."""
    return await ctrl.serve_file(invoice_id, user)
