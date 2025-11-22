"""Add shift_value to cached_schedules table

Revision ID: add_shift_value_cached
Revises: 0d13865987f1
Create Date: 2025-01-15 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_shift_value_cached'
down_revision = '32f175b5ae3d'  # Changed to point to the latest migration
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
        if 'shift_value' not in existing_columns:
            # Add shift_value column to store raw shift values from Google Sheets
            # This preserves exact values like "C 櫃台人力", "A 藥局人力", etc.
            op.add_column('cached_schedules', 
                         sa.Column('shift_value', sa.String(length=255), nullable=True,
                                  comment='Raw shift value from Google Sheets (e.g., C 櫃台人力, A 藥局人力)'))
            
            # Populate shift_value from shift_type for existing records (backward compatibility)
            # For existing records, use shift_type as the initial value
            op.execute("""
                UPDATE cached_schedules 
                SET shift_value = shift_type
                WHERE shift_value IS NULL AND shift_type IS NOT NULL
            """)
    else:
        # Table doesn't exist - this migration assumes table exists
        # If table doesn't exist, it should be created by a previous migration
        pass


def downgrade() -> None:
    # Remove shift_value column
    from sqlalchemy import inspect
    from alembic import context
    
    conn = context.get_bind()
    inspector = inspect(conn)
    existing_tables = inspector.get_table_names()
    
    if 'cached_schedules' in existing_tables:
        existing_columns = [col['name'] for col in inspector.get_columns('cached_schedules')]
        if 'shift_value' in existing_columns:
            op.drop_column('cached_schedules', 'shift_value')

