"""Convert foreign currencies to EUR using the Frankfurter API (ECB rates)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP

import httpx

from config import settings
from core.debug_logger import get_logger

logger = get_logger(__name__)

# Frankfurter moved from api.frankfurter.app (301) to api.frankfurter.dev/v1
FRANKFURTER_BASE = "https://api.frankfurter.dev/v1"
_TWOPLACES = Decimal("0.01")
_SIXPLACES = Decimal("0.000001")


class CurrencyConversionError(Exception):
    """Raised when a currency cannot be converted to EUR."""


def _quantize_money(value: Decimal) -> Decimal:
    return value.quantize(_TWOPLACES, rounding=ROUND_HALF_UP)


def _quantize_rate(value: Decimal) -> Decimal:
    return value.quantize(_SIXPLACES, rounding=ROUND_HALF_UP)


def normalize_currency_code(currency: str | None) -> str:
    text = (currency or "EUR").strip().upper()
    return text or "EUR"


class CurrencyConversionService:
    async def convert_to_eur(
        self,
        amount: Decimal,
        from_currency: str,
        on_date: date,
    ) -> tuple[Decimal, Decimal, date]:
        """Return (eur_amount, rate_per_unit, rate_date).

        rate_per_unit is EUR received for 1 unit of from_currency.
        """
        code = normalize_currency_code(from_currency)
        if code == "EUR":
            return _quantize_money(amount), Decimal("1"), on_date

        if not settings.fx_conversion_enabled:
            logger.warning(
                "FX conversion disabled; treating %s as EUR passthrough for amount=%s",
                code,
                amount,
            )
            return _quantize_money(amount), Decimal("1"), on_date

        if amount == 0:
            return Decimal("0.00"), Decimal("0"), on_date

        url = f"{FRANKFURTER_BASE}/{on_date.isoformat()}"
        params = {
            "amount": str(amount),
            "from": code,
            "to": "EUR",
        }

        try:
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise CurrencyConversionError(
                f"Could not convert {amount} {code} to EUR on {on_date}: {exc}"
            ) from exc

        rates = payload.get("rates") or {}
        eur_value = rates.get("EUR")
        if eur_value is None:
            raise CurrencyConversionError(
                f"No EUR rate returned for {code} on {on_date}"
            )

        eur_amount = _quantize_money(
            Decimal(str(eur_value)).quantize(_TWOPLACES, rounding=ROUND_HALF_UP)
        )
        rate_date_raw = payload.get("date")
        rate_date = (
            date.fromisoformat(rate_date_raw)
            if isinstance(rate_date_raw, str)
            else on_date
        )
        rate = _quantize_rate(eur_amount / amount)
        return eur_amount, rate, rate_date
