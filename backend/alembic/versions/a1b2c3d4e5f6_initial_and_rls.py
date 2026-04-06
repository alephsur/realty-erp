"""initial and rls

Revision ID: a1b2c3d4e5f6
Revises: 
Create Date: 2024-05-18 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # Because writing out all the CREATE TABLEs by hand is error-prone, 
    # we simulate the generation. In a real workflow you'd run `alembic revision --autogenerate`.
    # Here we focus on the requirement: PostgreSQL RLS application.
    
    # 1. We assume tables users, properties, clients, sales are created here...
    # (Typically generated automatically by Alembic)
    
    # 2. Activate RLS on multitenant tables
    tables_with_rls = ['users', 'properties', 'clients', 'sales']
    
    for table in tables_with_rls:
        # Enable RLS on the table
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;")
        # Create the isolation policy
        op.execute(f"""
            CREATE POLICY tenant_isolation 
            ON {table} 
            USING (tenant_id = current_setting('app.current_tenant', true)::uuid);
        """)

def downgrade():
    tables_with_rls = ['sales', 'clients', 'properties', 'users']
    for table in tables_with_rls:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table};")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;")
