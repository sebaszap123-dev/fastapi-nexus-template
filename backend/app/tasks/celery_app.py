from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

# Create Celery app
celery_app = Celery(
    "suremind",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

# Celery configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes hard limit
    task_soft_time_limit=25 * 60,  # 25 minutes soft limit
    worker_prefetch_multiplier=4,
    worker_max_tasks_per_child=1000,
)

# Task routing
celery_app.conf.task_routes = {
    "app.tasks.example.*": {"queue": "default"},
    "app.tasks.cleanup.*": {"queue": "cleanup"},
    "user_cleanup.*": {"queue": "cleanup"},
}

# Celery Beat schedule (periodic tasks)
celery_app.conf.beat_schedule = {
    # User cleanup tasks
    "delete-expired-users": {
        "task": "user_cleanup.delete_expired_users",
        "schedule": crontab(hour="2", minute="0"),  # Daily at 2:00 AM UTC
    },
    "send-deletion-reminders": {
        "task": "user_cleanup.send_deletion_reminders",
        "schedule": crontab(hour="10", minute="0"),  # Daily at 10:00 AM UTC
    },
    "cleanup-expired-tokens": {
        "task": "user_cleanup.cleanup_expired_tokens",
        "schedule": crontab(hour="3", minute="0"),  # Daily at 3:00 AM UTC
    },
}

# Auto-discover tasks in the tasks module
celery_app.autodiscover_tasks(["app.tasks"])
