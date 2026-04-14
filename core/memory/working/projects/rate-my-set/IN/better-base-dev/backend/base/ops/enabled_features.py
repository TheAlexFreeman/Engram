from __future__ import annotations

from functools import lru_cache
from typing import Final, Literal

from backend.base.ops.environment import get_environment
from backend.base.types.environment import Environment

FEATURE_ACCOUNTS_ACCOUNT_CREATE: Final = "accounts.account.create"
FEATURE_ACCOUNTS_ACCOUNT_CREATE_PERSONAL_ACCOUNT: Final = (
    "accounts.account.create_personal_account"
)
FEATURE_ACCOUNTS_ACCOUNT_CREATE_TEAM_ACCOUNT: Final = (
    "accounts.account.create_team_account"
)
FEATURE_ACCOUNTS_ACCOUNT_UPDATE: Final = "accounts.account.update"
FEATURE_ACCOUNTS_ACCOUNT_UPDATE_ACCOUNT_TYPE: Final = (
    "accounts.account.update_account_type"
)
FEATURE_ACCOUNTS_ACCOUNT_UPDATE_UPLOADED_PROFILE_IMAGE: Final = (
    "accounts.account.update_uploaded_profile_image"
)

FEATURE_ACCOUNTS_USER_UPDATE: Final = "accounts.user.update"
FEATURE_ACCOUNTS_USER_UPDATE_UPLOADED_PROFILE_IMAGE: Final = (
    "accounts.user.update_uploaded_profile_image"
)
FEATURE_ACCOUNTS_USER_DISPLAY_NAME_UPDATE: Final = "accounts.user.display_name_update"

FEATURE_AUTH_CHANGE_EMAIL: Final = "auth.change_email"

FEATURE_INVITATIONS: Final = "invitations"

type FeatureType = Literal[
    "accounts.account.create",
    "accounts.account.create_personal_account",
    "accounts.account.create_team_account",
    "accounts.account.update",
    "accounts.account.update_account_type",
    "accounts.account.update_uploaded_profile_image",
    "accounts.user.update",
    "accounts.user.update_uploaded_profile_image",
    "auth.change_email",
    "invitations",
]


class FeatureIsDisabledError(RuntimeError):
    def __init__(self, feature: FeatureType) -> None:
        self.message = f"The feature '{feature}' is disabled."

        super().__init__(self.message)


def check_if_feature_is_enabled(feature: FeatureType) -> None:
    disabled_features = get_disabled_features()
    if feature in disabled_features:
        raise FeatureIsDisabledError(feature)


def get_disabled_features() -> frozenset[FeatureType]:
    environment = get_environment()
    return _get_disabled_features(environment)


@lru_cache(8, typed=False)
def _get_disabled_features(environment: Environment) -> frozenset[FeatureType]:
    if not (environment.is_prod or environment.is_stage):
        return frozenset([])
    return frozenset(
        (
            # NOTE: At the time of writing, all features are enabled by default.
            # Uncomment the features you want to disable
            # FEATURE_ACCOUNTS_ACCOUNT_CREATE,
            # FEATURE_ACCOUNTS_ACCOUNT_CREATE_PERSONAL_ACCOUNT,
            # FEATURE_ACCOUNTS_ACCOUNT_CREATE_TEAM_ACCOUNT,
            # FEATURE_ACCOUNTS_ACCOUNT_UPDATE,
            # FEATURE_ACCOUNTS_ACCOUNT_UPDATE_ACCOUNT_TYPE,
            # FEATURE_ACCOUNTS_ACCOUNT_UPDATE_UPLOADED_PROFILE_IMAGE,
            # FEATURE_ACCOUNTS_USER_UPDATE,
            # FEATURE_ACCOUNTS_USER_UPDATE_UPLOADED_PROFILE_IMAGE,
            # FEATURE_AUTH_CHANGE_EMAIL,
            # FEATURE_INVITATIONS,
        )
    )
