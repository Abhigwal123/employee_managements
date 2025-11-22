"""Add tenant_id to cached_schedules table

Revision ID: add_tenant_id_cached
Revises: e8cb5d7c0e31
Create Date: 2025-11-05 10:15:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_tenant_id_cached'
down_revision = 'e8cb5d7c0e31'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Check if cached_schedules table exists
    from sqlalchemy import inspect
    from alembic import context
    
    conn = context.get_bind()
    inspector = inspect(conn)
    existing_tables = inspector.get_table_names()
    
    if 'cached_schedules' in existing_tables:
        existing_columns = [col['name'] for col in inspector.get_columns('cached_schedules')]
        if 'tenant_id' not in existing_columns:
            # Add tenant_id column (nullable first, then populate, then make NOT NULL)
            op.add_column('cached_schedules', 
                         sa.Column('tenant_id', sa.String(length=36), nullable=True))
            
            # Populate tenant_id from schedule_definitions
            op.execute("""
                UPDATE cached_schedules 
                SET tenant_id = (
                    SELECT tenantID 
                    FROM schedule_definitions 
                    WHERE schedule_definitions.scheduleDefID = cached_schedules.schedule_def_id
                    LIMIT 1
                )
            """)
            
            # Create foreign key constraint
            try:
                op.create_foreign_key('fk_cached_schedules_tenant_id', 'cached_schedules', 'tenants', 
                                     ['tenant_id'], ['tenantID'])
            except Exception:
                # Foreign key might already exist or tenants table might not exist yet
                pass
            
            # Create index
            try:
                op.create_index('ix_cached_schedules_tenant_id', 'cached_schedules', ['tenant_id'])
            except Exception:
                # Index might already exist
                pass
            
            # Make tenant_id NOT NULL after populating
            op.alter_column('cached_schedules', 'tenant_id', nullable=False)


def downgrade() -> None:
    # Remove tenant_id column
    op.drop_index('ix_cached_schedules_tenant_id', table_name='cached_schedules')
    op.drop_constraint('fk_cached_schedules_tenant_id', 'cached_schedules', type_='foreignkey')
    op.drop_column('cached_schedules', 'tenant_id')


