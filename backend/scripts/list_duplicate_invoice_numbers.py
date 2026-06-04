"""List duplicate invoice numbers per owner (for data clean-up before unique index).

  docker compose exec backend python scripts/list_duplicate_invoice_numbers.py
"""
from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text

from db.pool import async_session


SQL = """
SELECT
    uploaded_by,
    invoice_number_normalized,
    COUNT(*) AS row_count,
    array_agg(id ORDER BY id) AS invoice_ids
FROM invoices
WHERE invoice_number_normalized IS NOT NULL
GROUP BY uploaded_by, invoice_number_normalized
HAVING COUNT(*) > 1
ORDER BY row_count DESC, invoice_number_normalized
"""


async def main() -> None:
    async with async_session() as session:
        result = await session.execute(text(SQL))
        rows = result.all()
        if not rows:
            print("No duplicate invoice_number_normalized values per owner.")
            return
        print(f"Found {len(rows)} duplicate group(s):\n")
        for uploaded_by, normalized, count, ids in rows:
            print(
                f"  owner={uploaded_by} number={normalized!r} "
                f"count={count} invoice_ids={list(ids)}"
            )


if __name__ == "__main__":
    asyncio.run(main())
