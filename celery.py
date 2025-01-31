import os
from celery import Celery
from celery.schedules import crontab
from core.config import settings

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

app = Celery(
    'agentic_deals',
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=['core.tasks']
)

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django apps.
app.autodiscover_tasks()

# Configure periodic tasks
app.conf.beat_schedule = {
    'monitor-deals': {
        'task': 'core.tasks.monitor_deals',
        'schedule': crontab(minute='*/15'),  # Every 15 minutes
        'options': {
            'queue': 'monitoring',
            'retry': True,
            'retry_policy': {
                'max_retries': 3,
                'interval_start': 0,
                'interval_step': 0.2,
                'interval_max': 0.5,
            }
        }
    },
    'update-prices': {
        'task': 'core.tasks.update_prices',
        'schedule': crontab(minute=0, hour='*/1'),  # Every hour
        'options': {
            'queue': 'pricing',
            'retry': True,
            'retry_policy': {
                'max_retries': 5,
                'interval_start': 0,
                'interval_step': 0.2,
                'interval_max': 0.5,
            }
        }
    }
}

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
