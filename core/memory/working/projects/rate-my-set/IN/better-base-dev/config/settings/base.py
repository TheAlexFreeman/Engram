"""
Base settings to build other settings files upon.
"""

from __future__ import annotations

import re

import orjson
import structlog
from whitenoise.middleware import WhiteNoiseMiddleware

from backend.base.types.environment import Environment, EnvironmentType

from .root import *  # noqa  # isort: skip
from .root import APPS_DIR, BASE_DIR, env  # isort: skip

# Environment
# ------------------------------------------------------------------------------
_environment_string: EnvironmentType = env("ENVIRONMENT")
assert _environment_string in ([*Environment]), "Current Pre-Condition"
ENVIRONMENT = Environment(_environment_string)

# GENERAL
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#debug
DEBUG = env.bool("DJANGO_DEBUG", False)
# Local time zone. Choices are
# http://en.wikipedia.org/wiki/List_of_tz_zones_by_name
# though not all of them may be available with every OS.
# In Windows, this must be set to your system time zone.
TIME_ZONE = "UTC"
# https://docs.djangoproject.com/en/dev/ref/settings/#language-code
LANGUAGE_CODE = "en-us"
# https://docs.djangoproject.com/en/dev/ref/settings/#use-i18n
USE_I18N = True
# https://docs.djangoproject.com/en/dev/ref/settings/#use-tz
USE_TZ = True
# https://docs.djangoproject.com/en/dev/ref/settings/#locale-paths
LOCALE_PATHS = [str(BASE_DIR / "locale")]
# https://docs.djangoproject.com/en/dev/ref/settings/#silenced-system-checks
SILENCED_SYSTEM_CHECKS: list[str] = []
# https://docs.djangoproject.com/en/dev/ref/settings/#append-slash
APPEND_SLASH = env.bool("APPEND_SLASH", default=False)

# URL/Site Info
# (NOTE: Only `SITE_ID` below is a built-in Django settings. The others are present and
# will be picked up by other places in the settings and the code.)
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#site-id
SITE_ID = 1

# Something like: https://some-website.com, etc.
BASE_BACKEND_URL = env("BASE_BACKEND_URL").removesuffix("/")
# Something like: some-website.com, etc.
DEFAULT_SITE_DOMAIN = env("DEFAULT_SITE_DOMAIN").removesuffix("/")
DEFAULT_SITE_NAME = env("DEFAULT_SITE_NAME")
# Can remove these assertions if, for whatever reason, one or more of them are actually
# incorrect assertion to make down the line, etc. They're here for safety right now.
assert BASE_BACKEND_URL.startswith("http"), "Current Pre-condition"
if ENVIRONMENT.is_prod:
    assert BASE_BACKEND_URL.startswith("https"), "Current Pre-condition"
assert DEFAULT_SITE_DOMAIN in BASE_BACKEND_URL, "Current Pre-condition"
BASE_WEB_APP_URL = env("BASE_WEB_APP_URL").removesuffix("/")
BASE_LANDING_SITE_URL = env("BASE_LANDING_SITE_URL").removesuffix("/")

# DATABASES
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#databases
DATABASES = {"default": env.db("DATABASE_URL")}
DATABASES["default"]["ATOMIC_REQUESTS"] = True
# https://docs.djangoproject.com/en/stable/ref/settings/#std:setting-DEFAULT_AUTO_FIELD

# URLS
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#root-urlconf
ROOT_URLCONF = "config.urls"
# https://docs.djangoproject.com/en/dev/ref/settings/#wsgi-application
WSGI_APPLICATION = "config.wsgi.application"

# APPS
# ------------------------------------------------------------------------------
DJANGO_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.sites",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    "django.contrib.humanize",
    "django.contrib.admin",
    "django.forms",
]
THIRD_PARTY_APPS = [
    "django_celery_beat",
    "django_celery_results",
    "rest_framework",
    "corsheaders",
    "drf_spectacular",
    "jsoneditor",
    "djangoql",
    "django_structlog",
    "django_vite",
    "cachalot",
]

