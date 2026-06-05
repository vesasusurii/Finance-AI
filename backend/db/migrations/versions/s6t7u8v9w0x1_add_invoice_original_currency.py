"""add original currency fields to invoices

Revision ID: s6t7u8v9w0x1
Revises: r5s6t7u8v9w0
Create Date: 2026-06-05 10:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "s6t7u8v9w0x1"
down_revision: Union[str, Sequence[str], None] = "r5s6t7u8v9w0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {col["name"] for col in inspector.get_columns("invoices")}

    if "original_amount" not in columns:
        op.add_column(
            "invoices",
            sa.Column("original_amount", sa.Numeric(18, 2), nullable=True),
        )
    if "original_currency" not in columns:
        op.add_column(
            "invoices",
            sa.Column("original_currency", sa.String(length=10), nullable=True),
        )
    if "exchange_rate" not in columns:
        op.add_column(
            "invoices",
            sa.Column("exchange_rate", sa.Numeric(18, 6), nullable=True),
        )
    if "exchange_rate_date" not in columns:
        op.add_column(
            "invoices",
            sa.Column("exchange_rate_date", sa.Date(), nullable=True),
        )

    # Backfill EUR rows: copy current amount/currency into original fields.
    bind.execute(
        sa.text(
            """
            UPDATE invoices
            SET
                original_amount = amount,
                original_currency = COALESCE(NULLIF(UPPER(TRIM(currency)), ''), 'EUR'),
                exchange_rate = 1,
                exchange_rate_date = COALESCE(invoice_date, created_at::date)
            WHERE original_amount IS NULL
              AND (currency IS NULL OR UPPER(TRIM(currency)) = 'EUR')
            """
        )
    )

    # Non-EUR rows: preserve current values as originals; EUR conversion via backfill script.
    bind.execute(
        sa.text(
            """
            UPDATE invoices
            SET
                original_amount = amount,
                original_currency = UPPER(TRIM(currency))
            WHERE original_amount IS NULL
              AND currency IS NOT NULL
              AND UPPER(TRIM(currency)) <> 'EUR'
            """
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {col["name"] for col in inspector.get_columns("invoices")}

    if "exchange_rate_date" in columns:
        op.drop_column("invoices", "exchange_rate_date")
    if "exchange_rate" in columns:
        op.drop_column("invoices", "exchange_rate")
    if "original_currency" in columns:
        op.drop_column("invoices", "original_currency")
    if "original_amount" in columns:
        op.drop_column("invoices", "original_amount")
