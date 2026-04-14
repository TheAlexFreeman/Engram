from __future__ import annotations

import logging

import sentry_sdk
import structlog
from sentry_sdk.integrations.celery import CeleryIntegration
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.integrations.logging import LoggingIntegration
from sentry_sdk.integrations.redis import RedisIntegration
from structlog_sentry import SentryProcessor

from .base import *  # noqa  # isort: skip
from .base import env  # isort: skip

# GENERAL
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#secret-key
SECRET_KEY = env("DJANGO_SECRET_KEY")
# https://docs.djangoproject.com/en/dev/ref/settings/#allowed-hosts
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=["betterbase.com"])

# DATABASES
# ------------------------------------------------------------------------------
DATABASES["default"]["CONN_MAX_AGE"] = env.int("CONN_MAX_AGE", default=60)  # noqa: F405

# CACHES
# ------------------------------------------------------------------------------
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": env("REDIS_CACHE_URL"),
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            # Mimicing memcache behavior.
            # https://github.com/jazzband/django-redis#memcached-exceptions-behavior
            "IGNORE_EXCEPTIONS": True,
        },
    }
}

# SECURITY
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#secure-proxy-ssl-header
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
# https://docs.djangoproject.com/en/dev/ref/settings/#secure-ssl-redirect
SECURE_SSL_REDIRECT = env.bool("DJANGO_SECURE_SSL_REDIRECT", default=True)
# https://docs.djangoproject.com/en/dev/ref/settings/#session-cookie-secure
SESSION_COOKIE_SECURE = True
# https://docs.djangoproject.com/en/dev/ref/settings/#csrf-cookie-secure
CSRF_COOKIE_SECURE = True
# https://docs.djangoproject.com/en/dev/topics/security/#ssl-https
# https://docs.djangoproject.com/en/dev/ref/settings/#secure-hsts-seconds
# NOTE: When deploying, set this to 60 seconds first and then to 518400 (or another
# large value based on what you need, etc.) once you prove the former works
SECURE_HSTS_SECONDS = env.int("DJANGO_SECURE_HSTS_SECONDS", default=60)
# https://docs.djangoproject.com/en/dev/ref/settings/#secure-hsts-include-subdomains
SECURE_HSTS_INCLUDE_SUBDOMAINS = env.bool(
    "DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS", default=True
)
# https://docs.djangoproject.com/en/dev/ref/settings/#secure-hsts-preload
SECURE_HSTS_PRELOAD = env.bool("DJANGO_SECURE_HSTS_PRELOAD", default=True)
# https://docs.djangoproject.com/en/dev/ref/middleware/#x-content-type-options-nosniff
SECURE_CONTENT_TYPE_NOSNIFF = env.bool(
    "DJANGO_SECURE_CONTENT_TYPE_NOSNIFF", default=True
)

# ==
# Security settings changed with this Better Base App in mind that may be somewhat specific
# to this use case, etc.
# ==
# NOTE: That `default` is equivalent to forty days.
CSRF_TRUSTED_ORIGINS = env.list("DJANGO_CSRF_TRUSTED_ORIGINS")
SESSION_COOKIE_AGE = env.int("DJANGO_SESSION_COOKIE_AGE", default=60 * 60 * 24 * 40)
SESSION_EXPIRE_AT_BROWSER_CLOSE = env.bool(
    "DJANGO_SESSION_EXPIRE_AT_BROWSER_CLOSE", default=False
)
SESSION_SAVE_EVERY_REQUEST = env.bool(
    "DJANGO_SESSION_SAVE_EVERY_REQUEST", default=False
)

