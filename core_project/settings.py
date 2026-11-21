"""
Django settings for core_project project.
Enterprise IT Asset Audit & Multi-Location Inventory System.
"""

from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent

APP_ENV = os.environ.get('APP_ENV', 'development').lower()
IS_PRODUCTION = APP_ENV == 'production'

SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', '')
if IS_PRODUCTION and (not SECRET_KEY or SECRET_KEY.startswith('django-insecure-')):
    from django.core.exceptions import ImproperlyConfigured

    raise ImproperlyConfigured('DJANGO_SECRET_KEY must be configured for production.')
if not SECRET_KEY:
    SECRET_KEY = 'django-insecure-development-only-change-me'

DEBUG = os.environ.get('DJANGO_DEBUG', '0' if IS_PRODUCTION else '1') == '1'
ALLOWED_HOSTS = [host.strip() for host in os.environ.get('DJANGO_ALLOWED_HOSTS', '*' if not IS_PRODUCTION else '').split(',') if host.strip()]
if IS_PRODUCTION and (DEBUG or not ALLOWED_HOSTS or '*' in ALLOWED_HOSTS):
    from django.core.exceptions import ImproperlyConfigured

    raise ImproperlyConfigured('Production requires DEBUG=0 and explicit DJANGO_ALLOWED_HOSTS.')
CSRF_TRUSTED_ORIGINS = [origin.strip() for origin in os.environ.get('DJANGO_CSRF_TRUSTED_ORIGINS', '').split(',') if origin.strip()]

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
    *(['whitenoise.middleware.WhiteNoiseMiddleware'] if IS_PRODUCTION else []),
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
if IS_PRODUCTION and os.environ.get('AUDIT_DB_ENGINE') != 'postgresql':
    from django.core.exceptions import ImproperlyConfigured

    raise ImproperlyConfigured('Production requires AUDIT_DB_ENGINE=postgresql.')
if os.environ.get('AUDIT_DB_ENGINE') == 'postgresql':
    DATABASES['default'] = {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('AUDIT_DB_NAME', 'audit'),
        'USER': os.environ.get('AUDIT_DB_USER', 'audit'),
        'PASSWORD': os.environ.get('AUDIT_DB_PASSWORD', ''),
        'HOST': os.environ.get('AUDIT_DB_HOST', '127.0.0.1'),
        'PORT': os.environ.get('AUDIT_DB_PORT', '5432'),
        'CONN_MAX_AGE': int(os.environ.get('AUDIT_DB_CONN_MAX_AGE', '60')),
        'OPTIONS': {'connect_timeout': 5},
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
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {
        'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage'
        if IS_PRODUCTION else 'django.contrib.staticfiles.storage.StaticFilesStorage',
    },
}

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

if IS_PRODUCTION:
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_SSL_REDIRECT = os.environ.get('DJANGO_SECURE_SSL_REDIRECT', '1') == '1'
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'
    X_FRAME_OPTIONS = 'DENY'
    SECURE_HSTS_SECONDS = int(os.environ.get('DJANGO_SECURE_HSTS_SECONDS', '31536000'))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = os.environ.get('DJANGO_HSTS_INCLUDE_SUBDOMAINS', '1') == '1'
    SECURE_HSTS_PRELOAD = os.environ.get('DJANGO_HSTS_PRELOAD', '0') == '1'
