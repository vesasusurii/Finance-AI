import hashlib
import mimetypes
from datetime import date

from fastapi import HTTPException, UploadFile
from fastapi.responses import FileResponse, Response

from core.cache import cache
from core.debug_logger import debug_trace, get_logger
from core.exceptions import ExtractionError
from core.invoice_access import invoice_owner_user_id, user_may_delete_invoice
from core.upload_enqueue import safe_enqueue_invoice_ocr
from repositories.audit_repository import AuditRepository
from repositories.invoice_access_repository import InvoiceAccessRepository
from repositories.invoice_repository import (
    DuplicateInvoiceNumberError,
    InvoiceRepository,
)
from repositories.match_repository import MatchRepository
from repositories.upload_repository import UploadRepository
from schemas.reconciliation import MatchListResponse
from schemas.auth import UserContext
from schemas.invoice import (
    InvoiceApproveResponse,
    InvoiceListResponse,
    InvoiceResponse,
    InvoiceTabCountsResponse,
    InvoiceUpdate,
    InvoiceUploadResponse,
    UploadItemResponse,
)
from services.invoice_extraction_service import InvoiceExtractionService
from utils.invoice_currency import CurrencyConversionError
from utils.file_storage import resolve_upload_bytes, resolve_upload_path
from utils.safe_filename import content_disposition_inline
from utils.user_display import approver_paid_by

logger = get_logger(__name__)

_TAB_COUNTS_TTL_SECONDS = 30


def _invoice_tab_counts_cache_token(search: str | None) -> str:
    if not search:
        return "all"
    return hashlib.sha256(search.strip().encode()).hexdigest()[:16]


def _invalidate_invoice_tab_counts() -> None:
    cache.delete_pattern("invoice_tab_counts:*")


