import os

# Basic SQLite configuration
#DATABASES = {
#    'default': {
#        'ENGINE': 'django.db.backends.sqlite3',
#        'NAME': '/var/run/gource_studio/app.db',
#    }
#}

# Database configuration (configurable through environment variables)
DATABASES = {
    'default': {
        'ENGINE': os.environ.get('SQL_ENGINE', 'django.db.backends.postgresql'),
        'NAME': os.environ.get('SQL_DATABASE', 'gource_studio'),
        'USER': os.environ.get('SQL_USER', 'gource_studio_user'),
        'PASSWORD': os.environ.get('SQL_PASSWORD', 'password'),
        'HOST': os.environ.get('SQL_HOST', 'pgdb'),
        'PORT': os.environ.get('SQL_PORT', '5432'),
    }
}

# Enable debugging
DEBUG = os.environ.get('DEBUG', 'True').lower() in ('true', '1', 'on')

# Timezone information
TIME_ZONE = os.environ.get('TIME_ZONE', 'US/Eastern')
CELERY_TIMEZONE = TIME_ZONE

# Allowed connection hosts (space-delimited)
ALLOWED_HOSTS = os.environ.get('DJANGO_ALLOWED_HOSTS', '*').split(" ")

# Custom SECRET_KEY
if os.environ.get('SECRET_KEY'):
    SECRET_KEY = os.environ['SECRET_KEY']

# Celery configuration
CELERY_BROKER_URL = os.environ.get('CELERY_BROKER', 'redis://redis:6379')
CELERY_RESULT_BACKEND = os.environ.get('CELERY_BACKEND', 'redis://redis:6379')

MEDIA_ROOT = "/var/run/gource_studio/media"

#if DEBUG:
#    INTERNAL_IPS = ["127.0.0.1"]
#    INSTALLED_APPS += ['debug_toolbar']
#    MIDDLEWARE += ['debug_toolbar.middleware.DebugToolbarMiddleware']

# Whitelist of web domains that projects can be pulled from
if os.environ.get('PROJECT_DOMAINS'):
    PROJECT_DOMAINS = os.environ['PROJECT_DOMAINS'].split(" ")
else:
    # Public defaults
    PROJECT_DOMAINS = [
        'bitbucket.org',
        'github.com',
        'gitlab.com',
    ]

# Enable using headless X11 buffer
USE_XVFB = True
