"""add bank_statements.statement_date

Revision ID: j7e8f9a0b1c2
Revises: i6d7e8f9a0b1
Create Date: 2026-05-29 10:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "j7e8f9a0b1c2"
down_revision: Union[str, Sequence[str], None] = "i6d7e8f9a0b1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "bank_statements",
        sa.Column("statement_date", sa.Date(), nullable=True),
    )
    op.execute(
        """
        UPDATE bank_statements
        SET statement_date = uploaded_at::date
        WHERE statement_date IS NULL
        """
    )
    op.execute(
        """
        DELETE FROM bank_statements a
        USING bank_statements b
        WHERE a.uploaded_by = b.uploaded_by
          AND a.statement_date = b.statement_date
          AND a.statement_date IS NOT NULL
          AND a.uploaded_at < b.uploaded_at
        """
    )
    op.create_index(
        "ix_bank_statements_user_statement_date",
        "bank_statements",
        ["uploaded_by", "statement_date"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_bank_statements_user_statement_date", table_name="bank_statements")
    op.drop_column("bank_statements", "statement_date")
