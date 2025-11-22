"""add employee_id to users

Revision ID: add_employee_id_users
Revises: 0d13865987f1
Create Date: 2025-01-15

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_employee_id_users'
down_revision = '0d13865987f1'  # Update this to the latest migration
branch_labels = None
depends_on = None


def upgrade():
    from sqlalchemy import inspect
    from alembic import context
    
    conn = context.get_bind()
    inspector = inspect(conn)
    
    # Check if column already exists
    existing_columns = [col['name'] for col in inspector.get_columns('users')]
    
    if 'employee_id' not in existing_columns:
        # Add employee_id column to users table
        op.add_column('users', sa.Column('employee_id', sa.String(255), nullable=True))
        
        # Migrate existing data: Copy sheets_identifier from EmployeeMapping to User.employee_id
        # This ensures existing users get their employee_id set
        # SQLite-compatible syntax
        op.execute("""
            UPDATE users 
            SET employee_id = (
                SELECT em.sheets_identifier 
                FROM employee_mappings em 
                WHERE em.userID = users.userID 
                AND em.is_active = 1 
                LIMIT 1
            )
            WHERE EXISTS (
                SELECT 1 
                FROM employee_mappings em 
                WHERE em.userID = users.userID 
                AND em.is_active = 1
            )
        """)
    else:
        print("Column employee_id already exists, skipping add_column")
    
    # Check if index already exists
    existing_indexes = [idx['name'] for idx in inspector.get_indexes('users')]
    
    if 'ix_users_employee_id' not in existing_indexes:
        # Create index for faster lookups
        op.create_index('ix_users_employee_id', 'users', ['employee_id'], unique=True)
    else:
        print("Index ix_users_employee_id already exists, skipping create_index")


def downgrade():
    # Drop index
    op.drop_index('ix_users_employee_id', table_name='users')
    
    # Drop column
    op.drop_column('users', 'employee_id')

