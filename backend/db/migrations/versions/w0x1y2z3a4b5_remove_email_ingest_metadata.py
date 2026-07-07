"""remove email ingest metadata from uploaded_files

Revision ID: w0x1y2z3a4b5
Revises: v9w0x1y2z3a4
Create Date: 2026-07-07 17:30:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "w0x1y2z3a4b5"
down_revision: Union[str, Sequence[str], None] = "v9w0x1y2z3a4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _drop_column_if_exists(table: str, column: str) -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {col["name"] for col in inspector.get_columns(table)}
    if column in columns:
        op.drop_column(table, column)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    indexes = {idx["name"] for idx in inspector.get_indexes("uploaded_files")}
    if "ix_uploaded_files_upload_source" in indexes:
        op.drop_index("ix_uploaded_files_upload_source", table_name="uploaded_files")

    for column in (
        "ingest_message_id",
        "ingest_email_subject",
        "ingest_sender_name",
        "ingest_sender_email",
        "upload_source",
    ):
        _drop_column_if_exists("uploaded_files", column)


def downgrade() -> None:
    op.add_column(
        "uploaded_files",
        sa.Column(
            "upload_source",
            sa.String(length=50),
            nullable=False,
            server_default="portal",
        ),
    )
    op.create_index(
        "ix_uploaded_files_upload_source",
        "uploaded_files",
        ["upload_source"],
    )
    op.add_column(
        "uploaded_files",
        sa.Column("ingest_sender_email", sa.String(length=320), nullable=True),
    )
    op.add_column(
        "uploaded_files",
        sa.Column("ingest_sender_name", sa.String(length=300), nullable=True),
    )
    op.add_column(
        "uploaded_files",
        sa.Column("ingest_email_subject", sa.String(length=500), nullable=True),
    )
    op.add_column(
        "uploaded_files",
        sa.Column("ingest_message_id", sa.String(length=500), nullable=True),
    )
