# backend_health_hub/celery.py

import os
from celery import Celery
from celery.schedules import crontab

# Set default Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend_health_hub.settings')

app = Celery('backend_health_hub')

# Load configuration from Django settings with CELERY_ prefix
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks from all installed apps
app.autodiscover_tasks()

# Celery Beat Schedule
app.conf.beat_schedule = {
    'update-appointment-statuses': {
        'task': 'apps.patients.tasks.update_appointment_statuses',
        'schedule': crontab(minute='*/5'),  # Every 5 minutes
    },
    'process-pending-earnings': {
        'task': 'apps.patients.tasks.process_pending_earnings',
        'schedule': crontab(hour=0, minute=0),  # Daily at midnight
    },
}

app.conf.timezone = 'UTC'

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')