"""Re-enqueue OCR for invoice uploads stuck in queued/processing without an invoice row."""

from __future__ import annotations

import asyncio
import os
import sys

import httpx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from openai import AsyncOpenAI

from config import settings
from services.upload_recovery import recover_stuck_invoice_uploads


async def main() -> int:
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    client = (
        AsyncOpenAI(api_key=settings.openai_api_key)
        if settings.openai_api_key
        else None
    )
    async with httpx.AsyncClient(timeout=30.0) as http_client:
        enqueued = await recover_stuck_invoice_uploads(
            client,
            limit=limit,
            http_client=http_client,
        )
    print(f"Enqueued {enqueued} stuck invoice upload(s)")
    return 0 if enqueued >= 0 else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
