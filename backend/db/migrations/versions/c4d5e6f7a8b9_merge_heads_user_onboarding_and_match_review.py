"""merge_heads_user_onboarding_and_match_review

Revision ID: c4d5e6f7a8b9
Revises: b2c3d4e5f6a7, f3a4b5c6d7e8
Create Date: 2026-05-28 09:58:00.000000

"""
from typing import Sequence, Union


revision: str = "c4d5e6f7a8b9"
down_revision: Union[str, Sequence[str], None] = ("b2c3d4e5f6a7", "f3a4b5c6d7e8")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Merge revision; no schema changes.
    pass


def downgrade() -> None:
    # Downgrade across merged heads intentionally does nothing here.
    pass
