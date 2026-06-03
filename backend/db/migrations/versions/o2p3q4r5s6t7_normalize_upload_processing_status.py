"""normalize uploaded_files.processing_status to queued/processing/processed/failed

Revision ID: o2p3q4r5s6t7
Revises: n1i2j3k4l5m6
Create Date: 2026-06-02 18:00:00.000000
"""
from typing import Sequence, Union

from alembic import op

revision: str = "o2p3q4r5s6t7"
down_revision: Union[str, Sequence[str], None] = "n1i2j3k4l5m6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE uploaded_files
        SET processing_status = 'queued'
        WHERE processing_status IN ('pending', 'queued_deferred')
          AND file_kind = 'invoice'
        """
    )
    op.execute(
        """
        UPDATE uploaded_files
        SET processing_status = 'processed'
        WHERE processing_status = 'pending'
          AND file_kind <> 'invoice'
        """
    )


def downgrade() -> None:
    pass
