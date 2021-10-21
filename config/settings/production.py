import os
import urllib

import dj_database_url

from .default import *

BASE_NAME = os.environ["HEROKU_APP_NAME"]
BASE_DOMAIN = "buddies.michiganelections.io"
BASE_URL = f"https://{BASE_DOMAIN}"

###############################################################################
# Core

SECRET_KEY = os.environ["SECRET_KEY"]

ALLOWED_HOSTS = ["localhost", ".michiganelections.io"]

###############################################################################
# Databases

DATABASES = {}
DATABASES["default"] = dj_database_url.config()

###############################################################################
# Caches

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": os.environ["REDIS_URL"],
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        },
    }
}

###############################################################################
# Authentication

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

###############################################################################
# Static files

STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"
