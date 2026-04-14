"""
Factory Boy (https://github.com/FactoryBoy/factory_boy) uses a wrapper for faker values
(`factory.Faker`). Factory Boy (within the `factory` module) has its way of configuring
the underlying `faker.Faker` instances that it uses, and those might be configured
slightly differently than if you were to instantiate `faker.Faker` directly without
knowing the exact configuration (potentially including but not limited to locales,
random seeds, and maybe more) of the underlying `faker.Faker`(s) used by `factory`.

Hence, we provide a few "nice exports" here of a `faker.Faker` instance that should
match the underlying `factory` sort of configuration, and a `random.Random` instance
that should also match, so that tests wanting to use randomness can all share the
underlying seed or any other sort of random generation state that `factory` might be
configuring those underlying values with.

To describe it in a more simple way, we make available the internal faker and random
machinery Factory Boy is using so that randomness can be more reproducible and
deterministic, if/as needed, throughout the tests.
"""

from __future__ import annotations

from random import Random
from random import randint as _random_module_randint

import factory.random
import structlog
from django.conf import settings
from factory import Faker as FactoryFaker
from faker import Faker

logger = structlog.stdlib.get_logger()

# If the settings have a random seed set that we should use, then use that random seed.
# Otherwise, generate one to use for the tests (which, regardless of whether it comes
# from the settings or random generation, the `random_seed` variable will store its
# value).
random_seed: int | str
is_random_seed_set_from_settings: bool
if settings.FACTORY_BOY_SET_RANDOM_SEED_TO is None:
    # We'll just arbitrarily pick a number between `0` and `4294967295` (`2**32 - 1`)
    # (inclusive) as the random seed to use for the `factory` machinery.
    random_seed = _random_module_randint(0, 4294967295)
    is_random_seed_set_from_settings = True
else:
    random_seed = settings.FACTORY_BOY_SET_RANDOM_SEED_TO
    is_random_seed_set_from_settings = False
# Now that we have the seed, use it to set the random seed of the `factory` and also
# underlying `faker` (and then underlying `random`) machinery. This should help ensure
# that the randomness used by `factory` and `faker` is consistent and reproducible
# throughout the tests.
factory.random.reseed_random(random_seed)
logger.debug(
    "Random seed set.",
    random_seed=random_seed,
    is_random_seed_set_from_settings=is_random_seed_set_from_settings,
)

# This is a shared `Faker` instance (which is really a proxy class, see the
# docstring/documentation for more details) that can be used by code, regardless of
# whether it's using `factory` or not, etc. This `Faker` will have the same random seed,
# locale, and any other state of that sort as what is used by the `factory.Faker`.
fake: Faker = FactoryFaker._get_faker(FactoryFaker._DEFAULT_LOCALE)

# In similar veins to `faker` above, this is a shared `Random` instance that can be used
# by code, regardless of whether it's using `factory` or not, etc. This can help if
# `factory`, whether on its own or by us setting its config, uses a specific random
# seed. This `Random` instance below should have that seed, which was set by
# `factory.random.reseed_random(random_seed)` above. The seed should equal `random_seed`
# above as well.
random: Random = factory.random.randgen
