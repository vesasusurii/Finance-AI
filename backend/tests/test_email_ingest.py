"""Email ingest API key auth and response mapping."""

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from api.controllers.invoice_controller import _email_ingest_response
from api.dependencies_email_ingest import verify_email_ingest_user
from schemas.invoice import InvoiceResponse, UploadItemResponse


def test_email_ingest_response_queued():
    item = UploadItemResponse(
        upload_id=42,
        original_filename="inv.pdf",
        processing_status="saved",
    )
    out = _email_ingest_response(
        item,
        invoice=None,
        message_id="msg-1",
        sender_email="a@b.com",
        attachment_name="inv.pdf",
    )
    assert out.status == "queued"
    assert out.upload_id == 42
    assert out.duplicate is False


def test_email_ingest_response_duplicate_linked():
    item = UploadItemResponse(
        upload_id=0,
        original_filename="inv.pdf",
        processing_status="linked",
        invoice_id=7,
        message="Already in system",
    )
    inv = InvoiceResponse(
        id=7,
        invoice_date=None,
        name_of_company="ACME",
        address_of_company=None,
        invoice_number="INV-1",
        amount=Decimal("10.00"),
        debt=None,
        currency="EUR",
        original_amount=Decimal("10.00"),
        original_currency="EUR",
        exchange_rate=Decimal("1"),
        exchange_rate_date=None,
        account_details=None,
        internal_note_description=None,
        client_employee_related=None,
        paid_at_date=None,
        paid_by=None,
        fixed_status=None,
        category=None,
        extraction_confidence=Decimal("0.9"),
        field_confidences=None,
        review_status="approved",
        match_status="unmatched",
        uploaded_by=1,
        source_file_id=1,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    out = _email_ingest_response(
        item,
        invoice=inv,
        message_id="msg-1",
        sender_email=None,
        attachment_name="inv.pdf",
    )
    assert out.duplicate is True
    assert out.supplier == "ACME"
    assert out.amount == 10.0


def test_verify_email_ingest_user_rejects_bad_key(monkeypatch):
    import asyncio

    from config import settings

    monkeypatch.setattr(settings, "email_ingest_api_key", "secret-key")
    monkeypatch.setattr(settings, "email_ingest_user_email", "finance@borek.com")

    repo = MagicMock()
    repo.find_by_email = AsyncMock()
    audit = MagicMock()
    audit.log = AsyncMock()

    async def _run():
        with pytest.raises(HTTPException) as exc:
            await verify_email_ingest_user(
                x_email_ingest_key="wrong",
                user_repo=repo,
                audit_repo=audit,
            )
        assert exc.value.status_code == 401
        audit.log.assert_awaited_once()

    asyncio.run(_run())
