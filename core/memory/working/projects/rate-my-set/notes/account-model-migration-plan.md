---
type: project-note
project: rate-my-set
topic: account-model-migration-plan
created: 2026-04-14
depends-on: better-base-roadmap.md
status: draft
---

# Account Model Migration Plan

A concrete, phased plan for extending Better Base's existing `Account`/`Membership`/`Invitation`/`User` machinery to support Rate My Set's moderation needs without breaking the SaaS-shaped defaults that remain useful for reviewer auth.

Design recap in one paragraph: keep `Account.account_type` unchanged (`personal` / `team`). Add a nullable `team_type` TextChoices field on `Account` that is non-null only for team accounts — first value `moderation_pool`. Expand the `Role` enum with `moderator` and `senior_moderator`. Denormalize `team_type` onto `Membership` so role/team-type compatibility is a single-row CHECK. Add a `ModeratorProfile` one-to-one with `User` for per-person moderator state. Gate moderator-pool invitations through the existing owner-only rule (platform operators own the pool). Hide account-switching UI for users who have no team memberships.

Read order: this document assumes familiarity with `better-base-roadmap.md` (Phase 0/1 context), `moderation-workflows-paired-approval.md` in the knowledge base, and Better Base's `backend/accounts/` tree. Every phase below is testable in isolation and leaves the tree green.

---

## Phase 1 — Additive `team_type` field on Account

**Goal:** Account can carry a non-null `team_type` for team accounts. No behavior change yet.

### Code changes

`backend/accounts/types/account_types.py` (new file to avoid bloating `roles.py`):

```python
from __future__ import annotations
from django.db.models import TextChoices
from django.utils.translation import gettext_lazy as _


class TeamType(TextChoices):
    MODERATION_POOL = "moderation_pool", _("Moderation Pool")
    # Future: UNION_LOCAL, PRODUCTION_COMPANY (etc.) as v2/v3 needs emerge.
```

`backend/accounts/models/accounts.py`:

```python
from backend.accounts.types.account_types import TeamType

class Account(CoreModel):
    ...
    account_type = models.CharField(max_length=15, choices=AccountType)
    team_type = models.CharField(
        max_length=31,
        choices=TeamType.choices,
        null=True,
        blank=True,
        default=None,
        help_text=_(
            "Subtype discriminator for team accounts. NULL for personal accounts; "
            "required to be set for team accounts via app-layer policy."
        ),
    )
    ...

    class Meta:
        constraints = [
            # Existing constraint retained (act_act_at_cc)
            models.CheckConstraint(
                condition=Q(account_type__in=[t.value for t in AccountType]),
                name="act_act_at_cc",
            ),
            # NEW: team_type enum validity (when set).
            models.CheckConstraint(
                condition=Q(team_type__isnull=True) | Q(team_type__in=[t.value for t in TeamType]),
                name="act_act_tt_cc",
            ),
            # NEW: team_type only permitted on team accounts.
            models.CheckConstraint(
                condition=Q(team_type__isnull=True) | Q(account_type=AccountType.TEAM),
                name="act_act_tt_at_cc",
            ),
        ]
```

### Migration

`0002_account_team_type.py` — a single `AddField` + two `AddConstraint` operations. Nullable column add in Postgres 11+ is metadata-only; no table rewrite.

```python
operations = [
    migrations.AddField(
        model_name="account",
        name="team_type",
        field=models.CharField(
            max_length=31, null=True, blank=True, default=None,
            choices=[("moderation_pool", "Moderation Pool")],
        ),
    ),
    migrations.AddConstraint(
        model_name="account",
        constraint=models.CheckConstraint(
            condition=Q(team_type__isnull=True) | Q(team_type__in=["moderation_pool"]),
            name="act_act_tt_cc",
        ),
    ),
    migrations.AddConstraint(
        model_name="account",
        constraint=models.CheckConstraint(
            condition=Q(team_type__isnull=True) | Q(account_type="team"),
            name="act_act_tt_at_cc",
        ),
    ),
]
```

### Ops changes

Extend `backend/accounts/ops/accounts.py`:

```python
def create_team_account(*, name: str, team_type: TeamType | None = None) -> Account:
    name_to_use = name or "Team Account"
    with transaction_if_not_in_one_already():
        return Account.objects.create(
            account_type=AccountType.TEAM,
            team_type=team_type,
            name=name_to_use,
        )


def create_moderation_pool_account(*, name: str = "Moderation Pool") -> Account:
    return create_team_account(name=name, team_type=TeamType.MODERATION_POOL)
```

