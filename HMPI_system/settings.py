ALLOWED_HOSTS = ['.vercel.app', 'localhost', '127.0.0.1']
CSRF_TRUSTED_ORIGINS = ['https://*.vercel.app']

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',   # right after SecurityMiddleware
    # ...rest unchanged
]

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Vercel's filesystem is read-only, so keep sessions out of the database
SESSION_ENGINE = 'django.contrib.sessions.backends.signed_cookies'
