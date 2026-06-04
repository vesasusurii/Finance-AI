"""Backfill email ingest metadata on uploaded_files from audit_logs.

Run when migration q4r5s6t7u8v9 was skipped or Supabase was patched manually:

  docker compose exec backend python scripts/backfill_email_ingest.py
"""
from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text

from db.pool import async_session


BACKFILL_SQL = """
UPDATE uploaded_files uf
SET
    upload_source = COALESCE(al.after->>'source', 'outlook_email'),
    ingest_sender_email = NULLIF(al.after->>'sender_email', ''),
    ingest_sender_name = NULLIF(al.after->>'sender_name', ''),
    ingest_email_subject = NULLIF(al.after->>'email_subject', ''),
    ingest_message_id = NULLIF(al.after->>'message_id', '')
FROM audit_logs al
WHERE al.action = 'email_ingest'
  AND al.entity_type = 'uploaded_file'
  AND al.entity_id = uf.id
  AND al.after IS NOT NULL
"""


async def main() -> None:
    async with async_session() as session:
        result = await session.execute(text(BACKFILL_SQL))
        await session.commit()
        print(f"Backfilled {result.rowcount} uploaded_files row(s) from audit_logs.")


if __name__ == "__main__":
    asyncio.run(main())
