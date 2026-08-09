import os
import sys
import logging
import dj_database_url
from pathlib import Path
from datetime import timedelta
from decouple import config
from django.core.exceptions import ImproperlyConfigured

# Detected automatically so throttling/threading bypasses work in tests
TESTING = 'test' in sys.argv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

DEBUG = config('DEBUG', default=False, cast=bool)

# A deployment that boots with a fallback signing key silently invalidates every
# session and password-reset token on the next deploy, and anyone who has read
# this file can forge them. Fail loudly instead of starting up insecure.
_INSECURE_KEY = 'django-insecure-default-fallback-key'
_MIN_SECRET_KEY_LENGTH = 32
SECRET_KEY = config('SECRET_KEY', default=_INSECURE_KEY)
if not (DEBUG or TESTING):
    if SECRET_KEY == _INSECURE_KEY:
        raise ImproperlyConfigured(
            'SECRET_KEY is not set. Refusing to start with the built-in '
            'development key — set SECRET_KEY in the environment.'
        )
    # An empty or trivially short key is as forgeable as the default one, and a
    # blank environment variable is the usual way it happens.
    if len(SECRET_KEY.strip()) < _MIN_SECRET_KEY_LENGTH:
        raise ImproperlyConfigured(
            f'SECRET_KEY must be at least {_MIN_SECRET_KEY_LENGTH} characters; '
            f'got {len(SECRET_KEY.strip())}.'
        )
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1,.vercel.app').split(',')
if config('VERCEL_URL', default=None):
    ALLOWED_HOSTS.append(config('VERCEL_URL'))
# Custom domain (e.g. dgg.nexauratechs.com)
_site_url = config('SITE_URL', default='')
if _site_url:
    from urllib.parse import urlparse as _up
    _domain = _up(_site_url).netloc or _site_url.replace('https://', '').replace('http://', '').split('/')[0]
    if _domain and _domain not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(_domain)

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Third party apps
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',
    'django_filters',
    'drf_spectacular',
    # Local apps
    'accounts.apps.AccountsConfig',
    'funding.apps.FundingConfig',
    'notifications.apps.NotificationsConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'core.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'core.wsgi.application'

# Database
# Auto-switches between SQLite (local) and PostgreSQL (production via DATABASE_URL)
_db_url = config('DATABASE_URL', default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}")
# Never let the test runner touch a real database. Without this, a developer with
# a Supabase DATABASE_URL in .env has `manage.py test` attempt CREATE DATABASE on
# the production pooler — it hangs, and a --keepdb run would point tests at live data.
if TESTING:
    _db_url = f"sqlite:///{BASE_DIR / 'test-local.sqlite3'}"
# Persist Django→pooler connections across requests on Gunicorn (saves TCP+TLS
# handshake per request — major perf win for poll-heavy dashboards). The Supabase
# Transaction Pooler still recycles the underlying pg backend per transaction, so
# pooler-side state isn't shared; only the Django→pooler socket is kept warm.
_conn_max_age = config('DB_CONN_MAX_AGE', default=60, cast=int)
DATABASES = {
    'default': dj_database_url.config(
        default=_db_url,
        conn_max_age=_conn_max_age,
        ssl_require=not _db_url.startswith('sqlite'),
    )
}
# Required for Supabase Transaction Pooler (port 6543).
# Named / server-side cursors are not supported in transaction-mode pooling.
if not _db_url.startswith('sqlite'):
    DATABASES['default']['DISABLE_SERVER_SIDE_CURSORS'] = True

# Custom User Model
AUTH_USER_MODEL = 'accounts.User'

# REST Framework configurations
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 50,
    'DEFAULT_FILTER_BACKENDS': (
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ),
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    # Rate limiting — protects auth and public endpoints from abuse
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        # Anon covers public form discovery + shared office IPs — 200/day locked
        # out entire test sites for the day (phase-2 feedback).
        'anon': '2000/day',
        'user': '5000/day',
        'auth': '10/minute',      # login / register / forgot-password
        'password_reset': '5/hour',
    },
    # Never expose internal error details to API consumers
    'EXCEPTION_HANDLER': 'core.responses.custom_exception_handler',
}

# JWT configurations
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=30),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=3),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_TOKEN_CLASSES': ('rest_framework_simplejwt.tokens.AccessToken',),
}

# API Documentation settings
SPECTACULAR_SETTINGS = {
    'TITLE': 'DGG Student Portal API',
    'DESCRIPTION': 'Backend API for DGG Student Portal',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
}

# Public URL of the frontend — used to build links in outgoing emails
# (Form B registrar links, password resets). Must be a real Django setting:
# email builders read it via getattr(settings, 'FRONTEND_URL', ...).
FRONTEND_URL = config('FRONTEND_URL', default='http://localhost:3000').rstrip('/')

