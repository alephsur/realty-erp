"""add_status_changed_at_to_properties

Revision ID: b7c8d9e0f1a2
Revises: abc123def456
Create Date: 2026-05-04 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b7c8d9e0f1a2'
down_revision: Union[str, None] = 'abc123def456'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'properties',
        sa.Column('status_changed_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.execute("UPDATE properties SET status_changed_at = created_at WHERE status_changed_at IS NULL")


def downgrade() -> None:
    op.drop_column('properties', 'status_changed_at')
