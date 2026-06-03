from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Index, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class BankTransaction(Base):
    __tablename__ = "bank_transactions"
    __table_args__ = (
        Index("ix_bank_transactions_statement_id", "bank_statement_id"),
        Index("ix_bank_transactions_reconciliation_status", "reconciliation_status"),
        Index(
            "ix_bank_transactions_statement_status",
            "bank_statement_id",
            "reconciliation_status",
        ),
        Index(
            "ix_bank_transactions_status_date",
            "reconciliation_status",
            "transaction_date",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    bank_statement_id: Mapped[int] = mapped_column(
        ForeignKey("bank_statements.id", ondelete="CASCADE"),
        nullable=False,
    )
    transaction_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    debited_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    credited_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    transaction_type: Mapped[str | None] = mapped_column(String(200), nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    detected_invoice_numbers: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        server_default="[]",
    )
    reconciliation_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        server_default="pending",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