The existing single-arg `create_team_account` signature is kept intact (new arg is kwarg-only, default `None`); no existing call site breaks.

### Serializer

Add `team_type` to `AccountReadOnlySerializer.Meta.fields` so the frontend sees it. Keep it read-only everywhere except in admin-only contexts.

### Tests

- `test_accounts.py` model tests:
  - Personal account with `team_type` set → IntegrityError (new constraint).
  - Team account with `team_type="moderation_pool"` → allowed.
  - Team account with `team_type=None` → allowed (legacy team accounts).
  - Team account with `team_type="garbage"` → IntegrityError.
- `test_accounts.py` ops tests:
  - `create_moderation_pool_account` returns an Account with `team_type=MODERATION_POOL`.

### Rollback

Drop the two new constraints and the column. Reversible.

---

## Phase 2 — Role expansion

**Goal:** `Role` gains `MODERATOR` and `SENIOR_MODERATOR` while preserving `OWNER`/`MEMBER` and the existing priority-ordering contract.

### Code changes

`backend/accounts/types/roles.py`:

```python
class Role(TextChoices):
    MEMBER = "member", _("Member")
    MODERATOR = "moderator", _("Moderator")
    SENIOR_MODERATOR = "senior_moderator", _("Senior Moderator")
    OWNER = "owner", _("Owner")


# OWNER stays on top so a platform operator owning the pool sorts first.
role_priority_mapping: Final[dict[Role, int]] = {
    Role.OWNER: 4,
    Role.SENIOR_MODERATOR: 3,
    Role.MODERATOR: 2,
    Role.MEMBER: 1,
}

assert sorted(map(str, role_priority_mapping.keys())) == sorted(map(str, [*Role]))
assert sorted(role_priority_mapping.values()) == list(range(1, len(role_priority_mapping) + 1))
```

The two existing asserts still hold: every role is in the map; values are 1..n contiguous. The ordering contract ("OWNER first, then MEMBER") generalizes to "OWNER first, then SENIOR_MODERATOR, MODERATOR, MEMBER" with no call site requiring adjustment.

### Classification helpers

Add to `types/roles.py`:

```python
moderator_roles: Final[frozenset[Role]] = frozenset({
    Role.MODERATOR,
    Role.SENIOR_MODERATOR,
})

universal_roles: Final[frozenset[Role]] = frozenset({
    Role.OWNER,
    Role.MEMBER,
})

# Any role valid on any team type.
team_universal_roles: Final[frozenset[Role]] = frozenset({
    Role.OWNER,
    Role.MEMBER,
})

roles_valid_for_team_type: Final[dict[TeamType, frozenset[Role]]] = {
    TeamType.MODERATION_POOL: team_universal_roles | moderator_roles,
}
```

These structures will be the single source of truth for Phase 3's constraint and for Phase 5's invitation gating.

### Migration

`0003_role_expand_membership_invitation_roles.py` — updates the existing role CHECK constraints on `Membership` and `Invitation`. The values list simply grows.

```python
operations = [
    migrations.RemoveConstraint(model_name="membership", name="act_mbs_rl_cc"),
    migrations.AddConstraint(
        model_name="membership",
        constraint=models.CheckConstraint(
            condition=Q(role__in=["member", "moderator", "senior_moderator", "owner"]),
            name="act_mbs_rl_cc",
        ),
    ),
    migrations.RemoveConstraint(model_name="invitation", name="act_ivt_rl_cc"),
    migrations.AddConstraint(
        model_name="invitation",
        constraint=models.CheckConstraint(
            condition=Q(role__in=["member", "moderator", "senior_moderator", "owner"]),
            name="act_ivt_rl_cc",
        ),
    ),
]
```

### Tests

- Role ordering: confirm priority annotation places OWNER before moderator roles before MEMBER.
- Constraint: inserting a row with `role="garbage"` still fails; inserting with each new role succeeds.

### Rollback

If any moderator memberships exist and you revert Phase 2, the constraint rollback would fail. Plan: reverse-migration script deletes rows with moderator roles first. In practice Phase 2 ships and stays.

---

## Phase 3 — Denormalize `team_type` onto Membership

**Goal:** The "moderator role only on moderation_pool accounts" invariant is enforceable as a single-row Postgres CHECK.

