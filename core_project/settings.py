"""
Django settings for core_project project.
Enterprise IT Asset Audit & Multi-Location Inventory System.
"""

from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = 'django-insecure-($u%%5ad^vm(h+7anc_n)-o&2j4cdm1s&w1rz1$xz9wd##&k%d'

DEBUG = True

ALLOWED_HOSTS = ['*']

INSTALLED_APPS = [
    'apps.accounts.admin_site.TechnicalAdminConfig',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Custom Core Modules (Modular & Future-Proof)
    'apps.accounts',
    'apps.common',
    'apps.locations',
    'apps.devices',
    'apps.audits',
    'apps.reports',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'apps.common.middleware.system_policy',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'core_project.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'apps.accounts.administration.navigation',
            ],
        },
    },
]

WSGI_APPLICATION = 'core_project.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}
if os.environ.get('AUDIT_DB_ENGINE') == 'postgresql':
    DATABASES['default'] = {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('AUDIT_DB_NAME', 'audit'),
        'USER': os.environ.get('AUDIT_DB_USER', 'audit'),
        'PASSWORD': os.environ.get('AUDIT_DB_PASSWORD', ''),
        'HOST': os.environ.get('AUDIT_DB_HOST', ''),
        'PORT': os.environ.get('AUDIT_DB_PORT', ''),
    }

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'apps.accounts.password_policy.PortalPasswordValidator'},
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

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'Asia/Dhaka'

USE_I18N = True

USE_TZ = True

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'dashboard'
LOGOUT_REDIRECT_URL = 'login'

SYSTEM_BACKUP_ROOT = os.environ.get('AUDIT_BACKUP_ROOT', '')

EMAIL_HOST = os.environ.get('AUDIT_EMAIL_HOST', 'localhost')
EMAIL_PORT = int(os.environ.get('AUDIT_EMAIL_PORT', '25'))
EMAIL_HOST_USER = os.environ.get('AUDIT_EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('AUDIT_EMAIL_HOST_PASSWORD', '')
EMAIL_USE_TLS = os.environ.get('AUDIT_EMAIL_USE_TLS') == '1'
EMAIL_TIMEOUT = 10
DEFAULT_FROM_EMAIL = os.environ.get('AUDIT_FROM_EMAIL', 'audit@localhost')
