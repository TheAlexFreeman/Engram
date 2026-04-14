from __future__ import annotations

from types import SimpleNamespace
from typing import Final

from django.contrib.admin import site as admin_site
from django.contrib.admin.widgets import ForeignKeyRawIdWidget
from django.contrib.auth import forms as admin_forms
from django.db.models import BigAutoField
from django.forms import ChoiceField, EmailField, ModelChoiceField
from django.utils.translation import gettext_lazy as _
from django.views.decorators.debug import sensitive_variables

from backend.accounts.models import Account, User
from backend.accounts.ops.users import create_superuser, create_user
from backend.accounts.types.roles import Role
from backend.accounts.types.users import UserCreatedFrom, UserCreationResult
from backend.utils.model_state import is_inserting

fake_account_rel: Final[SimpleNamespace] = SimpleNamespace(
    model=Account,
    get_related_field=lambda: BigAutoField(name="id"),
    limit_choices_to=None,
)


class UserAdminCreationForm(admin_forms.UserCreationForm):
    """Form for creating a `User` in the admin area."""

    account = ModelChoiceField(
        queryset=Account.objects.all(),
        widget=ForeignKeyRawIdWidget(fake_account_rel, admin_site),  # type: ignore[arg-type]
        label=_("Account"),
        required=False,
        help_text=_(
            "If you leave this blank, only a personal account will be auto-created for "
            "the user. If you input a value, they will be added as a member of the "
            "account with the specified ID (instead of a personal account being "
            "auto-created)."
        ),
    )
    membership_role = ChoiceField(
        label=_("Membership Role"),
        choices=Role.choices,
        initial=Role.OWNER,
        help_text=_(
            "If you're leaving the Account blank so that it's automatically created, "
            "you should keep this set at the Owner default. Otherwise, you can select "
            "whatever role."
        ),
    )

    def clean(self):
        cleaned_data = super().clean() or {}
        account: Account | None = cleaned_data.get("account")

        membership_role: Role = Role(cleaned_data["membership_role"])
        # Confirm/make sure that `membership_role` is the `Role` enum and not just the
        # string.
        cleaned_data["membership_role"] = membership_role
        if account is None and membership_role != Role.OWNER:
            self.add_error(
                "membership_role",
                _(
                    "If you're leaving the Account blank so that it's automatically "
                    "created, you should keep the role set at the Owner default. Otherwise, "
                    "you can select whatever role."
                ),
            )

        if (
            existing_user := User.objects.first_existing_with_email_case_insensitive(
                cleaned_data["email"]
            )
        ) is not None:
            self.add_error(
                "email",
                (
                    _("This email has already been taken (%(email)s).")
                    % {"email": existing_user.email}
                ),
            )
        cleaned_data["account"] = account
        return cleaned_data

    class Meta(admin_forms.UserCreationForm.Meta):
        model = User
        fields = (
            "account",
            "email",
            "name",
            "membership_role",
            "password1",
            "password2",
        )
        field_classes = {"email": EmailField}
        error_messages = {
            "email": {"unique": _("This email has already been taken.")},
        }

    @sensitive_variables("password", "cleaned_data", "password1", "password2")
    def save(self, commit: bool = True) -> User:
        """
        Important NOTE: `commit=False` is ignored right now due to how the `User`
        creation process works with `Account`s, `Membership`s, `User`s, etc.
        """
        cleaned = self.cleaned_data

        account: Account | None = cleaned.get("account")

        email: str = cleaned["email"]
        password: str = cleaned["password1"]
        name: str = cleaned.get("name") or ""

        membership_role: Role = cleaned["membership_role"]

        is_active: bool = cleaned.get("is_active", True)

        is_staff: bool = cleaned.get("is_staff", False)
        is_superuser: bool = cleaned.get("is_superuser", False)

        _initial_instance: User = self.instance
        assert is_inserting(_initial_instance), (
            "Pre-condition: The `_initial_instance` `User` should not have been saved."
        )

        creation_result: UserCreationResult
        if is_superuser:
            creation_result = create_superuser(
                account=account,
                email=email,
                password=password,
                name=name,
                membership_role=membership_role,
                created_from=UserCreatedFrom.ADMIN,
                is_active=is_active,
                _is_staff_=is_staff,
                _is_superuser_=is_superuser,
            )
        else:
            creation_result = create_user(
                account=account,
                email=email,
                password=password,
                name=name,
                membership_role=membership_role,
                created_from=UserCreatedFrom.ADMIN,
                is_active=is_active,
                _is_staff_=is_staff,
                _is_superuser_=is_superuser,
            )

        new_instance: User = creation_result.user
        self.instance = new_instance

        if not commit:
            # If not committing, add a method to the form to allow deferred saving of
            # m2m data (copied from standard Django parent class implementation).
            self.save_m2m = self._save_m2m  # type: ignore[method-assign,attr-defined]

        return new_instance


class UserAdminChangeForm(admin_forms.UserChangeForm):
    """Form for updating a `User` in the admin area."""

    class Meta(admin_forms.UserChangeForm.Meta):
        model = User
        field_classes = {"email": EmailField}
