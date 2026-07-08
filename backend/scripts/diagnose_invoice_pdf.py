"""Compare stored invoice PDF bytes for diagnostics (working vs failing previews).

Usage (from backend container or local venv with deps):
  python scripts/diagnose_invoice_pdf.py 35 40

Prints storage path, size, SHA-256, first/last 32 bytes, and integrity flags.
"""

from __future__ import annotations

import asyncio
import sys

from sqlalchemy import select

from db.pool import async_session
from models.invoice import Invoice
from services.invoice_file_service import _load_invoice_file_meta
from utils.file_storage import resolve_upload_bytes
from utils.pdf_bytes import format_pdf_report, inspect_pdf_bytes


async def diagnose(invoice_id: int) -> None:
    meta = await _load_invoice_file_meta(invoice_id, owner_user_id=None)
    data = await resolve_upload_bytes(meta.storage_path, meta.original_filename)
    if data is None:
        print(invoice_id, "MISSING", meta.storage_path)
        return

    report = inspect_pdf_bytes(data)
    print("=" * 72)
    print(f"invoice_id={invoice_id}")
    print(f"storage_path={meta.storage_path}")
    print(f"filename={meta.original_filename}")
    print(f"db_file_size={meta.file_size}")
    print(format_pdf_report(report))
    print(f"first32={data[:32].hex()}")
    print(f"last32={data[-32:].hex() if data else ''}")
    if report.leading_prefix_len:
        print(f"leading_prefix={data[:report.leading_prefix_len]!r}")


async def main(argv: list[str]) -> None:
    if len(argv) < 2:
        async with async_session() as session:
            ids = (
                await session.execute(
                    select(Invoice.id).order_by(Invoice.id.desc()).limit(5)
                )
            ).scalars().all()
        print("No invoice ids passed; diagnosing latest:", list(ids))
        for invoice_id in ids:
            await diagnose(int(invoice_id))
        return

    for raw in argv[1:]:
        await diagnose(int(raw))


if __name__ == "__main__":
    asyncio.run(main(sys.argv))