HAS_ROOT_DOMAIN_COOKIE: bool
_session_cookie_domain = env("DJANGO_SESSION_COOKIE_DOMAIN", default=None) or None
if (
    _session_cookie_domain
    and _session_cookie_domain
    not in (
        None,
        "",
        "None",
        "none",
        "NULL",
        "Null",
        "null",
        "False",
        "false",
        "0",
        0,
    )
    and env.bool("ARE_ROOT_DOMAIN_COOKIES_ENABLED", default=False)
):
    HAS_ROOT_DOMAIN_COOKIE = True
    # https://docs.djangoproject.com/en/5.1/ref/settings/#std-setting-CSRF_COOKIE_DOMAIN
    CSRF_COOKIE_DOMAIN = _session_cookie_domain
    # https://docs.djangoproject.com/en/5.1/ref/settings/#std-setting-CSRF_COOKIE_NAME
    CSRF_COOKIE_NAME = "shareddjappcsrftoken"
    # https://docs.djangoproject.com/en/5.1/ref/settings/#language-cookie-domain
    LANGUAGE_COOKIE_DOMAIN = _session_cookie_domain
    # https://docs.djangoproject.com/en/5.1/ref/settings/#session-cookie-domain
    SESSION_COOKIE_DOMAIN = _session_cookie_domain
    # https://docs.djangoproject.com/en/5.1/ref/settings/#session-cookie-name
    SESSION_COOKIE_NAME = "shareddjappsessionid"
else:
    HAS_ROOT_DOMAIN_COOKIE = False


# django-storages
# ------------------------------------------------------------------------------
# https://django-storages.readthedocs.io/en/latest/#installation
INSTALLED_APPS += ["storages"]  # noqa: F405
# https://django-storages.readthedocs.io/en/latest/backends/amazon-S3.html#settings
AWS_ACCESS_KEY_ID = env("DJANGO_AWS_ACCESS_KEY_ID")
# https://django-storages.readthedocs.io/en/latest/backends/amazon-S3.html#settings
AWS_SECRET_ACCESS_KEY = env("DJANGO_AWS_SECRET_ACCESS_KEY")
# https://django-storages.readthedocs.io/en/latest/backends/amazon-S3.html#settings
AWS_STORAGE_BUCKET_NAME = env("DJANGO_AWS_STORAGE_BUCKET_NAME")
AWS_PUBLIC_STORAGE_BUCKET_NAME = env("DJANGO_AWS_PUBLIC_STORAGE_BUCKET_NAME")
AWS_PRIVATE_STORAGE_BUCKET_NAME = env("DJANGO_AWS_PRIVATE_STORAGE_BUCKET_NAME")
# https://django-storages.readthedocs.io/en/latest/backends/amazon-S3.html#settings
AWS_QUERYSTRING_AUTH = env.bool("DJANGO_AWS_QUERYSTRING_AUTH", default=False)
# DO NOT change these unless you know what you're doing.
_AWS_EXPIRY = 60 * 60 * 24 * 7
# https://django-storages.readthedocs.io/en/latest/backends/amazon-S3.html#settings
AWS_S3_OBJECT_PARAMETERS = {
    "CacheControl": f"max-age={_AWS_EXPIRY}, s-maxage={_AWS_EXPIRY}, must-revalidate",
}
# https://django-storages.readthedocs.io/en/latest/backends/amazon-S3.html#settings
AWS_S3_MAX_MEMORY_SIZE = env.int(
    "DJANGO_AWS_S3_MAX_MEMORY_SIZE",
    default=100_000_000,  # 100MB
)
# https://django-storages.readthedocs.io/en/latest/backends/amazon-S3.html#settings
AWS_S3_REGION_NAME = env("DJANGO_AWS_S3_REGION_NAME", default=None)
# https://django-storages.readthedocs.io/en/latest/backends/amazon-S3.html#cloudfront
AWS_S3_CUSTOM_DOMAIN = env("DJANGO_AWS_S3_CUSTOM_DOMAIN", default=None)
AWS_S3_PUBLIC_CUSTOM_DOMAIN = env("DJANGO_AWS_S3_PUBLIC_CUSTOM_DOMAIN", default=None)
AWS_S3_PRIVATE_CUSTOM_DOMAIN = env("DJANGO_AWS_S3_PRIVATE_CUSTOM_DOMAIN", default=None)
aws_s3_domain = AWS_S3_CUSTOM_DOMAIN
assert aws_s3_domain, "Current pre-condition"
aws_s3_public_domain = AWS_S3_PUBLIC_CUSTOM_DOMAIN
assert aws_s3_public_domain, "Current pre-condition"
aws_s3_private_domain = AWS_S3_PRIVATE_CUSTOM_DOMAIN
assert aws_s3_private_domain, "Current pre-condition"

