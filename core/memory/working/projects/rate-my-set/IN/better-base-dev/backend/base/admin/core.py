from __future__ import annotations

from django.contrib import admin
from django.contrib.admin.options import InlineModelAdmin
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models
from django.http.request import HttpRequest
from djangoql.admin import DjangoQLSearchMixin
from jsoneditor.forms import JSONEditor

from backend.base.models.core import CoreModel, CoreModelGenericType
from backend.utils.json import prettify_json_as_html


class CoreModelAdmin(DjangoQLSearchMixin, admin.ModelAdmin):
    djangoql_completion_enabled_by_default = False

    formfield_overrides = {
        models.JSONField: {
            "widget": JSONEditor(
                encoder=DjangoJSONEncoder,
                init_options={
                    "mode": "code",
                    "modes": ["code", "form", "text", "tree", "view"],
                },
            )
        }
    }

    can_add: bool | None = None
    can_view: bool | None = None
    can_change: bool | None = None
    can_delete: bool | None = None

    def has_add_permission(self, request: HttpRequest) -> bool:
        if self.can_add:
            return True
        if self.can_add is False:
            return False
        return super().has_add_permission(request)

    def has_view_permission(
        self, request: HttpRequest, obj: CoreModelGenericType | None = None
    ) -> bool:
        if self.can_view:
            return True
        if self.can_view is False:
            return False
        return super().has_view_permission(request, obj)

    def has_change_permission(
        self, request: HttpRequest, obj: CoreModelGenericType | None = None
    ) -> bool:
        if self.can_change:
            return True
        if self.can_change is False:
            return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(
        self, request: HttpRequest, obj: CoreModelGenericType | None = None
    ) -> bool:
        if self.can_delete:
            return True
        if self.can_delete is False:
            return False
        return super().has_delete_permission(request, obj)

    prettify_json_as_html = staticmethod(prettify_json_as_html)


class CoreInlineModelAdmin(InlineModelAdmin):
    can_add_inline: bool | None = None
    can_view_inline: bool | None = None
    can_change_inline: bool | None = None
    # NOTE: `can_add` is an `InlineModelAdmin`-specific attribute that Django handles.
    # See
    # https://docs.djangoproject.com/en/dev/ref/contrib/admin/#django.contrib.admin.InlineModelAdmin.can_delete
    # Hence (this is part of the reason why), we named all of these attributes
    # `can_*_inline` instead of `can_*`, etc.
    can_delete_inline: bool | None = None

    def has_add_permission(self, request: HttpRequest, obj: CoreModel) -> bool:  # type: ignore[override]
        if self.can_add_inline:
            return True
        if self.can_add_inline is False:
            return False
        return super().has_add_permission(request, obj)

    def has_view_permission(
        self, request: HttpRequest, obj: CoreModel | None = None
    ) -> bool:
        if self.can_view_inline:
            return True
        if self.can_view_inline is False:
            return False
        return super().has_view_permission(request, obj)

    def has_change_permission(
        self, request: HttpRequest, obj: CoreModel | None = None
    ) -> bool:
        if self.can_change_inline:
            return True
        if self.can_change_inline is False:
            return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(
        self, request: HttpRequest, obj: CoreModel | None = None
    ) -> bool:
        if self.can_delete_inline:
            return True
        if self.can_delete_inline is False:
            return False
        return super().has_delete_permission(request, obj)

    prettify_json_as_html = staticmethod(prettify_json_as_html)
