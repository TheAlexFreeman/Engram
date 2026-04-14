from __future__ import annotations

import logging
import os

import structlog
from celery import Celery
from celery.signals import setup_logging
from django_structlog.celery.steps import DjangoStructLogInitStep

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

app = Celery("backend")

# https://django-structlog.readthedocs.io/en/latest/celery.html#initialize-celery-worker-with-djangostructloginitstep
app.steps["worker"].add(DjangoStructLogInitStep)


# https://django-structlog.readthedocs.io/en/latest/celery.html#configure-celery-s-logger
@setup_logging.connect
def receiver_setup_logging(
    loglevel, logfile, format, colorize, **kwargs
):  # pragma: no cover
    from django.conf import settings

    IS_SENTRY_ENABLED: bool = getattr(settings, "IS_SENTRY_ENABLED", False)
    IS_STRUCTLOG_SENTRY_ENABLED: bool = getattr(
        settings, "IS_STRUCTLOG_SENTRY_ENABLED", False
    )
    if IS_SENTRY_ENABLED and IS_STRUCTLOG_SENTRY_ENABLED:
        from structlog_sentry import SentryProcessor

        SENTRY_LOG_LEVEL: int = getattr(settings, "SENTRY_LOG_LEVEL", logging.INFO)
        SENTRY_EVENT_LEVEL: int = getattr(
            settings, "SENTRY_EVENT_LEVEL", logging.WARNING
        )

    logging.config.dictConfig(  # type: ignore[attr-defined]
        {
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
    )

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


# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object("django.conf:settings", namespace="CELERY")

# Load task modules from all registered Django app configs.
app.autodiscover_tasks()
