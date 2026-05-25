"""add_bank_tables

Revision ID: a1b2c3d4e5f6
Revises: 85b8af9ad26f
Create Date: 2026-05-22 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "85b8af9ad26f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "bank_statements",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source_file_id", sa.Integer(), nullable=False),
        sa.Column("uploaded_by", sa.Integer(), nullable=False),
        sa.Column(
            "uploaded_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("row_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "processing_status",
            sa.String(length=50),
            server_default="pending",
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["source_file_id"], ["uploaded_files.id"]),
        sa.ForeignKeyConstraint(["uploaded_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_bank_statements_processing_status",
        "bank_statements",
        ["processing_status"],
        unique=False,
    )

    op.create_table(
        "bank_transactions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("bank_statement_id", sa.Integer(), nullable=False),
        sa.Column("transaction_date", sa.Date(), nullable=True),
        sa.Column("debited_amount", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("credited_amount", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("transaction_type", sa.String(length=200), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column(
            "detected_invoice_numbers",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
        sa.Column(
            "reconciliation_status",
            sa.String(length=50),
            server_default="pending",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["bank_statement_id"],
            ["bank_statements.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_bank_transactions_statement_id",
        "bank_transactions",
        ["bank_statement_id"],
        unique=False,
    )
    op.create_index(
        "ix_bank_transactions_reconciliation_status",
        "bank_transactions",
        ["reconciliation_status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_bank_transactions_reconciliation_status", table_name="bank_transactions"
    )
    op.drop_index("ix_bank_transactions_statement_id", table_name="bank_transactions")
    op.drop_table("bank_transactions")
    op.drop_index("ix_bank_statements_processing_status", table_name="bank_statements")
    op.drop_table("bank_statements")
