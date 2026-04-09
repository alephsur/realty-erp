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
    # 1. Activate RLS on multitenant tables
    tables_with_rls = ['users']
    
    for table in tables_with_rls:
        # Enable RLS on the table
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;")
        # Create the isolation policy, allowing access if tenant_id = current_tenant or current_tenant is empty (which might be the case for SUPER_ADMIN but we should restrict by default)
        
        op.execute(f"""
            CREATE POLICY tenant_isolation_policy 
            ON {table}
            FOR ALL
            USING (
                tenant_id = current_setting('app.current_tenant', true)::uuid
            );
        """)
        
        # We also need a way to allow super_admin to view all records, but strictly speaking,
        # the user requested "restringido al tenant_id del usuario autenticado".
        # For super admin, we could handle it in Python (using a different session without setting current_tenant, maybe?)
        # For this version, we stick to the required RLS:
        # "cualquier SELECT, UPDATE o DELETE esté restringido al tenant_id del usuario autenticado."

def downgrade():
    tables_with_rls = ['users']
    for table in tables_with_rls:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_policy ON {table};")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;")
