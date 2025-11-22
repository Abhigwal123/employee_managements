"""make_userid_nullable_in_employee_mappings

Revision ID: 32f175b5ae3d
Revises: add_employee_id_users
Create Date: 2025-11-11 11:13:05.012275

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '32f175b5ae3d'
down_revision = 'add_employee_id_users'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # SQLite doesn't support ALTER COLUMN directly, so we need to use a workaround
    # For SQLite, we'll use a table recreation approach
    from sqlalchemy import inspect
    from alembic import context
    
    conn = context.get_bind()
    inspector = inspect(conn)
    
    # Check if userID column exists and is currently NOT NULL
    existing_columns = {col['name']: col for col in inspector.get_columns('employee_mappings')}
    
    if 'userID' in existing_columns:
        userid_col = existing_columns['userID']
        # If it's already nullable, skip
        if userid_col['nullable']:
            print("userID column is already nullable, skipping migration")
            return
        
        # SQLite workaround: We need to recreate the table
        # Step 1: Create new table with nullable userID
        op.execute("""
            CREATE TABLE employee_mappings_new (
                mappingID VARCHAR(36) NOT NULL,
                userID VARCHAR(36),
                tenantID VARCHAR(36) NOT NULL,
                sheets_identifier VARCHAR(255) NOT NULL,
                sheets_name_id VARCHAR(255),
                employee_sheet_name VARCHAR(255),
                schedule_def_id VARCHAR(36),
                created_at DATETIME NOT NULL,
                updated_at DATETIME,
                is_active BOOLEAN NOT NULL,
                PRIMARY KEY (mappingID),
                UNIQUE (mappingID),
                FOREIGN KEY (schedule_def_id) REFERENCES schedule_definitions(scheduleDefID),
                FOREIGN KEY (tenantID) REFERENCES tenants(tenantID),
                FOREIGN KEY (userID) REFERENCES users(userID)
            )
        """)
        
        # Step 2: Copy data (including NULL userID values if any)
        op.execute("""
            INSERT INTO employee_mappings_new 
            SELECT * FROM employee_mappings
        """)
        
        # Step 3: Drop old table
        op.execute("DROP TABLE employee_mappings")
        
        # Step 4: Rename new table
        op.execute("ALTER TABLE employee_mappings_new RENAME TO employee_mappings")
        
        # Step 5: Recreate indexes
        op.create_index('ix_employee_mappings_schedule_def_id', 'employee_mappings', ['schedule_def_id'], unique=False)
        op.create_index('ix_employee_mappings_sheets_identifier', 'employee_mappings', ['sheets_identifier'], unique=False)
        op.create_index('ix_employee_mappings_tenantID', 'employee_mappings', ['tenantID'], unique=False)
        op.create_index('ix_employee_mappings_userID', 'employee_mappings', ['userID'], unique=True)
    else:
        print("userID column not found, skipping migration")


def downgrade() -> None:
    # Reverse: Make userID NOT NULL again
    from sqlalchemy import inspect
    from alembic import context
    
    conn = context.get_bind()
    inspector = inspect(conn)
    
    existing_columns = {col['name']: col for col in inspector.get_columns('employee_mappings')}
    
    if 'userID' in existing_columns:
        userid_col = existing_columns['userID']
        if not userid_col['nullable']:
            print("userID column is already NOT NULL, skipping downgrade")
            return
        
        # SQLite workaround: Recreate table with NOT NULL userID
        # First, ensure all rows have a userID (set to a default if needed)
        # For safety, we'll only proceed if all rows have userID
        result = conn.execute(sa.text("SELECT COUNT(*) FROM employee_mappings WHERE userID IS NULL"))
        null_count = result.scalar()
        
        if null_count > 0:
            raise ValueError(f"Cannot downgrade: {null_count} rows have NULL userID. Please set userID for all rows first.")
        
        # Create new table with NOT NULL userID
        op.execute("""
            CREATE TABLE employee_mappings_new (
                mappingID VARCHAR(36) NOT NULL,
                userID VARCHAR(36) NOT NULL,
                tenantID VARCHAR(36) NOT NULL,
                sheets_identifier VARCHAR(255) NOT NULL,
                sheets_name_id VARCHAR(255),
                employee_sheet_name VARCHAR(255),
                schedule_def_id VARCHAR(36),
                created_at DATETIME NOT NULL,
                updated_at DATETIME,
                is_active BOOLEAN NOT NULL,
                PRIMARY KEY (mappingID),
                UNIQUE (mappingID),
                FOREIGN KEY (schedule_def_id) REFERENCES schedule_definitions(scheduleDefID),
                FOREIGN KEY (tenantID) REFERENCES tenants(tenantID),
                FOREIGN KEY (userID) REFERENCES users(userID)
            )
        """)
        
        op.execute("""
            INSERT INTO employee_mappings_new 
            SELECT * FROM employee_mappings
        """)
        
        op.execute("DROP TABLE employee_mappings")
        op.execute("ALTER TABLE employee_mappings_new RENAME TO employee_mappings")
        
        # Recreate indexes
        op.create_index('ix_employee_mappings_schedule_def_id', 'employee_mappings', ['schedule_def_id'], unique=False)
        op.create_index('ix_employee_mappings_sheets_identifier', 'employee_mappings', ['sheets_identifier'], unique=False)
        op.create_index('ix_employee_mappings_tenantID', 'employee_mappings', ['tenantID'], unique=False)
        op.create_index('ix_employee_mappings_userID', 'employee_mappings', ['userID'], unique=True)
