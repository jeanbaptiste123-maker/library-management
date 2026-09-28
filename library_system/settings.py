# library_system/settings.py
import os
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-8x@2&k#9m!p$q3r5t7u9v1w3y5a7c9e1g3j5l7n9p1r3t5v7x9z1'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = []

# ===========================================
# DATABASE CONFIGURATION (MySQL)
# ===========================================
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'library_management_system',
        'USER': 'root',
        'PASSWORD': 'mysql',  # ← PUT YOUR MYSQL PASSWORD HERE
        'HOST': 'localhost',
        'PORT': '3306',
    }
}

# ===========================================
# INSTALLED APPS
# ===========================================
INSTALLED_APPS = [
    'django.contrib.sessions',
    'django.contrib.staticfiles',
    'library',  # Your library app
]

# ===========================================
# MIDDLEWARE
# ===========================================
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# ===========================================
# URL CONFIGURATION
# ===========================================
ROOT_URLCONF = 'library_system.urls'

# ===========================================
# TEMPLATES CONFIGURATION
# ===========================================
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'library' / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
            ],
        },
    },
]

# ===========================================
# WSGI APPLICATION
# ===========================================
WSGI_APPLICATION = 'library_system.wsgi.application'

# ===========================================
# SESSION CONFIGURATION (File-based - No Database Needed)
# ===========================================
SESSION_ENGINE = 'django.contrib.sessions.backends.file'
SESSION_FILE_PATH = BASE_DIR / 'sessions'  # Sessions will be stored here
SESSION_COOKIE_AGE = 86400  # 24 hours in seconds
SESSION_COOKIE_HTTPONLY = True
SESSION_SAVE_EVERY_REQUEST = True
SESSION_EXPIRE_AT_BROWSER_CLOSE = False

# ===========================================
# STATIC FILES (CSS, JavaScript, Images)
# ===========================================
STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

# ===========================================
# DEFAULT PRIMARY KEY FIELD TYPE
# ===========================================
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ===========================================
# LOGIN CONFIGURATION
# ===========================================
LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/'