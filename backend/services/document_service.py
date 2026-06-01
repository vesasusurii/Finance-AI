from fastapi import BackgroundTasks, HTTPException, UploadFile
from openai import AsyncOpenAI

from core.document_types import is_ocr_ready, validate_document_file
from core.exceptions import ExtractionError
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
from services.invoice_processing_worker import schedule_invoice_extraction
from utils.file_storage import save_bytes


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
        background_tasks: BackgroundTasks,
    ) -> DocumentUploadResponse:
        items: list[DocumentUploadItemResponse] = []
        for file in files:
            filename = file.filename or "upload"
            try:
                content = await file.read()
                mime = validate_document_file(filename, file.content_type, len(content))
                await file.seek(0)

                if is_ocr_ready(mime):
                    prepared = await self._extraction.prepare_upload(file, user)
                    await self._upload_repo.commit()

                    if isinstance(prepared, UploadItemResponse):
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

                    schedule_invoice_extraction(
                        prepared.upload_id,
                        user.user_id,
                        self._openai,
                        background_tasks,
                    )
                    items.append(
                        DocumentUploadItemResponse(
                            document_id=prepared.upload_id,
                            filename=prepared.stored_filename,
                            upload_status="processing",
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
                        processing_status="pending",
                        file_size=file_size,
                    )
                    items.append(
                        DocumentUploadItemResponse(
                            document_id=row.id,
                            filename=filename,
                            upload_status="pending",
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
                items.append(
                    DocumentUploadItemResponse(
                        document_id=0,
                        filename=filename,
                        upload_status="failed",
                        error=str(exc),
                    )
                )
        return DocumentUploadResponse(uploaded=len(items), items=items)

    async def get_status(
        self, document_id: int, user: UserContext
    ) -> DocumentStatusResponse:
        row = await self._upload_repo.get(document_id)
        if row is None or row.uploaded_by != user.user_id:
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