### Why denormalize

Postgres CHECK constraints cannot cross tables without a trigger. The alternatives are `django-pgtrigger` (adds a dependency and triggers to maintain) or denormalization of `Account.team_type` onto `Membership`. Denormalization wins here because `Account.team_type` is effectively immutable after creation — team accounts do not change their team type in normal operation — so keeping the two values in sync is trivial.

### Code changes

`backend/accounts/models/memberships.py`:

```python
class Membership(CoreModel):
    REPR_FIELDS = ("id", "account_id", "user_id", "role", "team_type")

    account = models.ForeignKey("accounts.Account", ...)
    user = models.ForeignKey("accounts.User", ...)
    role = models.CharField(...)
    last_selected_at = models.DateTimeField(...)

    # NEW: denormalized from account.team_type, synced on save().
    team_type = models.CharField(
        max_length=31, choices=TeamType.choices, null=True, blank=True, default=None,
    )

    def save(self, *args, **kwargs):
        # Sync team_type from the account so the CHECK stays internally consistent.
        if self.account_id is not None:
            # Read from the attached account object if loaded; else minimal DB hit.
            account_team_type = (
                self.account.team_type
                if "account" in self.__dict__   # already prefetched or set
                else Account.objects.filter(pk=self.account_id).values_list("team_type", flat=True).first()
            )
            self.team_type = account_team_type
        return super().save(*args, **kwargs)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(role__in=[r.value for r in Role]),
                name="act_mbs_rl_cc",
            ),
            # NEW: role must be valid for the membership's team_type.
            models.CheckConstraint(
                condition=(
                    # Personal account membership (team_type NULL): any universal role.
                    Q(team_type__isnull=True, role__in=[Role.OWNER, Role.MEMBER])
                    # Moderation-pool membership: universal or moderator roles.
                    | Q(
                        team_type=TeamType.MODERATION_POOL,
                        role__in=[Role.OWNER, Role.MEMBER, Role.MODERATOR, Role.SENIOR_MODERATOR],
                    )
                ),
                name="act_mbs_rl_tt_cc",
            ),
            models.UniqueConstraint(
                fields=["account", "user"], name="act_mbs_ac_us_uix",
            ),
        ]
```

### Migration with data backfill

`0004_membership_team_type.py`:

```python
from django.db import migrations, models
from django.db.models import Q


def backfill_membership_team_type(apps, schema_editor):
    Membership = apps.get_model("accounts", "Membership")
    # Copy account.team_type onto each membership in one UPDATE per distinct value.
    Membership.objects.filter(account__team_type__isnull=False).update(
        team_type=models.F("account__team_type"),
    )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [("accounts", "0003_role_expand_membership_invitation_roles")]

    operations = [
        migrations.AddField(
            model_name="membership",
            name="team_type",
            field=models.CharField(
                max_length=31, null=True, blank=True, default=None,
                choices=[("moderation_pool", "Moderation Pool")],
            ),
        ),
        migrations.RunPython(backfill_membership_team_type, noop_reverse),
        migrations.AddConstraint(
            model_name="membership",
            constraint=models.CheckConstraint(
                condition=(
                    Q(team_type__isnull=True, role__in=["owner", "member"])
                    | Q(
                        team_type="moderation_pool",
                        role__in=["owner", "member", "moderator", "senior_moderator"],
                    )
                ),
                name="act_mbs_rl_tt_cc",
            ),
        ),
    ]
```

Postgres caveat: `UPDATE ... FROM account` is more idiomatic than the implicit-join syntax above; if Django's ORM generates a subquery that's slow on large tables, switch to raw SQL in the RunPython. At Better Base's current size this is negligible.

### Account save-side sync

To keep Membership.team_type correct if an `Account.team_type` is ever changed (should be rare), add a post-save hook on `Account`:

```python
# backend/accounts/models/accounts.py

from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(post_save, sender=Account)
def sync_membership_team_type_on_account_change(sender, instance, created, **kwargs):
    if not created and instance.tracker.has_changed("team_type"):
        instance.memberships.update(team_type=instance.team_type)
```

This requires adding `"team_type"` to the `Account.tracker = FieldTracker(fields=[...])` field list.

### Tests

