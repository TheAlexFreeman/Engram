from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse

from django.conf import settings
from django.core.mail.message import EmailMultiAlternatives
from django.utils.html import escape
from django_stubs_ext import StrOrPromise
from pytest_django.asserts import assertInHTML

from backend.accounts.models.invitations import Invitation
from backend.accounts.ops.invitations import (
    check_invitation_email_delivery_signature,
    get_invitation_email_delivery_signature,
)


@dataclass(slots=True)
class TxtContains:
    value: str
    count: int | None = None


@dataclass(slots=True)
class HtmlContains:
    value: str
    count: int | None = None
    msg_prefix: str = ""


class EmailAssertions:
    m: EmailMultiAlternatives

    def __init__(self, m: EmailMultiAlternatives):
        self.m = m

    def assert_is_change_email_to_new_email(self, *, to_email: str) -> None:
        m = self.m

        assert m.subject == "Change Your Email on Better Base"
        assert m.to == [to_email]

        self._assert_from_email_correct()
        self._assert_has_both_txt_and_html()
        self._assert_contains(
            txt=[
                TxtContains("Change Your Email", count=1),
            ],
            html=[
                HtmlContains("Change Your Email"),
            ],
        )

        link = self.extract_change_email_link()

        assert link
        token = link.rsplit("/", 1)[1]
        assert token

    def assert_is_change_email_notifying_original_email(
        self, *, changing_from_email: str, changing_to_email: str
    ) -> None:
        m = self.m

        assert m.subject == "Email Change Request Made on Better Base"
        assert m.to == [changing_from_email]

        self._assert_from_email_correct()
        self._assert_has_both_txt_and_html()
        self._assert_contains(
            txt=[
                TxtContains(
                    "There has been a request to change your email from", count=1
                ),
                TxtContains(changing_from_email),
                TxtContains(changing_to_email),
                TxtContains(f"{changing_from_email} to {changing_to_email}", count=1),
            ],
            html=[
                HtmlContains("There has been a request to change your email from"),
                HtmlContains(changing_from_email),
                HtmlContains(changing_to_email),
            ],
        )

    def assert_is_verification_email(self, *, to_email: str) -> None:
        m = self.m

        assert m.subject == "Verify Your Email for Better Base"
        assert m.to == [to_email]

        self._assert_from_email_correct()
        self._assert_has_both_txt_and_html()
        self._assert_contains(
            txt=[
                TxtContains("Verify Your Email", count=1),
                TxtContains(
                    "Please verify this email by clicking the link below", count=1
                ),
            ],
            html=[
                HtmlContains("Verify Your Email"),
                HtmlContains(
                    "Please verify this email by clicking the link below", count=1
                ),
            ],
        )

        link = self.extract_verification_email_link()

        assert link
        token = link.rsplit("/", 1)[1]
        assert token

    def assert_is_invitation_email(
        self,
        invitation: Invitation,
        *,
        to_email: str,
        subject: StrOrPromise,
        user_exists: bool,
    ) -> None:
        m = self.m

        assert m.subject == subject
        assert m.to == [to_email]

        self._assert_from_email_correct()
        self._assert_has_both_txt_and_html()
        self._assert_contains(
            txt=[
                TxtContains("You have been invited to join", count=1),
                TxtContains(escape(invitation.team_display_name)),
                (
                    TxtContains("Accept Invitation", count=1)
                    if user_exists
                    else TxtContains("Create Account", count=1)
                ),
            ],
            html=[
                HtmlContains("You have been invited to join"),
                HtmlContains(escape(invitation.team_display_name)),
                (
                    HtmlContains("Accept Invitation")
                    if user_exists
                    else HtmlContains("Create Account")
                ),
            ],
        )

        link = self.extract_invitation_email_link()

        assert link
        token_part = link.rsplit("/", 1)[1]
        assert token_part
        token, signature_part = token_part.split("?")
        assert len(signature_part.split("=")) == 2
        signature = signature_part.split("=")[1]
        assert token
        assert invitation.secret_token == token
        assert signature == get_invitation_email_delivery_signature(invitation)
        assert check_invitation_email_delivery_signature(invitation, signature)

        assert invitation.email == to_email
        assert invitation.headline == subject, "Current expectation"

        parsed_url = urlparse(link)
        query_params = parse_qs(parsed_url.query, strict_parsing=True, errors="strict")
        assert (
            parsed_url.path
            == f"/accounts/invitations/redirect/to-follow/{invitation.secret_token}"
        )
        assert query_params == {
            "es": [get_invitation_email_delivery_signature(invitation)]
        }
        assert (
            check_invitation_email_delivery_signature(invitation, query_params["es"][0])
            is True
        )

    def assert_is_reset_password_email(self, *, to_email: str) -> None:
        m = self.m

        assert m.subject == "Password Reset for Better Base"
        assert m.to == [to_email]

        self._assert_from_email_correct()
        self._assert_has_both_txt_and_html()
        self._assert_contains(
            txt=[
                TxtContains("Reset Your Password", count=1),
                TxtContains(
                    "Please go to the following page and choose a new password", count=1
                ),
            ],
            html=[
                HtmlContains("Reset Your Password"),
                HtmlContains(
                    "Please go to the following page and choose a new password", count=1
                ),
            ],
        )

        link = self.extract_reset_password_email_link()

        assert link
        token = link.rsplit("/", 1)[1]
        assert token

    def extract_change_email_link(self) -> str:
        txt_re = re.compile(
            r"[\/\:a-zA-Z0-9]+auth/change-email/redirect/([a-zA-Z0-9_\-]+)/([a-zA-Z0-9_\-]+)"
        )
        html_re = txt_re

        txt_content = self._txt_content
        html_content = self._html_content

        txt_matches = list(txt_re.finditer(txt_content))
        html_matches = list(html_re.finditer(html_content))
        assert len(txt_matches) >= 1, "Current pre-condition"
        assert len(html_matches) >= 1, "Current pre-condition"

        urls_set: set[str] = set()
        uidb64s_set: set[str] = set()
        secret_tokens_set: set[str] = set()

        for m in txt_matches:
            assert m and m.group(0), "Current pre-condition"
            assert m.group(1), "Current pre-condition"
            assert m.group(2), "Current pre-condition"
            urls_set.add(m.group(0))
            uidb64s_set.add(m.group(1))
            secret_tokens_set.add(m.group(2))

        for m in html_matches:
            assert m and m.group(0), "Current pre-condition"
            assert m.group(1), "Current pre-condition"
            assert m.group(2), "Current pre-condition"
            urls_set.add(m.group(0))
            uidb64s_set.add(m.group(1))
            secret_tokens_set.add(m.group(2))

        assert len(urls_set) == 1, "Current post-condition"
        assert len(uidb64s_set) == 1, "Current post-condition"
        assert len(secret_tokens_set) == 1, "Current post-condition"

        return list(urls_set)[0]

    def extract_verification_email_link(self) -> str:
        txt_re = re.compile(
            r"[\/\:a-zA-Z0-9]+auth/verify-email/redirect/([a-zA-Z0-9_\-]+)/([a-zA-Z0-9_\-]+)"
        )
        html_re = txt_re

        txt_content = self._txt_content
        html_content = self._html_content

        txt_matches = list(txt_re.finditer(txt_content))
        html_matches = list(html_re.finditer(html_content))
        assert len(txt_matches) >= 1, "Current pre-condition"
        assert len(html_matches) >= 1, "Current pre-condition"

        urls_set: set[str] = set()
        uidb64s_set: set[str] = set()
        secret_tokens_set: set[str] = set()

        for m in txt_matches:
            assert m and m.group(0), "Current pre-condition"
            assert m.group(1), "Current pre-condition"
            assert m.group(2), "Current pre-condition"
            urls_set.add(m.group(0))
            uidb64s_set.add(m.group(1))
            secret_tokens_set.add(m.group(2))

        for m in html_matches:
            assert m and m.group(0), "Current pre-condition"
            assert m.group(1), "Current pre-condition"
            assert m.group(2), "Current pre-condition"
            urls_set.add(m.group(0))
            uidb64s_set.add(m.group(1))
            secret_tokens_set.add(m.group(2))

        assert len(urls_set) == 1, "Current post-condition"
        assert len(uidb64s_set) == 1, "Current post-condition"
        assert len(secret_tokens_set) == 1, "Current post-condition"

        return list(urls_set)[0]

    def extract_invitation_email_link(self) -> str:
        txt_re = re.compile(
            r"[\/\:a-zA-Z0-9]+accounts/invitations/redirect/to-follow/([a-zA-Z0-9_\-\?\&\=\#]+)"
        )
        html_re = txt_re

        txt_content = self._txt_content
        html_content = self._html_content

        txt_matches = list(txt_re.finditer(txt_content))
        html_matches = list(html_re.finditer(html_content))
        assert len(txt_matches) >= 1, "Current pre-condition"
        assert len(html_matches) >= 1, "Current pre-condition"

        urls_set: set[str] = set()
        secret_tokens_set: set[str] = set()

        for m in txt_matches:
            assert m and m.group(0), "Current pre-condition"
            assert m.group(1), "Current pre-condition"
            urls_set.add(m.group(0))
            secret_tokens_set.add(m.group(1))

        for m in html_matches:
            assert m and m.group(0), "Current pre-condition"
            assert m.group(1), "Current pre-condition"
            urls_set.add(m.group(0))
            secret_tokens_set.add(m.group(1))

        assert len(urls_set) == 1, "Current post-condition"
        assert len(secret_tokens_set) == 1, "Current post-condition"

        return list(urls_set)[0]

    def extract_reset_password_email_link(self) -> str:
        txt_re = re.compile(
            r"[\/\:a-zA-Z0-9]+auth/reset-password/redirect/([a-zA-Z0-9_\-]+)/([a-zA-Z0-9_\-]+)"
        )
        html_re = txt_re

        txt_content = self._txt_content
        html_content = self._html_content

        txt_matches = list(txt_re.finditer(txt_content))
        html_matches = list(html_re.finditer(html_content))
        assert len(txt_matches) >= 1, "Current pre-condition"
        assert len(html_matches) >= 1, "Current pre-condition"

        urls_set: set[str] = set()
        uidb64s_set: set[str] = set()
        secret_tokens_set: set[str] = set()

        for m in txt_matches:
            assert m and m.group(0), "Current pre-condition"
            assert m.group(1), "Current pre-condition"
            assert m.group(2), "Current pre-condition"
            urls_set.add(m.group(0))
            uidb64s_set.add(m.group(1))
            secret_tokens_set.add(m.group(2))

        for m in html_matches:
            assert m and m.group(0), "Current pre-condition"
            assert m.group(1), "Current pre-condition"
            assert m.group(2), "Current pre-condition"
            urls_set.add(m.group(0))
            uidb64s_set.add(m.group(1))
            secret_tokens_set.add(m.group(2))

        assert len(urls_set) == 1, "Current post-condition"
        assert len(uidb64s_set) == 1, "Current post-condition"
        assert len(secret_tokens_set) == 1, "Current post-condition"

        return list(urls_set)[0]

    @property
    def _txt_content(self) -> str:
        m = self.m

        assert isinstance(m.body, str), "Current pre-condition"

        return m.body

    @property
    def _html_content(self) -> str:
        m = self.m

        assert len(m.alternatives) == 1, "Current pre-condition"
        assert m.alternatives[0][1] == "text/html", "Current pre-condition"
        assert isinstance(m.alternatives[0][0], str), "Current pre-condition"

        return m.alternatives[0][0]

    def _assert_from_email_correct(self, from_email: str | None = None) -> None:
        m = self.m
        use_from_email = from_email or settings.DEFAULT_FROM_EMAIL

        assert m.from_email == use_from_email

    def _assert_has_both_txt_and_html(self) -> None:
        m = self.m

        txt = m.body
        assert txt

        assert len(m.alternatives) == 1, "Current pre-condition"
        assert m.alternatives[0][1] == "text/html"
        html = m.alternatives[0][0]
        assert html

    def _assert_contains(
        self,
        *,
        txt: list[TxtContains],
        html: list[HtmlContains],
    ) -> None:
        assert isinstance(txt, list | tuple | set), "Current pre-condition"
        assert isinstance(html, list | tuple | set), "Current pre-condition"

        if txt:
            txt_content = self._txt_content

        if html:
            html_content = self._html_content

        for txt_c in txt:
            if txt_c.count is None:
                assert txt_c.value in txt_content
            else:
                assert txt_content.count(txt_c.value) == txt_c.count

        for html_c in html:
            # This can cover some edge cases that `assertInHTML`, in my opinion, will
            # throw a false negative on in this context. `assertInHTML` will assume that
            # `html_c.value` is an "HTML fragment", but we want to be able to check even
            # partial strings. I.E., assume that the HTML we're checking against has:
            # ```
            # <div>Some text that is within a div</div>
            # ```
            # within it. If we have `html_c.value` equal to "Some text", we want that to
            # pass. `assertInHTML` may fail that test because it's not a complete HTML
            # fragment. This is a more general/loose check in that regard, but is what
            # we want.
            if html_c.value in html_content:
                continue
            assertInHTML(
                html_c.value,
                html_content,
                count=html_c.count,
                msg_prefix=html_c.msg_prefix,
            )
