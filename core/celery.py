"""Celery application module."""

import os
from celery import Celery
from core.config import get_settings

settings = get_settings()

# Create the Celery app
app = Celery(
    "agentic_deals",
    broker=str(settings.REDIS_URL),
    backend=str(settings.REDIS_URL)
)

# Load configuration from celery_config module
app.config_from_object("core.config.celery_config")

# Auto-discover tasks in all registered app modules
app.autodiscover_tasks([
    "core.tasks.goal_tasks",
    "core.tasks.price_monitor",
    "core.tasks.notification_tasks",
    "core.tasks.token_tasks",
])

# Debug task
@app.task(bind=True)
def debug_task(self):
    """Debug task to test Celery configuration."""
    print(f"Request: {self.request!r}")

# Export the app
celery_app = app
__all__ = ["celery_app", "app"] 