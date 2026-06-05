"""Invoice amount normalization to EUR."""

from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from models.invoice import Invoice
from utils.invoice_currency import normalize_from_extraction, normalize_invoice_amounts


class _FakeConverter:
    async def convert_to_eur(self, amount, from_currency, on_date):
        assert from_currency == "USD"
        eur = (amount * Decimal("0.87")).quantize(Decimal("0.01"))
        return eur, Decimal("0.870000"), on_date


@pytest.mark.asyncio
async def test_normalize_from_extraction_usd():
    row = Invoice(
        uploaded_by=1,
        review_status="pending",
        match_status="unmatched",
        created_at=datetime.now(timezone.utc),
    )
    await normalize_from_extraction(
        row,
        amount=Decimal("30.11"),
        debt=Decimal("30.11"),
        currency="USD",
        converter=_FakeConverter(),
    )
    assert row.original_amount == Decimal("30.11")
    assert row.original_currency == "USD"
    assert row.amount == Decimal("26.20")
    assert row.debt == Decimal("26.20")
    assert row.currency == "EUR"
    assert row.exchange_rate == Decimal("0.870000")


@pytest.mark.asyncio
async def test_normalize_eur_invoice():
    row = Invoice(
        uploaded_by=1,
        review_status="pending",
        match_status="unmatched",
        invoice_date=date(2026, 2, 1),
        created_at=datetime.now(timezone.utc),
    )
    await normalize_invoice_amounts(
        row,
        original_amount=Decimal("100.00"),
        original_debt=Decimal("50.00"),
        original_currency="EUR",
    )
    assert row.amount == Decimal("100.00")
    assert row.debt == Decimal("50.00")
    assert row.original_amount == Decimal("100.00")
    assert row.original_currency == "EUR"
    assert row.exchange_rate == Decimal("1")
