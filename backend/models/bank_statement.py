from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class BankStatement(Base):
    __tablename__ = "bank_statements"
    __table_args__ = (
        Index("ix_bank_statements_processing_status", "processing_status"),
        Index(
            "ix_bank_statements_user_statement_date",
            "uploaded_by",
            "statement_date",
            unique=True,
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    statement_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    source_file_id: Mapped[int] = mapped_column(
        ForeignKey("uploaded_files.id"),
        nullable=False,
    )
    uploaded_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    row_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    processing_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        server_default="pending",
    )
