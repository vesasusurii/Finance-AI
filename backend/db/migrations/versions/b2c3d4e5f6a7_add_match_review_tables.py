"""add_match_review_tables

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-05-22 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "invoice_payment_matches",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("invoice_id", sa.Integer(), nullable=False),
        sa.Column("bank_transaction_id", sa.Integer(), nullable=False),
        sa.Column("invoice_number", sa.String(length=200), nullable=False),
        sa.Column(
            "match_type",
            sa.String(length=50),
            server_default="invoice_number",
            nullable=False,
        ),
        sa.Column("match_confidence", sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("paid_at_date", sa.Date(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["bank_transaction_id"], ["bank_transactions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["invoice_id"], ["invoices.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "invoice_id",
            "bank_transaction_id",
            name="uq_matches_invoice_bank",
        ),
    )
    op.create_index("ix_matches_invoice_id", "invoice_payment_matches", ["invoice_id"], unique=False)
    op.create_index(
        "ix_matches_bank_transaction_id",
        "invoice_payment_matches",
        ["bank_transaction_id"],
        unique=False,
    )

    op.create_table(
        "review_tasks",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("task_type", sa.String(length=50), nullable=False),
        sa.Column("invoice_id", sa.Integer(), nullable=True),
        sa.Column("bank_transaction_id", sa.Integer(), nullable=True),
        sa.Column("reason", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=50), server_default="open", nullable=False),
        sa.Column("assigned_to", sa.Integer(), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["assigned_to"], ["users.id"]),
        sa.ForeignKeyConstraint(["bank_transaction_id"], ["bank_transactions.id"]),
        sa.ForeignKeyConstraint(["invoice_id"], ["invoices.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_review_tasks_status", "review_tasks", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_review_tasks_status", table_name="review_tasks")
    op.drop_table("review_tasks")
    op.drop_index("ix_matches_bank_transaction_id", table_name="invoice_payment_matches")
    op.drop_index("ix_matches_invoice_id", table_name="invoice_payment_matches")
    op.drop_table("invoice_payment_matches")
