"""
With these settings, tests run faster.
"""

from __future__ import annotations

from .base import *  # noqa  # isort:skip
from .base import env  # isort:skip

# GENERAL
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#secret-key
SECRET_KEY = env(
    "DJANGO_SECRET_KEY",
    default="4xgzq598HmCPqJIFU5XMALbVu2MlGbcheRklTMND34rzS7LmHPWhsIYPb9NLcLfW",
)
# https://docs.djangoproject.com/en/dev/ref/settings/#test-runner
TEST_RUNNER = "django.test.runner.DiscoverRunner"

# PASSWORDS
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#password-hashers
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# EMAIL
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#email-backend
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

# DEBUGGING FOR TEMPLATES
# ------------------------------------------------------------------------------
TEMPLATES[0]["OPTIONS"]["debug"] = True  # type: ignore # noqa: F405

# Celery
# ------------------------------------------------------------------------------
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#task-always-eager
CELERY_TASK_ALWAYS_EAGER = True
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#task-eager-propagates
CELERY_TASK_EAGER_PROPAGATES = True

# django-rest-framework
# -------------------------------------------------------------------------------
# https://www.django-rest-framework.org/api-guide/testing/#setting-the-default-format
REST_FRAMEWORK["TEST_REQUEST_DEFAULT_FORMAT"] = "json"  # noqa: F405

# Factory Boy
# ------------------------------------------------------------------------------
# Optionally, if desired, set a random seed value to use for `factory` and underlying
# code. See, at the time of writing, `backend/tests/shared.py` for more details.
FACTORY_BOY_SET_RANDOM_SEED_TO = env("FACTORY_BOY_SET_RANDOM_SEED_TO", default=None)

# Your stuff...
# ------------------------------------------------------------------------------
