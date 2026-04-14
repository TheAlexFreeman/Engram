from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Collection
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import ClassVar, Final, Literal, Self, TypeAlias, final

from django.conf import settings
from django.core.mail import EmailMessage, EmailMultiAlternatives
from django.template import Template
from django.template.loader import get_template
from django.utils import timezone
from django_stubs_ext import StrOrPromise
from typing_extensions import Sentinel

from backend.utils.emails import (
    parse_just_email_from_email_or_name_and_email_string,
)
from backend.utils.repr import NiceReprMixin

ExtType: TypeAlias = Literal[".html", ".txt"]

is_abstract: Sentinel = Sentinel("is_abstract")
use_default: Sentinel = Sentinel("use_default")


class Key(StrEnum):
    EMAIL_EXAMPLE = "email_example"
    EMAIL_RESET_PASSWORD = "email_reset_password"
    EMAIL_VERIFICATION_EMAIL = "email_verification_email"
    EMAIL_CHANGE_EMAIL = "email_change_email"
    EMAIL_NOTIFY_ORIGINAL_EMAIL_OF_EMAIL_CHANGE_REQUEST = (
        "email_notify_original_email_of_email_change_request"
    )
    EMAIL_TEAM_INVITATION = "email_team_invitation"


@dataclass(kw_only=True)
class CoreSpecBase:
    template_path: str

    is_transactional: bool

    use_html: bool = True
    use_txt: bool = True
    raise_exception_on_failure_to_send: bool = True


@dataclass(kw_only=True)
class RenderSpecBase:
    web_app_root_url: str | Sentinel = use_default
    landing_site_root_url: str | Sentinel = use_default
    support_email: str | Sentinel = use_default

    def __post_init__(self):
        if self.web_app_root_url is use_default:
            self.web_app_root_url = settings.BASE_WEB_APP_URL
        if self.landing_site_root_url is use_default:
            self.landing_site_root_url = settings.BASE_LANDING_SITE_URL
        if self.support_email is use_default:
            self.support_email = parse_just_email_from_email_or_name_and_email_string(
                settings.DEFAULT_SUPPORT_EMAIL
            )


@dataclass(kw_only=True)
class DeliverySpecBase:
    to_email: str

    subject: StrOrPromise

    from_email: str | Sentinel = use_default

    cc: list[str] = field(default_factory=list)
    bcc: list[str] = field(default_factory=list)

    def __post_init__(self):
        if self.from_email is use_default:
            self.from_email = settings.DEFAULT_FROM_EMAIL


@dataclass(kw_only=True)
class EmailSendResult:
    num_sent: int
    sent_at: datetime


