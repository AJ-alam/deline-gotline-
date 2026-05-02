import os
import dj_database_url
from pathlib import Path
from datetime import timedelta
from decouple import config

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Quick-start development settings - unsuitable for production
SECRET_KEY = config('SECRET_KEY', default='django-insecure-default-fallback-key')
DEBUG = config('DEBUG', default=False, cast=bool)
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1,.vercel.app').split(',')
if config('VERCEL_URL', default=None):
    ALLOWED_HOSTS.append(config('VERCEL_URL'))

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
    'corsheaders',
    'django_filters',
    'drf_spectacular',
    # Local apps
    'users.apps.UsersConfig',
    'programs.apps.ProgramsConfig',
    'forms.apps.FormsConfig',
    'dashboard.apps.DashboardConfig',
    'notifications.apps.NotificationsConfig',
    'api',
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
DATABASES = {
    'default': dj_database_url.config(
        default=_db_url,
        # conn_max_age=0 is required for Supabase Transaction Pooler.
        # The pooler resets connection state after each transaction,
        # so Django must NOT hold connections open across requests.
        conn_max_age=0,
        ssl_require=not _db_url.startswith('sqlite'),
    )
}
# Required for Supabase Transaction Pooler (port 6543).
# Named / server-side cursors are not supported in transaction-mode pooling.
if not _db_url.startswith('sqlite'):
    DATABASES['default']['DISABLE_SERVER_SIDE_CURSORS'] = True

# Custom User Model
AUTH_USER_MODEL = 'users.CustomUser'

# REST Framework configurations
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 50,  # Increased from 10 to reduce number of requests
    'DEFAULT_FILTER_BACKENDS': (
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ),
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}

# JWT configurations
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': False,
    'BLACKLIST_AFTER_ROTATION': True,
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

# CORS configuration
CORS_ALLOWED_ORIGINS = [
    config('FRONTEND_URL', default='http://localhost:3000'),
    config('FRONTEND_URL_ALT', default='http://localhost:5173'),
]
if config('VERCEL_URL', default=None):
    CORS_ALLOWED_ORIGINS.append(f"https://{config('VERCEL_URL')}")

CORS_ALLOW_CREDENTIALS = True

# CSRF configuration
CSRF_TRUSTED_ORIGINS = config('CSRF_TRUSTED_ORIGINS', default='http://localhost:3000,http://localhost:5173').split(',')
if config('VERCEL_URL', default=None):
    CSRF_TRUSTED_ORIGINS.append(f"https://{config('VERCEL_URL')}")

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

# Production Security
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    { 'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator' },
    { 'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator' },
    { 'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator' },
    { 'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator' },
]

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

