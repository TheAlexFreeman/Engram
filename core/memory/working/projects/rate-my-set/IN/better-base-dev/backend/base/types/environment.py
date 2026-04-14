from __future__ import annotations

from enum import StrEnum
from typing import Literal

EnvironmentType = Literal["dev", "test", "ci", "stage", "prod"]


class Environment(StrEnum):
    DEV = "dev"
    TEST = "test"
    CI = "ci"
    STAGE = "stage"
    PROD = "prod"

    @property
    def is_dev(self) -> bool:
        return self == Environment.DEV

    @property
    def is_test(self) -> bool:
        return self == Environment.TEST

    @property
    def is_ci(self) -> bool:
        return self == Environment.CI

    @property
    def is_stage(self) -> bool:
        return self == Environment.STAGE

    @property
    def is_prod(self) -> bool:
        return self == Environment.PROD

    @property
    def is_running_tests(self) -> bool:
        return self.is_test or self.is_ci
