from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class InvoiceAccess(Base):
    """Grants a user visibility to an invoice uploaded by someone else."""

    __tablename__ = "invoice_access"
    __table_args__ = (
        UniqueConstraint("invoice_id", "user_id", name="uq_invoice_access_invoice_user"),
        Index("ix_invoice_access_user_id", "user_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    invoice_id: Mapped[int] = mapped_column(
        ForeignKey("invoices.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    grant_reason: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        server_default="duplicate_upload",
    )
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
