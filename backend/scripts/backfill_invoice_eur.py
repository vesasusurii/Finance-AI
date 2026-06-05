"""Backfill non-EUR invoices: preserve originals and convert amount/debt to EUR.

Usage (from backend/):
  python -m scripts.backfill_invoice_eur
"""

from __future__ import annotations

import asyncio
from decimal import Decimal

from sqlalchemy import select

from db.pool import async_session
from models.invoice import Invoice
from utils.invoice_currency import normalize_invoice_amounts
from services.currency_conversion_service import (
    CurrencyConversionError,
    normalize_currency_code,
)


async def main() -> None:
    converted = 0
    skipped = 0
    failed: list[int] = []

    async with async_session() as session:
        rows = (
            await session.execute(
                select(Invoice).where(
                    Invoice.original_amount.isnot(None),
                    Invoice.exchange_rate.is_(None),
                )
            )
        ).scalars().all()

        for row in rows:
            currency = normalize_currency_code(row.original_currency or row.currency)
            if currency == "EUR":
                row.exchange_rate = Decimal("1")
                row.exchange_rate_date = row.invoice_date or row.created_at.date()
                skipped += 1
                continue
            try:
                await normalize_invoice_amounts(
                    row,
                    original_amount=row.original_amount,
                    original_debt=row.debt,
                    original_currency=currency,
                )
                converted += 1
            except CurrencyConversionError as exc:
                failed.append(row.id)
                print(f"  invoice {row.id} ({currency}): {exc}")

        await session.commit()

    print(f"Converted: {converted}, EUR skipped: {skipped}, failed: {len(failed)}")
    if failed:
        print("Failed invoice IDs:", failed)


if __name__ == "__main__":
    asyncio.run(main())
