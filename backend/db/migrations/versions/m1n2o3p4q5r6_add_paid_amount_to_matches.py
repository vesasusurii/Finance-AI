"""add paid_amount to invoice_payment_matches

Revision ID: m1n2o3p4q5r6
Revises: o2p3q4r5s6t7
Create Date: 2026-06-02 15:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "m1n2o3p4q5r6"
down_revision: Union[str, Sequence[str], None] = "o2p3q4r5s6t7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {
        col["name"]
        for col in inspector.get_columns("invoice_payment_matches")
    }
    if "paid_amount" not in columns:
        op.add_column(
            "invoice_payment_matches",
            sa.Column("paid_amount", sa.Numeric(18, 2), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {
        col["name"]
        for col in inspector.get_columns("invoice_payment_matches")
    }
    if "paid_amount" in columns:
        op.drop_column("invoice_payment_matches", "paid_amount")
