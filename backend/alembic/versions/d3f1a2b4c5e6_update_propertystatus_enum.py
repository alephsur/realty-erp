"""update_propertystatus_enum_values

Revision ID: d3f1a2b4c5e6
Revises: cef0313b424f
Create Date: 2026-04-10 10:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd3f1a2b4c5e6'
down_revision: Union[str, None] = 'cef0313b424f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # The old propertystatus enum only had: AVAILABLE, RESERVED, SOLD
    # We need to replace it with the new pipeline values.
    # PostgreSQL doesn't allow removing enum values easily, so we:
    # 1. Rename old type
    # 2. Create new type with all values
    # 3. Alter column to use new type (casting old AVAILABLE->CAPTADA, etc.)
    # 4. Drop old type

    op.execute("ALTER TYPE propertystatus RENAME TO propertystatus_old")
    op.execute("""
        CREATE TYPE propertystatus AS ENUM (
            'CAPTADA',
            'PUBLICADA',
            'EN_VISITAS',
            'RESERVADA',
            'PENDIENTE_NOTARIA',
            'VENDIDA',
            'RETIRADA'
        )
    """)
    op.execute("""
        ALTER TABLE properties
            ALTER COLUMN status DROP DEFAULT,
            ALTER COLUMN status TYPE propertystatus
                USING CASE status::text
                    WHEN 'AVAILABLE' THEN 'CAPTADA'::propertystatus
                    WHEN 'RESERVED' THEN 'RESERVADA'::propertystatus
                    WHEN 'SOLD'     THEN 'VENDIDA'::propertystatus
                    ELSE 'CAPTADA'::propertystatus
                END,
            ALTER COLUMN status SET DEFAULT 'CAPTADA'::propertystatus
    """)
    op.execute("DROP TYPE propertystatus_old")


def downgrade() -> None:
    op.execute("ALTER TYPE propertystatus RENAME TO propertystatus_new")
    op.execute("""
        CREATE TYPE propertystatus AS ENUM ('AVAILABLE', 'RESERVED', 'SOLD')
    """)
    op.execute("""
        ALTER TABLE properties
            ALTER COLUMN status DROP DEFAULT,
            ALTER COLUMN status TYPE propertystatus
                USING CASE status::text
                    WHEN 'VENDIDA'   THEN 'SOLD'::propertystatus
                    WHEN 'RESERVADA' THEN 'RESERVED'::propertystatus
                    ELSE 'AVAILABLE'::propertystatus
                END,
            ALTER COLUMN status SET DEFAULT 'AVAILABLE'::propertystatus
    """)
    op.execute("DROP TYPE propertystatus_new")
