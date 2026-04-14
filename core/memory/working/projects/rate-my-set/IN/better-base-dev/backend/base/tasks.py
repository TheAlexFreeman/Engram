from __future__ import annotations

import fractions
from types import EllipsisType
from typing import Any, NoReturn, TypedDict

import structlog
from celery import Task

from backend.base.ops.emails import send_example_email as send_example_email_op
from config import celery_app

logger = structlog.stdlib.get_logger()


class SendExampleEmailResultDict(TypedDict):
    to_email: str
    num_sent: int
    sent_at: str  # ISO 8601 datetime string


@celery_app.task(
    # https://docs.celeryq.dev/en/stable/userguide/configuration.html#task-acks-late
    acks_late=True,
    # https://docs.celeryq.dev/en/stable/userguide/configuration.html#task-reject-on-worker-lost
    task_reject_on_worker_lost=None,
    # https://docs.celeryq.dev/en/stable/userguide/configuration.html#task-track-started
    track_started=True,
    # https://docs.celeryq.dev/en/latest/userguide/tasks.html#automatic-retry-for-known-exceptions
    autoretry_for=(Exception,),
    retry_backoff=5,  # 5 seconds
    retry_backoff_max=30,  # 30 seconds
    retry_kwargs={"max_retries": 3},  # 3 retries max
    # https://docs.celeryq.dev/en/stable/userguide/configuration.html#std-setting-task_soft_time_limit
    soft_time_limit=20,  # 20 seconds
    # https://docs.celeryq.dev/en/stable/userguide/configuration.html#task-time-limit
    time_limit=30,  # 30 seconds
)
def send_example_email(
    to_email: str,
    *,
    one_variable: str | EllipsisType = ...,
    another_variable: str | EllipsisType = ...,
) -> SendExampleEmailResultDict:
    """
    Send an example email (through a Celery task) to `to_email`. At the time of writing,
    if `one_variable` or `another_variable` are not provided, the defaults from
    `send_example_email_op` will be used.
    """
    kwargs: dict[str, Any] = {}
    if one_variable is not ...:
        kwargs["one_variable"] = one_variable
    if another_variable is not ...:
        kwargs["another_variable"] = another_variable

    result = send_example_email_op(to_email, **kwargs)

    return SendExampleEmailResultDict(
        to_email=to_email,
        num_sent=result.num_sent,
        sent_at=result.sent_at.isoformat(),
    )


class IntentionallyThrownError(Exception):
    pass


@celery_app.task(
    # https://docs.celeryq.dev/en/stable/userguide/tasks.html#example
    bind=True,
    # https://docs.celeryq.dev/en/stable/userguide/configuration.html#task-acks-late
    acks_late=False,
    # https://docs.celeryq.dev/en/stable/userguide/configuration.html#task-reject-on-worker-lost
    task_reject_on_worker_lost=None,
    # https://docs.celeryq.dev/en/stable/userguide/configuration.html#task-track-started
    track_started=True,
    # https://docs.celeryq.dev/en/latest/userguide/tasks.html#automatic-retry-for-known-exceptions
    autoretry_for=(Exception,),
    retry_backoff=2,  # 2 seconds
    retry_backoff_max=15,  # 15 seconds
    retry_kwargs={"max_retries": 2},  # 2 retries max
    # https://docs.celeryq.dev/en/stable/userguide/configuration.html#std-setting-task_soft_time_limit
    soft_time_limit=10,  # 10 seconds
    # https://docs.celeryq.dev/en/stable/userguide/configuration.html#task-time-limit
    time_limit=20,  # 20 seconds
)
def intentionally_throw_error(
    self: Task,
    *,
    check_stack_info_logging: bool = False,
    check_critical_logging: bool = False,
    check_exception_logging: bool = False,
) -> NoReturn:
    """
    Intentionally throw an error (and log message at various log levels) so that we can
    test any error handling or logging services appropriately (I.E. https://sentry.io
    and/or anything else).
    """

    x = 1
    y = "two"
    z = f"{x} - {y}"

    # Throw a more interesting type in variable in as well for the variables and stack
    # trace handling, etc.
    some_other_var = fractions.Fraction(100, 9899)

    logger.debug("Here's a debug message.", x=x, y=y, some_other_var=some_other_var)
    logger.info("Here's an info message.", x=x, y=y, some_other_var=some_other_var)
    logger.warning("Here's a warning message.", x=x, y=y, some_other_var=some_other_var)
    logger.error("Here's an error message.", x=x, y=y, some_other_var=some_other_var)

    if check_stack_info_logging:
        assert z, "Pre-condition"
        assert some_other_var, "Pre-condition"
        logger.info(
            "Here's a message with stack info.",
            x=x,
            y=y,
            some_other_var=some_other_var,
            stack_info=True,
        )

    if check_critical_logging:
        logger.critical(
            "Here's a critical message.",
            x=x,
            y=y,
            some_other_var=some_other_var,
        )

    if check_exception_logging:
        try:
            z0 = 5 / 0  # noqa: F841
        except ZeroDivisionError:
            logger.exception(
                "Here's a message with an exception.",
                x=x,
                y=y,
                some_other_var=some_other_var,
            )

    logger.info(
        f"Info - Celery Retries Value: {self.request.retries}",
        retries=self.request.retries,
    )

    raise IntentionallyThrownError(
        "Here is my intentionally thrown error message - retries - "
        f"{self.request.retries}."
    )
