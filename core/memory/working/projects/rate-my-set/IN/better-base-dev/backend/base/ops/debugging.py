from __future__ import annotations

import os

from .environment import get_environment


def is_in_debugger() -> bool:
    """
    NOTE: At the time of writing, this `is_in_debugger()` function can only return true
    in the dev environment when the `IS_RUNNING_DEBUGGER` environment variable is set
    and one of the values `(True, "True", "true", "1")`.
    """
    environment = get_environment()

    environment_passes = environment.is_dev
    env_variable_passes = os.environ.get("IS_RUNNING_DEBUGGER") in (
        True,
        "True",
        "true",
        "1",
    )

    return environment_passes and env_variable_passes
