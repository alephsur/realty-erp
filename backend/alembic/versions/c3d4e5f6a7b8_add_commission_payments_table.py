"""add_commission_payments_table

Revision ID: c3d4e5f6a7b8
Revises: b7c8d9e0f1a2
Create Date: 2026-05-04 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, None] = 'b7c8d9e0f1a2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Define the enum using postgresql.ENUM with create_type=False so that
# create_table does NOT try to emit CREATE TYPE — we handle that ourselves
# with IF NOT EXISTS to be idempotent across partial runs.
commission_status = postgresql.ENUM(
    'PENDING', 'INVOICED', 'PAID',
    name='commissionstatus',
    create_type=False,
)


def upgrade() -> None:
    # Create the enum type — DO block catches duplicate_object if a previous partial run left it
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE commissionstatus AS ENUM ('PENDING', 'INVOICED', 'PAID');
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$;
    """)

    op.create_table(
        'commission_payments',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('sale_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('sales.id', ondelete='CASCADE'), nullable=False, unique=True),
        sa.Column('agent_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('amount', sa.Float, nullable=False),
        sa.Column('status', commission_status, nullable=False, server_default='PENDING'),
        sa.Column('payment_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('invoice_number', sa.String, nullable=True),
        sa.Column('notes', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now()),
    )

    # Backfill: create PENDING payment for every existing sale
    op.execute("""
        INSERT INTO commission_payments (id, tenant_id, sale_id, agent_id, amount, status, created_at)
        SELECT
            gen_random_uuid(),
            s.tenant_id,
            s.id,
            s.agent_id,
            s.agent_commission,
            'PENDING',
            COALESCE(s.created_at, NOW())
        FROM sales s
        WHERE NOT EXISTS (
            SELECT 1 FROM commission_payments cp WHERE cp.sale_id = s.id
        )
    """)


def downgrade() -> None:
    op.drop_table('commission_payments')
    op.execute("DROP TYPE IF EXISTS commissionstatus")
