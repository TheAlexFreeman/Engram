from __future__ import annotations

from functools import lru_cache

from django.conf import settings
from redis import Redis

from backend.base.ops.environment import get_environment


@lru_cache(1)
def get_redis_cache() -> Redis:
    settings_attribute_names: tuple[str, ...] = (
        "REDIS_CACHE_URL",
        "REDIS_URL",
        "REDIS_CELERY_RESULTS_URL",
        "REDIS_CELERY_BROKER_URL",
        "CELERY_BROKER_URL",
    )
    for attribute_name in settings_attribute_names:
        if (settings_value := getattr(settings, attribute_name, None)) and (
            "redis://" in settings_value or "rediss://" in settings_value
        ):
            return Redis.from_url(settings_value)
    raise RuntimeError("No compatible Redis URL found in the settings.")


@lru_cache(32)
def get_redis_caching_key_prefix() -> str:
    environment = get_environment()
    env_str = environment.value.casefold()
    return f"{env_str}::rcache::"
