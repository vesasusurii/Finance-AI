"""partial unique index on (uploaded_by, invoice_number_normalized)

Revision ID: r5s6t7u8v9w0
Revises: q4r5s6t7u8v9
Create Date: 2026-06-03 20:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "r5s6t7u8v9w0"
down_revision: Union[str, Sequence[str], None] = "q4r5s6t7u8v9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

INDEX_NAME = "uq_invoices_owner_invoice_number_normalized"


def upgrade() -> None:
    bind = op.get_bind()
    duplicate_groups = bind.execute(
        sa.text(
            """
            SELECT COUNT(*) FROM (
                SELECT uploaded_by, invoice_number_normalized
                FROM invoices
                WHERE invoice_number_normalized IS NOT NULL
                GROUP BY uploaded_by, invoice_number_normalized
                HAVING COUNT(*) > 1
            ) dup
            """
        )
    ).scalar_one()

    if int(duplicate_groups or 0) > 0:
        return

    inspector = sa.inspect(bind)
    indexes = {idx["name"] for idx in inspector.get_indexes("invoices")}
    if INDEX_NAME in indexes:
        return

    op.create_index(
        INDEX_NAME,
        "invoices",
        ["uploaded_by", "invoice_number_normalized"],
        unique=True,
        postgresql_where=sa.text("invoice_number_normalized IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index(INDEX_NAME, table_name="invoices")
