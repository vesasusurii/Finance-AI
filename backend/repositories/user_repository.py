from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.user import User


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_by_email(self, email: str) -> User | None:
        result = await self._session.execute(
            select(User).where(User.email == email.lower())
        )
        return result.scalar_one_or_none()

    async def get(self, user_id: int) -> User | None:
        return await self._session.get(User, user_id)

    async def list_all(self) -> list[User]:
        result = await self._session.execute(
            select(User).order_by(User.created_at.desc())
        )
        return list(result.scalars().all())

    async def create(
        self,
        *,
        email: str,
        password_hash: str,
        role: str,
        must_change_password: bool = True,
        email_verification_code_hash: str | None = None,
        email_verification_expires_at: datetime | None = None,
    ) -> User:
        user = User(
            email=email.lower(),
            password_hash=password_hash,
            role=role,
            is_active=True,
            email_verified_at=None,
            must_change_password=must_change_password,
            email_verification_code_hash=email_verification_code_hash,
            email_verification_expires_at=email_verification_expires_at,
        )
        self._session.add(user)
        await self._session.flush()
        await self._session.refresh(user)
        return user

    async def mark_email_verified(self, user: User) -> User:
        user.email_verified_at = datetime.now(timezone.utc)
        user.email_verification_code_hash = None
        user.email_verification_expires_at = None
        await self._session.flush()
        await self._session.refresh(user)
        return user

    async def update_password(self, user: User, password_hash: str) -> User:
        user.password_hash = password_hash
        user.must_change_password = False
        await self._session.flush()
        await self._session.refresh(user)
        return user

    async def set_email_verification_code(
        self,
        user: User,
        *,
        code_hash: str,
        expires_at: datetime,
    ) -> User:
        user.email_verified_at = None
        user.email_verification_code_hash = code_hash
        user.email_verification_expires_at = expires_at
        await self._session.flush()
        await self._session.refresh(user)
        return user

    async def delete(self, user: User) -> None:
        await self._session.delete(user)
        await self._session.flush()