class Email(ABC, NiceReprMixin):
    REPR_FIELDS = ("core", "render", "delivery")

    key: ClassVar[Key | Sentinel] = is_abstract

    def __init_subclass__(
        cls,
        *args,
        key: Key | Sentinel,
        **kwargs,
    ) -> None:
        return_value = super().__init_subclass__(*args, **kwargs)

        cls.key = key

        return return_value

    HTML_EXTENSION: Final[Literal[".html"]] = ".html"
    TXT_EXTENSION: Final[Literal[".txt"]] = ".txt"

    @dataclass(kw_only=True)
    class CoreSpec(CoreSpecBase):
        pass

    @dataclass(kw_only=True)
    class RenderSpec(RenderSpecBase):
        pass

    @dataclass(kw_only=True)
    class DeliverySpec(DeliverySpecBase):  # type: ignore[override,unused-ignore]
        pass

    def __init__(
        self,
        *,
        core: CoreSpec,
        render: RenderSpec,
        delivery: DeliverySpec,
    ):
        self.core = core
        self.render = render
        self.delivery = delivery

    @classmethod
    @abstractmethod
    def prepare(cls, *args, **kwargs) -> Self:
        raise NotImplementedError("Subclasses must implement this method")

    @final
    def send(self) -> EmailSendResult:
        return self._send()

    def _render_template(self, template_path: str) -> str:
        template = self._get_template(template_path)
        context_dict = asdict(self.render)
        rendered = template.render(context_dict)  # type: ignore[arg-type]
        return rendered

    def _get_template(self, template_path: str) -> Template:
        return get_template(template_path)  # type: ignore[return-value]

    def _find_template_paths(self) -> dict[ExtType, str]:
        core = self.core

        html_extension = self.HTML_EXTENSION
        txt_extension = self.TXT_EXTENSION
        start = core.template_path
        for ext in (html_extension, txt_extension):
            if start.endswith(ext):
                start = start[: -len(ext)]
        paths: dict[ExtType, str] = {}

        if core.use_html:
            paths[html_extension] = f"{start}{html_extension}"
        if core.use_txt:
            paths[txt_extension] = f"{start}{txt_extension}"

        return paths

    def _render_all(self) -> dict[ExtType, str]:
        paths = self._find_template_paths()
        if not paths:
            raise ValueError(
                f'No templates found for `template_path` of "{self.core.template_path}".'
            )

        rendered: dict[ExtType, str] = {}
        for ext, path in paths.items():
            rendered[ext] = self._render_template(path)

        return rendered

    def _send(self) -> EmailSendResult:
        rendered = self._render_all()
        message_instance = self._get_email_message_instance(rendered)
        email_send_result = self._send_from_email_message_instance(message_instance)
        return email_send_result

    def _get_email_message_class(
        self, extensions: Collection[ExtType]
    ) -> type[EmailMessage]:
        if len(extensions) >= 2 and self.TXT_EXTENSION in extensions:
            return EmailMultiAlternatives
        return EmailMessage

    def _get_email_message_instance(self, rendered: dict[ExtType, str]) -> EmailMessage:
        email_message_class = self._get_email_message_class(tuple(rendered.keys()))

        from_email = self.delivery.from_email
        if from_email is use_default:
            from_email = settings.DEFAULT_FROM_EMAIL

        change_content_subtype_to: str | None = None
        attach_alternatives: list[tuple[str, Literal["text/html"]]] = []

        kwargs = {
            "subject": self.delivery.subject,
            "from_email": from_email,
            "to": [self.delivery.to_email],
            "bcc": (self.delivery.bcc or None),
            "cc": (self.delivery.cc or None),
        }
        has_txt = self.TXT_EXTENSION in rendered
        has_html = self.HTML_EXTENSION in rendered
        if has_txt:
            kwargs["body"] = rendered[self.TXT_EXTENSION]
        if has_html:
            if not has_txt:
                kwargs["body"] = rendered[self.HTML_EXTENSION]
                change_content_subtype_to = "html"
            if has_txt and len(rendered) > 1:
                attach_alternatives.append((rendered[self.HTML_EXTENSION], "text/html"))

        instance = email_message_class(**kwargs)  # type: ignore[arg-type]

        if change_content_subtype_to:
            instance.content_subtype = change_content_subtype_to

        if hasattr(instance, "attach_alternative"):
            for alternative in attach_alternatives:
                instance.attach_alternative(*alternative)

        return instance

    def _send_from_email_message_instance(
        self, email_message: EmailMessage
    ) -> EmailSendResult:
        fail_silently: bool = not self.core.raise_exception_on_failure_to_send
        num_sent = email_message.send(fail_silently=fail_silently)
        sent_at = timezone.now()
        return EmailSendResult(num_sent=num_sent, sent_at=sent_at)


class TransactionalEmail(Email, key=is_abstract):
    @dataclass(kw_only=True)
    class CoreSpec(Email.CoreSpec):
        is_transactional: bool = True


class ExampleEmail(TransactionalEmail, key=Key.EMAIL_EXAMPLE):
    @dataclass(kw_only=True)
    class CoreSpec(TransactionalEmail.CoreSpec):
        template_path: str = "emails/example"

    @dataclass(kw_only=True)
    class RenderSpec(TransactionalEmail.RenderSpec):
        one_variable: str
        another_variable: str

    @dataclass(kw_only=True)
    class DeliverySpec(TransactionalEmail.DeliverySpec):  # type: ignore[override,unused-ignore]
        subject: str = "Example Email for Better Base"

    @classmethod
    def prepare(cls, *, to_email: str, one_variable: str, another_variable: str):
        return cls(
            core=cls.CoreSpec(),
            render=cls.RenderSpec(
                one_variable=one_variable, another_variable=another_variable
            ),
            delivery=cls.DeliverySpec(to_email=to_email),
        )


def send_example_email(
    to_email: str,
    *,
    one_variable: str = "One Variable default From Backend",
    another_variable: str = "Another Variable default From Backend",
) -> EmailSendResult:
    email = ExampleEmail.prepare(
        to_email=to_email,
        one_variable=one_variable,
        another_variable=another_variable,
    )
    return email.send()
