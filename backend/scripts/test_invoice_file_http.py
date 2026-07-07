"""Smoke-test GET /api/invoices/{id}/file headers and PDF magic bytes."""

from __future__ import annotations

import asyncio

import httpx
from sqlalchemy import select

from db.pool import async_session
from models.user import User
from services.jwt_service import create_access_token


async def main() -> None:
    async with async_session() as session:
        user = (await session.execute(select(User).limit(1))).scalar_one()
    token = create_access_token(
        user_id=user.id,
        email=user.email,
        role=user.role,
        token_version=user.token_version,
    )
    async with httpx.AsyncClient(
        base_url="http://127.0.0.1:8000",
        cookies={"access_token": token},
        timeout=120.0,
    ) as client:
        for invoice_id in (35, 36, 37, 39, 40):
            resp = await client.get(f"/api/invoices/{invoice_id}/file")
            ct = resp.headers.get("content-type")
            cd = resp.headers.get("content-disposition")
            data = resp.content
            is_pdf = len(data) >= 4 and data[:4] == b"%PDF"
            print(
                invoice_id,
                resp.status_code,
                ct,
                cd,
                len(data),
                is_pdf,
            )


if __name__ == "__main__":
    asyncio.run(main())