- Creating a moderation_pool Account and then adding a Membership with `role=moderator` → succeeds; Membership.team_type is `moderation_pool`.
- Adding a Membership with `role=moderator` on a personal Account → IntegrityError.
- Changing `Account.team_type` syncs through to all its Memberships.
- Consistency check: `Membership.objects.filter(team_type=F("account__team_type"))` equals `.count()`.

### Rollback

Drop the constraint, drop the column. Reversible as long as no code depends on the denormalized field (hence keep reads off `Membership.team_type` and on `account.team_type` throughout app code; the denorm field is for the CHECK only).

---

## Phase 4 — ModeratorProfile

**Goal:** Per-person moderator state lives outside Membership so it survives pool changes and avoids duplication when a moderator belongs to multiple pools.

### Model

`backend/accounts/models/moderator_profiles.py`:

```python
from __future__ import annotations
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from backend.base.models.core import CoreModel, CoreQuerySet


class ModeratorProfileQuerySet(CoreQuerySet["ModeratorProfile"]):
    def active(self):
        return self.filter(paused_until__isnull=True).filter(
            Q(paused_until__isnull=True) | Q(paused_until__lt=timezone.now())
        )


class ModeratorProfile(CoreModel):
    REPR_FIELDS = ("id", "user_id", "training_completed_at", "paused_until")

    user = models.OneToOneField(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="moderator_profile",
    )

    # Training / onboarding lifecycle
    training_completed_at = models.DateTimeField(null=True, blank=True, default=None)
    mfa_enrolled_at = models.DateTimeField(null=True, blank=True, default=None)

    # Career metrics (maintained by ops, not directly mutated)
    total_first_approvals = models.PositiveIntegerField(default=0)
    total_final_approvals = models.PositiveIntegerField(default=0)
    total_rejections = models.PositiveIntegerField(default=0)
    total_escalations_raised = models.PositiveIntegerField(default=0)

    # Pause / leave
    paused_until = models.DateTimeField(null=True, blank=True, default=None)
    pause_reason = models.TextField(blank=True, default="")

    objects = ModeratorProfileQuerySet.as_manager()

    class Meta:
        verbose_name = _("Moderator Profile")
        verbose_name_plural = _("Moderator Profiles")

    @property
    def is_trained(self) -> bool:
        return self.training_completed_at is not None

    @property
    def is_mfa_enrolled(self) -> bool:
        return self.mfa_enrolled_at is not None

    @property
    def is_active(self) -> bool:
        if self.paused_until is None:
            return True
        return self.paused_until < timezone.now()

    @property
    def is_operationally_ready(self) -> bool:
        """Required conditions to accept moderator-queue work."""
        return self.is_trained and self.is_mfa_enrolled and self.is_active
```

### Migration

`0005_moderator_profile.py` — straightforward `CreateModel`.

### Ops

`backend/accounts/ops/moderator_profiles.py`:

```python
def ensure_moderator_profile(user: User) -> ModeratorProfile:
    profile, _created = ModeratorProfile.objects.get_or_create(user=user)
    return profile


def record_training_completed(profile: ModeratorProfile) -> None:
    profile.training_completed_at = timezone.now()
    profile.save(update_fields=["training_completed_at", "modified"])


def record_mfa_enrolled(profile: ModeratorProfile) -> None:
    profile.mfa_enrolled_at = timezone.now()
    profile.save(update_fields=["mfa_enrolled_at", "modified"])


def pause_moderator(profile: ModeratorProfile, *, until: datetime, reason: str) -> None:
    profile.paused_until = until
    profile.pause_reason = reason or ""
    profile.save(update_fields=["paused_until", "pause_reason", "modified"])
```

### Signal: auto-create on moderator-role Membership

```python
# backend/accounts/signals/moderator_profile.py
@receiver(post_save, sender=Membership)
def ensure_moderator_profile_on_mod_membership(sender, instance, created, **kwargs):
    if instance.role in moderator_roles:
        ensure_moderator_profile(instance.user)
```

### Admin

Add a `ModeratorProfileInline` under `UserAdmin` with the career metrics in a read-only fieldset, and training/MFA/pause fields in an editable fieldset.

### Tests

- Adding a Membership with moderator role auto-creates a ModeratorProfile.
- A user promoted to moderator in pool A, then demoted, still has the profile (and its career stats).
- `is_operationally_ready` returns False until training + MFA + not paused.

### Rollback

Drop the model. Reversible (with data loss for career stats).

---

## Phase 5 — MFA gate for moderators

