"""add uploaded_files.upload_source for email ingest filtering

Revision ID: p3q4r5s6t7u8
Revises: o2p3q4r5s6t7
Create Date: 2026-06-03 12:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "p3q4r5s6t7u8"
down_revision: Union[str, Sequence[str], None] = "m1n2o3p4q5r6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {col["name"] for col in inspector.get_columns("uploaded_files")}
    if "upload_source" not in columns:
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


def downgrade() -> None:
    op.drop_index("ix_uploaded_files_upload_source", table_name="uploaded_files")
    op.drop_column("uploaded_files", "upload_source")