AWS_S3_ENDPOINT_URL = env("DJANGO_AWS_S3_ENDPOINT_URL", default=None)
assert AWS_S3_ENDPOINT_URL, "Current pre-condition"
AWS_S3_PRIVATE_ENDPOINT_URL = env("DJANGO_AWS_S3_PRIVATE_ENDPOINT_URL", default=None)
assert AWS_S3_PRIVATE_ENDPOINT_URL, "Current pre-condition"
AWS_S3_PUBLIC_ENDPOINT_URL = env("DJANGO_AWS_S3_PUBLIC_ENDPOINT_URL", default=None)
assert AWS_S3_PUBLIC_ENDPOINT_URL, "Current pre-condition"

assert AWS_S3_ENDPOINT_URL.startswith("https://"), "Current pre-condition"
assert AWS_S3_PRIVATE_ENDPOINT_URL.startswith("https://"), "Current pre-condition"
assert AWS_S3_PUBLIC_ENDPOINT_URL.startswith("https://"), "Current pre-condition"
assert AWS_S3_ENDPOINT_URL == f"https://{aws_s3_domain}", "Current pre-condition"
assert AWS_S3_PRIVATE_ENDPOINT_URL == f"https://{aws_s3_private_domain}", (
    "Current pre-condition"
)
# NOTE: This is intentionally set to `f"https://{aws_s3_private_domain}"` (it's not a
# bug/typo).
assert AWS_S3_PUBLIC_ENDPOINT_URL == f"https://{aws_s3_private_domain}", (
    "Current pre-condition"
)

# MEDIA
# ------------------------------------------------------------------------------
MEDIA_URL = f"https://{aws_s3_private_domain}/media/"

# STORAGES
# ------------------------
STORAGES = {
    "default": {
        "BACKEND": "backend.base.storages.MediaS3PrivateStorage",
    },
    "private": {
        "BACKEND": "backend.base.storages.MediaS3PrivateStorage",
    },
    "public": {
        "BACKEND": "backend.base.storages.MediaS3PublicStorage",
    },
    "staticfiles": {
        "BACKEND": "backend.base.staticfiles.ViteManifestStaticFilesStorage",
    },
}

# EMAIL
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#default-from-email
DEFAULT_FROM_EMAIL = env(
    "DJANGO_DEFAULT_FROM_EMAIL",
    default="Better Base Accounts <accounts@mail.betterbase.com>",
)
# https://docs.djangoproject.com/en/dev/ref/settings/#server-email
SERVER_EMAIL = env("DJANGO_SERVER_EMAIL", default=DEFAULT_FROM_EMAIL)
# https://docs.djangoproject.com/en/dev/ref/settings/#email-subject-prefix
EMAIL_SUBJECT_PREFIX = env("DJANGO_EMAIL_SUBJECT_PREFIX", default="")
if EMAIL_SUBJECT_PREFIX in (
    "",
    None,
    "None",
    "none",
    "NULL",
    "Null",
    "null",
    False,
    "False",
    "false",
):
    EMAIL_SUBJECT_PREFIX = ""

# ADMIN
# ------------------------------------------------------------------------------
# Django Admin URL regex.
ADMIN_URL = env("DJANGO_ADMIN_URL")

