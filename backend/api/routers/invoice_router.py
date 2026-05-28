import mimetypes
from datetime import date

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from api.controllers.invoice_controller import InvoiceController
from api.dependencies import get_current_user, get_db_session, get_invoice_controller
from models.invoice import Invoice
from models.uploaded_file import UploadedFile
from schemas.auth import UserContext
from schemas.invoice import (
    InvoiceApproveResponse,
    InvoiceListResponse,
    InvoiceResponse,
    InvoiceUpdate,
    InvoiceUploadResponse,
)
from utils.file_storage import get_file_path

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


@router.get("", response_model=InvoiceListResponse)
async def list_invoices(
    review_status: str | None = None,
    match_status: str | None = None,
    invoice_date_from: date | None = None,
    invoice_date_to: date | None = None,
    company: str | None = None,
    sort: str | None = None,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    user: UserContext = Depends(get_current_user),
    ctrl: InvoiceController = Depends(get_invoice_controller),
):
    return await ctrl.list(
        review_status,
        match_status,
        invoice_date_from,
        invoice_date_to,
        company,
        sort,
        page,
        limit,
    )


@router.get("/{invoice_id}", response_model=InvoiceResponse)
async def get_invoice(
    invoice_id: int,
    user: UserContext = Depends(get_current_user),
    ctrl: InvoiceController = Depends(get_invoice_controller),
):
    return await ctrl.get(invoice_id)


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
    await ctrl.delete(invoice_id)


@router.post("/{invoice_id}/approve", response_model=InvoiceApproveResponse)
async def approve_invoice(
    invoice_id: int,
    user: UserContext = Depends(get_current_user),
    ctrl: InvoiceController = Depends(get_invoice_controller),
):
    return await ctrl.approve(invoice_id, user)


@router.get("/{invoice_id}/file")
async def get_invoice_file(
    invoice_id: int,
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    """Serve the original uploaded file for an invoice (PDF or image)."""
    invoice = await session.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(
            status_code=404,
            detail={"error": "invoice_not_found", "message": "Invoice not found."},
        )
    if not invoice.source_file_id:
        raise HTTPException(
            status_code=404,
            detail={"error": "no_source_file", "message": "No source file attached to this invoice."},
        )

    uploaded = await session.get(UploadedFile, invoice.source_file_id)
    if not uploaded:
        raise HTTPException(
            status_code=404,
            detail={"error": "file_record_missing", "message": "File record not found."},
        )

    file_path = get_file_path(uploaded.storage_path)
    if not file_path.exists():
        raise HTTPException(
            status_code=404,
            detail={"error": "file_missing", "message": "File not found on storage."},
        )

    mime = (
        uploaded.mime_type
        or mimetypes.guess_type(str(file_path))[0]
        or "application/octet-stream"
    )
    return FileResponse(
        path=str(file_path),
        media_type=mime,
        filename=uploaded.original_filename,
        headers={"Content-Disposition": "inline"},
    )
