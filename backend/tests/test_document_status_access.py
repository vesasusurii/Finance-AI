from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from schemas.auth import UserContext
from services.document_service import DocumentService


def _user(user_id: int, role: str = "finance") -> UserContext:
    return UserContext(user_id=user_id, email=f"user{user_id}@example.com", role=role)


@pytest.fixture
def document_service() -> DocumentService:
    return DocumentService(
        upload_repo=AsyncMock(),
        invoice_repo=AsyncMock(),
        extraction_service=MagicMock(),
        openai_client=None,
    )


@pytest.mark.asyncio
async def test_get_status_allows_invoice_shared_access(document_service: DocumentService):
    upload_row = MagicMock()
    upload_row.id = 141
    upload_row.uploaded_by = 1
    upload_row.original_filename = "invoice.pdf"
    upload_row.processing_status = "processed"
    upload_row.mime_type = "application/pdf"
    upload_row.file_size = 1000

    document_service._upload_repo.get = AsyncMock(return_value=upload_row)
    document_service._invoice_repo.get_id_by_source_file = AsyncMock(return_value=273)
    document_service._invoice_repo.get = AsyncMock(
        return_value=MagicMock(id=273),
    )

    result = await document_service.get_status(141, _user(21))

    assert result.document_id == 141
    assert result.upload_status == "processed"
    document_service._invoice_repo.get.assert_awaited_once_with(
        273,
        owner_user_id=21,
    )


@pytest.mark.asyncio
async def test_get_status_denies_foreign_upload_without_invoice(
    document_service: DocumentService,
):
    upload_row = MagicMock()
    upload_row.id = 141
    upload_row.uploaded_by = 1

    document_service._upload_repo.get = AsyncMock(return_value=upload_row)
    document_service._invoice_repo.get_id_by_source_file = AsyncMock(return_value=None)

    with pytest.raises(HTTPException) as exc:
        await document_service.get_status(141, _user(21))

    assert exc.value.status_code == 404