# Anymail
# ------------------------------------------------------------------------------
# https://anymail.dev/en/stable/installation/#installing-anymail
INSTALLED_APPS += ["anymail"]
# https://docs.djangoproject.com/en/dev/ref/settings/#email-backend
# https://anymail.dev/en/stable/installation/#anymail-settings-reference
# https://anymail.dev/en/stable/esps/
EMAIL_BACKEND = "anymail.backends.mailgun.EmailBackend"
# https://anymail.dev/en/stable/esps/mailgun/
ANYMAIL = {
    "MAILGUN_API_KEY": env("MAILGUN_API_KEY"),
    "MAILGUN_WEBHOOK_SIGNING_KEY": env("MAILGUN_WEBHOOK_SIGNING_KEY"),
    "MAILGUN_API_URL": env("MAILGUN_API_URL", default="https://api.mailgun.net/v3"),
    "MAILGUN_SENDER_DOMAIN": env("MAILGUN_DOMAIN"),
}

# Sentry
# ------------------------------------------------------------------------------
IS_SENTRY_ENABLED = env.bool("DJANGO_IS_SENTRY_ENABLED", default=True)
IS_STRUCTLOG_SENTRY_ENABLED = env.bool(
    "DJANGO_IS_STRUCTLOG_SENTRY_ENABLED", default=True
)
if IS_SENTRY_ENABLED:
    SENTRY_DSN = env("SENTRY_DSN")
    SENTRY_LOG_LEVEL = env.int("DJANGO_SENTRY_LOG_LEVEL", logging.INFO)
    SENTRY_EVENT_LEVEL = env.int("DJANGO_SENTRY_EVENT_LEVEL", logging.WARNING)

    # NOTE: Read the Sentry release from the environment first. If it's not truthy, then
    # assume it might be at `BASE_DIR / ".sentry-release"` (see the production
    # Dockerfile for more details).
    SENTRY_RELEASE: str | None = env("SENTRY_RELEASE", default=None)
    if not SENTRY_RELEASE:
        _sentry_release_file = BASE_DIR / ".sentry-release"  # noqa: F405
        if _sentry_release_file.exists():
            SENTRY_RELEASE = _sentry_release_file.read_text().strip()
            assert SENTRY_RELEASE and isinstance(SENTRY_RELEASE, str), (
                "Current pre-condition"
            )
            assert len(SENTRY_RELEASE) >= 6, "Current pre-condition"
    SENTRY_RELEASE = SENTRY_RELEASE or None

    sentry_logging = LoggingIntegration(
        level=SENTRY_LOG_LEVEL,  # Capture info and above (default from above) as breadcrumbs
        event_level=SENTRY_EVENT_LEVEL,  # Send warnings and above (default from above) as events
    )
    integrations = [
        *(
            # NOTE: Allowing duplication for now. Potential future enhancement ideas may
            # be found here (https://github.com/kiwicom/structlog-sentry/issues/100) for
            # example.
            [sentry_logging] if IS_STRUCTLOG_SENTRY_ENABLED else [sentry_logging]  # noqa: RUF034
        ),
        DjangoIntegration(),
        CeleryIntegration(),
        RedisIntegration(),
    ]
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        release=(SENTRY_RELEASE or None),
        environment=env("SENTRY_ENVIRONMENT", default=str(ENVIRONMENT)),  # noqa: F405
        integrations=integrations,
        profiles_sample_rate=env.float("SENTRY_PROFILES_SAMPLE_RATE", default=0.0),
        send_default_pii=env.bool("SENTRY_SEND_DEFAULT_PII", default=False),
        traces_sample_rate=env.float("SENTRY_TRACES_SAMPLE_RATE", default=0.0),
    )

