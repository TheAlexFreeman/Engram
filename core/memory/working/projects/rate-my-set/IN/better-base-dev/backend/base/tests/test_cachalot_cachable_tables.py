from __future__ import annotations

from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.contrib.sessions.models import Session
from django.db import models

from backend.accounts.models import Account, Membership, User


def test_cachalot_cachable_tables(settings):
    tables = settings.CACHALOT_ONLY_CACHABLE_TABLES
    tables_set = set(tables)
    assert sorted(tables) == sorted(tables_set)
    assert len(tables) == len(tables_set)

    expected_models: list[type[models.Model]] = [
        Account,
        ContentType,
        Group,
        Membership,
        Permission,
        Session,
        User,
    ]
    expected_model_db_tables = [model._meta.db_table for model in expected_models]

    # Add in the `ManyToMany` `through=...` tables.
    expected_model_db_tables.extend(
        [
            Group.permissions.through._meta.db_table,
            User.groups.through._meta.db_table,
            User.user_permissions.through._meta.db_table,
        ]
    )

    assert sorted(expected_model_db_tables) == sorted(tables)
    assert set(expected_model_db_tables) == set(tables)
