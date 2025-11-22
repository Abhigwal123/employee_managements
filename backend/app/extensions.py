import platform
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager
from flask_cors import CORS


# Core extensions singletons
# SQLAlchemy - engine_options will be read from app.config['SQLALCHEMY_ENGINE_OPTIONS']
# Note: Flask-SQLAlchemy 3.x automatically reads SQLALCHEMY_ENGINE_OPTIONS from app.config
# We can also pass engine_options here as defaults, but config takes precedence
db = SQLAlchemy()
jwt = JWTManager()
cors = CORS()


celery = None  # type: ignore[assignment]


def init_celery(app):
    global celery
    if celery is not None:
        return celery

    # Import Celery lazily to avoid hard dependency for API-only runs
    try:
        from celery import Celery  # type: ignore
    except Exception as e:
        # Celery not available in this process (e.g., while upgrading); skip init
        return None

    # Extract broker and backend URLs from Flask config (support both old and new names)
    # Use Redis database 0 for broker and database 1 for result backend
    broker_url = app.config.get("CELERY_BROKER_URL") or app.config.get("broker_url", "redis://localhost:6379/0")
    result_backend = app.config.get("CELERY_RESULT_BACKEND") or app.config.get("result_backend", "redis://localhost:6379/1")

    # 🔧 CRITICAL: Ensure environment variables are set to prevent AMQP defaults
    import os
    os.environ["CELERY_BROKER_URL"] = broker_url
    os.environ["CELERY_RESULT_BACKEND"] = result_backend
    os.environ["CELERY_BROKER_TRANSPORT"] = "redis"  # Explicitly set transport to redis

    celery = Celery(
        "projectup",
        broker=broker_url,
        backend=result_backend,
        include=[
            "app.services.celery_tasks",
            "app.tasks.google_sync",
            "app.tasks.tasks"
        ]
    )
    
    # Autodiscover tasks from all task modules
    celery.autodiscover_tasks([
        'app.services.celery_tasks',
        'app.tasks.google_sync',
        'app.tasks.tasks'
    ], force=True)
    
    # Store Celery instance in Flask app extensions for easy access
    app.extensions['celery'] = celery

    # Use ONLY new-style Celery 5+ configuration keys
    # DO NOT pass entire Flask config as it contains old-style CELERY_* keys
    # Explicitly set broker_url and result_backend to override any defaults
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
    
    # 🔧 FORCE broker URL and transport again to ensure they're not overridden by any defaults
    celery.conf.broker_url = broker_url
    celery.conf.result_backend = result_backend
    celery.conf.broker_transport = "redis"
    celery.conf.enable_test_tasks = bool(app.config.get("ENABLE_TEST_CELERY_TASKS", False))

    # 🪟 Windows Fix: Use solo pool to prevent PermissionError (WinError 5)
    # Windows cannot use the prefork pool due to multiprocessing limitations
    if platform.system() == "Windows":
        celery.conf.worker_pool = "solo"

    TaskBase = celery.Task

    class ContextTask(TaskBase):
        abstract = True

        def __call__(self, *args, **kwargs):
            with app.app_context():
                return TaskBase.__call__(self, *args, **kwargs)

    celery.Task = ContextTask
    return celery


