# Import Refactoring Documentation
## Backend: `app.*` → `backend.app.*` Migration Guide

### Overview
The backend codebase currently uses `app.*` imports, but the actual package structure is `backend.app.*`. This document lists all files that need import refactoring to work correctly in Docker.

---

## Files Requiring Import Changes

### 1. Root Backend Files (outside `backend/app/`)

#### `backend/main.py`
**Current imports:**
- Line 9: `from app import create_app`
- Line 19: `from app.utils.trace_logger import trace_startup`

**Should become:**
- `from backend.app import create_app`
- `from backend.app.utils.trace_logger import trace_startup`

---

#### `backend/celery_worker.py`
**Current imports:**
- Line 55: `from app import create_app`
- Line 56: `from app.extensions import init_celery`

**Should become:**
- `from backend.app import create_app`
- `from backend.app.extensions import init_celery`

---

#### `backend/trigger_sync.py`
**Current imports:**
- Line 11: `from app import create_app, db`
- Line 12: `from app.models import ScheduleDefinition`
- Line 13: `from app.services.google_sheets_sync_service import GoogleSheetsSyncService`

**Should become:**
- `from backend.app import create_app, db`
- `from backend.app.models import ScheduleDefinition`
- `from backend.app.services.google_sheets_sync_service import GoogleSheetsSyncService`

---

#### `backend/alembic/env.py`
**Current imports:**
- Line 16: `from app import create_app`
- Line 17: `from app.extensions import db`
- Line 23: `from app.models import (...)` (multiple models)

**Should become:**
- `from backend.app import create_app`
- `from backend.app.extensions import db`
- `from backend.app.models import (...)` (all model imports)

---

### 2. Core Application Files

#### `backend/app/__init__.py`
**Current imports (Lines 4-28):**
- `from app.config import Config`
- `from app.extensions import db, jwt, cors, init_celery`
- `from app.utils.logger import configure_logging`
- `from app.routes.common_routes import common_bp`
- `from app.routes.auth import auth_bp`
- `from app.routes.sysadmin_routes import sysadmin_bp`
- `from app.routes.clientadmin_routes import clientadmin_bp`
- `from app.routes.schedulemanager_routes import schedulemanager_bp`
- `from app.routes.employee_routes import employee_bp`
- `from app.routes.tenant_routes import tenant_bp`
- `from app.routes.user_routes import user_bp`
- `from app.routes.department_routes import department_bp`
- `from app.routes.schedule_definition_routes import schedule_definition_bp`
- `from app.routes.schedule_permission_routes import schedule_permission_bp`
- `from app.routes.permissions_routes import permissions_bp`
- `from app.routes.schedule_job_log_routes import schedule_job_log_bp`
- `from app.routes.google_sheets_routes import google_sheets_bp`
- `from app.routes.role_routes import role_bp`
- `from app.routes.alert_routes import alert_bp`
- `from app.routes.diagnostic_routes import diagnostic_bp`
- `from app.services.celery_tasks import bind_celery, register_periodic_tasks, register_schedule_execution_task`

**Should become:**
- All `app.*` → `backend.app.*`

---

#### `backend/app/extensions.py`
**Check for any `app.*` imports**

---

#### `backend/app/config.py`
**Check for any `app.*` imports**

---

### 3. Routes Directory (`backend/app/routes/`)

#### `backend/app/routes/auth.py`
**Current imports:**
- Line 4: `from app import db`
- Line 5: `from app.models import User, Tenant`
- Line 14: `from app.utils.security import hash_password, verify_password, validate_password_strength`
- Line 15: `from app.utils.role_utils import (...)`

**Should become:**
- `from backend.app import db`
- `from backend.app.models import User, Tenant`
- `from backend.app.utils.security import ...`
- `from backend.app.utils.role_utils import ...`

---

#### `backend/app/routes/common_routes.py`
**Current imports:**
- Line 21: `from app import db` (inside function)
- Line 437: `from app import db` (inside function)

**Should become:**
- `from backend.app import db`

---

