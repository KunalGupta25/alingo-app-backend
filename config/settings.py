import os
import json
import tempfile
import logging
from pathlib import Path
from dotenv import load_dotenv
try:
    import dj_database_url
    _HAS_DJ_DB_URL = True
except ImportError:
    _HAS_DJ_DB_URL = False

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from .env file
load_dotenv()

# ── Security Settings ─────────────────────────────────────────
# In production, all of these MUST be set via environment variables.
# The defaults are ONLY safe for local development.

DEBUG = os.getenv('DEBUG', 'True') == 'True'

# SECRET_KEY: fail fast in production if not set
_secret_key = os.getenv('SECRET_KEY')
if not _secret_key and not DEBUG:
    raise ValueError(
        'SECRET_KEY environment variable is required in production. '
        'Generate one with: python -c "import secrets; print(secrets.token_urlsafe(64))"'
    )
SECRET_KEY = _secret_key or 'django-insecure-dev-only-do-not-use-in-production'

# JWT_SECRET: separate from Django's SECRET_KEY for token signing
_jwt_secret = os.getenv('JWT_SECRET')
if not _jwt_secret and not DEBUG:
    raise ValueError(
        'JWT_SECRET environment variable is required in production. '
        'Generate one with: python -c "import secrets; print(secrets.token_urlsafe(64))"'
    )
JWT_SECRET = _jwt_secret or 'jwt-dev-only-secret-do-not-use-in-production'

# ALLOWED_HOSTS: no wildcard default in production
_allowed_hosts = os.getenv('ALLOWED_HOSTS')
if not _allowed_hosts and not DEBUG:
    raise ValueError('ALLOWED_HOSTS environment variable is required in production.')
ALLOWED_HOSTS = (_allowed_hosts or '*').split(',')


# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'corsheaders',
    'apps.core',
    'apps.authentication',
    'apps.verification',
    'apps.users',
    'apps.rides',
    'apps.reviews',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],  # Add templates directory
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# Use signed cookies for sessions instead of DB to avoid SQLite missing table errors on Railway's ephemeral file system
SESSION_ENGINE = 'django.contrib.sessions.backends.signed_cookies'

# ── Database ──────────────────────────────────────────────────
# Priority:
#   1. DATABASE_URL env var  → PostgreSQL (production / Railway)
#   2. SQLite fallback       → local development only
_database_url = os.getenv('DATABASE_URL')
if _database_url and _HAS_DJ_DB_URL:
    DATABASES = {'default': dj_database_url.config(default=_database_url, conn_max_age=600)}
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }
    if not DEBUG:
        import warnings
        warnings.warn(
            'No DATABASE_URL set in production. Using SQLite — data may be lost on redeploy!',
            RuntimeWarning,
        )

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Internationalization
LANGUAGE_CODE = 'en-us'
# All users are in India — comparisons like "is this ride today" and time-window
# matching need to line up with IST, not the server's UTC clock (Render runs UTC).
# USE_TZ stays True so everything is still stored in UTC internally; this setting
# only affects timezone.localtime() conversions used for date/time comparisons.
TIME_ZONE = 'Asia/Kolkata'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = 'static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Media Files Configuration
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# ── Cloud Media Storage (GCS) ─────────────────────────────
# Activated when GCS_BUCKET_NAME env var is set (e.g. on Railway/production).
# Falls back to local filesystem storage in development.
_gcs_bucket = os.getenv('GCS_BUCKET_NAME')
USE_GCS = bool(_gcs_bucket)

if USE_GCS:
    INSTALLED_APPS = INSTALLED_APPS + ['storages']
    STORAGES = {
        'default': {
            'BACKEND': 'storages.backends.gcloud.GoogleCloudStorage',
        },
        'staticfiles': {
            'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
        },
    }
    GS_BUCKET_NAME = _gcs_bucket
    GS_PROJECT_ID = os.getenv('GCS_PROJECT_ID', '')
    GS_DEFAULT_ACL = None          # uniform bucket-level access — no per-object ACLs
    GS_FILE_OVERWRITE = False       # keep unique filenames (timestamp already in name)
    GS_QUERYSTRING_AUTH = False     # public bucket → plain https:// URLs
    MEDIA_URL = f'https://storage.googleapis.com/{_gcs_bucket}/'

# Verification Upload Settings
VERIFICATION_UPLOAD_DIR = 'verifications'
PROFILE_PHOTO_UPLOAD_DIR = 'profile_photos'
MAX_UPLOAD_SIZE = 5 * 1024 * 1024  # 5MB
ALLOWED_IMAGE_TYPES = ['image/jpeg', 'image/png', 'image/jpg']

# ── Admin Panel Settings ──────────────────────────────────
ADMIN_SESSION_MAX_AGE = int(os.getenv('ADMIN_SESSION_MAX_AGE', 3600))  # 1 hour default


# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ── CORS Settings ─────────────────────────────────────────────
# Allow all origins ONLY in debug mode
CORS_ALLOW_ALL_ORIGINS = DEBUG
if not CORS_ALLOW_ALL_ORIGINS:
    _cors_origins = os.getenv('CORS_ALLOWED_ORIGINS', '')
    CORS_ALLOWED_ORIGINS = [o.strip() for o in _cors_origins.split(',') if o.strip()]
CORS_ALLOW_CREDENTIALS = True

# ── HTTPS / Proxy / Security headers ─────────────────────────

if not DEBUG:
    # Trust HTTPS proxy headers (Railway, etc.)
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    # Force HTTPS
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 31536000          # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    # Secure cookies
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    CSRF_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    # Clickjacking & content sniffing
    X_FRAME_OPTIONS = 'DENY'
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_BROWSER_XSS_FILTER = True

# CSRF trusted origins — set via env var (comma-separated)
# Example: https://your-app.onrender.com,https://your-app.up.railway.app
_csrf_origins = os.getenv('CSRF_TRUSTED_ORIGINS', '')
CSRF_TRUSTED_ORIGINS = [o.strip() for o in _csrf_origins.split(',') if o.strip()]

# Session timeout — 7 days (matches JWT expiry)
SESSION_COOKIE_AGE = 7 * 24 * 60 * 60

# ── REST Framework Settings ───────────────────────────────────
REST_FRAMEWORK = {
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
    'DEFAULT_PARSER_CLASSES': [
        'rest_framework.parsers.JSONParser',
    ],
    # Global rate limiting
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '30/minute',
        'user': '120/minute',
    },
}

# MongoDB settings
MONGODB_URI = os.getenv('MONGODB_URI', 'mongodb://localhost:27017/')
MONGODB_DB_NAME = os.getenv('MONGODB_DB_NAME', 'alingo_db')

# Firebase settings
# Railway: pass the entire service account JSON as FIREBASE_CREDENTIALS_JSON env var
# Local: use FIREBASE_CREDENTIALS_PATH pointing to the JSON file
_firebase_json = os.getenv('FIREBASE_CREDENTIALS_JSON')
if _firebase_json:
    # Write the JSON to a temp file so firebase_admin can read it
    _tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
    _tmp.write(_firebase_json)
    _tmp.close()
    FIREBASE_CREDENTIALS_PATH = _tmp.name
else:
    FIREBASE_CREDENTIALS_PATH = os.getenv(
        'FIREBASE_CREDENTIALS_PATH',
        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'firebase_service_account_key.json')
    )

# ── Logging Configuration ────────────────────────────────────
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '[{asctime}] {levelname} {name}: {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'apps': {
            'handlers': ['console'],
            'level': 'DEBUG' if DEBUG else 'INFO',
            'propagate': False,
        },
    },
}
