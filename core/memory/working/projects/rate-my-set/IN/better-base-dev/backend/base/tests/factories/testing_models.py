from __future__ import annotations

from backend.base.models.testing_models import ConcreteCoreModelForTests
from backend.base.tests.factories.core import CoreFactory


class ConcreteCoreModelForTestsFactory(CoreFactory[ConcreteCoreModelForTests]):
    class Meta:
        skip_postgeneration_save = True
