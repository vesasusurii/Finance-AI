"""Tests for Frankfurter-based currency conversion."""

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from services.currency_conversion_service import (
    CurrencyConversionError,
    CurrencyConversionService,
)


@pytest.mark.asyncio
async def test_convert_eur_passthrough():
    svc = CurrencyConversionService()
    amount, rate, rate_date = await svc.convert_to_eur(
        Decimal("100.00"), "EUR", date(2026, 1, 15)
    )
    assert amount == Decimal("100.00")
    assert rate == Decimal("1")
    assert rate_date == date(2026, 1, 15)


@pytest.mark.asyncio
async def test_convert_usd_to_eur_success():
    svc = CurrencyConversionService()
    mock_response = httpx.Response(
        200,
        json={
            "amount": 30.11,
            "base": "USD",
            "date": "2026-01-15",
            "rates": {"EUR": 26.19},
        },
        request=httpx.Request("GET", "https://api.frankfurter.dev/v1/2026-01-15"),
    )

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_response
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None

    with patch(
        "services.currency_conversion_service.httpx.AsyncClient",
        return_value=mock_client,
    ):
        amount, rate, rate_date = await svc.convert_to_eur(
            Decimal("30.11"), "USD", date(2026, 1, 15)
        )

    assert amount == Decimal("26.19")
    assert rate == (Decimal("26.19") / Decimal("30.11")).quantize(Decimal("0.000001"))
    assert rate_date == date(2026, 1, 15)


@pytest.mark.asyncio
async def test_convert_api_failure_raises():
    svc = CurrencyConversionService()

    mock_client = AsyncMock()
    mock_client.get.side_effect = httpx.ConnectError("network down")
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None

    with patch(
        "services.currency_conversion_service.httpx.AsyncClient",
        return_value=mock_client,
    ):
        with pytest.raises(CurrencyConversionError):
            await svc.convert_to_eur(
                Decimal("10.00"), "USD", date(2026, 1, 15)
            )
