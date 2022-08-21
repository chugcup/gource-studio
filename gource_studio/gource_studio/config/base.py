"""
Django settings for gource_studio project.

Generated by 'django-admin startproject' using Django 3.1.4.

For more information on this file, see
https://docs.djangoproject.com/en/3.1/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/3.1/ref/settings/
"""

from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Override in 'secrets.py'
SECRET_KEY = '00000000000000000000000000000000000000000000000000'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

# Not recommended to leave this in production
ALLOWED_HOSTS = ['*']


# Application definition

SITE_NAME = 'Gource Studio'

INSTALLED_APPS = [
    'gource_studio.core.apps.CoreConfig',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.humanize',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'rest_framework.authtoken',
]

MIDDLEWARE = [
    'gource_studio.core.middleware.RangesMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'gource_studio.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            Path(__file__).resolve().parent / "templates",
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'gource_studio.core.context_processors.app_request_default',
            ],
        },
    },
]

WSGI_APPLICATION = 'gource_studio.wsgi.application'


# Database
# https://docs.djangoproject.com/en/3.1/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'app.db',
    }
}

# Configure automatic PK field (Django 3.2+)
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# Password validation
# https://docs.djangoproject.com/en/3.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/3.1/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_L10N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/3.1/howto/static-files/

STATIC_URL = '/static/'
STATICFILES_DIRS = [
    Path(__file__).resolve().parent / "static",
]

MEDIA_ROOT = Path(__file__).resolve().parent / "media"

# Django REST Framework options
REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticatedOrReadOnly',
        #'rest_framework.permissions.DjangoModelPermissionsOrAnonReadOnly',
    ],
    'DEFAULT_AUTHENTICATION_CLASSES': [
        #'rest_framework.authentication.BasicAuthentication',
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.TokenAuthentication',
    ],
    'DEFAULT_VERSIONING_CLASS': 'rest_framework.versioning.NamespaceVersioning',
    # - Pagination
    #'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'DEFAULT_PAGINATION_CLASS': 'gource_studio.utils.rest_framework.CustomPageNumberPagination',
    'PAGE_SIZE': 20,
    # - Searching
    'SEARCH_PARAM': 'q',
    # - Sort order
    #'ORDERING_PARAM': 'ordering',   # Default
}

# Celery Configuration Options
CELERY_TIMEZONE = "UTC"
CELERY_TASK_TRACK_STARTED = True
CELERY_BROKER_URL = "redis://localhost:6379"

# Whitelist of web domains that projects can be pulled from
PROJECT_DOMAINS = [
    'bitbucket.org',
    'github.com',
    'gitlab.com',
]

# Custom software executable paths
# - `git`
GIT_PATH = None
# - `hg` (Mercurial)
MERCURIAL_PATH = None
# - `ffmpeg`
FFMPEG_PATH = None
# - `ffprobe`
FFPROBE_PATH = None
# - `ffplay`
FFPLAY_PATH = None
# - `gource`
GOURCE_PATH = None
# - `xvfb-run` (Headless X11 Frame Buffer)
XVFB_RUN_PATH = None
# Enable using headless X11 buffer (requires `XVFB_RUN_PATH`)
USE_XVFB = False
