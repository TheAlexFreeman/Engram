from __future__ import annotations

from functools import lru_cache
from typing import Final

from django.conf import settings

POSTGRESQL_ENGINE_CANDIDATES: Final[frozenset] = frozenset(
    (
        "postgresql",
        "postgres",
        "postgis",
        "psql",
        "pgsql",
        "psycopg",
        "psycopg2",
        "asyncpg",
        "postgresql_psycopg2",
    )
)


def is_db_postgresql(
    using: str = "default",
    *,
    candidates=POSTGRESQL_ENGINE_CANDIDATES,
) -> bool:
    engine = settings.DATABASES[using]["ENGINE"]
    return _is_db_engine_postgresql(engine, candidates=candidates)


@lru_cache(16, typed=True)
def _is_db_engine_postgresql(engine: str, *, candidates=POSTGRESQL_ENGINE_CANDIDATES):
    for part in engine.split("."):
        if part in candidates:
            return True
    return False
