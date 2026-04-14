from __future__ import annotations


# -----
# Thanks to https://github.com/encode/django-rest-framework/issues/2768 and
# https://github.com/encode/django-rest-framework/issues/2768#issuecomment-479929271 for
# the code.
def sensitive_drf_or_django_post_parameters(*parameters):
    """
    adapted from: django.views.decorators.debug.sensitive_post_parameters
    """
    import functools

    from django.http import HttpRequest
    from rest_framework.request import Request

    def decorator(view):
        @functools.wraps(view)
        def sensitive_post_parameters_wrapper(request, *args, **kwargs):
            assert isinstance(request, (HttpRequest | Request)), (
                "sensitive_post_parameters didn't receive an HttpRequest or DRF Request. "
                "If you are decorating a classmethod, be sure to use "
                "@method_decorator."
            )
            request.sensitive_post_parameters = parameters or "__ALL__"  # type: ignore[union-attr]

            if isinstance(
                request, Request
            ):  # for DRF, don't forget original Django request
                request._request.sensitive_post_parameters = parameters or "__ALL__"  # type: ignore[attr-defined]

            return view(request, *args, **kwargs)

        return sensitive_post_parameters_wrapper

    return decorator


# -----
