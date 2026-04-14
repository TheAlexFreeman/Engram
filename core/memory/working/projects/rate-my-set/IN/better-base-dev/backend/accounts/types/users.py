from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from django.db.models import TextChoices

if TYPE_CHECKING:
    from backend.accounts.models import Account, Membership, User


class UserCreatedFrom(TextChoices):
    DIRECT_SIGNUP = "direct_signup", "Direct Signup"
    ACCOUNT_INVITATION = "account_invitation", "Account Invitation"
    ADMIN = "admin", "Admin"
    CREATE_DEFAULT_ADMINS = "create_default_admins", "Create Default Admins Command"
    CREATE_SUPERUSER = "create_superuser", "Create Superuser Command"
    OTHER = "other", "Other"
    UNKNOWN = "unknown", "Unknown"


@dataclass
class UserCreationResult:
    user: User

    account: Account
    account_automatically_created: bool

    membership: Membership

    is_active: bool

    is_staff: bool
    is_superuser: bool

    created_from: UserCreatedFrom
