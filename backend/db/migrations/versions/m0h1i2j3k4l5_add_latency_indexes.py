"""add latency-focused indexes

Revision ID: m0h1i2j3k4l5
Revises: l9m0a1b2c3d4
Create Date: 2026-06-02 10:00:00.000000
"""
from typing import Sequence, Union

from alembic import op

revision: str = "m0h1i2j3k4l5"
down_revision: Union[str, Sequence[str], None] = "l9m0a1b2c3d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Composite indexes mirror the high-traffic filters used by review queues,
    # document lists, startup OCR recovery, and reconciliation runs.
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_uploaded_files_user_kind_status "
        "ON uploaded_files (uploaded_by, file_kind, processing_status)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_uploaded_files_status_uploaded_at "
        "ON uploaded_files (processing_status, uploaded_at)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_invoices_source_file_id "
        "ON invoices (source_file_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_invoices_owner_review_created "
        "ON invoices (uploaded_by, review_status, created_at)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_invoices_owner_match_date "
        "ON invoices (uploaded_by, match_status, invoice_date)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_bank_transactions_statement_status "
        "ON bank_transactions (bank_statement_id, reconciliation_status)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_bank_tx_owner_lookup "
        "ON bank_statements (uploaded_by)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_bank_tx_status "
        "ON bank_transactions (reconciliation_status)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_bank_tx_statement_id "
        "ON bank_transactions (bank_statement_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_bank_transactions_status_date "
        "ON bank_transactions (reconciliation_status, transaction_date)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_review_tasks_status_created "
        "ON review_tasks (status, created_at)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_review_tasks_type_status_created "
        "ON review_tasks (task_type, status, created_at)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_review_task_lookup "
        "ON review_tasks (task_type, created_at DESC)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_review_tasks_invoice_id "
        "ON review_tasks (invoice_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_review_tasks_bank_transaction_id "
        "ON review_tasks (bank_transaction_id)"
    )


def downgrade() -> None:
    for index_name in (
        "ix_review_tasks_bank_transaction_id",
        "ix_review_tasks_invoice_id",
        "idx_review_task_lookup",
        "ix_review_tasks_type_status_created",
        "ix_review_tasks_status_created",
        "ix_bank_transactions_status_date",
        "idx_bank_tx_statement_id",
        "idx_bank_tx_status",
        "idx_bank_tx_owner_lookup",
        "ix_bank_transactions_statement_status",
        "ix_invoices_owner_match_date",
        "ix_invoices_owner_review_created",
        "ix_invoices_source_file_id",
        "ix_uploaded_files_status_uploaded_at",
        "ix_uploaded_files_user_kind_status",
    ):
        op.execute(f"DROP INDEX IF EXISTS {index_name}")
