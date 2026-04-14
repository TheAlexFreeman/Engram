from __future__ import annotations

from datetime import datetime

import pytest
from django.test.client import Client, RequestFactory
from django.urls import reverse as django_reverse
from django.utils import timezone
from requests_mock import Mocker
from respx import MockRouter
from rest_framework.reverse import reverse as rest_framework_reverse
from rest_framework.test import APIClient, APIRequestFactory

from backend.accounts.models import User
from backend.accounts.tests.factories import UserFactory
from backend.base.tests.helpers.datetimes import Times


@pytest.fixture(autouse=True)
def autouse_requests_mock(requests_mock: Mocker):
    """
    Prevent `requests` requests from running unless they're an explicit `requests_mock`
    mock configuration for them.
    """
    pass


@pytest.fixture(autouse=True)
def autouse_respx_mock(respx_mock: MockRouter):
    """
    Prevent `httpx` requests from running unless they're an explicit `respx_mock` mock
    configuration for them.
    """
    pass


@pytest.fixture(scope="session")
def reverse():
    return django_reverse


@pytest.fixture(scope="session")
def drf_reverse():
    return rest_framework_reverse


@pytest.fixture
def now() -> datetime:
    return timezone.now()


@pytest.fixture
def times(now: datetime) -> Times:
    return Times(now)


@pytest.fixture
def user(db) -> User:
    return UserFactory.create()


@pytest.fixture
def admin_user(db) -> User:
    """
    NOTE: This `admin_user` fixture needs to be present, at least at the time of
    writing, for the third-party `admin_client` fixture, because the default
    `admin_user` fixture that `admin_client` depends on _may not_ not work out of the
    box with the way we have the `User`, `Account`, and/or `Membership` models set up
    right now.
    """
    return UserFactory.create(create_superuser=True)


@pytest.fixture
def client() -> Client:
    return Client()


@pytest.fixture
def request_factory() -> RequestFactory:
    return RequestFactory()


@pytest.fixture
def api_client() -> APIClient:
    return APIClient()


@pytest.fixture
def api_request_factory() -> APIRequestFactory:
    return APIRequestFactory()
