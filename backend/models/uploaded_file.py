from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class UploadedFile(Base):
    __tablename__ = "uploaded_files"
    __table_args__ = (
        Index("ix_uploaded_files_kind_status", "file_kind", "processing_status"),
        Index("ix_uploaded_files_uploaded_by", "uploaded_by"),
        Index(
            "ix_uploaded_files_user_kind_status",
            "uploaded_by",
            "file_kind",
            "processing_status",
        ),
        Index(
            "ix_uploaded_files_status_uploaded_at",
            "processing_status",
            "uploaded_at",
        ),
        Index("ix_uploaded_files_upload_source", "upload_source"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    original_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    mime_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    file_size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    content_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    file_kind: Mapped[str] = mapped_column(String(50), nullable=False)
    uploaded_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    processing_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        server_default="pending",
    )
    upload_source: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        server_default="portal",
    )
    ingest_sender_email: Mapped[str | None] = mapped_column(
        String(320),
        nullable=True,
    )
    ingest_sender_name: Mapped[str | None] = mapped_column(
        String(300),
        nullable=True,
    )
    ingest_email_subject: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )
    ingest_message_id: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )
