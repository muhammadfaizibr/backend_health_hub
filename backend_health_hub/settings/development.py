"""
Development settings for healthcare_platform project.

- Uncomment the next line to enable mock emails (to console)
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

- Note that Django will use the values in this file AND values from
  settings/base.py
"""
from .base import *
from dotenv import load_dotenv
import os

load_dotenv()

DEBUG = os.getenv('DEBUG', default=True)

ALLOWED_HOSTS = ['127.0.0.1', 'localhost']

# Corsheaders (all origins) for development
CORS_ALLOW_ALL_ORIGINS = True

# Speeds up most test runs by skipping the check for circular imports in views.
# It has no effect on the operation of the site in production.
# See PEP 170 for details.  We do this here because it cannot be done in
# settings/base.py -- that module can be imported before this one.
SETTINGS_MODULE = 'backend_health_hub.settings.development'

# Logging
LOGGING['loggers']['django']['level'] = 'DEBUG'