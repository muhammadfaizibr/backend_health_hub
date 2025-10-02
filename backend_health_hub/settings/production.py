"""
Production settings for healthcare_platform project.

- Activate by setting `DJANGO_SETTINGS_MODULE=config.settings.production` in
  your production environment.
- Add your production-specific settings here.
"""
from .base import *
import os
from dotenv import load_dotenv

load_dotenv()

DEBUG = os.getenv('DEBUG', default=False)

ALLOWED_HOSTS = ['127.0.0.1']

# Security
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

# Static files
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'  # Requires whitenoise package

# Email
EMAIL_BACKEND = os.getenv('EMAIL_BACKEND', default='django.core.mail.backends.smtp.EmailBackend')

# Disable debug toolbar & other debug-comfy things
INSTALLED_APPS = [app for app in INSTALLED_APPS if 'debug_toolbar' not in app]
MIDDLEWARE = [mw for mw in MIDDLEWARE if not any(x in mw for x in ['debug', 'corsheaders.middleware.CorsDebug'])]