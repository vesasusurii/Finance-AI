"""add invoices.review_reasons

Revision ID: l9m0a1b2c3d4
Revises: k8f9a0b1c2d3
Create Date: 2026-05-29 16:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "l9m0a1b2c3d4"
down_revision: Union[str, Sequence[str], None] = "k8f9a0b1c2d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {col["name"] for col in inspector.get_columns("invoices")}
    if "review_reasons" not in columns:
        op.add_column(
            "invoices",
            sa.Column(
                "review_reasons",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=True,
            ),
        )


def downgrade() -> None:
    op.drop_column("invoices", "review_reasons")
