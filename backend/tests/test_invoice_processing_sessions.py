from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from schemas.invoice import ExtractionResult, UploadItemResponse
from services.invoice_extraction_service import InvoiceExtractionService


def _service(session: MagicMock) -> InvoiceExtractionService:
    return InvoiceExtractionService(
        upload_repo=MagicMock(_session=session),
        invoice_repo=MagicMock(_session=session),
        invoice_access_repo=MagicMock(_session=session),
        audit_repo=MagicMock(_session=session),
        ai_validation=MagicMock(),
        openai_client=MagicMock(),
    )


@pytest.mark.asyncio
async def test_complete_upload_releases_db_connection_before_extraction():
    call_order: list[str] = []
    session = MagicMock()
    session.close = AsyncMock(side_effect=lambda: call_order.append("close"))
    service = _service(session)
    service._upload_repo.get = AsyncMock(
        return_value=MagicMock(
            id=103,
            original_filename="invoice.pdf",
            mime_type="application/pdf",
            storage_path="users/1/invoice.pdf",
        )
    )
    service._upload_repo.commit = AsyncMock()
    service._upload_repo.update_status = AsyncMock()
    service._invoice_repo.create = AsyncMock(
        return_value=MagicMock(id=164)
    )
    service._audit_repo.log = AsyncMock()

    extract_result = (
        ExtractionResult(confidence_score=0.95),
        "gpt-test",
        {"extraction_mode": "text_llm"},
    )

    async def track_extract(*_args, **_kwargs):
        call_order.append("extract")
        return extract_result

    with (
        patch(
            "services.invoice_extraction_service.get_ocr_progress",
            return_value={},
        ),
        patch.object(service, "_extract", new=AsyncMock(side_effect=track_extract)),
        patch.object(
            service._ai_validation,
            "sanitize_and_validate",
            side_effect=lambda value: value,
        ),
        patch.object(
            service._ai_validation,
            "validate_required_fields",
            return_value=[],
        ),
        patch.object(
            service._ai_validation,
            "determine_review_status",
            return_value="pending_review",
        ),
    ):
        result = await service.complete_upload(
            103,
            24,
            content=b"%PDF-1.4",
        )

    assert isinstance(result, UploadItemResponse)
    assert result.invoice_id == 164
    assert call_order.index("close") < call_order.index("extract")
