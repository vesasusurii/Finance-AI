"""add uploaded_files.file_size and documents view

Revision ID: i6d7e8f9a0b1
Revises: h5c6d7e8f9a0
Create Date: 2026-05-28 16:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "i6d7e8f9a0b1"
down_revision: Union[str, Sequence[str], None] = "h5c6d7e8f9a0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "uploaded_files",
        sa.Column("file_size", sa.BigInteger(), nullable=True),
    )
    op.execute(
        """
        CREATE OR REPLACE VIEW documents AS
        SELECT
            id,
            uploaded_by AS user_id,
            original_filename AS filename,
            storage_path,
            mime_type,
            file_size,
            processing_status AS upload_status,
            uploaded_at AS created_at,
            file_kind
        FROM uploaded_files
        WHERE file_kind IN ('invoice', 'document')
        """
    )


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS documents")
    op.drop_column("uploaded_files", "file_size")