# CORS configuration
CORS_ALLOWED_ORIGINS = [
    FRONTEND_URL,
    config('FRONTEND_URL_ALT', default='http://localhost:5173'),
]
if config('VERCEL_URL', default=None):
    CORS_ALLOWED_ORIGINS.append(f"https://{config('VERCEL_URL')}")
if _site_url:
    _cors_origin = _site_url if _site_url.startswith('http') else f'https://{_site_url}'
    if _cors_origin not in CORS_ALLOWED_ORIGINS:
        CORS_ALLOWED_ORIGINS.append(_cors_origin)

CORS_ALLOW_CREDENTIALS = True

# CSRF configuration
CSRF_TRUSTED_ORIGINS = config('CSRF_TRUSTED_ORIGINS', default='http://localhost:3000,http://localhost:5173').split(',')
if config('VERCEL_URL', default=None):
    CSRF_TRUSTED_ORIGINS.append(f"https://{config('VERCEL_URL')}")
if _site_url:
    _csrf_origin = _site_url if _site_url.startswith('http') else f'https://{_site_url}'
    if _csrf_origin not in CSRF_TRUSTED_ORIGINS:
        CSRF_TRUSTED_ORIGINS.append(_csrf_origin)

# Static and Media files
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# Supabase Storage configuration
SUPABASE_URL = config('SUPABASE_URL', default='')
SUPABASE_ANON_KEY = config('SUPABASE_ANON_KEY', default='')
SUPABASE_SERVICE_KEY = config('SUPABASE_SERVICE_KEY', default=None)
SUPABASE_STORAGE_BUCKET = config('SUPABASE_STORAGE_BUCKET', default='dgg-documents')

_use_supabase_storage = bool(SUPABASE_SERVICE_KEY)

STORAGES = {
    "default": {
        "BACKEND": "core.supabase_storage.SupabaseStorage" if _use_supabase_storage else "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

# ── Transport and cookie security ───────────────────────────────────────────
# Hardening is ON unless a developer explicitly opts out for local work. It was
# previously gated behind `if not DEBUG`, so a single copied .env with DEBUG=True
# silently disabled TLS redirection, HSTS and every secure-cookie flag in
# production — with nothing in the logs to say so.
INSECURE_LOCAL = config('INSECURE_LOCAL', default=False, cast=bool)

# Always safe, regardless of transport.
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = 'DENY'                    # clickjacking
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_AGE = 3600                   # 1 hour
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'

if INSECURE_LOCAL or TESTING:
    # Plain HTTP for localhost and the test client.
    SECURE_SSL_REDIRECT = False
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False
    SECURE_HSTS_SECONDS = 0
else:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_HSTS_SECONDS = 31536000          # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

    if DEBUG:
        logging.getLogger(__name__).warning(
            'DEBUG is enabled with production security settings active. '
            'Set INSECURE_LOCAL=1 for local development.'
        )

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    { 'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator' },
    { 'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator' },
    { 'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator' },
    { 'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator' },
]

# Production keeps Django's default PBKDF2 hasher. It costs ~1.2s per hash, which
# is the correct trade for stored credentials but makes a suite that creates
# hundreds of users unusably slow (265s → ~30s with the fast hasher below).
# Test-only: never let this reach a non-test settings path.
if TESTING:
    PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ── EMAIL CONFIGURATION (Task 9.1) ──
EMAIL_BACKEND = config('EMAIL_BACKEND', default='django.core.mail.backends.smtp.EmailBackend')
EMAIL_HOST = config('EMAIL_HOST', default='smtp.gmail.com')
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='DGG Student Funding <noreply@deline.ca>')
EMAIL_SUBJECT_PREFIX = '[DGG Funding] '

# Finance recipient (for dispatch_report)
FINANCE_EMAIL = config('FINANCE_EMAIL', default='')

# ── FILE UPLOAD SECURITY ────────────────────────────────────────────────────
# 10 MB hard cap on uploaded files
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024   # 10 MB
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024   # 10 MB

ALLOWED_UPLOAD_EXTENSIONS = ['.pdf', '.jpg', '.jpeg', '.png', '.doc', '.docx']
ALLOWED_UPLOAD_MIME_TYPES = [
    'application/pdf',
    'image/jpeg',
    'image/png',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
]

# ── LOGGING ─────────────────────────────────────────────────────────────────
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {asctime} {module}: {message}',
            'style': '{',
        },
    },
    'filters': {
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'WARNING',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': False,
        },
        'django.security': {
            'handlers': ['console'],
            'level': 'ERROR',
            'propagate': False,
        },
        'api': {
            'handlers': ['console'],
            'level': 'INFO' if DEBUG else 'WARNING',
            'propagate': False,
        },
        'users': {
            'handlers': ['console'],
            'level': 'INFO' if DEBUG else 'WARNING',
            'propagate': False,
        },
    },
}

