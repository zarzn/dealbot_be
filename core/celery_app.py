"""Celery application configuration module.

This module configures the Celery application for the AI Agentic Deals System,
including task routing, scheduling, monitoring, and error handling.
"""

from celery import Celery, signals
from celery.schedules import crontab
from celery.signals import task_prerun, task_postrun, worker_process_init
from datetime import timedelta
import os
import psutil
from typing import Any, Dict
from prometheus_client import Counter, Histogram, Gauge

from backend.core.config import settings
from backend.core.utils.logger import get_logger
from backend.core.metrics.celery import CeleryMetrics

logger = get_logger(__name__)
metrics = CeleryMetrics()

# Initialize Celery app
celery_app = Celery(
    "deals_system",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "backend.core.tasks.deal_tasks",
        "backend.core.tasks.notification_tasks",
        "backend.core.tasks.token_tasks"
    ]
)

# Configure Celery
celery_app.conf.update(
    # Task settings
    task_serializer=settings.CELERY_TASK_SERIALIZER,
    accept_content=settings.CELERY_ACCEPT_CONTENT,
    result_serializer=settings.CELERY_RESULT_SERIALIZER,
    timezone=settings.CELERY_TIMEZONE,
    enable_utc=settings.CELERY_ENABLE_UTC,
    
    # Task execution settings
    task_time_limit=settings.CELERY_TASK_TIME_LIMIT,
    task_soft_time_limit=settings.CELERY_TASK_SOFT_TIME_LIMIT,
    worker_max_tasks_per_child=1000,
    worker_prefetch_multiplier=1,  # Prevent worker starvation
    task_acks_late=True,  # Prevent task loss
    task_reject_on_worker_lost=True,  # Requeue tasks if worker dies
    task_default_rate_limit="100/m",  # Default rate limit
    
    # Result backend settings
    result_expires=timedelta(days=1),
    result_backend_always_retry=True,
    result_backend_max_retries=10,
    result_backend_transport_options={
        "retry_policy": {
            "max_retries": 3,
            "interval_start": 0,
            "interval_step": 0.2,
            "interval_max": 0.5,
        }
    },
    
    # Broker settings
    broker_connection_timeout=30,
    broker_connection_retry=True,
    broker_connection_max_retries=None,
    broker_transport_options={
        "visibility_timeout": 3600,  # 1 hour
        "max_connections": 100,
        "socket_timeout": 30,
        "socket_connect_timeout": 30
    },
    
    # Beat settings (periodic tasks)
    beat_schedule={
        # Deal monitoring tasks
        "monitor_prices": {
            "task": "backend.core.tasks.deal_tasks.monitor_prices",
            "schedule": timedelta(minutes=30),
            "options": {
                "expires": 600,  # 10 minutes
                "retry": True,
                "retry_policy": {
                    "max_retries": 3,
                    "interval_start": 0,
                    "interval_step": 0.2,
                    "interval_max": 0.5
                }
            }
        },
        "cleanup_expired_deals": {
            "task": "backend.core.tasks.deal_tasks.cleanup_expired_deals",
            "schedule": crontab(hour="*/6", minute=0),  # Every 6 hours
            "options": {
                "expires": 3600,  # 1 hour
                "retry": True
            }
        },
        
        # Notification tasks
        "cleanup_old_notifications": {
            "task": "backend.core.tasks.notification_tasks.cleanup_old_notifications",
            "schedule": crontab(hour=0, minute=0),  # Daily at midnight
            "args": (settings.NOTIFICATION_RETENTION_DAYS,),
            "options": {
                "expires": 3600,  # 1 hour
                "retry": True
            }
        },
        "process_notifications": {
            "task": "backend.core.tasks.notification_tasks.process_notifications",
            "schedule": timedelta(minutes=5),
            "options": {
                "expires": 300,  # 5 minutes
                "retry": True,
                "rate_limit": "100/m"
            }
        },
        
        # Token tasks
        "update_token_prices": {
            "task": "backend.core.tasks.token_tasks.update_token_prices",
            "schedule": timedelta(minutes=15),
            "options": {
                "expires": 600,  # 10 minutes
                "retry": True,
                "retry_policy": {
                    "max_retries": 3,
                    "interval_start": 0,
                    "interval_step": 0.2,
                    "interval_max": 0.5
                }
            }
        },
        "process_token_transactions": {
            "task": "backend.core.tasks.token_tasks.process_token_transactions",
            "schedule": timedelta(minutes=5),
            "options": {
                "expires": 300,  # 5 minutes
                "retry": True,
                "rate_limit": "50/m"
            }
        }
    },
    
    # Task routing
    task_routes={
        # Deal tasks
        "backend.core.tasks.deal_tasks.monitor_prices": {
            "queue": "deals_high"
        },
        "backend.core.tasks.deal_tasks.*": {
            "queue": "deals"
        },
        
        # Notification tasks
        "backend.core.tasks.notification_tasks.process_notifications": {
            "queue": "notifications_high"
        },
        "backend.core.tasks.notification_tasks.*": {
            "queue": "notifications"
        },
        
        # Token tasks
        "backend.core.tasks.token_tasks.update_token_prices": {
            "queue": "tokens_high"
        },
        "backend.core.tasks.token_tasks.*": {
            "queue": "tokens"
        }
    },
    
    # Queue settings
    task_queues={
        # Deal queues
        "deals_high": {
            "exchange": "deals",
            "routing_key": "deals.high",
            "queue_arguments": {"x-max-priority": 10}
        },
        "deals": {
            "exchange": "deals",
            "routing_key": "deals.default",
            "queue_arguments": {"x-max-priority": 5}
        },
        
        # Notification queues
        "notifications_high": {
            "exchange": "notifications",
            "routing_key": "notifications.high",
            "queue_arguments": {"x-max-priority": 10}
        },
        "notifications": {
            "exchange": "notifications",
            "routing_key": "notifications.default",
            "queue_arguments": {"x-max-priority": 5}
        },
        
        # Token queues
        "tokens_high": {
            "exchange": "tokens",
            "routing_key": "tokens.high",
            "queue_arguments": {"x-max-priority": 10}
        },
        "tokens": {
            "exchange": "tokens",
            "routing_key": "tokens.default",
            "queue_arguments": {"x-max-priority": 5}
        }
    },
    
    # Task default settings
    task_default_queue="default",
    task_default_exchange="default",
    task_default_routing_key="default",
    task_queue_max_priority=10,
    task_default_priority=5,
    
    # Logging
    worker_hijack_root_logger=False,
    worker_log_format=(
        "[%(asctime)s: %(levelname)s/%(processName)s] "
        "[%(task_name)s] %(message)s"
    ),
    worker_task_log_format=(
        "[%(asctime)s: %(levelname)s/%(processName)s] "
        "[%(task_name)s(%(task_id)s)] %(message)s"
    )
)

