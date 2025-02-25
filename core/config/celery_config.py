"""Celery configuration module."""

from celery.schedules import crontab

# Celery configuration
broker_url = "redis://localhost:6379/0"
result_backend = "redis://localhost:6379/0"

# Task settings
task_serializer = "json"
result_serializer = "json"
accept_content = ["json"]
timezone = "UTC"
enable_utc = True

# Task execution settings
task_track_started = True
task_time_limit = 30 * 60  # 30 minutes
task_soft_time_limit = 25 * 60  # 25 minutes
worker_max_tasks_per_child = 1000
worker_prefetch_multiplier = 1

# Task routing
task_routes = {
    "core.tasks.goal_tasks.*": {"queue": "goals"},
    "core.tasks.price_monitor.*": {"queue": "price_monitor"},
    "core.tasks.notification_tasks.*": {"queue": "notifications"},
    "core.tasks.token_tasks.*": {"queue": "tokens"},
}

# Beat schedule
beat_schedule = {
    "monitor-deals": {
        "task": "core.tasks.price_monitor.monitor_deals",
        "schedule": crontab(minute="*/15"),  # Every 15 minutes
        "options": {
            "expires": 60 * 14,  # 14 minutes
            "retry": True,
            "retry_policy": {
                "max_retries": 3,
                "interval_start": 0,
                "interval_step": 0.2,
                "interval_max": 0.5,
            },
        },
    },
    "process-deals": {
        "task": "core.tasks.price_monitor.process_deals",
        "schedule": crontab(minute=0),  # Every hour
        "options": {
            "expires": 60 * 55,  # 55 minutes
            "retry": True,
            "retry_policy": {
                "max_retries": 3,
                "interval_start": 0,
                "interval_step": 0.2,
                "interval_max": 0.5,
            },
        },
    },
}

# Debug task
task_always_eager = False  # Set to True for testing/debugging 