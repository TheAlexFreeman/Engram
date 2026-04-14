from __future__ import annotations

from typing import Any, Final, Generic, TypeVar, cast

from django.db.models import Model

from backend.accounts.models.accounts import Account
from backend.accounts.models.invitations import Invitation
from backend.accounts.models.memberships import Membership
from backend.accounts.models.users import User
from backend.accounts.tests.factories.accounts import AccountFactory
from backend.accounts.tests.factories.invitations import InvitationFactory
from backend.accounts.tests.factories.memberships import MembershipFactory
from backend.accounts.tests.factories.users import UserFactory
from backend.base.models.testing_models import ConcreteCoreModelForTests
from backend.base.tests.factories.testing_models import (
    ConcreteCoreModelForTestsFactory,
)

M = TypeVar("M", bound=Model)


class _FactoryType(Generic[M]):
    def build(self, *args: Any, **kwargs: Any) -> M: ...  # type: ignore[empty-body]

    def build_batch(self, size: int, *args: Any, **kwargs: Any) -> list[M]: ...  # type: ignore[empty-body]

    def create(self, *args: Any, **kwargs: Any) -> M: ...  # type: ignore[empty-body]

    def create_batch(self, size: int, *args: Any, **kwargs: Any) -> list[M]: ...  # type: ignore[empty-body]

    def stub(self, *args: Any, **kwargs: Any) -> M: ...  # type: ignore[empty-body]

    def stub_batch(self, size: int, *args: Any, **kwargs: Any) -> list[M]: ...  # type: ignore[empty-body]

    def __call__(self, *args: Any, **kwargs: Any) -> M: ...  # type: ignore[empty-body]


def get_factory(model: type[M]) -> _FactoryType[M]:
    try:
        factory_class = _model_to_factory[model]
    except KeyError as e:
        raise ValueError(f"No factory found for model - `{model}`.") from e

    return cast(_FactoryType[M], factory_class)


gf = get_factory


_model_to_factory: Final[dict[type[Model], _FactoryType[Model]]] = {
    Account: AccountFactory,  # type: ignore[dict-item]
    ConcreteCoreModelForTests: ConcreteCoreModelForTestsFactory,  # type: ignore[dict-item]
    Invitation: InvitationFactory,  # type: ignore[dict-item]
    Membership: MembershipFactory,  # type: ignore[dict-item]
    User: UserFactory,  # type: ignore[dict-item]
}
