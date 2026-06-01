"""add uploaded_files.content_sha256 and invoice_access

Revision ID: k8f9a0b1c2d3
Revises: j7e8f9a0b1c2
Create Date: 2026-05-29 14:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "k8f9a0b1c2d3"
down_revision: Union[str, Sequence[str], None] = "j7e8f9a0b1c2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "uploaded_files",
        sa.Column("content_sha256", sa.String(length=64), nullable=True),
    )
    op.create_index(
        "ix_uploaded_files_invoice_content_sha256",
        "uploaded_files",
        ["content_sha256"],
        unique=True,
        postgresql_where=sa.text(
            "file_kind = 'invoice' AND content_sha256 IS NOT NULL"
        ),
        sqlite_where=sa.text(
            "file_kind = 'invoice' AND content_sha256 IS NOT NULL"
        ),
    )

    op.create_table(
        "invoice_access",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("invoice_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column(
            "grant_reason",
            sa.String(length=50),
            server_default="duplicate_upload",
            nullable=False,
        ),
        sa.Column(
            "granted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["invoice_id"], ["invoices.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "invoice_id", "user_id", name="uq_invoice_access_invoice_user"
        ),
    )
    op.create_index(
        "ix_invoice_access_user_id", "invoice_access", ["user_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_invoice_access_user_id", table_name="invoice_access")
    op.drop_table("invoice_access")
    op.drop_index(
        "ix_uploaded_files_invoice_content_sha256", table_name="uploaded_files"
    )
    op.drop_column("uploaded_files", "content_sha256")
