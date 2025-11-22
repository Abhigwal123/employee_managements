"""
Celery tasks module - exports celery instance and task definitions
"""
from .celery_app import celery, init_celery

__all__ = ['celery', 'init_celery']
