"""
With these settings, tests run faster.
"""

from __future__ import annotations

from backend.base.types.environment import Environment

from .mixins.dev_env_files import *  # noqa  # isort:skip
from .ci import *  # noqa  # isort:skip

_environment_string = "test"
assert _environment_string in ([*Environment]), "Current Pre-Condition"
ENVIRONMENT = Environment(_environment_string)
