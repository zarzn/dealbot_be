"""Celery configuration for the application."""

from celery.schedules import crontab

# Broker and result backend settings
broker_url = "redis://redis:6379/0"
result_backend = "redis://redis:6379/0"

# Task serialization settings
task_serializer = "json"
result_serializer = "json"
accept_content = ["json"]
timezone = "UTC"
enable_utc = True

# Task execution settings
task_track_started = True
worker_concurrency = 4  # Number of worker processes (adjust based on your CPU)
broker_connection_retry_on_startup = True  # Retry connecting to broker on startup
task_time_limit = 1800  # 30 minutes in seconds
task_soft_time_limit = 1500  # 25 minutes in seconds
worker_max_tasks_per_child = 1000
worker_prefetch_multiplier = 1

# Task routing configurations
task_routes = {
    "core.tasks.market_monitor.*": {"queue": "market_monitor"},
    "core.tasks.price_tracker.*": {"queue": "price_tracker"},
    "core.tasks.deal_processor.*": {"queue": "deal_processor"},
    "core.tasks.ai_processor.*": {"queue": "ai_processor"},
    "core.tasks.notification.*": {"queue": "notification"},
    "core.tasks.background_tasks.*": {"queue": "background"},
}

# Result backend settings
result_expires = 86400  # Results expire after 1 day (in seconds)
result_extended = True  # Extended result information

# Beat scheduler settings
beat_schedule = {
    "monitor-markets-every-30-min": {
        "task": "core.tasks.market_monitor.monitor_markets",
        "schedule": 1800.0,  # Every 30 minutes
    },
    "update-price-trackers-every-hour": {
        "task": "core.tasks.price_tracker.update_price_trackers",
        "schedule": 3600.0,  # Every hour
    },
    "clean-expired-deals-daily": {
        "task": "core.tasks.deal_processor.clean_expired_deals",
        "schedule": 86400.0,  # Every day
    },
    "process-notifications-every-5-min": {
        "task": "core.tasks.notification.process_pending_notifications",
        "schedule": 300.0,  # Every 5 minutes
    },
}

# Debug task
task_always_eager = False  # Set to True for testing/debugging 