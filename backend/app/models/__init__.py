# Models Package - Import all models for easy access
from app.models.tenant import Tenant
from app.models.user import User
from app.models.department import Department
from app.models.schedule_definition import ScheduleDefinition
from app.models.schedule_permission import SchedulePermission
from app.models.schedule_job_log import ScheduleJobLog

# Try to import new models (may not exist yet)
try:
    from app.models.employee_mapping import EmployeeMapping
except ImportError:
    EmployeeMapping = None

try:
    from app.models.sheet_cache import CachedSheetData
except ImportError:
    CachedSheetData = None

try:
    from app.models.cached_schedule import CachedSchedule
except ImportError:
    CachedSchedule = None

try:
    from app.models.sync_log import SyncLog
except ImportError:
    SyncLog = None

# Schedule model removed - not used
Schedule = None

try:
    from app.models.schedule_task import ScheduleTask
except ImportError:
    ScheduleTask = None

# Legacy alias for backwards compatibility
SheetCache = CachedSheetData

# Export all models
__all__ = [
    'Tenant',
    'User', 
    'Department',
    'ScheduleDefinition',
    'SchedulePermission',
    'ScheduleJobLog',
    'EmployeeMapping',
    'SheetCache',
    'CachedSchedule',
    'SyncLog',
    'ScheduleTask'
]