#### `backend/app/routes/user_routes.py`
**Current imports:**
- Line 4: `from app import db`
- Line 5: `from app.models import User, Tenant, EmployeeMapping, SchedulePermission`
- Line 6: `from app.utils.auth import role_required`
- Line 7: `from app.utils.role_utils import EMPLOYEE_ROLE, normalize_role`
- Line 16: `from app.utils.security import sanitize_input`

**Should become:**
- All `app.*` → `backend.app.*`

---

#### `backend/app/routes/sysadmin_routes.py`
**Current imports:**
- Line 4: `from app.models import User, Tenant, ScheduleDefinition, ScheduleJobLog`
- Line 5: `from app.utils.auth import role_required`
- Line 6: `from app.utils.role_utils import is_client_admin_role`

**Should become:**
- All `app.*` → `backend.app.*`

---

#### `backend/app/routes/clientadmin_routes.py`
**Current imports:**
- Line 3: `from app.utils.auth import role_required`
- Line 4: `from app import db`
- Line 5: `from app.models import Department, User`
- Line 6: `from app.utils.security import sanitize_input`

**Should become:**
- All `app.*` → `backend.app.*`

---

#### `backend/app/routes/schedulemanager_routes.py`
**Current imports:**
- Line 4: `from app.utils.auth import role_required`
- Line 6: `from app.services.google_io import summarize_sheet_target, get_default_input_url, get_default_output_url`

**Should become:**
- All `app.*` → `backend.app.*`

---

#### `backend/app/routes/employee_routes.py`
**Current imports:**
- Line 3: `from app import db`
- Line 4: `from app.models import User`
- Line 735: `import app.services.google_sheets_import as sheets_import_module` (inside function)
- Line 877: `from app import db` (inside function)

**Should become:**
- All `app.*` → `backend.app.*`

---

#### `backend/app/routes/tenant_routes.py`
**Current imports:**
- Line 4: `from app import db`
- Line 5: `from app.models import Tenant, User`
- Line 14: `from app.utils.security import sanitize_input`
- Line 15: `from app.utils.role_utils import is_sys_admin_role`

**Should become:**
- All `app.*` → `backend.app.*`

---

#### `backend/app/routes/department_routes.py`
**Current imports:**
- Line 4: `from app import db`
- Line 5: `from app.models import Department, User`
- Line 14: `from app.utils.security import sanitize_input`
- Line 15: `from app.utils.role_utils import is_client_admin_role, is_schedule_manager_role`
- Line 16: `from app.utils.tenant_filter import get_tenant_filtered_query`

**Should become:**
- All `app.*` → `backend.app.*`

---

#### `backend/app/routes/schedule_definition_routes.py`
**Current imports:**
- Line 4: `from app import db`
- Line 5: `from app.models import ScheduleDefinition, User, Department`
- Line 14: `from app.utils.security import sanitize_input`
- Line 15: `from app.utils.role_utils import is_client_admin_role, is_schedule_manager_role`
- Line 16: `from app.utils.tenant_filter import get_tenant_filtered_query`

**Should become:**
- All `app.*` → `backend.app.*`

---

#### `backend/app/routes/schedule_permission_routes.py`
**Current imports:**
- Line 4: `from app import db`
- Line 5: `from app.models import SchedulePermission, User, ScheduleDefinition`
- Line 6: `from app.utils.role_utils import is_client_admin_role, is_schedule_manager_role`

**Should become:**
- All `app.*` → `backend.app.*`

---

#### `backend/app/routes/permissions_routes.py`
**Current imports:**
- Line 4: `from app import db`
- Line 5: `from app.models import SchedulePermission, User, ScheduleDefinition`
- Line 6: `from app.utils.role_utils import is_client_admin_role, is_schedule_manager_role`

**Should become:**
- All `app.*` → `backend.app.*`

---

#### `backend/app/routes/schedule_routes.py`
**Current imports:**
- Line 26: `from app.utils.role_utils import is_client_admin_role, is_schedule_manager_role`
- Line 171: `from app import db` (inside function)
- Line 587: `from app import db` (inside function)

**Should become:**
- All `app.*` → `backend.app.*`

---

