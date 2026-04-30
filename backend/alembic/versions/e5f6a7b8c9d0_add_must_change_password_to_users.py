"""add_must_change_password_to_users

Revision ID: e5f6a7b8c9d0
Revises: d3f1a2b4c5e6
Create Date: 2026-04-23 10:35:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add must_change_password column — defaults to False for all existing users.
    # New bootstrap superadmin accounts are created with True to force a
    # password rotation on the first login.
    op.add_column(
        'users',
        sa.Column(
            'must_change_password',
            sa.Boolean(),
            nullable=False,
            server_default=sa.text('false'),
        )
    )


def downgrade() -> None:
    op.drop_column('users', 'must_change_password')
