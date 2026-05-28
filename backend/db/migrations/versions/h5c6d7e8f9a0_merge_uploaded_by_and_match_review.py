"""merge_uploaded_by_and_match_review

Revision ID: h5c6d7e8f9a0
Revises: c4d5e6f7a8b9, g4b5c6d7e8f9
Create Date: 2026-05-28 13:00:00.000000

"""
from typing import Sequence, Union


revision: str = "h5c6d7e8f9a0"
down_revision: Union[str, Sequence[str], None] = ("c4d5e6f7a8b9", "g4b5c6d7e8f9")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
