from fastapi import HTTPException, UploadFile

from schemas.auth import UserContext
from schemas.document import DocumentStatusResponse, DocumentUploadResponse
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