#### `backend/app/routes/schedule_job_log_routes.py`
**Current imports:**
- Line 4: `from app import db`
- Line 5: `from app.models import ScheduleJobLog, User, ScheduleDefinition, SchedulePermission`
- Line 6: `from app.utils.role_utils import is_sys_admin_role, is_client_admin_role, normalize_role, SYS_ADMIN_ROLE, CLIENT_ADMIN_ROLE`

**Should become:**
- All `app.*` → `backend.app.*`

---

#### `backend/app/routes/google_sheets_routes.py`
**Current imports:**
- Line 7: `from app.models import User, ScheduleDefinition`
- Line 17: `from app.services.google_sheets_import import (...)`

**Should become:**
- All `app.*` → `backend.app.*`

---

#### `backend/app/routes/alert_routes.py`
**Current imports:**
- Line 4: `from app.models import User`

**Should become:**
- `from backend.app.models import User`

---

#### `backend/app/routes/diagnostic_routes.py`
**Current imports:**
- Line 6: `from app.models import User, CachedSchedule, ScheduleDefinition, EmployeeMapping`

**Should become:**
- `from backend.app.models import User, CachedSchedule, ScheduleDefinition, EmployeeMapping`

---

### 4. Models Directory (`backend/app/models/`)

#### `backend/app/models/__init__.py`
**Current imports (Lines 2-7):**
- `from app.models.tenant import Tenant`
- `from app.models.user import User`
- `from app.models.department import Department`
- `from app.models.schedule_definition import ScheduleDefinition`
- `from app.models.schedule_permission import SchedulePermission`
- `from app.models.schedule_job_log import ScheduleJobLog`

**Should become:**
- All `app.models.*` → `backend.app.models.*`

**Note:** These are relative imports within the same package. Consider converting to relative imports:
- `from .tenant import Tenant`
- `from .user import User`
- etc.

---

#### `backend/app/models/user.py`
**Current imports:**
- Line 2: `from app import db`
- Line 9: `from app.utils.role_utils import (...)`

**Should become:**
- `from backend.app import db`
- `from backend.app.utils.role_utils import ...`

---

#### `backend/app/models/tenant.py`
**Current imports:**
- Line 2: `from app import db`

**Should become:**
- `from backend.app import db`

---

#### `backend/app/models/department.py`
**Current imports:**
- Line 2: `from app import db`

**Should become:**
- `from backend.app import db`

---

#### `backend/app/models/schedule_definition.py`
**Current imports:**
- Line 2: `from app import db`

**Should become:**
- `from backend.app import db`

---

#### `backend/app/models/schedule_permission.py`
**Current imports:**
- Line 2: `from app import db`

**Should become:**
- `from backend.app import db`

---

#### `backend/app/models/schedule_job_log.py`
**Current imports:**
- Line 2: `from app import db`

**Should become:**
- `from backend.app import db`

---

#### `backend/app/models/schedule_task.py`
**Current imports:**
- Line 7: `from app.extensions import db`
- Line 8: `from app.database.connection import Base as AlembicBase`

**Should become:**
- `from backend.app.extensions import db`
- `from backend.app.database.connection import Base as AlembicBase`

---

#### `backend/app/models/cached_schedule.py`
**Current imports:**
- Line 6: `from app import db`

**Should become:**
- `from backend.app import db`

---

#### `backend/app/models/sheet_cache.py`
**Current imports:**
- Line 6: `from app import db`

**Should become:**
- `from backend.app import db`

---

#### `backend/app/models/sync_log.py`
**Current imports:**
- Line 5: `from app import db`

**Should become:**
- `from backend.app import db`

---

#### `backend/app/models/employee_mapping.py`
**Current imports:**
- Line 5: `from app import db`

**Should become:**
- `from backend.app import db`

---

### 5. Services Directory (`backend/app/services/`)

#### `backend/app/services/celery_tasks.py`
**Current imports:**
- Line 5: `from app.extensions import init_celery`
- Line 7: `from app.services.google_io import get_default_input_url, get_default_output_url`
- Line 119: `from app import db` (inside function)
- Line 330: `from app import db` (inside function)
- Line 435: `from app import db` (inside function)
- Line 538: `from app import db` (inside function)
- Line 601: `from app import db` (inside function)
- Line 672: `from app import db` (inside function)

