from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.http import HttpRequest

from backend.accounts.models.users import User


@dataclass
class UserLoggedIn:
    sender: type[User]
    request: HttpRequest
    user: User

    counter_num: int


@dataclass
class UserLoggedOut:
    sender: type[User] | None
    request: HttpRequest
    user: User | None

    counter_num: int


AuthSignaledEvent = UserLoggedIn | UserLoggedOut


@dataclass
class UserEmail:
    email: str


class AuthWatcher:
    """
    Auth-Related Context Managers for tests.

    Example Usage:

    ```
    user = User()
    auth_watcher = AuthWatcher()
    with auth_watcher.expect_user_login(user=user):
        # Similar to `pytest.raises` except this will assert on the exit of the `with`
        # block that the provided user was logged in.
        ...
    ```
    """

    signaled_events: list[AuthSignaledEvent]

    def __init__(self, *, counter_start: int = 0):
        self.signaled_events = []
        self.counter = counter_start

    @contextmanager
    def expect_user_login(
        self, user: User | UserEmail, *, assert_counter_equals: int | None = None
    ):
        starting_index = len(self.signaled_events)

        try:
            user_logged_in.connect(self._on_user_logged_in)

            yield

            was_found: bool = False
            saw_counter_unequal_to: int | None = None
            for event in self.signaled_events[starting_index:]:
                if isinstance(event, UserLoggedIn):
                    if isinstance(user, UserEmail):
                        if event.user.email != user.email:
                            continue
                    else:
                        if event.user != user:
                            continue

                    if (
                        assert_counter_equals is not None
                        and event.counter_num != assert_counter_equals
                    ):
                        saw_counter_unequal_to = event.counter_num
                        continue

                    was_found = True
                    break

            if saw_counter_unequal_to is not None:
                assert was_found, (
                    f"`UserLoggedIn` signaled event was not found with counter value. "
                    f"Wanted counter to be equal to `{assert_counter_equals}`, but "
                    f"latest counter found was `{saw_counter_unequal_to}`."
                )
            else:
                assert was_found, "`UserLoggedIn` signaled event was not found."

        finally:
            user_logged_in.disconnect(self._on_user_logged_in)

    @contextmanager
    def expect_no_user_login(
        self, user: User | UserEmail, *, assert_counter_equals: int | None = None
    ):
        starting_index = len(self.signaled_events)

        try:
            user_logged_in.connect(self._on_user_logged_in)

            yield

            was_found: bool = False
            for event in self.signaled_events[starting_index:]:
                if isinstance(event, UserLoggedIn):
                    if isinstance(user, UserEmail):
                        if event.user.email != user.email:
                            continue
                    else:
                        if event.user != user:
                            continue

                    if (
                        assert_counter_equals is not None
                        and event.counter_num != assert_counter_equals
                    ):
                        continue

                    was_found = True
                    break

            assert not was_found, (
                "`UserLoggedIn` signaled event was found (with counter value "
                f"{event.counter_num})."
            )

        finally:
            user_logged_in.disconnect(self._on_user_logged_in)

    @contextmanager
    def expect_user_logout(
        self,
        user: User | UserEmail | None = None,
        *,
        assert_counter_equals: int | None = None,
    ):
        starting_index = len(self.signaled_events)

        try:
            user_logged_out.connect(self._on_user_logged_out)

            yield

            was_found: bool = False
            saw_counter_unequal_to: int | None = None
            for event in self.signaled_events[starting_index:]:
                if isinstance(event, UserLoggedOut):
                    if isinstance(user, UserEmail):
                        if getattr(event.user, "email", None) != user.email:
                            continue
                    else:
                        if event.user != user:
                            continue

                    if (
                        assert_counter_equals is not None
                        and event.counter_num != assert_counter_equals
                    ):
                        saw_counter_unequal_to = event.counter_num
                        continue

                    was_found = True
                    break

            if saw_counter_unequal_to is not None:
                assert was_found, (
                    f"`UserLoggedOut` signaled event was not found with counter value. "
                    f"Wanted counter to be equal to `{assert_counter_equals}`, but "
                    f"latest counter found was `{saw_counter_unequal_to}`."
                )
            else:
                assert was_found, "`UserLoggedOut` signaled event was not found."

        finally:
            user_logged_out.disconnect(self._on_user_logged_out)

    @contextmanager
    def expect_no_user_logout(
        self,
        user: User | UserEmail | None = None,
        *,
        assert_counter_equals: int | None = None,
    ):
        starting_index = len(self.signaled_events)

        try:
            user_logged_out.connect(self._on_user_logged_out)

            yield

            was_found: bool = False
            for event in self.signaled_events[starting_index:]:
                if isinstance(event, UserLoggedOut):
                    if isinstance(user, UserEmail):
                        if getattr(event.user, "email", None) != user.email:
                            continue
                    else:
                        if event.user != user:
                            continue

                    if (
                        assert_counter_equals is not None
                        and event.counter_num != assert_counter_equals
                    ):
                        continue

                    was_found = True
                    break

            assert not was_found, (
                "`UserLoggedOut` signaled event was found (with counter value "
                f"{event.counter_num})."
            )

        finally:
            user_logged_out.disconnect(self._on_user_logged_out)

    def _on_user_logged_in(
        self,
        *,
        sender: type[User],
        request: HttpRequest,
        user: User,
        **kwargs: Any,
    ) -> None:
        next_counter_num = self.counter + 1
        self.counter = next_counter_num
        self.signaled_events.append(
            UserLoggedIn(sender, request, user, next_counter_num)
        )

    def _on_user_logged_out(
        self,
        *,
        sender: type[User] | None,
        request: HttpRequest,
        user: User | None,
        **kwargs: Any,
    ) -> None:
        next_counter_num = self.counter + 1
        self.counter = next_counter_num
        self.signaled_events.append(
            UserLoggedOut(sender, request, user, next_counter_num)
        )