# Environment-specific configuration
if settings.ENVIRONMENT == "production":
    celery_app.conf.update(
        broker_pool_limit=None,
        worker_concurrency=os.cpu_count() * 2,
        worker_max_memory_per_child=350000,  # 350MB
        worker_proc_alive_timeout=60.0,
        worker_cancel_long_running_tasks_on_connection_loss=True
    )
else:
    celery_app.conf.update(
        broker_pool_limit=10,
        worker_concurrency=2,
        worker_max_memory_per_child=200000  # 200MB
    )

# Task lifecycle hooks
@task_prerun.connect
def task_prerun_handler(task_id: str, task: Any, args: tuple, kwargs: Dict, **_):
    """Handle task pre-run events."""
    metrics.task_started(task.name)
    logger.info(
        f"Starting task {task.name}",
        extra={
            "task_id": task_id,
            "args": args,
            "kwargs": kwargs
        }
    )

@task_postrun.connect
def task_postrun_handler(task_id: str, task: Any, state: str, **_):
    """Handle task post-run events."""
    metrics.task_completed(task.name, state)
    logger.info(
        f"Task {task.name} completed",
        extra={
            "task_id": task_id,
            "state": state
        }
    )

# Error handling
@celery_app.task_failure.connect
def handle_task_failure(
    task_id: str,
    exception: Exception,
    args: tuple,
    kwargs: Dict,
    traceback: Any,
    einfo: Any,
    **_
):
    """Handle task failure with detailed logging and metrics."""
    metrics.task_failed(sender.name, type(exception).__name__)
    logger.error(
        f"Task {sender.name} failed",
        extra={
            "task_id": task_id,
            "exception_type": type(exception).__name__,
            "exception": str(exception),
            "args": args,
            "kwargs": kwargs,
            "traceback": str(traceback),
            "error_info": str(einfo)
        },
        exc_info=True
    )

@celery_app.task_retry.connect
def handle_task_retry(sender: Any, reason: str, request: Any, einfo: Any, **_):
    """Handle task retry events with metrics."""
    metrics.task_retried(sender.name, str(reason))
    logger.warning(
        f"Task {sender.name} being retried",
        extra={
            "task_id": request.id,
            "reason": str(reason),
            "error_info": str(einfo),
            "retry_count": request.retries
        }
    )

@celery_app.task_revoked.connect
def handle_task_revoked(
    sender: Any,
    terminated: bool,
    signum: int,
    expired: bool,
    **_
):
    """Handle task revocation events."""
    metrics.task_revoked(sender.name)
    logger.warning(
        f"Task {sender.name} revoked",
        extra={
            "task_id": sender.request.id,
            "terminated": terminated,
            "signal": signum,
            "expired": expired
        }
    )

# Worker lifecycle hooks
@signals.worker_ready.connect
def handle_worker_ready(**_):
    """Handle worker ready event with metrics."""
    metrics.worker_started()
    logger.info(
        "Celery worker ready",
        extra={
            "hostname": celery_app.conf.hostname,
            "concurrency": celery_app.conf.worker_concurrency
        }
    )

@signals.worker_shutdown.connect
def handle_worker_shutdown(**_):
    """Handle worker shutdown event."""
    metrics.worker_stopped()
    logger.info("Celery worker shutting down")

@worker_process_init.connect
def worker_process_init_handler(**_):
    """Initialize worker process with resource monitoring."""
    process = psutil.Process()
    metrics.worker_process_started()
    logger.info(
        "Worker process initialized",
        extra={
            "pid": process.pid,
            "memory_info": process.memory_info()._asdict()
        }
    )

# Periodic task monitoring
@signals.beat_init.connect
def handle_beat_init(**_):
    """Handle beat scheduler initialization."""
    logger.info("Celery beat scheduler starting")

@signals.beat_embedded_init.connect
def handle_beat_embedded_init(**_):
    """Handle embedded beat scheduler initialization."""
    logger.info("Embedded beat scheduler starting")