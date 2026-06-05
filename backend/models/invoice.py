from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base


class Invoice(Base):
    __tablename__ = "invoices"
    __table_args__ = (
        Index("ix_invoices_invoice_number", "invoice_number"),
        Index("ix_invoices_invoice_number_normalized", "invoice_number_normalized"),
        Index("ix_invoices_review_status", "review_status"),
        Index("ix_invoices_match_status", "match_status"),
        Index("ix_invoices_paid_at_date", "paid_at_date"),
        Index("ix_invoices_uploaded_by", "uploaded_by"),
        Index("ix_invoices_source_file_id", "source_file_id"),
        Index(
            "ix_invoices_owner_review_created",
            "uploaded_by",
            "review_status",
            "created_at",
        ),
        Index(
            "ix_invoices_owner_match_date",
            "uploaded_by",
            "match_status",
            "invoice_date",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    invoice_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    name_of_company: Mapped[str | None] = mapped_column(String(500), nullable=True)
    address_of_company: Mapped[str | None] = mapped_column(Text, nullable=True)
    invoice_number: Mapped[str | None] = mapped_column(String(200), nullable=True)
    invoice_number_normalized: Mapped[str | None] = mapped_column(String(200), nullable=True)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    debt: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(10), nullable=True)
    original_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    original_currency: Mapped[str | None] = mapped_column(String(10), nullable=True)
    exchange_rate: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    exchange_rate_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    account_details: Mapped[str | None] = mapped_column(Text, nullable=True)
    internal_note_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    client_employee_related: Mapped[str | None] = mapped_column(String(500), nullable=True)
    paid_at_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    paid_by: Mapped[str | None] = mapped_column(String(300), nullable=True)
    fixed_status: Mapped[str | None] = mapped_column(String(100), nullable=True)
    category: Mapped[str | None] = mapped_column(String(200), nullable=True)
    extraction_confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    field_confidences: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    review_reasons: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    review_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        server_default="pending",
    )
    match_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        server_default="unmatched",
    )
    source_file_id: Mapped[int | None] = mapped_column(
        ForeignKey("uploaded_files.id"),
        nullable=True,
    )
    uploaded_by: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
    )
    source_file: Mapped["UploadedFile | None"] = relationship(
        "UploadedFile",
        foreign_keys=[source_file_id],
        lazy="joined",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