LOCAL_APPS = [
    "backend.accounts",
    "backend.auth",
    "backend.base",
]
# https://docs.djangoproject.com/en/dev/ref/settings/#installed-apps
INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# MIGRATIONS
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#migration-modules
MIGRATION_MODULES = {"sites": "backend.contrib.sites.migrations"}

# AUTHENTICATION
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#authentication-backends
AUTHENTICATION_BACKENDS = ["django.contrib.auth.backends.ModelBackend"]
# https://docs.djangoproject.com/en/dev/ref/settings/#auth-user-model
AUTH_USER_MODEL = "accounts.User"
# https://docs.djangoproject.com/en/dev/ref/settings/#login-redirect-url
LOGIN_REDIRECT_URL = "home"
# https://docs.djangoproject.com/en/dev/ref/settings/#login-url
LOGIN_URL = "auth:login"
# https://docs.djangoproject.com/en/dev/ref/settings/#logout-redirect-url
LOGOUT_REDIRECT_URL = "home"

# PASSWORDS
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#password-hashers
PASSWORD_HASHERS = [
    # https://docs.djangoproject.com/en/dev/topics/auth/passwords/#using-argon2-with-django
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
    "django.contrib.auth.hashers.BCryptSHA256PasswordHasher",
]
# https://docs.djangoproject.com/en/dev/ref/settings/#auth-password-validators
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {
            "min_length": 9,
        },
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
    {"NAME": "backend.auth.ops.password_validators.AtLeastOneNumberPasswordValidator"},
    {
        "NAME": "backend.auth.ops.password_validators.AtLeastOneSpecialCharacterPasswordValidator"
    },
]

# The number of seconds a password reset link is valid for.
PASSWORD_RESET_TIMEOUT = 60 * 60 * 3  # 3 hours

# MIDDLEWARE
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#middleware
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "djangorestframework_camel_case.middleware.CamelCaseMiddleWare",
    "django_structlog.middlewares.RequestMiddleware",
]

# STATIC
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#static-root
STATIC_ROOT = str(BASE_DIR / "staticfiles")
# https://docs.djangoproject.com/en/dev/ref/settings/#static-url
STATIC_URL = "/static/"
# https://docs.djangoproject.com/en/dev/ref/settings/#std-setting-STATICFILES_DIRS
STATICFILES_DIRS = [
    # Vite public folder. We have `copyPublicDir` set to `false` since `collectstatic`
    # will take care of it.
    str(BASE_DIR / "public"),
    # Vite SPA-like frontend web app compiled files
    # (https://github.com/MrBin99/django-vite#miscellaneous-configuration).
    ("bundler", str(BASE_DIR / "dist")),
    # The rest of the regular static files likely only used by non SPA-like frontend web
    # app Django stuff.
    str(APPS_DIR / "static"),
]
# https://docs.djangoproject.com/en/dev/ref/settings/#std-setting-STATICFILES_FINDERS
STATICFILES_FINDERS = [
    "django.contrib.staticfiles.finders.FileSystemFinder",
    "django.contrib.staticfiles.finders.AppDirectoriesFinder",
]

# whitenoise + django-vite
# ------------------------


# https://whitenoise.readthedocs.io/en/stable/django.html#WHITENOISE_IMMUTABLE_FILE_TEST
def immutable_file_test(
    path,
    url,
    *,
    _mw: WhiteNoiseMiddleware | None = WhiteNoiseMiddleware(),  # noqa: B008
):
    middleware = WhiteNoiseMiddleware() if _mw is None else _mw
    # Use whitenoise's default test for immutable files to handle non-vite static files.
    # (Thanks to https://github.com/MrBin99/django-vite/commit/644dd9e8ae544ba8209561a328257a51574ffd16)
    if middleware.immutable_file_test(path, url):
        return True

    # Match vite (rollup)-generated hashes, à la, `some_file-CSliV9zW.js`.
    # (Thanks to https://github.com/MrBin99/django-vite?tab=readme-ov-file#whitenoise)
    return re.match(r"^.+[.-][0-9a-zA-Z_-]{8,12}\..+$", url)