**Goal:** A user with a `ModeratorProfile` cannot authenticate without MFA enrolled and verified.

### Observation

Better Base ships session-based custom auth but does not (at inspection) ship MFA. This phase adds MFA as a User-level capability and requires it for moderators; other users remain unaffected.

Two realistic paths:

1. **Integrate `django-otp` + TOTP.** Mature, well-tested. Add `django_otp.middleware.OTPMiddleware` after Django's `AuthenticationMiddleware`. Use `@otp_required` decorators or a DRF permission.
2. **Integrate WebAuthn via `django-webauthn` or Simplewebauthn.** Better UX (hardware keys, platform authenticators) but more frontend work.

For v1, django-otp with TOTP is the pragmatic choice; add WebAuthn later without disturbing the ModeratorProfile contract.

### Code changes

`backend/auth/mfa.py` (new):

```python
from django_otp import user_has_device

from backend.accounts.models import User


def user_requires_mfa(user: User) -> bool:
    return hasattr(user, "moderator_profile")


def user_has_verified_mfa(user: User) -> bool:
    if not user_requires_mfa(user):
        return True
    return user_has_device(user, confirmed=True) and user.is_verified()  # django-otp contract
```

DRF permission:

```python
class ModeratorMFAVerified(BasePermission):
    message = _("Two-factor authentication is required for moderator actions.")
    code = "mfa_required"

    def has_permission(self, request, view):
        user = request.user
        return user.is_authenticated and user_has_verified_mfa(user)
```

Every moderator endpoint composes `ModeratorMFAVerified` with its other permission classes.

### Migration

No model migration for the ModeratorProfile itself (the `mfa_enrolled_at` field was added in Phase 4). Requires `django-otp` migrations; include via standard `INSTALLED_APPS` addition and `python manage.py migrate`.

### Tests

- A moderator without an OTP device is denied on moderator endpoints.
- A moderator with an OTP device enrolled but not verified in this session is denied.
- A non-moderator user is unaffected.

### Rollback

Remove the permission from views; remove `django-otp` from INSTALLED_APPS. Reversible.

---

## Phase 6 — Invitation gating for moderation pools

**Goal:** Moderator invitations follow the existing owner-only rule but are restricted to moderator roles and moderation-pool accounts. Reviewer signup remains invitation-free.

### Observations from the existing code

`validate_can_create_invitation` already enforces `initiator.role == Role.OWNER`. The `Invitation.role` field already goes into a CHECK constraint that Phase 2 widened. The outstanding work is constraining role-to-team-type and making clear which endpoint creates moderator invitations.

### Code changes

Extend `backend/accounts/ops/invitations.py`:

```python
from backend.accounts.types.roles import moderator_roles
from backend.accounts.types.account_types import TeamType


def validate_can_create_invitation(
    *,
    initiator: Membership,
    email: str | None,
    intended_role: Role | None = None,   # NEW arg
) -> None:
    if initiator.role != Role.OWNER:
        raise ValidationError(
            _("You must be an account owner to invite new users."),
            code="owner_required",
        )

    # NEW: role × team_type compatibility
    account = initiator.account
    if intended_role in moderator_roles:
        if account.team_type != TeamType.MODERATION_POOL:
            raise ValidationError(
                _("Moderator roles can only be granted in a moderation pool account."),
                code="role_requires_moderation_pool",
            )
    else:
        # Non-moderator roles on a moderation-pool account: only OWNER/MEMBER allowed.
        if account.team_type == TeamType.MODERATION_POOL and intended_role not in {Role.OWNER, Role.MEMBER}:
            raise ValidationError(
                _("Invalid role for a moderation pool account."),
                code="invalid_role_for_team_type",
            )

    # Existing email-duplicate checks follow...
```

Every call site of `validate_can_create_invitation` needs to pass `intended_role`. A compatible default (None) lets the check be skipped for legacy call paths during the rollout; remove the default after all call sites are updated.

### API / serializer

The existing invitation creation serializer already accepts `role`. Add client-side defaults on the moderator-pool invitation UI so a moderator invitation always defaults to `role=moderator`. The constraint is enforced server-side regardless.

### Tests

