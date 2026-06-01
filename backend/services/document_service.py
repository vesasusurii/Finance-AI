from fastapi import UploadFile

from core.document_types import is_ocr_ready, validate_document_file
from repositories.upload_repository import UploadRepository
from schemas.auth import UserContext
from schemas.document import DocumentUploadItemResponse, DocumentUploadResponse
from services.invoice_extraction_service import InvoiceExtractionService
from utils.file_storage import save_bytes


class DocumentService:
    def __init__(
        self,
        upload_repo: UploadRepository,
        extraction_service: InvoiceExtractionService,
    ) -> None:
        self._upload_repo = upload_repo
        self._extraction = extraction_service

    async def upload_files(
        self, files: list[UploadFile], user: UserContext
    ) -> DocumentUploadResponse:
        items: list[DocumentUploadItemResponse] = []
        for file in files:
            filename = file.filename or "upload"
            try:
                content = await file.read()
                mime = validate_document_file(filename, file.content_type, len(content))
                await file.seek(0)

                if is_ocr_ready(mime):
                    upload_item = await self._extraction.process_upload(file, user)
                    doc_row = await self._upload_repo.get(upload_item.upload_id)
                    items.append(
                        DocumentUploadItemResponse(
                            document_id=upload_item.upload_id,
                            filename=upload_item.original_filename,
                            upload_status=upload_item.processing_status,
                            mime_type=doc_row.mime_type if doc_row else mime,
                            file_size=doc_row.file_size if doc_row else len(content),
                            invoice_id=upload_item.invoice_id,
                            error=upload_item.error,
                            message=upload_item.message,
                            original_uploader_email=upload_item.original_uploader_email,
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
            except ValueError as exc:
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
