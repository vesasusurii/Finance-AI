"""remove email verification columns from users

Revision ID: u8v9w0x1y2z3
Revises: t7u8v9w0x1y2
Create Date: 2026-07-07 10:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "u8v9w0x1y2z3"
down_revision: Union[str, Sequence[str], None] = "t8u9v0w1x2y3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {col["name"] for col in inspector.get_columns("users")}

    if "email_verification_expires_at" in columns:
        op.drop_column("users", "email_verification_expires_at")
    if "email_verification_code_hash" in columns:
        op.drop_column("users", "email_verification_code_hash")
    if "email_verified_at" in columns:
        op.drop_column("users", "email_verified_at")


def downgrade() -> None:
    pass
