from fastapi import HTTPException, UploadFile

from schemas.auth import UserContext
from schemas.document import (
    DocumentStatusBatchResponse,
    DocumentStatusResponse,
    DocumentUploadResponse,
)
from services.document_service import DocumentService


class DocumentController:
    def __init__(self, service: DocumentService) -> None:
        self._service = service

    async def upload(
        self,
        files: list[UploadFile],
        user: UserContext,
    ) -> DocumentUploadResponse:
        if not files:
            raise HTTPException(
                status_code=400,
                detail={"error": "no_files", "message": "No files attached."},
            )
        return await self._service.upload_files(files, user)

    async def status(
        self,
        document_id: int,
        user: UserContext,
    ) -> DocumentStatusResponse:
        return await self._service.get_status(document_id, user)

    async def status_batch(
        self,
        document_ids: list[int],
        user: UserContext,
    ) -> DocumentStatusBatchResponse:
        items = await self._service.get_status_batch(document_ids, user)
        return DocumentStatusBatchResponse(items=items)