**Should become:**
- All `app.*` → `backend.app.*`

---

#### `backend/app/services/schedule_executor.py`
**Current imports:**
- Line 10: `from app import db`
- Line 11: `from app.models import ScheduleJobLog`

**Should become:**
- `from backend.app import db`
- `from backend.app.models import ScheduleJobLog`

---

#### `backend/app/services/dashboard_data_service.py`
**Current imports:**
- Line 16: `import app.services.google_sheets_import as sheets_import_module`
- Line 17: `from app.services.google_sheets_import import (...)`
- Line 22: `from app.utils.role_utils import is_client_admin_role`
- Line 233: `from app import db` (inside function)

**Should become:**
- All `app.*` → `backend.app.*`

---

#### `backend/app/services/google_sheets_sync_service.py`
**Current imports:**
- Line 14: `from app import db`
- Line 24: `from app.services.dashboard_data_service import DashboardDataService`
- Line 26: `import app.services.google_sheets_import as sheets_import_module`

**Should become:**
- All `app.*` → `backend.app.*`

---

#### `backend/app/services/auto_regeneration_service.py`
**Current imports:**
- Line 14: `from app import db`
- Line 15: `from app.models import ScheduleDefinition, ScheduleJobLog`

**Should become:**
- `from backend.app import db`
- `from backend.app.models import ScheduleDefinition, ScheduleJobLog`

---

### 6. Tasks Directory (`backend/app/tasks/`)

#### `backend/app/tasks/tasks.py`
**Current imports:**
- Line 10: `from app.tasks.celery_app import celery`
- Line 11: `from app.extensions import db`
- Line 13: `from app.models.schedule_task import ScheduleTask`
- Line 14: `from app.scheduling.integration import run_scheduling_task_saas`

**Should become:**
- `from backend.app.tasks.celery_app import celery`
- `from backend.app.extensions import db`
- `from backend.app.models.schedule_task import ScheduleTask`
- `from backend.app.scheduling.integration import run_scheduling_task_saas`

**Note:** `from app.tasks.celery_app` could be relative: `from .celery_app import celery`

---

#### `backend/app/tasks/google_sync.py`
**Current imports:**
- Line 7: `from app import db`
- Line 8: `from app.models import ScheduleDefinition, SyncLog`
- Line 9: `from app.services.google_sheets_sync_service import GoogleSheetsSyncService`

**Should become:**
- All `app.*` → `backend.app.*`

---

### 7. Utils Directory (`backend/app/utils/`)

#### `backend/app/utils/auth.py`
**Current imports:**
- Line 5: `from app.utils.role_utils import normalize_role`

**Should become:**
- `from backend.app.utils.role_utils import normalize_role`

**Note:** Could be relative: `from .role_utils import normalize_role`

---

#### `backend/app/utils/db.py`
**Current imports:**
- Line 42: `from app import db` (inside function)
- Line 102: `from app import db` (inside function)

**Should become:**
- `from backend.app import db`

---

#### `backend/app/utils/register_user_helper.py`
**Current imports:**
- Line 8: `from app.models import User`
- Line 9: `from app.utils.role_utils import (...)`

**Should become:**
- `from backend.app.models import User`
- `from backend.app.utils.role_utils import ...`

---

#### `backend/app/utils/tenant_filter.py`
**Current imports:**
- Line 8: `from app.extensions import db`
- Line 9: `from app.utils.role_utils import is_client_admin_role`

**Should become:**
- `from backend.app.extensions import db`
- `from backend.app.utils.role_utils import is_client_admin_role`

---

#### `backend/app/utils/sync_guard.py`
**Current imports:**
- Line 13: `from app.models import CachedSchedule, SyncLog, ScheduleDefinition, User, EmployeeMapping`
- Line 14: `from app.services.google_sheets_sync_service import GoogleSheetsSyncService`

**Should become:**
- All `app.*` → `backend.app.*`

---

### 8. Scheduling Directory (`backend/app/scheduling/`)

