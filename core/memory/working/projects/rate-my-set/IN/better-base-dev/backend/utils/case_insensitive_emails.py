from __future__ import annotations

from typing import TypeVar

from django.db import connection
from django.db.models import EmailField, Model, QuerySet, Value
from django.db.models.functions import Lower

M = TypeVar("M", bound=Model)


def filter_to_email_case_insensitive_equals(
    queryset: QuerySet[M],
    *,
    email_field_name: str,
    email_value: str,
) -> QuerySet[M]:
    assert "@" not in email_field_name, "Current pre-condition"

    return (
        queryset.all()
        .annotate(db_lower_email=Lower(email_field_name))
        .filter(db_lower_email=Lower(Value(email_value, output_field=EmailField())))
    )


def first_existing_with_email_case_insensitive(
    queryset: QuerySet[M],
    *,
    email_field_name: str,
    email_value: str,
) -> M | None:
    assert "@" not in email_field_name, "Current pre-condition"

    first = (
        filter_to_email_case_insensitive_equals(
            queryset,
            email_field_name=email_field_name,
            email_value=email_value,
        )
        .order_by(email_field_name, "pk")
        .first()
    )

    return first or None


def are_emails_equal_case_insensitive_in_db(email1: str, email2: str) -> bool:
    sql = """
    --begin-sql
    SELECT LOWER(%(email1)s) = LOWER(%(email2)s);
    """

    with connection.cursor() as cursor:
        cursor.execute(sql, {"email1": email1, "email2": email2})
        row = cursor.fetchone()

    assert isinstance(row, tuple) and len(row) == 1, "Current post-condition"
    assert row[0] is True or row[0] is False or row[0] == 0 or row[0] == 1, (
        "Current post-condition"
    )

    return bool(row[0])
