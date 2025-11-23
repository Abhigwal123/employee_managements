"""
Celery Worker Entry Point
Run with: celery -A celery_worker.celery worker --loglevel=info
Or from backend/: celery -A backend.celery_worker.celery worker --loglevel=info
"""
import sys
import os

# 🔧 CRITICAL: Force Redis configuration BEFORE any Celery imports
# This ensures Celery reads Redis URLs from environment before any default AMQP settings
os.environ.setdefault("CELERY_BROKER_URL", "redis://localhost:6379/0")
os.environ.setdefault("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")
os.environ.setdefault("CELERY_BROKER_TRANSPORT", "redis")  # Explicitly set transport to redis
# Explicitly unset any AMQP defaults
os.environ.pop("BROKER_URL", None)  # Remove if exists
os.environ.pop("RABBITMQ_URL", None)  # Remove if exists

# 🔧 CRITICAL: Add project root to sys.path BEFORE any imports
# This ensures run_refactored.py and app.* modules can be imported
# For "from app.*" imports to work, we need PROJECT ROOT in sys.path
# NOT the app directory itself (that would break package imports)
backend_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(backend_dir, ".."))

# CRITICAL: Remove app_dir from sys.path if it exists (it breaks package imports)
# Something else might have added it (e.g., Google Sheets service loader)
app_dir = os.path.abspath(os.path.join(project_root, "app"))
if app_dir in sys.path:
    sys.path.remove(app_dir)

# CRITICAL: Add backend directory FIRST (before project root) so backend/app is found first
# This ensures "from app import create_app" finds backend/app, not root/app
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# Add project root AFTER backend - this allows root app.* imports for run_refactored.py
# But backend/app takes precedence for direct "from app" imports
if project_root not in sys.path:
    sys.path.insert(1, project_root)  # Insert at position 1, not 0

# DO NOT add app_dir to sys.path - that breaks "from app.*" package imports!
# The app directory is a package in the project root, not a standalone path

# Log path setup for debugging
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logger.info(f"[CELERY_WORKER] Backend dir added FIRST to sys.path: {backend_dir}")
logger.info(f"[CELERY_WORKER] Project root added to sys.path: {project_root}")
logger.info(f"[CELERY_WORKER] App package location: {app_dir}")
logger.info(f"[CELERY_WORKER] sys.path[0:3]: {sys.path[0:3]}")
logger.info(f"[CELERY_WORKER] ✅ Backend dir in sys.path first - 'from app' will find backend/app")

# Import backend app (will find backend/app because backend_dir is first in sys.path)
from backend.app import create_app
from backend.app.extensions import init_celery

# Create Flask app and initialize Celery
flask_app = create_app()
celery = init_celery(flask_app)

if celery:
    # Autodiscover tasks from all task modules
    celery.autodiscover_tasks([
        'backend.app.services.celery_tasks',
        'backend.app.tasks.google_sync',
        'backend.app.tasks.tasks'
    ], force=True)
    
    # Also import tasks from celery_tasks module if it exists
    try:
        import celery_tasks
        celery.autodiscover_tasks(['celery_tasks'], force=True)
    except ImportError:
        pass
    
    import logging
    logger = logging.getLogger(__name__)
    logger.info("[CELERY] Task autodiscovery completed")
    logger.info(f"[CELERY] Registered tasks: {list(celery.tasks.keys())}")

# Export celery for celery command
__all__ = ['celery', 'flask_app']



