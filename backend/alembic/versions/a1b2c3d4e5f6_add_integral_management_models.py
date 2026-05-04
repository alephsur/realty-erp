"""add_integral_management_models

Revision ID: a1b2c3d4e5f6
Revises: d3f1a2b4c5e6
Create Date: 2026-04-10 13:17:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'd3f1a2b4c5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- Property model: add agent_commission_rate ---
    op.add_column('properties', sa.Column('agent_commission_rate', sa.Float(), nullable=True))
    
    # --- Sale model: add buyer_id ---
    op.add_column('sales', sa.Column('buyer_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        'fk_sales_buyer_id', 'sales', 'clients',
        ['buyer_id'], ['id'], ondelete='SET NULL'
    )
    
    # --- Client model: add extended CRM fields ---
    op.add_column('clients', sa.Column('dni', sa.String(), nullable=True))
    op.add_column('clients', sa.Column('address', sa.String(), nullable=True))
    op.add_column('clients', sa.Column('budget_min', sa.Float(), nullable=True))
    op.add_column('clients', sa.Column('budget_max', sa.Float(), nullable=True))
    op.add_column('clients', sa.Column('desired_zones', sa.String(), nullable=True))
    op.add_column('clients', sa.Column('desired_type', sa.String(), nullable=True))
    op.add_column('clients', sa.Column('notes', sa.Text(), nullable=True))
    
    # --- New table: client_property_interests ---
    op.create_table(
        'client_property_interests',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, index=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('client_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('clients.id', ondelete='CASCADE'), nullable=False),
        sa.Column('property_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('properties.id', ondelete='CASCADE'), nullable=False),
        sa.Column('interest_level', sa.String(), server_default='medium'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    
    # --- New table: visits ---
    # Create the enum type explicitly first (checkfirst avoids DuplicateObject if it already exists)
    op.execute("DO $$ BEGIN CREATE TYPE visitstatus AS ENUM ('SCHEDULED', 'COMPLETED', 'CANCELLED', 'NO_SHOW'); EXCEPTION WHEN duplicate_object THEN null; END $$;")

    # Use a pre-built ENUM instance with create_type=False so create_table does NOT fire
    # an additional CREATE TYPE DDL event via SQLAlchemy's before_create hook.
    visit_status_col = postgresql.ENUM(
        'SCHEDULED', 'COMPLETED', 'CANCELLED', 'NO_SHOW',
        name='visitstatus',
        create_type=False,
    )

    op.create_table(
        'visits',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, index=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('property_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('properties.id', ondelete='CASCADE'), nullable=False),
        sa.Column('client_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('clients.id', ondelete='SET NULL'), nullable=True),
        sa.Column('agent_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('scheduled_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('duration_minutes', sa.Integer(), server_default='30'),
        sa.Column('status', visit_status_col, server_default='SCHEDULED', nullable=False),
        sa.Column('feedback', sa.Text(), nullable=True),
        sa.Column('rating', sa.Integer(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    )
    
    # --- New table: notes ---
    op.create_table(
        'notes',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, index=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('entity_type', sa.String(), nullable=False),
        sa.Column('entity_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('notes')
    op.drop_table('visits')
    
    # Drop visitstatus enum
    visit_status = postgresql.ENUM('SCHEDULED', 'COMPLETED', 'CANCELLED', 'NO_SHOW', name='visitstatus')
    visit_status.drop(op.get_bind(), checkfirst=True)
    
    op.drop_table('client_property_interests')
    
    # Remove extended client fields
    op.drop_column('clients', 'notes')
    op.drop_column('clients', 'desired_type')
    op.drop_column('clients', 'desired_zones')
    op.drop_column('clients', 'budget_max')
    op.drop_column('clients', 'budget_min')
    op.drop_column('clients', 'address')
    op.drop_column('clients', 'dni')
    
    # Remove buyer_id from sales
    op.drop_constraint('fk_sales_buyer_id', 'sales', type_='foreignkey')
    op.drop_column('sales', 'buyer_id')
    
    # Remove agent_commission_rate from properties
    op.drop_column('properties', 'agent_commission_rate')
