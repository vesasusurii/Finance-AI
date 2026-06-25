from fastapi import HTTPException, UploadFile
from openai import AsyncOpenAI

from core.debug_logger import get_logger
from core.document_types import is_ocr_ready, validate_document_file
from core.exceptions import ExtractionError
from core.roles import is_admin
from core.upload_enqueue import safe_enqueue_invoice_ocr
from repositories.invoice_repository import InvoiceRepository
from repositories.upload_repository import UploadRepository
from schemas.auth import UserContext
from schemas.document import (
    DocumentStatusResponse,
    DocumentUploadItemResponse,
    DocumentUploadResponse,
)
from schemas.invoice import UploadItemResponse
from services.invoice_extraction_service import InvoiceExtractionService
from utils.file_storage import save_bytes

logger = get_logger(__name__)


class DocumentService:
    def __init__(
        self,
        upload_repo: UploadRepository,
        invoice_repo: InvoiceRepository,
        extraction_service: InvoiceExtractionService,
        openai_client: AsyncOpenAI | None,
    ) -> None:
        self._upload_repo = upload_repo
        self._invoice_repo = invoice_repo
        self._extraction = extraction_service
        self._openai = openai_client

    async def upload_files(
        self,
        files: list[UploadFile],
        user: UserContext,
    ) -> DocumentUploadResponse:
        items: list[DocumentUploadItemResponse] = []

        for file in files:
            filename = file.filename or "upload"
            try:
                content = await file.read()
                mime = validate_document_file(filename, file.content_type, len(content))

                if is_ocr_ready(mime):
                    prepared = await self._extraction.prepare_upload(
                        file, user, content=content
                    )

                    if isinstance(prepared, UploadItemResponse):
                        await self._upload_repo.commit()
                        if (
                            prepared.invoice_id is None
                            and prepared.upload_id
                            and prepared.processing_status
                            in ("queued", "processing")
                        ):
                            safe_enqueue_invoice_ocr(
                                prepared.upload_id,
                                user.user_id,
                                priority="high" if len(files) == 1 else "normal",
                            )
                        items.append(
                            DocumentUploadItemResponse(
                                document_id=prepared.upload_id,
                                filename=prepared.original_filename,
                                upload_status=prepared.processing_status,
                                mime_type=mime,
                                file_size=len(content),
                                invoice_id=prepared.invoice_id,
                                error=prepared.error,
                                message=prepared.message,
                                original_uploader_email=prepared.original_uploader_email,
                            )
                        )
                        continue

                    priority = "high" if len(files) == 1 else "normal"
                    await self._upload_repo.commit()
                    safe_enqueue_invoice_ocr(
                        prepared.upload_id,
                        user.user_id,
                        priority=priority,
                    )
                    logger.info(
                        "Upload stored upload_id=%d filename=%r",
                        prepared.upload_id,
                        prepared.stored_filename,
                    )
                    items.append(
                        DocumentUploadItemResponse(
                            document_id=prepared.upload_id,
                            filename=prepared.stored_filename,
                            upload_status="saved",
                            mime_type=prepared.mime,
                            file_size=prepared.file_size,
                        )
                    )
                else:
                    storage_path, file_size = await save_bytes(
                        content,
                        user_id=user.user_id,
                        filename=filename,
                        mime_type=mime,
                    )
                    row = await self._upload_repo.create(
                        file_kind="document",
                        filename=filename,
                        storage_path=storage_path,
                        mime_type=mime,
                        user_id=user.user_id,
                        processing_status="processed",
                        file_size=file_size,
                    )
                    await self._upload_repo.commit()
                    items.append(
                        DocumentUploadItemResponse(
                            document_id=row.id,
                            filename=filename,
                            upload_status="saved",
                            mime_type=mime,
                            file_size=file_size,
                        )
                    )
            except (ValueError, ExtractionError) as exc:
                items.append(
                    DocumentUploadItemResponse(
                        document_id=0,
                        filename=filename,
                        upload_status="failed",
                        error=str(exc),
                    )
                )
            except Exception as exc:
                logger.exception("Document upload failed for %r", filename)
                items.append(
                    DocumentUploadItemResponse(
                        document_id=0,
                        filename=filename,
                        upload_status="failed",
                        error=str(exc),
                    )
                )

        return DocumentUploadResponse(uploaded=len(items), items=items)

    async def _user_can_view_upload(self, row, user: UserContext) -> bool:
        if row.uploaded_by == user.user_id or is_admin(user.role):
            return True
        invoice_id = await self._invoice_repo.get_id_by_source_file(row.id)
        if invoice_id is None:
            return False
        invoice = await self._invoice_repo.get(
            invoice_id,
            owner_user_id=user.user_id,
        )
        return invoice is not None

    async def get_status(
        self,
        document_id: int,
        user: UserContext,
    ) -> DocumentStatusResponse:
        row = await self._upload_repo.get(document_id)
        if row is None or not await self._user_can_view_upload(row, user):
            raise HTTPException(
                status_code=404,
                detail={"error": "not_found", "message": "Document not found."},
            )

        invoice_id = None
        if row.processing_status == "processed":
            invoice_id = await self._invoice_repo.get_id_by_source_file(row.id)

        return DocumentStatusResponse(
            document_id=row.id,
            filename=row.original_filename,
            upload_status=row.processing_status,
            mime_type=row.mime_type,
            file_size=row.file_size,
            invoice_id=invoice_id,
        )
