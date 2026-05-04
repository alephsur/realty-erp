"""add_agent_fields_and_property_pipeline

Revision ID: cef0313b424f
Revises: 72983075a3a0
Create Date: 2026-04-09 16:34:36.633840

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cef0313b424f'
down_revision: Union[str, None] = '72983075a3a0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create the new PostgreSQL enum type FIRST
    propertytype_enum = sa.Enum('PISO', 'CASA', 'CHALET', 'ATICO', 'LOCAL', 'OFICINA', 'TERRENO', 'GARAJE', 'TRASTERO', name='propertytype')
    propertytype_enum.create(op.get_bind(), checkfirst=True)

    # Properties: new columns
    op.add_column('properties', sa.Column('reference', sa.String(), nullable=True))
    op.add_column('properties', sa.Column('property_type', propertytype_enum, nullable=True))
    op.execute("UPDATE properties SET property_type = 'PISO' WHERE property_type IS NULL")
    op.alter_column('properties', 'property_type', nullable=False)
    op.add_column('properties', sa.Column('city', sa.String(), nullable=True))
    op.add_column('properties', sa.Column('postal_code', sa.String(), nullable=True))
    op.add_column('properties', sa.Column('owner_name', sa.String(), nullable=True))
    op.add_column('properties', sa.Column('owner_phone', sa.String(), nullable=True))
    op.add_column('properties', sa.Column('owner_email', sa.String(), nullable=True))
    op.add_column('properties', sa.Column('commission_rate', sa.Float(), nullable=True))

    # Sales: new commission split columns
    op.add_column('sales', sa.Column('agent_id', sa.UUID(), nullable=True))
    op.add_column('sales', sa.Column('agent_commission', sa.Float(), nullable=True))
    op.add_column('sales', sa.Column('agency_commission', sa.Float(), nullable=True))
    op.add_column('sales', sa.Column('notes', sa.Text(), nullable=True))
    op.execute("UPDATE sales SET agent_commission = 0 WHERE agent_commission IS NULL")
    op.execute("UPDATE sales SET agency_commission = 0 WHERE agency_commission IS NULL")
    op.alter_column('sales', 'agent_commission', nullable=False)
    op.alter_column('sales', 'agency_commission', nullable=False)
    op.drop_constraint('sales_selling_agent_id_fkey', 'sales', type_='foreignkey')
    op.drop_constraint('sales_listing_agent_id_fkey', 'sales', type_='foreignkey')
    op.create_foreign_key(None, 'sales', 'users', ['agent_id'], ['id'], ondelete='SET NULL')
    op.drop_column('sales', 'selling_agent_id')
    op.drop_column('sales', 'listing_agent_id')

    # Users: agent-specific fields
    op.add_column('users', sa.Column('phone', sa.String(), nullable=True))
    op.add_column('users', sa.Column('license_number', sa.String(), nullable=True))
    op.add_column('users', sa.Column('commission_rate', sa.Float(), nullable=True))
    op.add_column('users', sa.Column('hire_date', sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'hire_date')
    op.drop_column('users', 'commission_rate')
    op.drop_column('users', 'license_number')
    op.drop_column('users', 'phone')
    op.add_column('sales', sa.Column('listing_agent_id', sa.UUID(), autoincrement=False, nullable=True))
    op.add_column('sales', sa.Column('selling_agent_id', sa.UUID(), autoincrement=False, nullable=True))
    op.drop_constraint(None, 'sales', type_='foreignkey')
    op.create_foreign_key('sales_listing_agent_id_fkey', 'sales', 'users', ['listing_agent_id'], ['id'], ondelete='SET NULL')
    op.create_foreign_key('sales_selling_agent_id_fkey', 'sales', 'users', ['selling_agent_id'], ['id'], ondelete='SET NULL')
    op.drop_column('sales', 'notes')
    op.drop_column('sales', 'agency_commission')
    op.drop_column('sales', 'agent_commission')
    op.drop_column('sales', 'agent_id')
    op.drop_column('properties', 'commission_rate')
    op.drop_column('properties', 'owner_email')
    op.drop_column('properties', 'owner_phone')
    op.drop_column('properties', 'owner_name')
    op.drop_column('properties', 'postal_code')
    op.drop_column('properties', 'city')
    op.drop_column('properties', 'property_type')
    op.drop_column('properties', 'reference')
    sa.Enum(name='propertytype').drop(op.get_bind(), checkfirst=True)