# LOGGING
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#logging See
# https://docs.djangoproject.com/en/dev/topics/logging for more details on how to
# customize your logging configuration.
#
# Also, this is configured with `django-structlog`. See
# https://django-structlog.readthedocs.io/en/latest/index.html for more details.
#
# * Other Important NOTE: At the time of writing, this partially overrides the logging
# configuration from `config/settings/base.py`, just be aware of that. Additionally,
# want to note that `celery_app.py` has its own `django-structlog`/`structlog`
# configuration as well that will, to my current understanding, be called after the one
# below.

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json_formatter": {
            "()": structlog.stdlib.ProcessorFormatter,
            "processor": structlog.processors.JSONRenderer(),
            # https://github.com/jrobichaud/django-structlog#standard-loggers
            "foreign_pre_chain": [
                structlog.contextvars.merge_contextvars,
                # Customize as needed (https://github.com/jrobichaud/django-structlog#standard-loggers)
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.stdlib.PositionalArgumentsFormatter(),
            ],
        },
        "plain_console": {
            "()": structlog.stdlib.ProcessorFormatter,
            "processor": structlog.dev.ConsoleRenderer(),
            # https://github.com/jrobichaud/django-structlog#standard-loggers
            "foreign_pre_chain": [
                structlog.contextvars.merge_contextvars,
                # Customize as needed (https://github.com/jrobichaud/django-structlog#standard-loggers)
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.stdlib.PositionalArgumentsFormatter(),
            ],
        },
        "key_value": {
            "()": structlog.stdlib.ProcessorFormatter,
            "processor": structlog.processors.KeyValueRenderer(
                key_order=["timestamp", "level", "event", "logger"]
            ),
            # https://github.com/jrobichaud/django-structlog#standard-loggers
            "foreign_pre_chain": [
                structlog.contextvars.merge_contextvars,
                # Customize as needed (https://github.com/jrobichaud/django-structlog#standard-loggers)
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.stdlib.PositionalArgumentsFormatter(),
            ],
        },
    },
    "handlers": {
        "console": {
            "level": "DEBUG",
            "class": "logging.StreamHandler",
            "formatter": "plain_console",
        },
    },
    "loggers": {
        "django.db.backends": {
            "level": "ERROR",
            "handlers": ["console"],
            "propagate": False,
        },
        "django.security.DisallowedHost": {
            "level": "ERROR",
            "handlers": ["console"],
            "propagate": False,
        },
        "django_structlog": {
            "level": "INFO",
            "handlers": ["console"],
        },
        # Errors logged by the SDK itself
        "sentry_sdk": {
            "level": "ERROR",
            "handlers": ["console"],
            "propagate": False,
        },
        "backend": {
            "level": "INFO",
            "handlers": ["console"],
        },
    },
}

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.filter_by_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
        *(
            [
                SentryProcessor(
                    level=SENTRY_LOG_LEVEL,
                    event_level=SENTRY_EVENT_LEVEL,
                    tag_keys=[
                        "ip",
                        "request",
                        "request_id",
                        "user_agent",
                        "user_id",
                        "account_pk",
                        "account_id",
                        "user_pk",
                        "user_id",
                        "membership_pk",
                        "membership_id",
                        "invitation_pk",
                        "invitation_id",
                    ],
                )
            ]
            if IS_SENTRY_ENABLED and IS_STRUCTLOG_SENTRY_ENABLED
            else []
        ),
        structlog.processors.UnicodeDecoder(),
        structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
    ],
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

# django-rest-framework
# -------------------------------------------------------------------------------
# Tools that generate code samples can use SERVERS to point to the correct domain
SPECTACULAR_SETTINGS["SERVERS"] = [  # noqa: F405
    {
        "url": BASE_BACKEND_URL,  # noqa: F405
        "description": "Production server",
    },
]

# django-cors-headers - https://github.com/adamchainz/django-cors-headers#setup
# -------------------------------------------------------------------------------
CORS_ALLOWED_ORIGINS = env.list("DJANGO_CORS_ALLOWED_ORIGINS")

# Your stuff...
# ------------------------------------------------------------------------------
