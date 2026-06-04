"""add email ingest metadata columns on uploaded_files

Revision ID: q4r5s6t7u8v9
Revises: p3q4r5s6t7u8
Create Date: 2026-06-03 18:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "q4r5s6t7u8v9"
down_revision: Union[str, Sequence[str], None] = "p3q4r5s6t7u8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {col["name"] for col in inspector.get_columns("uploaded_files")}

    if "ingest_sender_email" not in columns:
        op.add_column(
            "uploaded_files",
            sa.Column("ingest_sender_email", sa.String(length=320), nullable=True),
        )
    if "ingest_sender_name" not in columns:
        op.add_column(
            "uploaded_files",
            sa.Column("ingest_sender_name", sa.String(length=300), nullable=True),
        )
    if "ingest_email_subject" not in columns:
        op.add_column(
            "uploaded_files",
            sa.Column("ingest_email_subject", sa.String(length=500), nullable=True),
        )
    if "ingest_message_id" not in columns:
        op.add_column(
            "uploaded_files",
            sa.Column("ingest_message_id", sa.String(length=500), nullable=True),
        )

    # Backfill upload_source + ingest metadata from email_ingest audit rows.
    op.execute(
        """
        UPDATE uploaded_files uf
        SET
            upload_source = COALESCE(al.after->>'source', 'outlook_email'),
            ingest_sender_email = NULLIF(al.after->>'sender_email', ''),
            ingest_sender_name = NULLIF(al.after->>'sender_name', ''),
            ingest_email_subject = NULLIF(al.after->>'email_subject', ''),
            ingest_message_id = NULLIF(al.after->>'message_id', '')
        FROM audit_logs al
        WHERE al.action = 'email_ingest'
          AND al.entity_type = 'uploaded_file'
          AND al.entity_id = uf.id
          AND al.after IS NOT NULL
        """
    )


def downgrade() -> None:
    op.drop_column("uploaded_files", "ingest_message_id")
    op.drop_column("uploaded_files", "ingest_email_subject")
    op.drop_column("uploaded_files", "ingest_sender_name")
    op.drop_column("uploaded_files", "ingest_sender_email")
