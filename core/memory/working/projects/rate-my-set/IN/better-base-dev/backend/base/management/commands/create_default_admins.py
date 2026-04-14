from __future__ import annotations

import time

import pyperclip
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from backend.accounts.models import User
from backend.accounts.ops.users import create_superuser
from backend.accounts.types.roles import Role
from backend.accounts.types.users import UserCreatedFrom
from backend.base.ops.environment import get_environment


class Command(BaseCommand):
    """
    Create default admin `User`(s) and any other associated records.

    Not intended for production use. For production, use `python manage.py
    createsuperuser` and explicitly set the email + password + anything else there.
    """

    help = __doc__

    def handle(self, *args, **options):
        environment = get_environment()
        if not environment.is_dev and not environment.is_running_tests:
            raise CommandError(
                "Cannot run this command outside of the dev environment right now."
            )

        email = "admin@betterbase.com"
        password = "better_base_admin_pw_9*"
        defaults = {
            "name": "Admin Superuser",
            "membership_role": Role.OWNER,
            "created_from": UserCreatedFrom.CREATE_DEFAULT_ADMINS,
        }
        admin_user = User.objects.filter(email=email).first()
        admin_user_created = False
        if admin_user is None:
            with transaction.atomic():
                admin_creation_result = create_superuser(
                    account=None,
                    email=email,
                    password=password,
                    **defaults,  # type: ignore[arg-type]
                )
                admin_user = admin_creation_result.user
                admin_user_created = True

        if admin_user_created:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Admin superuser for {email} was created: {admin_user!r}. The "
                    f"password is `{password}` (inside the `s)."
                )
            )
        else:
            self.stdout.write(
                self.style.NOTICE(
                    f"Admin superuser for {email} already existed: {admin_user!r}. "
                    "The default password the superuser is initially created with "
                    f"is `{password}` (inside the `s)."
                )
            )

        try:
            pyperclip.copy(email)
            # See
            # https://github.com/asweigart/pyperclip/issues/196#issuecomment-912801976.
            # It seems like a slight pause is needed to lock lock up access to the
            # clipboard and have this work for, for example, Windows clipboard history
            # (Windows Key + v by default).
            time.sleep(0.250)
            pyperclip.copy(password)
        except Exception as e:
            self.stdout.write(
                self.style.NOTICE(
                    "Unable to copy email and password to the clipboard. You'll have "
                    f'to copy paste and/or input them manually. Exception: "{e}".'
                )
            )
        else:
            self.stdout.write(
                "Copied email (first copy) and password (second copy) to the system "
                "clipboard."
            )
