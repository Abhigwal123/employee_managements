"""
Celery application configuration with optional disable mode.

If environment variable ENABLE_CELERY is not set to "true", this module
exposes a MockCelery that runs tasks synchronously via .delay().
"""

import os
import platform
from celery import Celery

# Use new-style configuration keys (extract from old-style env vars for backward compatibility)
# Use Redis database 0 for broker and database 1 for result backend
broker_url = os.getenv("CELERY_BROKER_URL") or os.getenv("broker_url") or "redis://localhost:6379/0"
result_backend = os.getenv("CELERY_RESULT_BACKEND") or os.getenv("result_backend") or "redis://localhost:6379/1"

class _MockTask:
    def __init__(self, fn):
        self._fn = fn

    def delay(self, *args, **kwargs):
        return self._fn(*args, **kwargs)

    __call__ = delay


class MockCelery:
    def task(self, *dargs, **dkwargs):
        def _decorator(fn):
            return _MockTask(fn)
        return _decorator


celery = Celery(
    "projectup",
    broker=broker_url,
    backend=result_backend,
    include=["app.tasks.tasks", "app.tasks.google_sync"],
)

def init_celery(flask_app):
    # Use ONLY new-style Celery 5+ configuration keys
    celery.conf.update(
        broker_url=broker_url,
        result_backend=result_backend,
        # 🔧 CRITICAL: Explicitly set broker_transport to "redis" to prevent AMQP defaults
        broker_transport="redis",
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="Asia/Kolkata",
        enable_utc=True,
        task_track_started=True,
        worker_prefetch_multiplier=1,
        worker_max_tasks_per_child=1000,
        result_expires=3600,
    )
    
    # 🔧 FORCE broker transport to ensure it's not overridden
    celery.conf.broker_transport = "redis"
    
    # 🪟 Windows Fix: Use solo pool to prevent PermissionError (WinError 5)
    # Windows cannot use the prefork pool due to multiprocessing limitations
    if platform.system() == "Windows":
        celery.conf.worker_pool = "solo"
    
    # Configure beat schedule for periodic tasks
    from celery.schedules import crontab
    from datetime import timedelta
    celery.conf.beat_schedule = {
        'daily-google-sheet-sync': {
            'task': 'app.tasks.google_sync.sync_google_sheets_daily',
            'schedule': crontab(minute=0, hour=0),  # Run daily at midnight (00:00)
        },
        # Also run every 4 hours to catch any missed syncs
        'periodic-google-sheet-sync': {
            'task': 'app.tasks.google_sync.sync_google_sheets_daily',
            'schedule': crontab(minute=0, hour='*/4'),  # Every 4 hours (00:00, 04:00, 08:00, 12:00, 16:00, 20:00)
        },
        # Sync Google Sheets metadata every 5 minutes for real-time data freshness
        'sync-all-sheets-metadata': {
            'task': 'app.tasks.google_sync.sync_all_sheets_metadata',
            'schedule': timedelta(minutes=5),  # Every 5 minutes
        },
        # Auto-ensure schedule sync every 10 minutes - checks all employees and triggers sync if needed
        'auto-ensure-schedule-sync': {
            'task': 'app.tasks.google_sync.ensure_schedule_auto_sync',
            'schedule': timedelta(minutes=10),  # Every 10 minutes
        },
    }

    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with flask_app.app_context():
                return self.run(*args, **kwargs)

    celery.Task = ContextTask
    return celery

