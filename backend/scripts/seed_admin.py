"""
One-time admin seed — run inside backend container:
  docker compose exec backend python scripts/seed_admin.py
"""

import asyncio
import os
import sys

import bcrypt

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select

from config import settings
from db.pool import async_session, engine
from models.user import User

DEFAULT_EMAIL = "finance@borek.com"
DEFAULT_PASSWORD = "changeme"


async def main() -> None:
    email = os.getenv("SEED_ADMIN_EMAIL", DEFAULT_EMAIL).lower()
    password = os.getenv("SEED_ADMIN_PASSWORD", DEFAULT_PASSWORD)
    role = os.getenv("SEED_ADMIN_ROLE", "finance")

    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    async with async_session() as session:
        existing = await session.execute(select(User).where(User.email == email))
        user = existing.scalar_one_or_none()
        if user:
            user.password_hash = hashed
            user.is_active = True
            user.role = role
            print(f"Updated user: {email}")
        else:
            session.add(
                User(
                    email=email,
                    password_hash=hashed,
                    role=role,
                    is_active=True,
                )
            )
            print(f"Created user: {email}")
        await session.commit()

    await engine.dispose()
    print("Done. Store password in team password manager — not in Git.")


if __name__ == "__main__":
    asyncio.run(main())
