from datetime import datetime, timezone

from sqlalchemy import delete, func, select, update

from core.token_version_cache import cache_token_version, invalidate_token_version_cache
from sqlalchemy.ext.asyncio import AsyncSession

from models.audit_log import AuditLog
from models.bank_statement import BankStatement
from models.bank_transaction import BankTransaction
from models.invoice import Invoice
from models.invoice_payment_match import InvoicePaymentMatch
from models.review_task import ReviewTask
from models.uploaded_file import UploadedFile
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

    async def get_token_version(self, user_id: int) -> int | None:
        user = await self.get(user_id)
        if user is None or not user.is_active:
            return None
        return int(user.token_version)

    async def bump_token_version(self, user_id: int) -> int | None:
        user = await self.get(user_id)
        if user is None:
            return None
        user.token_version = int(user.token_version or 1) + 1
        await self._session.flush()
        invalidate_token_version_cache(user_id)
        cache_token_version(user_id, user.token_version)
        return user.token_version

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

    async def reset_password(self, user: User, password_hash: str) -> User:
        user.password_hash = password_hash
        user.must_change_password = True
        await self._session.flush()
        await self._session.refresh(user)
        return user

    async def update_role(self, user: User, role: str) -> User:
        user.role = role
        await self._session.flush()
        await self._session.refresh(user)
        return user

    async def count_admins(self, *, exclude_user_id: int | None = None) -> int:
        q = select(func.count()).select_from(User).where(
            User.role == "admin",
            User.is_active.is_(True),
        )
        if exclude_user_id is not None:
            q = q.where(User.id != exclude_user_id)
        return int((await self._session.execute(q)).scalar_one())

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
        await self.delete_user_and_related_data(user.id)

    async def delete_user_and_related_data(self, user_id: int) -> None:
        """Remove a user and all rows that block FK deletion."""
        user = await self._session.get(User, user_id)
        if user is None:
            return

        invoice_ids = select(Invoice.id).where(Invoice.uploaded_by == user_id)
        statement_ids = select(BankStatement.id).where(
            BankStatement.uploaded_by == user_id
        )
        transaction_ids = select(BankTransaction.id).where(
            BankTransaction.bank_statement_id.in_(statement_ids)
        )

        await self._session.execute(
            delete(InvoicePaymentMatch).where(
                InvoicePaymentMatch.invoice_id.in_(invoice_ids)
            )
        )
        await self._session.execute(
            delete(InvoicePaymentMatch).where(
                InvoicePaymentMatch.bank_transaction_id.in_(transaction_ids)
            )
        )
        await self._session.execute(
            delete(ReviewTask).where(ReviewTask.invoice_id.in_(invoice_ids))
        )
        await self._session.execute(
            delete(ReviewTask).where(
                ReviewTask.bank_transaction_id.in_(transaction_ids)
            )
        )
        await self._session.execute(
            delete(Invoice).where(Invoice.uploaded_by == user_id)
        )
        await self._session.execute(
            delete(BankStatement).where(BankStatement.uploaded_by == user_id)
        )
        await self._session.execute(
            delete(UploadedFile).where(UploadedFile.uploaded_by == user_id)
        )
        await self._session.execute(
            update(AuditLog)
            .where(AuditLog.user_id == user_id)
            .values(user_id=None)
        )
        await self._session.execute(
            update(ReviewTask)
            .where(ReviewTask.assigned_to == user_id)
            .values(assigned_to=None)
        )

        await self._session.delete(user)
        await self._session.flush()
