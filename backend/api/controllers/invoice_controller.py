from datetime import date

from fastapi import HTTPException, UploadFile

from core.debug_logger import debug_trace, get_logger
from core.exceptions import ExtractionError
from repositories.audit_repository import AuditRepository
from repositories.invoice_repository import InvoiceRepository
from schemas.auth import UserContext
from schemas.invoice import (
    InvoiceApproveResponse,
    InvoiceListResponse,
    InvoiceResponse,
    InvoiceUpdate,
    InvoiceUploadResponse,
    UploadItemResponse,
)
from services.invoice_extraction_service import InvoiceExtractionService

logger = get_logger(__name__)


class InvoiceController:
    def __init__(
        self,
        extraction_service: InvoiceExtractionService,
        invoice_repo: InvoiceRepository,
        audit_repo: AuditRepository,
    ) -> None:
        self._extraction = extraction_service
        self._invoice_repo = invoice_repo
        self._audit_repo = audit_repo

    @debug_trace
    async def upload(
        self, files: list[UploadFile], user: UserContext
    ) -> InvoiceUploadResponse:
        if not files:
            raise HTTPException(
                status_code=400,
                detail={"error": "no_files", "message": "No files attached."},
            )

        items: list[UploadItemResponse] = []
        for file in files:
            try:
                item = await self._extraction.process_upload(file, user)
                items.append(item)
            except ExtractionError as exc:
                items.append(
                    UploadItemResponse(
                        upload_id=0,
                        original_filename=file.filename or "unknown",
                        processing_status="failed",
                        error=str(exc),
                    )
                )

        return InvoiceUploadResponse(uploaded=len(items), items=items)

    @debug_trace
    async def list(
        self,
        review_status: str | None,
        match_status: str | None,
        invoice_date_from: date | None,
        invoice_date_to: date | None,
        company: str | None,
        sort: str | None,
        page: int,
        limit: int,
    ) -> InvoiceListResponse:
        filters = {
            k: v
            for k, v in {
                "review_status": review_status,
                "match_status": match_status,
                "invoice_date_from": invoice_date_from,
                "invoice_date_to": invoice_date_to,
                "company": company,
                "sort": sort,
            }.items()
            if v is not None
        }
        items, total = await self._invoice_repo.list_invoices(filters, page, limit)
        return InvoiceListResponse(
            items=items, total=total, page=page, limit=limit
        )

    @debug_trace
    async def get(self, invoice_id: int) -> InvoiceResponse:
        invoice = await self._invoice_repo.get(invoice_id)
        if not invoice:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "invoice_not_found",
                    "message": "Invoice not found.",
                },
            )
        return invoice

    @debug_trace
    async def update(
        self, invoice_id: int, data: InvoiceUpdate, user: UserContext
    ) -> InvoiceResponse:
        before = await self._invoice_repo.get(invoice_id)
        if not before:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "invoice_not_found",
                    "message": "Invoice not found.",
                },
            )
        updated = await self._invoice_repo.update(invoice_id, data)
        if updated:
            await self._audit_repo.log(
                user.user_id,
                "invoice_updated",
                "invoice",
                invoice_id,
                before.model_dump(mode="json"),
                updated.model_dump(mode="json"),
            )
        return updated  # type: ignore[return-value]

    @debug_trace
    async def delete(self, invoice_id: int) -> None:
        if not await self._invoice_repo.delete(invoice_id):
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "invoice_not_found",
                    "message": "Invoice not found.",
                },
            )

    @debug_trace
    async def approve(
        self, invoice_id: int, user: UserContext
    ) -> InvoiceApproveResponse:
        invoice = await self._invoice_repo.approve(invoice_id)
        if not invoice:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "invoice_not_found",
                    "message": "Invoice not found.",
                },
            )
        await self._audit_repo.log(
            user.user_id,
            "invoice_approved",
            "invoice",
            invoice_id,
            None,
            {"review_status": "approved"},
        )
        return InvoiceApproveResponse(id=invoice.id, review_status=invoice.review_status)
