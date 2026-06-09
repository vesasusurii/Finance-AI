"""
Seed finance and admin users — run inside backend container:
  docker compose exec backend python scripts/seed_users.py
"""
 
import asyncio
import os
import sys
from datetime import datetime, timezone
 
import bcrypt
 
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
 
from sqlalchemy import select
 
from core.roles import ROLE_ADMIN, ROLE_FINANCE
from db.pool import async_session, engine
from models.user import User
 
DEFAULT_USERS = (
    ("lum.meta@boreksolutions.de", "changeme", ROLE_ADMIN),
    ("vesa.susuri@boreksolutions.de", "changeme", ROLE_ADMIN),
    ("lummeta25@gmail.com", "changeme", ROLE_FINANCE),
)
 
 
async def upsert_user(session, email: str, password: str, role: str) -> None:
    email = email.lower()
    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    result = await session.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user:
        user.password_hash = hashed
        user.is_active = True
        user.role = role
        user.email_verified_at = user.email_verified_at or datetime.now(timezone.utc)
        user.must_change_password = True
        user.email_verification_code_hash = None
        user.email_verification_expires_at = None
        print(f"Updated user: {email} ({role})")
    else:
        session.add(
            User(
                email=email,
                password_hash=hashed,
                role=role,
                is_active=True,
                email_verified_at=datetime.now(timezone.utc),
                must_change_password=True,
            )
        )
        print(f"Created user: {email} ({role})")
 
 
async def main() -> None:
    async with async_session() as session:
        for email, password, role in DEFAULT_USERS:
            await upsert_user(session, email, password, role)
        await session.commit()
 
    await engine.dispose()
    print("Done. Store passwords in the team password manager — not in Git.")
 
 
if __name__ == "__main__":
    asyncio.run(main())