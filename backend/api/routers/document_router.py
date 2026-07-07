from fastapi import APIRouter, Depends, File, UploadFile, status

from api.controllers.document_controller import DocumentController
from api.dependencies import get_current_user, get_document_controller
from schemas.auth import UserContext
from schemas.document import (
    DocumentStatusBatchRequest,
    DocumentStatusBatchResponse,
    DocumentStatusResponse,
    DocumentUploadResponse,
)

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post(
    "/upload",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=DocumentUploadResponse,
)
async def upload_documents(
    files: list[UploadFile] = File(...),
    user: UserContext = Depends(get_current_user),
    ctrl: DocumentController = Depends(get_document_controller),
):
    return await ctrl.upload(files, user)


@router.post(
    "/batch-status",
    response_model=DocumentStatusBatchResponse,
)
async def document_status_batch(
    body: DocumentStatusBatchRequest,
    user: UserContext = Depends(get_current_user),
    ctrl: DocumentController = Depends(get_document_controller),
):
    return await ctrl.status_batch(body.document_ids, user)


@router.get(
    "/{document_id}/status",
    response_model=DocumentStatusResponse,
)
async def document_status(
    document_id: int,
    user: UserContext = Depends(get_current_user),
    ctrl: DocumentController = Depends(get_document_controller),
):
    return await ctrl.status(document_id, user)
