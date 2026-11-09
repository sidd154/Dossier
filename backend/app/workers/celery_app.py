"""Celery application and the daily sync schedule."""

from celery import Celery
from celery.schedules import crontab

from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "dossier",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    beat_schedule={
        "daily-source-sync": {
            "task": "app.workers.tasks.sync_all_sources",
            "schedule": crontab(hour=settings.daily_sync_hour_utc, minute=0),
        },
        "mail-schedule-dispatch": {
            "task": "app.workers.tasks.dispatch_mail_schedules",
            "schedule": crontab(minute="*"),
        }
    },
)