- Creating a moderator invitation in a non-moderation-pool team → ValidationError.
- Creating a moderator invitation in a moderation-pool team as owner → succeeds.
- Creating a member invitation in a moderation-pool team → allowed (this is how you'd add an observer / non-privileged account).
- Creating any invitation as non-owner → rejected (unchanged behavior).

### Rollback

Remove the new branches from `validate_can_create_invitation`. Reversible.

---

## Phase 7 — Permission classes for moderator endpoints

**Goal:** The moderation app (forthcoming in roadmap Phase 7) has a short menu of permission classes that encode the role/pool/MFA surface.

### Code

`backend/accounts/api/permissions/moderation.py` (new):

```python
from backend.accounts.models import Membership
from backend.accounts.types.roles import Role, moderator_roles
from backend.accounts.types.account_types import TeamType


class IsModerator(BasePermission):
    """User has at least one active Membership in a moderation pool with a moderator role."""
    message = _("Moderator access required.")
    code = "moderator_required"

    def has_permission(self, request, view):
        user = request.user
        if not (user.is_authenticated and isinstance(user, User)):
            return False
        return Membership.objects.filter(
            user=user,
            role__in=moderator_roles | {Role.OWNER},    # OWNER of the pool counts as moderator too
            team_type=TeamType.MODERATION_POOL,
        ).exists()


class IsSeniorModerator(BasePermission):
    message = _("Senior moderator access required.")
    code = "senior_moderator_required"

    def has_permission(self, request, view):
        user = request.user
        if not (user.is_authenticated and isinstance(user, User)):
            return False
        return Membership.objects.filter(
            user=user,
            role__in={Role.SENIOR_MODERATOR, Role.OWNER},
            team_type=TeamType.MODERATION_POOL,
        ).exists()


class ModeratorInPool(BasePermission):
    """
    Object-level check: user is a moderator in the *same* moderation pool as the object
    being acted on (e.g., a ReviewModeration record is routed to a specific pool).
    """
    def has_object_permission(self, request, view, obj):
        pool_id = getattr(obj, "pool_id", None)
        if pool_id is None:
            return False
        return Membership.objects.filter(
            user=request.user,
            account_id=pool_id,
            role__in=moderator_roles | {Role.OWNER},
        ).exists()
```

Moderator viewsets compose `IsModerator + ModeratorMFAVerified + ModeratorInPool (for detail)`.

### Tests

Live in `tests/api/permissions/test_moderation.py`. Test matrix: (authenticated, has mod membership, has mfa) × (action allowed, action denied).

### Rollback

Unused permission classes don't affect anything if not referenced. Reversible.

---

## Phase 8 — UI gating and account switcher

**Goal:** A reviewer (personal-only user) sees no account-switching UI. A user who becomes a moderator sees the moderation pool as an additional account context.

### Backend signal

Already available through the existing user-endpoint response: the frontend already receives `memberships`. Add a convenience boolean in the `UserReadOnlySerializer`:

```python
class UserReadOnlySerializer(serializers.ModelSerializer):
    has_team_membership = serializers.SerializerMethodField()

    def get_has_team_membership(self, obj: User) -> bool:
        return obj.memberships.filter(account__account_type=AccountType.TEAM).exists()

    class Meta:
        fields = [*existing_fields, "has_team_membership"]
```

For performance, annotate in the view queryset rather than issuing a per-request query:

```python
def get_queryset(self):
    return User.objects.annotate(
        _has_team_membership=Exists(
            Membership.objects.filter(user=OuterRef("pk"), account__account_type="team")
        ),
    )
```

### Frontend gating

In the app shell (TanStack Router layout), conditionally render the account switcher:

```tsx
function AppHeader() {
  const { data: user } = useMe();
  return (
    <header>
      <Logo />
      {user?.has_team_membership && <AccountSwitcher />}
      <UserMenu />
    </header>
  );
}
```

Hide the `/accounts/new` route for non-staff users. The existing `AccountTypeMustBePersonal` permission already prevents a reviewer from acting on a team account they don't belong to; this UI change just suppresses entry points.

### Moderator dashboard route

When `user.memberships` includes a moderation-pool membership, expose the `/moderation` section of the app (roadmap Phase 7).

### Tests

Frontend: snapshot test for the header with/without team membership. Backend: ensure `has_team_membership` is correctly computed for zero, personal-only, and mixed cases.

---

## Phase 9 — Seeding and staff bootstrap

**Goal:** A fresh dev or prod database has exactly one moderation pool, and staff users can become its owners.

### Management command

`backend/accounts/management/commands/bootstrap_moderation_pool.py`:

```python
from django.core.management.base import BaseCommand
from django.db import transaction

from backend.accounts.models import User
from backend.accounts.models.accounts import Account, AccountType
from backend.accounts.types.account_types import TeamType
from backend.accounts.types.roles import Role
from backend.accounts.ops.accounts import create_moderation_pool_account
from backend.accounts.ops.memberships import create_membership


class Command(BaseCommand):
    help = "Create the default moderation pool if it does not exist; add given staff user as owner."

    def add_arguments(self, parser):
        parser.add_argument("--owner-email", required=True)
        parser.add_argument("--pool-name", default="Moderation Pool")

    def handle(self, *args, **opts):
        with transaction.atomic():
            pool = Account.objects.filter(
                account_type=AccountType.TEAM,
                team_type=TeamType.MODERATION_POOL,
                name=opts["pool_name"],
            ).first()
            if pool is None:
                pool = create_moderation_pool_account(name=opts["pool_name"])

            owner = User.objects.get(email__iexact=opts["owner_email"])
            create_membership(account=pool, user=owner, role=Role.OWNER)

        self.stdout.write(self.style.SUCCESS(f"Pool ready: {pool.pk} (owner: {owner.pk})"))
```

### Tests

- Command is idempotent: re-running doesn't duplicate the pool or the membership.
- A non-staff user passed as owner raises a clear error.

### Rollback

Delete the created Account + Membership rows. Pool creation is non-destructive.

---

## Phase 10 — Test matrix and migration safety

**Goal:** A single comprehensive test module verifies the invariants end-to-end, plus a migration-safety pass.

### Comprehensive invariant tests

`backend/accounts/tests/invariants/test_account_model_invariants.py`:

```python
@pytest.mark.django_db
class TestAccountModelInvariants:
    # --- Constraint invariants ---

    def test_personal_account_cannot_have_team_type(self):
        with pytest.raises(IntegrityError):
            Account.objects.create(account_type="personal", team_type="moderation_pool", name="X")

    def test_team_account_without_team_type_is_allowed(self):
        Account.objects.create(account_type="team", team_type=None, name="Legacy")

    def test_moderator_role_only_on_moderation_pool(self):
        personal = AccountFactory(account_type="personal")
        user = UserFactory()
        with pytest.raises(IntegrityError):
            Membership.objects.create(
                account=personal, user=user, role=Role.MODERATOR, team_type=None,
            )

    def test_moderator_role_on_moderation_pool_allowed(self):
        pool = AccountFactory(account_type="team", team_type="moderation_pool")
        user = UserFactory()
        Membership.objects.create(account=pool, user=user, role=Role.MODERATOR)  # team_type synced on save

    # --- Denormalization sync ---

    def test_membership_team_type_synced_from_account(self):
        pool = AccountFactory(account_type="team", team_type="moderation_pool")
        user = UserFactory()
        m = Membership.objects.create(account=pool, user=user, role=Role.MEMBER)
        assert m.team_type == "moderation_pool"

    def test_changing_account_team_type_syncs_memberships(self):
        pool = AccountFactory(account_type="team", team_type="moderation_pool")
        user = UserFactory()
        m = Membership.objects.create(account=pool, user=user, role=Role.MEMBER)
        # Administratively change the pool type (unusual but must be consistent).
        pool.team_type = None
        pool.save(update_fields=["team_type"])
        m.refresh_from_db()
        assert m.team_type is None

    # --- Invitation gating ---

    def test_moderator_invitation_rejected_on_non_pool(self):
        team = AccountFactory(account_type="team", team_type=None)
        owner_m = MembershipFactory(account=team, role=Role.OWNER)
        with pytest.raises(ValidationError):
            validate_can_create_invitation(
                initiator=owner_m, email="x@y.com", intended_role=Role.MODERATOR,
            )

    # --- Permission classes ---

    def test_is_moderator_false_for_reviewer(self):
        user = UserFactory()
        request = mock_request(user=user)
        assert IsModerator().has_permission(request, None) is False

    def test_is_moderator_true_for_pool_member_with_moderator_role(self):
        pool = AccountFactory(account_type="team", team_type="moderation_pool")
        user = UserFactory()
        MembershipFactory(account=pool, user=user, role=Role.MODERATOR)
        request = mock_request(user=user)
        assert IsModerator().has_permission(request, None) is True
```

### Migration safety

Run `python manage.py sqlmigrate accounts 0002` through `0005` and inspect the generated SQL for lock acquisition patterns. None of the operations here require table rewrites on Postgres 11+ given the nullable-column-add semantics; the only meaningful lock is the `AddConstraint` ACCESS EXCLUSIVE lock, which is brief on tables of any reasonable size.

If deploying to a production Better Base-based system with large existing data:

- Use `ATOMIC = False` migrations and `AddConstraint(... validate=False)` + `VALIDATE CONSTRAINT` in a follow-up migration to avoid long locks. Better Base's migration style may already use this pattern; check `backend/base/migrations/` for precedent.
- Run the data backfill in Phase 3 in chunks if Memberships > 1M rows.

### CI gate

Add a pre-merge check that runs `python manage.py makemigrations --check` and fails if the model tree has drifted from the migration state.

---

## Dependency graph

```
Phase 1 (team_type field)
  └─► Phase 2 (Role expansion)
        └─► Phase 3 (Membership.team_type denorm + constraint)
              ├─► Phase 4 (ModeratorProfile)
              │     └─► Phase 5 (MFA gate)
              └─► Phase 6 (Invitation gating)
                    └─► Phase 7 (Permission classes)
                          └─► Phase 8 (UI gating)
Phase 9 (Bootstrap command) — depends on Phases 1–4, can ship alongside Phase 4.
Phase 10 (Test matrix) — accumulated during every phase; a final pass cross-verifies.
```

Phases 1–3 are a tight chain; Phases 4–9 can parallelize once 3 lands. Phase 5 (MFA) has the highest risk because it introduces an external dep (`django-otp`) and a session-level requirement; build it in a feature branch and gate via a settings flag until ready.

---

## What this plan deliberately doesn't do

- **Does not remove personal accounts for reviewers.** They stay; the UI hides them. Leaves room for richer personal-account features.
- **Does not introduce production companies as Accounts.** Productions are records. The roadmap's permanent exclusion of production-facing dashboards is reflected here by omission.
- **Does not ship union-local accounts.** Adding `UNION_LOCAL` to `TeamType` in v2 is a single-line change plus a `roles_valid_for_team_type` entry; the plumbing is already in place after Phase 3.
- **Does not touch the `AccountType` enum.** `AccountType.PERSONAL` and `AccountType.TEAM` remain the top-level discriminator. All Rate My Set's specificity lives in `team_type`.
- **Does not reshape the invitation model.** It remains a team-account onboarding tool, now appropriately gated.

---

## Open questions worth confirming before coding Phase 1

1. Does Better Base's existing `CoreModel` or migration tooling already support `AddConstraint(validate=False)` for non-locking constraint additions? If yes, prefer that pattern throughout. (The inspection above suggests standard Django constraints only.)
2. Is `django-otp` acceptable as the v1 MFA substrate, or would you prefer WebAuthn from the start?
3. Should MODERATION_POOL membership OWNER be synonymous with "platform operator" (implying `User.is_staff=True`), or do we want a distinct role? This plan assumes the former; pool owners are staff.
4. Does the frontend account switcher already exist as a distinct component? If yes, gating it is a one-liner; if it's interleaved with account context routing, Phase 8 has more reach.

---

## Sources referenced during review

- `backend/accounts/models/accounts.py` (existing `Account`, `AccountQuerySet`, `AccountType`)
- `backend/accounts/models/memberships.py` (existing `Membership`, constraints, role priority)
- `backend/accounts/models/invitations.py` (existing `Invitation`, validation, indexes)
- `backend/accounts/models/users.py` (`User`, membership caches, consistency checks)
- `backend/accounts/types/roles.py` (`Role` TextChoices + priority mapping + invariant asserts)
- `backend/accounts/ops/accounts.py` (`create_team_account`, `update_account_type`)
- `backend/accounts/ops/invitations.py` (`validate_can_create_invitation`, owner-only rule)
- `backend/accounts/ops/data_consistency.py` (account ↔ membership consistency checks)
- `backend/accounts/api/permissions/accounts.py` (existing permission classes, `AccountTypeMustBePersonal`)
- `backend/accounts/migrations/0001_initial.py` (existing constraint naming convention: `act_*_cc`, `act_*_uix`, `act_*_ix`)
- Existing knowledge base: `memory/knowledge/_unverified/django/moderation-workflows-paired-approval.md`, `memory/knowledge/_unverified/devops/better-base-toolchain.md`
