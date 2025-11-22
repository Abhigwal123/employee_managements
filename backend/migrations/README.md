# Migrations Folder - Development Tools Only

## ⚠️ NOT FOR PRODUCTION

This folder contains **one-time fix scripts** and **debugging utilities** that should **NOT** be deployed to production.

## What's in This Folder

### One-Time Fix Scripts (Already Applied)
These scripts were used to fix specific issues and are no longer needed:

- `fix_shift_value_column.py` - Added `shift_value` column (already applied)
- `fix_character_encoding.py` - Fixed UTF-8 encoding (already applied)
- `SIMPLE_SQL_FIX.sql` - SQL fix script (already applied)
- `run_sql_fix.ps1` - PowerShell wrapper (Windows only, not needed)

### Debugging/Utility Scripts
These are development tools for inspecting data:

- `view_schedule_data.py` - View schedule data from database
- `inspect_schedule_data.sql` - SQL queries for data inspection

### Reference Documentation
SQL schema reference files (optional, for documentation):

- `create_cached_schedules_table.sql` - Full table schema
- `verify_cached_schedules_schema.sql` - Schema verification queries
- `add_shift_value_column.sql` - Column addition reference

## What IS Needed in Production

### ✅ Alembic Migrations
**Location**: `backend/alembic/versions/`

These are the **actual database migrations** that should be included in production:

- `add_shift_value_to_cached_schedules.py` - Official Alembic migration
- `add_tenant_id_to_cached_schedules.py` - Tenant ID migration
- `e8cb5d7c0e31_add_cached_schedule_and_sync_log_tables.py` - Initial tables
- Other Alembic migration files

**These are automatically included** because they're in `alembic/versions/`, not in `migrations/`.

## Production Deployment

### Docker Build
The `backend/.dockerignore` file excludes the `migrations/` folder, so these files won't be included in production Docker images.

### Manual Deployment
If deploying manually, you can safely exclude this entire folder:

```bash
# Exclude migrations folder
rsync -av --exclude='migrations/' backend/ production-server:/app/
```

## Running Migrations in Production

Use **Alembic** (not the scripts in this folder):

```bash
# In production container
cd /app
alembic upgrade head
```

This will run all migrations from `alembic/versions/`.

## Summary

| Folder | Purpose | Production? |
|--------|---------|-------------|
| `migrations/` | One-time fixes, debugging tools | ❌ **NO** |
| `alembic/versions/` | Official database migrations | ✅ **YES** |

## If You Need to Run a Fix Script

If you need to run one of these fix scripts in production (e.g., after a new deployment):

1. **Copy only the specific script** you need
2. **Run it manually** on the production server
3. **Delete it** after running
4. **Don't include it in the Docker image**

Example:
```bash
# Copy script to production
scp backend/migrations/fix_character_encoding.py production:/tmp/

# Run it
ssh production "cd /app && python /tmp/fix_character_encoding.py"

# Delete it
ssh production "rm /tmp/fix_character_encoding.py"
```