# Thanks to https://github.com/MrBin99/django-vite#notes.
WHITENOISE_IMMUTABLE_FILE_TEST = immutable_file_test

# MEDIA
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#media-root
MEDIA_ROOT = str(APPS_DIR / "media")
# https://docs.djangoproject.com/en/dev/ref/settings/#media-url
MEDIA_URL = "/media/"

# STORAGES
# ------------------------------------------------------------------------------
STORAGES = {
    "default": {
        "BACKEND": "backend.base.storages.DefaultMediaStorage",
    },
    "private": {
        "BACKEND": "backend.base.storages.DefaultPublicMediaStorage",
    },
    "public": {
        "BACKEND": "backend.base.storages.DefaultPrivateMediaStorage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

# TEMPLATES
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#templates
TEMPLATES = [
    {
        # https://docs.djangoproject.com/en/dev/ref/settings/#std:setting-TEMPLATES-BACKEND
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        # https://docs.djangoproject.com/en/dev/ref/settings/#dirs
        "DIRS": [str(APPS_DIR / "templates")],
        # https://docs.djangoproject.com/en/dev/ref/settings/#app-dirs
        "APP_DIRS": True,
        "OPTIONS": {
            # https://docs.djangoproject.com/en/dev/ref/settings/#template-context-processors
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.template.context_processors.i18n",
                "django.template.context_processors.media",
                "django.template.context_processors.static",
                "django.template.context_processors.tz",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    }
]

# https://docs.djangoproject.com/en/dev/ref/settings/#form-renderer
FORM_RENDERER = "django.forms.renderers.TemplatesSetting"

# FIXTURES
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#fixture-dirs
FIXTURE_DIRS = (str(APPS_DIR / "fixtures"),)

# SECURITY
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#session-cookie-httponly
SESSION_COOKIE_HTTPONLY = True
# https://docs.djangoproject.com/en/dev/ref/settings/#csrf-cookie-httponly
CSRF_COOKIE_HTTPONLY = True
# https://docs.djangoproject.com/en/dev/ref/settings/#x-frame-options
X_FRAME_OPTIONS = "DENY"

# EMAIL
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#email-backend
EMAIL_BACKEND = env(
    "DJANGO_EMAIL_BACKEND",
    default="django.core.mail.backends.smtp.EmailBackend",
)
# https://docs.djangoproject.com/en/dev/ref/settings/#email-timeout
EMAIL_TIMEOUT = 5

# Support Email(s)
DEFAULT_SUPPORT_EMAIL = env(
    "DEFAULT_SUPPORT_EMAIL",
    default="Better Base Support <support@betterbase.com>",
)

# ADMIN
# ------------------------------------------------------------------------------
# Django Admin URL.
ADMIN_URL = "admin/"
# https://docs.djangoproject.com/en/dev/ref/settings/#admins
ADMINS = ["admins@mail.betterbase.com"]
# https://docs.djangoproject.com/en/dev/ref/settings/#managers
MANAGERS = ADMINS

# LOGGING
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#logging See
# https://docs.djangoproject.com/en/dev/topics/logging for more details on how to
# customize your logging configuration.
#
# Also, this is configured with `django-structlog`. See
# https://django-structlog.readthedocs.io/en/latest/index.html for more details.
#
# * Other Important NOTE: At the time of writing, `config/settings/prod.py` *has its own
# `django-structlog`-related configuration in that file that *partially overrides* this
# one. Just be aware of that. Additionally, want to note that `celery_app.py` has its
# own `django-structlog`/`structlog` configuration as well that will, to my current
# understanding, be called after the one below.

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
        "django_structlog": {
            "level": "INFO",
            "handlers": ["console"],
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
        structlog.processors.UnicodeDecoder(),
        structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
    ],
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

# Celery
# ------------------------------------------------------------------------------
if USE_TZ:
    # https://docs.celeryq.dev/en/stable/userguide/configuration.html#std:setting-timezone
    CELERY_TIMEZONE = TIME_ZONE
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#std:setting-broker_url
CELERY_BROKER_URL = env("CELERY_BROKER_URL")
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#std:setting-result_backend
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND")
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#result-extended
CELERY_RESULT_EXTENDED = True
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#result-backend-always-retry
# https://github.com/celery/celery/pull/6122
CELERY_RESULT_BACKEND_ALWAYS_RETRY = True
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#result-backend-max-retries
CELERY_RESULT_BACKEND_MAX_RETRIES = 10
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#std:setting-accept_content
CELERY_ACCEPT_CONTENT = ["json"]
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#std:setting-task_serializer
CELERY_TASK_SERIALIZER = "json"
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#std:setting-result_serializer
CELERY_RESULT_SERIALIZER = "json"
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#task-time-limit
CELERY_TASK_TIME_LIMIT = 4 * 60  # 4 minutes
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#task-soft-time-limit
CELERY_TASK_SOFT_TIME_LIMIT = 3 * 60 + 30  # 3 minutes and 30 seconds
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#beat-scheduler
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#worker-send-task-events
CELERY_WORKER_SEND_TASK_EVENTS = env.bool(
    "CELERY_WORKER_SEND_TASK_EVENTS", default=True
)
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#std-setting-task_send_sent_event
CELERY_TASK_SEND_SENT_EVENT = env.bool("CELERY_TASK_SEND_SENT_EVENT", default=True)
# https://docs.celeryq.dev/en/stable/userguide/optimizing.html#memory-usage
# https://docs.celeryq.dev/en/stable/userguide/workers.html#max-tasks-per-child-setting
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#worker-max-tasks-per-child
CELERY_WORKER_MAX_TASKS_PER_CHILD = env.int(
    "CELERY_WORKER_MAX_TASKS_PER_CHILD", default=2_000
)
# https://docs.celeryq.dev/en/stable/userguide/concurrency/index.html
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#worker-concurrency
if _celery_worker_concurrency := env.int("CELERY_WORKER_CONCURRENCY", default=None):
    CELERY_WORKER_CONCURRENCY = _celery_worker_concurrency
# https://docs.celeryq.dev/en/stable/userguide/optimizing.html#prefetch-limits
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#worker-prefetch-multiplier
CELERY_WORKER_PREFETCH_MULTIPLIER = env.int(
    "CELERY_WORKER_PREFETCH_MULTIPLIER", default=4
)
# https://github.com/celery/django-celery-results#issues-with-mysql
DJANGO_CELERY_RESULTS_TASK_ID_MAX_LENGTH = 191

# Celery Newer (v5.5+) Soft Shutdown
# https://docs.celeryq.dev/en/latest/userguide/configuration.html#worker-soft-shutdown-timeout
CELERY_WORKER_SOFT_SHUTDOWN_TIMEOUT = env.int(
    "CELERY_WORKER_SOFT_SHUTDOWN_TIMEOUT", default=10
)
CELERY_WORKER_ENABLE_SOFT_SHUTDOWN_ON_IDLE = env.bool(
    "CELERY_WORKER_ENABLE_SOFT_SHUTDOWN_ON_IDLE", default=False
)

# django-rest-framework
# -------------------------------------------------------------------------------
# django-rest-framework - https://www.django-rest-framework.org/api-guide/settings/
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework.authentication.SessionAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_RENDERER_CLASSES": (
        # https://github.com/vbabiy/djangorestframework-camel-case/tree/master#installation
        "djangorestframework_camel_case.render.CamelCaseJSONRenderer",
        "djangorestframework_camel_case.render.CamelCaseBrowsableAPIRenderer",
        # https://github.com/brianjbuck/drf_orjson_renderer#installation
        "drf_orjson_renderer.renderers.ORJSONRenderer",
        # https://www.django-rest-framework.org/api-guide/settings/
        "rest_framework.renderers.JSONRenderer",
    ),
    "DEFAULT_PARSER_CLASSES": (
        # https://github.com/vbabiy/djangorestframework-camel-case/tree/master#installation
        "djangorestframework_camel_case.parser.CamelCaseFormParser",
        "djangorestframework_camel_case.parser.CamelCaseMultiPartParser",
        "djangorestframework_camel_case.parser.CamelCaseJSONParser",
        # https://github.com/brianjbuck/drf_orjson_renderer#installation
        "drf_orjson_renderer.parsers.ORJSONParser",
        # https://www.django-rest-framework.org/api-guide/settings/
        "rest_framework.parsers.JSONParser",
    ),
    # https://github.com/brianjbuck/drf_orjson_renderer#installation
    "ORJSON_RENDERER_OPTIONS": (
        # https://github.com/ijl/orjson#opt_non_str_keys
        orjson.OPT_NON_STR_KEYS,
    ),
}
# https://github.com/vbabiy/djangorestframework-camel-case#swapping-renderer
JSON_CAMEL_CASE = {"RENDERER_CLASS": "drf_orjson_renderer.renderers.ORJSONRenderer"}

REST_FRAMEWORK_SHOW_BROWSABLE_API = env.bool(
    "REST_FRAMEWORK_SHOW_BROWSABLE_API", default=True
)
if not REST_FRAMEWORK_SHOW_BROWSABLE_API:
    REST_FRAMEWORK["DEFAULT_RENDERER_CLASSES"] = type(  # type: ignore[call-arg]
        REST_FRAMEWORK["DEFAULT_RENDERER_CLASSES"]
    )(
        class_name
        for class_name in REST_FRAMEWORK["DEFAULT_RENDERER_CLASSES"]
        if "BrowsableAPIRenderer" not in class_name  # type: ignore[operator]
    )

# django-cors-headers - https://github.com/adamchainz/django-cors-headers#setup
CORS_URLS_REGEX = r"^/api/.*$"

# By Default swagger ui is available only to admin user(s). You can change permission classes to change that
# See more configuration options at https://drf-spectacular.readthedocs.io/en/latest/settings.html#settings
SPECTACULAR_SETTINGS = {
    "TITLE": "Better Base API",
    "DESCRIPTION": "Documentation of API endpoints of Better Base",
    "VERSION": "0.1.0",
    "SERVE_PERMISSIONS": ["rest_framework.permissions.IsAdminUser"],
    "POSTPROCESSING_HOOKS": [
        "drf_spectacular.hooks.postprocess_schema_enums",
        "drf_spectacular.contrib.djangorestframework_camel_case.camelize_serializer_fields",
    ],
    "CAMELIZE_NAMES": False,
    "EXTENSIONS": {
        "authentication": [
            "backend.utils.rest_framework.csrf.CsrfExemptSessionAuthentication.CsrfExemptSessionScheme",
        ]
    },
}

# django-vite
# ------------------------------------------------------------------------------
# https://github.com/MrBin99/django-vite?tab=readme-ov-file#usage
DJANGO_VITE = {
    "default": {
        "dev_mode": env.bool("DJANGO_VITE_DEV_MODE", default=DEBUG),
        "dev_server_port": env.int("DJANGO_VITE_DEV_SERVER_PORT", default=4020),
        "static_url_prefix": "bundler",
    }
}

# django-extensions
# ------------------------------------------------------------------------------
# https://django-extensions.readthedocs.io/en/latest/installation_instructions.html#configuration
INSTALLED_APPS += ["django_extensions"]
# https://django-extensions.readthedocs.io/en/latest/shell_plus.html#additional-imports
SHELL_PLUS_POST_IMPORTS = [
    "from datetime import date as da, datetime as dt, timedelta as td, timezone as tz",
    "from decimal import Decimal as D",
    "from rich import print as rp",
    "from django.utils.timezone import now",
]
# https://django-extensions.readthedocs.io/en/latest/shell_plus.html#sql-queries
SHELL_PLUS_PRINT_SQL_TRUNCATE = 100_000


# structlog
# ------------------------------------------------------------------------------

# django-structlog
DJANGO_STRUCTLOG_CELERY_ENABLED = True


# Your stuff...
# ------------------------------------------------------------------------------

# Email Verifications
# ------------------------------------------------------------------------------
# The number of seconds a verify email link is valid for.
VERIFY_EMAIL_TIMEOUT = env.int(
    "VERIFY_EMAIL_TIMEOUT",
    default=60 * 60 * 24 * 21,  # 21 days
)

# Change Email
# ------------------------------------------------------------------------------
# The number of seconds a change email link is valid for.
CHANGE_EMAIL_TIMEOUT = env.int(
    "CHANGE_EMAIL_TIMEOUT",
    default=60 * 60 * 3,  # 3 hours
)

# Invitations
# ------------------------------------------------------------------------------
# After creating users, should we check for existing `Invitation`s that have an email
# matching the user's email but don't have an associated `user` yet?
INVITATIONS_CHECK_FOR_USER_ASSOCIATION_POST_USER_CREATION = env.bool(
    "INVITATIONS_CHECK_FOR_USER_ASSOCIATION_POST_USER_CREATION",
    default=True,
)
# If a secure invitation link is followed via email (which, at the time of writing, is
# implemented by appending an additional email-sending specified signature to secret
# links sent to email addresses), and we can detect the email followed matches the
# created or associated user's email (from the request or about to be associated with
# the request), should we automatically mark the user's email as verified?
INVITATIONS_ALLOW_USER_EMAIL_VERIFICATION_IF_CONDITIONS_SATISFIED = env.bool(
    "INVITATIONS_ALLOW_USER_EMAIL_VERIFICATION_IF_CONDITIONS_SATISFIED",
    default=True,
)

# Signup
# ------------------------------------------------------------------------------
SIGNUP_ENABLE_ONLY_ALLOWING_SPECIFIC_EMAIL_DOMAINS: bool = env.bool(
    "SIGNUP_ENABLE_ONLY_ALLOWING_SPECIFIC_EMAIL_DOMAINS",
    default=False,
)
SIGNUP_ONLY_ALLOW_SPECIFIC_EMAIL_DOMAINS: list[str] = env.list(
    "SIGNUP_ONLY_ALLOW_SPECIFIC_EMAIL_DOMAINS", default=[]
)
SIGNUP_ENABLE_ALLOWING_ANY_EMAIL_DOMAIN_IF_CREATING_FROM_INVITATION: bool = env.bool(
    "SIGNUP_ENABLE_ALLOWING_ANY_EMAIL_DOMAIN_IF_CREATING_FROM_INVITATION",
    default=False,
)

# Django Cachalot
# ------------------------------------------------------------------------------
# https://django-cachalot.readthedocs.io/en/latest/quickstart.html#settings
#
# https://django-cachalot.readthedocs.io/en/latest/quickstart.html#cachalot-enabled
CACHALOT_ENABLED = env.bool("CACHALOT_ENABLED", default=False)
# https://django-cachalot.readthedocs.io/en/latest/quickstart.html#cachalot-cache
CACHALOT_CACHE = env("CACHALOT_CACHE", default="default")
# https://django-cachalot.readthedocs.io/en/latest/quickstart.html#cachalot-only-cachable-tables
CACHALOT_ONLY_CACHABLE_TABLES = frozenset(
    [
        "accounts_account",
        "accounts_membership",
        "accounts_user",
        "accounts_user_groups",
        "accounts_user_user_permissions",
        "auth_group",
        "auth_group_permissions",
        "auth_permission",
        "django_content_type",
        "django_session",
    ]
)
CACHALOT_FINAL_SQL_CHECK = env.bool("CACHALOT_FINAL_SQL_CHECK", default=True)
