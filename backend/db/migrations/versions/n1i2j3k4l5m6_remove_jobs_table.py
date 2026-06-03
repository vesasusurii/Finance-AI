"""remove accidental persistent jobs table

Revision ID: n1i2j3k4l5m6
Revises: m0h1i2j3k4l5
Create Date: 2026-06-02 12:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "n1i2j3k4l5m6"
down_revision: Union[str, Sequence[str], None] = "m0h1i2j3k4l5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DROP TABLE IF EXISTS jobs")
    op.add_column(
        "review_tasks",
        sa.Column("enriched_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("review_tasks", "enriched_payload")