#### `backend/app/scheduling/integration.py`
**Current imports:**
- Line 58: `logger.info(f"[INTEGRATION] Attempting to import app.* modules...")` (log message only)
- Line 109: `logger.error(f"[INTEGRATION] ❌ FAILED to import app.* modules: {e}")` (log message only)
- Line 112: `raise ImportError(f"Cannot import app.* modules. App dir: {app_dir_str}, Error: {e}")` (error message only)

**Note:** These are log/error messages, not actual imports. May need to update for clarity.

---

### 9. Special Files

#### `backend/run_refactored.py`
**Current references:**
- Line 63: `_path_logger.info(f"[RUN_REFACTORED] Attempting to import app.* modules...")` (log message)
- Line 170: Comment mentions `from app import db`
- Line 198: `import app` (dynamic import)
- Line 220: `_path_logger.error(f"[RUN_REFACTORED] ❌ FAILED to import app.* modules: {e}")` (log message)
- Line 226: `raise ImportError(f"Cannot import app.* modules. App dir: {app_dir}, Error: {e}")` (error message)

**Note:** This file imports from the ROOT `app/` directory (not `backend/app/`), so it may need special handling. The imports here are for the legacy scheduling system in the root `app/` folder, not the backend.

---

## Summary Statistics

### Total Files Requiring Changes: **47 files**

**Breakdown by directory:**
- Root backend files: 4 files (`main.py`, `celery_worker.py`, `trigger_sync.py`, `alembic/env.py`)
- `backend/app/__init__.py`: 1 file
- Routes: 17 files
- Models: 11 files
- Services: 5 files
- Tasks: 2 files
- Utils: 5 files
- Scheduling: 1 file (mostly log messages)
- Special: 1 file (`run_refactored.py` - may need special handling)

### Total Import Statements to Change: **~148 import statements**

---

## Special Considerations

### 1. Relative Imports
Some imports within the same package can be converted to relative imports:
- `from app.models.tenant import Tenant` → `from .tenant import Tenant` (in `models/__init__.py`)
- `from app.tasks.celery_app import celery` → `from .celery_app import celery` (in `tasks/tasks.py`)
- `from app.utils.role_utils import ...` → `from .role_utils import ...` (within utils)

### 2. Circular Import Prevention
After refactoring, watch for circular imports. Convert to relative imports or use lazy imports inside functions if needed.

### 3. Dynamic Imports
Some files use dynamic imports (e.g., `import app`). These need special handling:
- `backend/run_refactored.py` - imports root `app/`, not `backend/app/`
- `backend/app/scheduling/integration.py` - may have dynamic imports

### 4. Alembic Migrations
- `backend/alembic/env.py` needs updating
- Migration files in `backend/alembic/versions/` may also need checking

---

## Recommended Refactoring Order

1. **Start with core files:**
   - `backend/app/__init__.py`
   - `backend/app/extensions.py`
   - `backend/app/config.py`

2. **Then models:**
   - `backend/app/models/__init__.py` (convert to relative imports)
   - Individual model files

3. **Then utilities:**
   - `backend/app/utils/*.py`

4. **Then services:**
   - `backend/app/services/*.py`

5. **Then routes:**
   - `backend/app/routes/*.py`

6. **Then tasks:**
   - `backend/app/tasks/*.py`

7. **Finally root files:**
   - `backend/main.py`
   - `backend/celery_worker.py`
   - `backend/trigger_sync.py`
   - `backend/alembic/env.py`

---

## Testing Checklist

After refactoring, test:
- [ ] Backend server starts (`python backend/main.py`)
- [ ] Celery worker starts (`celery -A celery_worker.celery worker`)
- [ ] All routes are accessible
- [ ] Database migrations work (`alembic upgrade head`)
- [ ] All services import correctly
- [ ] No circular import errors
- [ ] Docker build succeeds
- [ ] Docker containers start without import errors

---

## Notes

- **DO NOT** rename any folders or files
- **ONLY** change import statements
- Keep relative imports where appropriate (same package)
- Update log/error messages that reference `app.*` for clarity
- Test thoroughly after each batch of changes

