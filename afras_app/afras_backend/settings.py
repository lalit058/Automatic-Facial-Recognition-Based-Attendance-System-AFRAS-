import os
from pathlib import Path
import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent

# ==========================================
# 1. SECURITY & HOSTS (Environment Variable Powered)
# ==========================================
SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-local-fallback-key')

# Set DEBUG=False on Render, keeps True locally if DEBUG env var is set
DEBUG = os.environ.get('DEBUG', 'True') == 'True'

ALLOWED_HOSTS = ['192.168.100.18', '127.0.0.1', 'localhost', '.onrender.com']

CSRF_TRUSTED_ORIGINS = [
    'http://localhost:8000',
    'http://127.0.0.1:8000',
    'https://*.onrender.com',
]

# ==========================================
# 2. INSTALLED APPS
# ==========================================
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django_browser_reload',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Your Apps
    'accounts',
    'attendance',
    'dashboard',
    'recognition',
]

# ==========================================
# 3. MIDDLEWARE (WhiteNoise added for static files)
# ==========================================
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # REQUIRED for Render static files
    'django_browser_reload.middleware.BrowserReloadMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'afras_backend.urls'

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
            ],
        },
    },
]

WSGI_APPLICATION = 'afras_backend.wsgi.application'
ASGI_APPLICATION = 'afras_backend.asgi.application'

# ==========================================
# 4. DATABASE (Uses DATABASE_URL on Render, local MySQL as fallback)
# ==========================================
DATABASES = {
    'default': dj_database_url.config(
        default='mysql://root:Lalit%4098@127.0.0.1:3306/afras_db',
        conn_max_age=600,
    )
}

# ==========================================
# 5. EMAIL CONFIGURATION
# ==========================================
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', 'lalitnegi2058@gmail.com')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', 'smevauphghfajojw')
DEFAULT_FROM_EMAIL = 'AFRAS System <lalitnegi2058@gmail.com>'

# ==========================================
# 6. INTERNATIONALIZATION
# ==========================================
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Kathmandu'
USE_TZ = True
USE_I18N = True
USE_L10N = True

# ==========================================
# 7. STATIC & MEDIA FILES (Fixed for production)
# ==========================================
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
# REQUIRED for collectstatic to work on Render
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
AUTH_USER_MODEL = 'accounts.CustomUser'