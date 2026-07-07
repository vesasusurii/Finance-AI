"""add bank_statements.statement_month

Revision ID: v9w0x1y2z3a4
Revises: u8v9w0x1y2z3
Create Date: 2026-07-07 15:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "v9w0x1y2z3a4"
down_revision: Union[str, Sequence[str], None] = "u8v9w0x1y2z3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "bank_statements",
        sa.Column("statement_month", sa.Date(), nullable=True),
    )
    op.execute(
        """
        UPDATE bank_statements
        SET statement_month = date_trunc(
            'month',
            COALESCE(statement_date, uploaded_at::date)
        )::date
        WHERE statement_month IS NULL
        """
    )
    op.alter_column("bank_statements", "statement_month", nullable=False)

    # Consolidate overlapping statements for the same uploader/month.
    op.execute(
        """
        WITH ranked AS (
            SELECT
                id,
                uploaded_by,
                statement_month,
                ROW_NUMBER() OVER (
                    PARTITION BY uploaded_by, statement_month
                    ORDER BY row_count DESC, uploaded_at DESC, id DESC
                ) AS rn
            FROM bank_statements
        ),
        winners AS (
            SELECT id AS winner_id, uploaded_by, statement_month
            FROM ranked
            WHERE rn = 1
        ),
        losers AS (
            SELECT r.id AS loser_id, w.winner_id
            FROM ranked r
            JOIN winners w
              ON w.uploaded_by = r.uploaded_by
             AND w.statement_month = r.statement_month
            WHERE r.rn > 1
        )
        UPDATE bank_transactions bt
        SET bank_statement_id = l.winner_id
        FROM losers l
        WHERE bt.bank_statement_id = l.loser_id
        """
    )
    op.execute(
        """
        WITH ranked AS (
            SELECT
                id,
                uploaded_by,
                statement_month,
                ROW_NUMBER() OVER (
                    PARTITION BY uploaded_by, statement_month
                    ORDER BY row_count DESC, uploaded_at DESC, id DESC
                ) AS rn
            FROM bank_statements
        ),
        winners AS (
            SELECT id AS winner_id, uploaded_by, statement_month
            FROM ranked
            WHERE rn = 1
        ),
        losers AS (
            SELECT r.id AS loser_id, w.winner_id
            FROM ranked r
            JOIN winners w
              ON w.uploaded_by = r.uploaded_by
             AND w.statement_month = r.statement_month
            WHERE r.rn > 1
        ),
        duplicate_txns AS (
            SELECT bt.id
            FROM bank_transactions bt
            JOIN losers l ON bt.bank_statement_id = l.winner_id
            WHERE EXISTS (
                SELECT 1
                FROM bank_transactions keep_txn
                WHERE keep_txn.bank_statement_id = l.winner_id
                  AND keep_txn.id < bt.id
                  AND keep_txn.transaction_date IS NOT DISTINCT FROM bt.transaction_date
                  AND keep_txn.debited_amount IS NOT DISTINCT FROM bt.debited_amount
                  AND keep_txn.credited_amount IS NOT DISTINCT FROM bt.credited_amount
                  AND lower(COALESCE(keep_txn.comment, ''))
                      = lower(COALESCE(bt.comment, ''))
                  AND lower(COALESCE(keep_txn.transaction_type, ''))
                      = lower(COALESCE(bt.transaction_type, ''))
            )
        )
        DELETE FROM bank_transactions
        WHERE id IN (SELECT id FROM duplicate_txns)
        """
    )
    op.execute(
        """
        WITH ranked AS (
            SELECT
                id,
                uploaded_by,
                statement_month,
                ROW_NUMBER() OVER (
                    PARTITION BY uploaded_by, statement_month
                    ORDER BY row_count DESC, uploaded_at DESC, id DESC
                ) AS rn
            FROM bank_statements
        ),
        winners AS (
            SELECT id AS winner_id
            FROM ranked
            WHERE rn = 1
        )
        UPDATE bank_statements bs
        SET
            row_count = (
                SELECT COUNT(*)
                FROM bank_transactions bt
                WHERE bt.bank_statement_id = bs.id
            ),
            statement_date = (
                SELECT MAX(bt.transaction_date)
                FROM bank_transactions bt
                WHERE bt.bank_statement_id = bs.id
            )
        WHERE bs.id IN (SELECT winner_id FROM winners)
        """
    )
    op.execute(
        """
        DELETE FROM bank_statements bs
        WHERE EXISTS (
            SELECT 1
            FROM bank_statements newer
            WHERE newer.uploaded_by = bs.uploaded_by
              AND newer.statement_month = bs.statement_month
              AND newer.id <> bs.id
              AND (
                    newer.row_count > bs.row_count
                 OR (
                        newer.row_count = bs.row_count
                    AND newer.uploaded_at > bs.uploaded_at
                 )
                 OR (
                        newer.row_count = bs.row_count
                    AND newer.uploaded_at = bs.uploaded_at
                    AND newer.id > bs.id
                 )
              )
        )
        """
    )

    op.drop_index(
        "ix_bank_statements_user_statement_date",
        table_name="bank_statements",
    )
    op.create_index(
        "ix_bank_statements_user_statement_month",
        "bank_statements",
        ["uploaded_by", "statement_month"],
        unique=True,
    )
    op.execute(
        """
        SELECT setval(
            pg_get_serial_sequence('bank_statements', 'id'),
            (SELECT COALESCE(MAX(id), 1) FROM bank_statements)
        )
        """
    )


def downgrade() -> None:
    op.drop_index(
        "ix_bank_statements_user_statement_month",
        table_name="bank_statements",
    )
    op.create_index(
        "ix_bank_statements_user_statement_date",
        "bank_statements",
        ["uploaded_by", "statement_date"],
        unique=True,
    )
    op.drop_column("bank_statements", "statement_month")
