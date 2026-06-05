"""Normalize invoice monetary fields to EUR while preserving original currency."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from services.currency_conversion_service import (
    CurrencyConversionError,
    CurrencyConversionService,
    normalize_currency_code,
)

if TYPE_CHECKING:
    from models.invoice import Invoice


def conversion_date_for_invoice(
    invoice_date: date | None,
    created_at: datetime | None,
) -> date:
    if invoice_date is not None:
        return invoice_date
    if created_at is not None:
        return created_at.date()
    return date.today()


async def normalize_invoice_amounts(
    row: Invoice,
    *,
    original_amount: Decimal | None,
    original_debt: Decimal | None | object = ...,
    original_currency: str | None,
    on_date: date | None = None,
    converter: CurrencyConversionService | None = None,
) -> None:
    """Write EUR amount/debt on row and preserve original currency fields."""
    fx = converter or CurrencyConversionService()
    rate_date = on_date or conversion_date_for_invoice(row.invoice_date, row.created_at)
    currency = normalize_currency_code(original_currency)

    if original_amount is not None:
        row.original_amount = original_amount
    row.original_currency = currency

    amount_src = original_amount if original_amount is not None else row.original_amount
    if amount_src is None:
        return

    if original_debt is not ...:
        debt_src = original_debt
    elif (
        row.original_amount is not None
        and row.amount is not None
        and row.debt is not None
        and row.exchange_rate is not None
        and row.exchange_rate > 0
        and currency != "EUR"
    ):
        debt_src = (row.debt / row.exchange_rate).quantize(Decimal("0.01"))
    else:
        debt_src = row.debt

    if currency == "EUR":
        row.amount = amount_src
        if original_debt is not ...:
            row.debt = debt_src
        elif original_amount is not None and row.debt is not None and row.amount is not None:
            if row.original_amount == row.amount or row.original_amount is None:
                row.debt = amount_src
        row.currency = "EUR"
        row.exchange_rate = Decimal("1")
        row.exchange_rate_date = rate_date
        return

    eur_amount, rate, used_date = await fx.convert_to_eur(amount_src, currency, rate_date)
    row.amount = eur_amount
    row.currency = "EUR"
    row.exchange_rate = rate
    row.exchange_rate_date = used_date

    if debt_src is not None:
        if debt_src == amount_src:
            row.debt = eur_amount
        else:
            eur_debt, _, _ = await fx.convert_to_eur(debt_src, currency, rate_date)
            row.debt = eur_debt
    elif original_amount is not None:
        row.debt = eur_amount


async def normalize_from_extraction(
    row: Invoice,
    *,
    amount: Decimal | None,
    debt: Decimal | None,
    currency: str | None,
    converter: CurrencyConversionService | None = None,
) -> None:
    await normalize_invoice_amounts(
        row,
        original_amount=amount,
        original_debt=debt,
        original_currency=currency,
        converter=converter,
    )


def monetary_fields_changed(payload: dict) -> bool:
    keys = {"amount", "debt", "currency", "original_amount", "original_currency"}
    return bool(keys.intersection(payload))


__all__ = [
    "CurrencyConversionError",
    "conversion_date_for_invoice",
    "monetary_fields_changed",
    "normalize_from_extraction",
    "normalize_invoice_amounts",
]