class InvoiceController:
    def __init__(
        self,
        extraction_service: InvoiceExtractionService,
        invoice_repo: InvoiceRepository,
        invoice_access_repo: InvoiceAccessRepository,
        audit_repo: AuditRepository,
        upload_repo: UploadRepository,
        match_repo: MatchRepository,
    ) -> None:
        self._extraction = extraction_service
        self._invoice_repo = invoice_repo
        self._invoice_access_repo = invoice_access_repo
        self._audit_repo = audit_repo
        self._upload_repo = upload_repo
        self._match_repo = match_repo

    @debug_trace
    async def upload(
        self,
        files: list[UploadFile],
        user: UserContext,
    ) -> InvoiceUploadResponse:
        if not files:
            raise HTTPException(
                status_code=400,
                detail={"error": "no_files", "message": "No files attached."},
            )

        items: list[UploadItemResponse] = []

        for file in files:
            try:
                prepared = await self._extraction.prepare_upload(
                    file, user
                )
                if isinstance(prepared, UploadItemResponse):
                    await self._upload_repo.commit()
                    if (
                        prepared.invoice_id is None
                        and prepared.upload_id
                        and prepared.processing_status in ("queued", "processing")
                    ):
                        upload_row = await self._upload_repo.get(prepared.upload_id)
                        mime = (
                            upload_row.mime_type
                            if upload_row and upload_row.mime_type
                            else (file.content_type or "application/pdf")
                        )
                        file_size = int(upload_row.file_size or 0) if upload_row else 0
                        safe_enqueue_invoice_ocr(
                            prepared.upload_id,
                            user.user_id,
                            priority="high" if len(files) == 1 else "normal",
                            mime=mime,
                            file_size=file_size,
                            batch_upload=len(files) > 1,
                        )
                    items.append(prepared)
                    continue

                priority = "high" if len(files) == 1 else "normal"
                await self._upload_repo.commit()
                safe_enqueue_invoice_ocr(
                    prepared.upload_id,
                    user.user_id,
                    priority=priority,
                    content=prepared.content,
                    mime=prepared.mime,
                    file_size=prepared.file_size,
                    duplicate_reprocess=prepared.duplicate_reprocess,
                    batch_upload=len(files) > 1,
                )
                items.append(
                    UploadItemResponse(
                        upload_id=prepared.upload_id,
                        original_filename=prepared.stored_filename,
                        processing_status="saved",
                        message="File saved.",
                    )
                )
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
        user: UserContext,
        review_status: str | None,
        match_status: str | None,
        invoice_date_from: date | None,
        invoice_date_to: date | None,
        company: str | None,
        search: str | None,
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
                "search": search,
                "sort": sort,
            }.items()
            if v is not None
        }
        items, total = await self._invoice_repo.list_invoices(
            filters,
            page,
            limit,
            owner_user_id=invoice_owner_user_id(user),
        )
        return InvoiceListResponse(
            items=items, total=total, page=page, limit=limit
        )

    @debug_trace
    async def tab_counts(
        self,
        user: UserContext,
        search: str | None,
    ) -> InvoiceTabCountsResponse:
        owner = invoice_owner_user_id(user)
        cache_key = (
            f"invoice_tab_counts:{owner}:"
            f"{_invoice_tab_counts_cache_token(search)}"
        )
        cached = cache.get_model(cache_key, InvoiceTabCountsResponse)
        if cached is not None:
            return cached
        filters: dict = {}
        if search is not None:
            filters["search"] = search
        counts = await self._invoice_repo.count_by_tabs(
            filters,
            owner_user_id=owner,
        )
        response = InvoiceTabCountsResponse(**counts)
        cache.set_model(cache_key, response, ttl_seconds=_TAB_COUNTS_TTL_SECONDS)
        return response

    @debug_trace
    async def get(self, invoice_id: int, user: UserContext) -> InvoiceResponse:
        invoice = await self._invoice_repo.get(
            invoice_id,
            owner_user_id=invoice_owner_user_id(user),
        )
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
    async def list_matches(
        self, invoice_id: int, user: UserContext
    ) -> MatchListResponse:
        owner = invoice_owner_user_id(user)
        invoice = await self._invoice_repo.get(invoice_id, owner_user_id=owner)
        if not invoice:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "invoice_not_found",
                    "message": "Invoice not found.",
                },
            )
        items = await self._match_repo.list_for_invoice(invoice_id)
        return MatchListResponse(
            items=items,
            total=len(items),
            page=1,
            limit=max(len(items), 1),
        )

    @debug_trace
    async def update(
        self, invoice_id: int, data: InvoiceUpdate, user: UserContext
    ) -> InvoiceResponse:
        owner = invoice_owner_user_id(user)
        before = await self._invoice_repo.get(invoice_id, owner_user_id=owner)
        if not before:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "invoice_not_found",
                    "message": "Invoice not found.",
                },
            )
        try:
            updated = await self._invoice_repo.update(
                invoice_id,
                data,
                owner_user_id=owner,
            )
        except DuplicateInvoiceNumberError as exc:
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "duplicate_invoice_number",
                    "message": (
                        f"Another invoice with number {exc.args[0]!r} already exists "
                        "in your documents."
                    ),
                },
            ) from exc
        except CurrencyConversionError as exc:
            raise HTTPException(
                status_code=422,
                detail={
                    "error": "currency_conversion_failed",
                    "message": str(exc),
                },
            ) from exc
        if updated is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "invoice_not_found",
                    "message": "Invoice not found.",
                },
            )
        await self._audit_repo.log(
            user.user_id,
            "invoice_updated",
            "invoice",
            invoice_id,
            before.model_dump(mode="json"),
            updated.model_dump(mode="json"),
        )
        _invalidate_invoice_tab_counts()
        return updated

    @debug_trace
    async def delete(self, invoice_id: int, user: UserContext) -> None:
        owner = invoice_owner_user_id(user)
        invoice = await self._invoice_repo.get(invoice_id, owner_user_id=owner)
        if not invoice:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "invoice_not_found",
                    "message": "Invoice not found.",
                },
            )

        if user_may_delete_invoice(invoice.uploaded_by, owner):
            if not await self._invoice_repo.delete(
                invoice_id, owner_user_id=owner
            ):
                raise HTTPException(
                    status_code=404,
                    detail={
                        "error": "invoice_not_found",
                        "message": "Invoice not found.",
                    },
                )
            await self._audit_repo.log(
                user.user_id,
                "invoice_deleted",
                "invoice",
                invoice_id,
                invoice.model_dump(mode="json"),
                None,
            )
            _invalidate_invoice_tab_counts()
            return

        if owner is not None and await self._invoice_access_repo.revoke(
            invoice_id, owner
        ):
            await self._audit_repo.log(
                user.user_id,
                "invoice_access_revoked",
                "invoice",
                invoice_id,
                None,
                {"reason": "user_removed_shared_invoice"},
            )
            _invalidate_invoice_tab_counts()
            return

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
        invoice = await self._invoice_repo.approve(
            invoice_id,
            owner_user_id=invoice_owner_user_id(user),
            paid_by=approver_paid_by(user),
        )
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
        _invalidate_invoice_tab_counts()
        return InvoiceApproveResponse(id=invoice.id, review_status=invoice.review_status)

    async def serve_file(self, invoice_id: int, user: UserContext) -> Response:
        owner = invoice_owner_user_id(user)
        row = await self._invoice_repo.get_owned_row(invoice_id, owner_user_id=owner)
        if not row:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "invoice_not_found",
                    "message": "Invoice not found.",
                },
            )
        if not row.source_file_id:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "no_source_file",
                    "message": "No source file attached to this invoice.",
                },
            )

        upload = row.source_file
        if not upload:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "file_record_missing",
                    "message": "File record not found.",
                },
            )

        mime = (
            upload.mime_type
            or mimetypes.guess_type(upload.original_filename)[0]
            or "application/octet-stream"
        )

        data = await resolve_upload_bytes(
            upload.storage_path,
            upload.original_filename,
        )
        if data is None:
            file_path = resolve_upload_path(
                upload.storage_path,
                upload.original_filename,
            )
            if file_path is None:
                raise HTTPException(
                    status_code=404,
                    detail={
                        "error": "file_missing",
                        "message": (
                            "Original file is not available in storage. "
                            "Re-upload the invoice to attach a new copy."
                        ),
                    },
                )
            return FileResponse(
                path=str(file_path),
                media_type=mime,
                filename=upload.original_filename,
                headers=content_disposition_inline(upload.original_filename),
            )

        return Response(
            content=data,
            media_type=mime,
            headers=content_disposition_inline(upload.original_filename),
        )
