"""
Clear invoices, uploads, bank data, matches, and review tasks — keeps users.

Run inside backend container:
  docker compose exec backend python scripts/clear_uploaded_data.py
"""
from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text

from db.pool import async_session, engine

TABLES_IN_DELETE_ORDER = (
    "invoice_payment_matches",
    "review_tasks",
    "invoice_access",
    "invoices",
    "bank_transactions",
    "bank_statements",
    "uploaded_files",
    "audit_logs",
)

SEQUENCES = (
    "invoice_payment_matches_id_seq",
    "review_tasks_id_seq",
    "invoice_access_id_seq",
    "invoices_id_seq",
    "bank_transactions_id_seq",
    "bank_statements_id_seq",
    "uploaded_files_id_seq",
    "audit_logs_id_seq",
)


async def main() -> None:
    async with async_session() as session:
        for table in TABLES_IN_DELETE_ORDER:
            result = await session.execute(text(f"DELETE FROM {table}"))
            print(f"Deleted {result.rowcount} rows from {table}")

        for seq in SEQUENCES:
            await session.execute(text(f"ALTER SEQUENCE {seq} RESTART WITH 1"))

        await session.commit()

    await engine.dispose()
    print("Done. User accounts were kept. Uploaded files on disk were not removed.")


if __name__ == "__main__":
    asyncio.run(main())
