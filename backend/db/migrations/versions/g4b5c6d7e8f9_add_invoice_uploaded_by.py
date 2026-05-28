"""add_invoice_uploaded_by

Revision ID: g4b5c6d7e8f9
Revises: f3a4b5c6d7e8
Create Date: 2026-05-28 12:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "g4b5c6d7e8f9"
down_revision: Union[str, None] = "f3a4b5c6d7e8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "invoices",
        sa.Column("uploaded_by", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_invoices_uploaded_by_users",
        "invoices",
        "users",
        ["uploaded_by"],
        ["id"],
    )
    op.create_index("ix_invoices_uploaded_by", "invoices", ["uploaded_by"])

    # Backfill from source upload records
    op.execute(
        """
        UPDATE invoices AS i
        SET uploaded_by = uf.uploaded_by
        FROM uploaded_files AS uf
        WHERE i.source_file_id = uf.id
          AND i.uploaded_by IS NULL
        """
    )

    # Orphans without a source file — assign to the earliest user account
    op.execute(
        """
        UPDATE invoices
        SET uploaded_by = (SELECT id FROM users ORDER BY id LIMIT 1)
        WHERE uploaded_by IS NULL
        """
    )

    op.alter_column("invoices", "uploaded_by", nullable=False)


def downgrade() -> None:
    op.drop_index("ix_invoices_uploaded_by", table_name="invoices")
    op.drop_constraint("fk_invoices_uploaded_by_users", "invoices", type_="foreignkey")
    op.drop_column("invoices", "uploaded_by")
