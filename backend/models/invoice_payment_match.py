from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class InvoicePaymentMatch(Base):
    __tablename__ = "invoice_payment_matches"
    __table_args__ = (
        UniqueConstraint(
            "invoice_id",
            "bank_transaction_id",
            name="uq_matches_invoice_bank",
        ),
        Index("ix_matches_invoice_id", "invoice_id"),
        Index("ix_matches_bank_transaction_id", "bank_transaction_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    invoice_id: Mapped[int] = mapped_column(
        ForeignKey("invoices.id", ondelete="CASCADE"),
        nullable=False,
    )
    bank_transaction_id: Mapped[int] = mapped_column(
        ForeignKey("bank_transactions.id", ondelete="CASCADE"),
        nullable=False,
    )
    invoice_number: Mapped[str] = mapped_column(String(200), nullable=False)
    match_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        server_default="invoice_number",
    )
    match_confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    paid_at_date: Mapped[date] = mapped_column(Date, nullable=False)
    paid_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
