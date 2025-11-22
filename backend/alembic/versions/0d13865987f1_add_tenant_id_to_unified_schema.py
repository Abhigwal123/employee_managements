"""add_tenant_id_to_unified_schema

Revision ID: 0d13865987f1
Revises: e8cb5d7c0e31
Create Date: 2025-11-05 09:59:33.730926

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0d13865987f1'
down_revision = 'add_tenant_id_cached'
branch_labels = None
depends_on = None


def upgrade() -> None:
    from sqlalchemy import inspect
    from alembic import context
    import sqlalchemy as sa
    from alembic import op

    conn = context.get_bind()
    inspector = inspect(conn)
    existing_tables = inspector.get_table_names()

    # Helper: check if index exists before creating
    def safe_create_index(index_name, table_name, columns, unique=False):
        existing_indexes = [i['name'] for i in inspector.get_indexes(table_name)]
        if index_name not in existing_indexes:
            op.create_index(index_name, table_name, columns, unique=unique)

    # Add tenant_id column to cached_schedules if missing
    if 'cached_schedules' in existing_tables:
        existing_columns = [col['name'] for col in inspector.get_columns('cached_schedules')]
        if 'tenant_id' not in existing_columns:
            op.add_column('cached_schedules', sa.Column('tenant_id', sa.String(length=36), nullable=True))
            op.create_foreign_key('fk_cached_schedules_tenant_id', 'cached_schedules', 'tenants', ['tenant_id'], ['tenantID'])
            safe_create_index('ix_cached_schedules_tenant_id', 'cached_schedules', ['tenant_id'])
            op.execute("""
                UPDATE cached_schedules 
                SET tenant_id = (
                    SELECT tenantID 
                    FROM schedule_definitions 
                    WHERE schedule_definitions.scheduleDefID = cached_schedules.schedule_def_id
                )
            """)
            op.alter_column('cached_schedules', 'tenant_id', nullable=False)

    # Tenants table
    if 'tenants' not in existing_tables:
        op.create_table(
            'tenants',
            sa.Column('tenantID', sa.String(length=36), nullable=False),
            sa.Column('tenantName', sa.String(length=255), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.Column('is_active', sa.Boolean(), nullable=False),
            sa.PrimaryKeyConstraint('tenantID'),
            sa.UniqueConstraint('tenantID'),
        )
        safe_create_index('ix_tenants_tenantName', 'tenants', ['tenantName'])
    else:
        safe_create_index('ix_tenants_tenantName', 'tenants', ['tenantName'])

    # Departments table
    if 'departments' not in existing_tables:
        op.create_table(
            'departments',
            sa.Column('departmentID', sa.String(length=36), nullable=False),
            sa.Column('tenantID', sa.String(length=36), nullable=False),
            sa.Column('departmentName', sa.String(length=255), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('is_active', sa.Boolean(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['tenantID'], ['tenants.tenantID']),
            sa.PrimaryKeyConstraint('departmentID'),
            sa.UniqueConstraint('departmentID'),
        )
        safe_create_index('ix_departments_departmentName', 'departments', ['departmentName'])
        safe_create_index('ix_departments_is_active', 'departments', ['is_active'])
        safe_create_index('ix_departments_tenantID', 'departments', ['tenantID'])

    # Schedule Definitions table
    if 'schedule_definitions' not in existing_tables:
        op.create_table(
            'schedule_definitions',
            sa.Column('scheduleDefID', sa.String(length=36), nullable=False),
            sa.Column('tenantID', sa.String(length=36), nullable=False),
            sa.Column('departmentID', sa.String(length=36), nullable=False),
            sa.Column('scheduleName', sa.String(length=255), nullable=False),
            sa.Column('paramsSheetURL', sa.String(length=500), nullable=False),
            sa.Column('prefsSheetURL', sa.String(length=500), nullable=False),
            sa.Column('resultsSheetURL', sa.String(length=500), nullable=False),
            sa.Column('schedulingAPI', sa.String(length=500), nullable=False),
            sa.Column('remarks', sa.Text(), nullable=True),
            sa.Column('is_active', sa.Boolean(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['departmentID'], ['departments.departmentID']),
            sa.ForeignKeyConstraint(['tenantID'], ['tenants.tenantID']),
            sa.PrimaryKeyConstraint('scheduleDefID'),
            sa.UniqueConstraint('scheduleDefID'),
        )

    # ✅ Always safe: only create if not exists
    safe_create_index('ix_schedule_definitions_scheduleName', 'schedule_definitions', ['scheduleName'])
    safe_create_index('ix_schedule_definitions_departmentID', 'schedule_definitions', ['departmentID'])
    safe_create_index('ix_schedule_definitions_is_active', 'schedule_definitions', ['is_active'])
    safe_create_index('ix_schedule_definitions_tenantID', 'schedule_definitions', ['tenantID'])

    # (You can keep the rest of your existing logic for users, schedules, job logs, etc.)
