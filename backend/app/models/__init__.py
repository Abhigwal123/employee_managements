# Models Package - Import all models for easy access
from .tenant import Tenant
from .user import User
from .department import Department
from .schedule_definition import ScheduleDefinition
from .schedule_permission import SchedulePermission
from .schedule_job_log import ScheduleJobLog

# Try to import new models (may not exist yet)
try:
    from .employee_mapping import EmployeeMapping
except ImportError:
    EmployeeMapping = None

try:
    from .sheet_cache import CachedSheetData
except ImportError:
    CachedSheetData = None

try:
    from .cached_schedule import CachedSchedule
except ImportError:
    CachedSchedule = None

try:
    from .sync_log import SyncLog
except ImportError:
    SyncLog = None

# Schedule model removed - not used
Schedule = None

try:
    from .schedule_task import ScheduleTask
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
