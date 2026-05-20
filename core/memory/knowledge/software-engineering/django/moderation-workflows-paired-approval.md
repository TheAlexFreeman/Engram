---
source: agent-generated
type: knowledge
created: 2026-04-14
last_verified: 2026-04-14
trust: low
related:
  - verification-upload-lifecycle.md
  - ../../software-engineering/django/django-react-drf.md
  - ../../software-engineering/django/celery-worker-beat-ops.md
origin_session: memory/activity/2026/04/14/chat-002
---

# Moderation Workflows: State Machines and Paired Approval

Any platform that accepts user-generated content and publishes it at a later step needs a moderation pipeline. The engineering substance lies in four questions: how do you model the states, how do you prevent a single actor from rubber-stamping high-stakes decisions, how do you keep an audit trail that survives the workflow, and how do you keep the moderator UX fast enough to avoid backlog. This note covers a Django-specific answer.

---

## 1. State machines first

A moderation record has a small number of valid states and a small number of valid transitions between them. Encode this in the model, not in ad-hoc view logic.

```python
# moderation/models/review_moderation.py
class ReviewModeration(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending first review"
        FIRST_APPROVED = "first_approved", "First mod approved, awaiting second"
        APPROVED = "approved", "Approved by paired mods"
        REJECTED = "rejected", "Rejected"
        NEEDS_INFO = "needs_info", "Needs more info from reviewer"
        ESCALATED = "escalated", "Escalated to senior moderator"
        EXPIRED = "expired", "Reviewer did not respond in time"

    review = models.OneToOneField("productions.Review", on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    # Audit fields populated by transition methods, never directly mutated
    first_moderator = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT, related_name="first_moderations")
    first_decision_at = models.DateTimeField(null=True, blank=True)
    second_moderator = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT, related_name="second_moderations")
    second_decision_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)
    needs_info_prompt = models.TextField(blank=True)
```

The valid transitions:

```
PENDING         → FIRST_APPROVED, REJECTED, NEEDS_INFO, ESCALATED
FIRST_APPROVED  → APPROVED, REJECTED, ESCALATED
NEEDS_INFO      → PENDING (reviewer responded), EXPIRED, REJECTED
ESCALATED       → APPROVED, REJECTED
REJECTED        → (terminal)
APPROVED        → (terminal)
EXPIRED         → (terminal)
```

Code this as a transition guard, not as implicit permission in views:

```python
VALID_TRANSITIONS: dict[str, set[str]] = {
    Status.PENDING:        {Status.FIRST_APPROVED, Status.REJECTED, Status.NEEDS_INFO, Status.ESCALATED},
    Status.FIRST_APPROVED: {Status.APPROVED, Status.REJECTED, Status.ESCALATED},
    Status.NEEDS_INFO:     {Status.PENDING, Status.REJECTED, Status.EXPIRED},
    Status.ESCALATED:      {Status.APPROVED, Status.REJECTED},
    Status.REJECTED:       set(),
    Status.APPROVED:       set(),
    Status.EXPIRED:        set(),
}


class InvalidTransition(Exception):
    pass


def transition(record: ReviewModeration, new_status: str) -> None:
    if new_status not in VALID_TRANSITIONS[record.status]:
        raise InvalidTransition(f"{record.status} → {new_status} not allowed")
    record.status = new_status
```

Finite state machine libraries like `django-fsm` or `django-fsm-2` wrap this pattern with decorators and admin integration. They're worth pulling in when the state graph gets complex enough that managing guards by hand becomes error-prone. For a graph this size, explicit guards are fine and easier to read in a code review.

---

## 2. Paired approval

"Paired approval" (also called dual control or four-eyes principle) means no single actor can drive a sensitive decision to its terminal state. This matters when a single moderator's misjudgment or bad-faith approval has real consequences — in Rate My Set's case, publishing a verified review affects a production's public scorecard.

Two enforcement rules:

1. **Distinct actors**: second_moderator ≠ first_moderator.
2. **Distinct steps**: the second moderator acts only after the first has transitioned to FIRST_APPROVED.

```python
# moderation/ops/paired_approve.py
def first_approve(record: ReviewModeration, moderator: User) -> None:
    if not moderator.has_perm("moderation.first_approve"):
        raise PermissionDenied()

    with transaction.atomic():
        # select_for_update prevents race with a concurrent reject
        record = ReviewModeration.objects.select_for_update().get(pk=record.pk)
        transition(record, Status.FIRST_APPROVED)
        record.first_moderator = moderator
        record.first_decision_at = timezone.now()
        record.save(update_fields=["status", "first_moderator", "first_decision_at"])
        ModerationEvent.objects.create(
            record=record,
            actor=moderator,
            from_status=Status.PENDING,
            to_status=Status.FIRST_APPROVED,
        )


def final_approve(record: ReviewModeration, moderator: User) -> None:
    if not moderator.has_perm("moderation.final_approve"):
        raise PermissionDenied()
    if record.first_moderator_id == moderator.id:
        raise PermissionDenied("Second approval must come from a different moderator.")

    with transaction.atomic():
        record = ReviewModeration.objects.select_for_update().get(pk=record.pk)
        transition(record, Status.APPROVED)
        record.second_moderator = moderator
        record.second_decision_at = timezone.now()
        record.save(update_fields=["status", "second_moderator", "second_decision_at"])
        ModerationEvent.objects.create(
            record=record,
            actor=moderator,
            from_status=Status.FIRST_APPROVED,
            to_status=Status.APPROVED,
        )
        # Side effects only happen at the terminal transition.
        publish_review.delay(str(record.review_id))
```

A few things are deliberate:

- **`select_for_update`** prevents a race where two moderators each believe they're the second approver.
- **Distinct actor is checked in the op**, not just in the serializer. Ops are the last line of defense.
- **Side effects fire only at the terminal transition.** The review is queued for publication on the second approval, never the first. If a first-approval side effect existed, it'd break the "no publication without two approvals" invariant.
- **All status writes happen via `update_fields=[...]`.** This prevents `.save()` from silently resetting something that another concurrent op just changed.

### Escalation

Any single moderator can escalate to a senior reviewer. Escalation is not a veto on either of their peers — it's an opt-out:

```python
def escalate(record: ReviewModeration, moderator: User, reason: str) -> None:
    with transaction.atomic():
        record = ReviewModeration.objects.select_for_update().get(pk=record.pk)
        transition(record, Status.ESCALATED)
        record.save(update_fields=["status"])
        ModerationEvent.objects.create(
            record=record,
            actor=moderator,
            from_status=record.status,
            to_status=Status.ESCALATED,
            note=reason,
        )
        notify_senior_moderators(record, reason)
```

Senior moderators need an elevated permission (`moderation.senior_approve`) so the paired rule doesn't silently override the escalation.

---

## 3. Permissions and roles

Django has two reasonable approaches. Pick one; don't mix.

### Option A: Permissions + Groups (Django built-in)

```python
# moderation/apps.py
from django.apps import AppConfig

class ModerationConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "moderation"

    def ready(self):
        from django.db.models.signals import post_migrate
        post_migrate.connect(ensure_permissions, sender=self)


def ensure_permissions(sender, **kwargs):
    content_type = ContentType.objects.get_for_model(ReviewModeration)
    for codename, name in [
        ("first_approve", "Can perform first moderation approval"),
        ("final_approve", "Can perform second/final moderation approval"),
        ("senior_approve", "Can approve from escalation queue"),
        ("reject", "Can reject moderation records"),
    ]:
        Permission.objects.get_or_create(
            content_type=content_type, codename=codename, defaults={"name": name}
        )
    # Create moderator and senior moderator groups
    mod_group, _ = Group.objects.get_or_create(name="moderators")
    senior_group, _ = Group.objects.get_or_create(name="senior_moderators")
    # ...assign perms to groups
```

Check in views:

```python
class ModerationApproveView(APIView):
    permission_classes = [IsAuthenticated, DjangoModelPermissions]
    # DRF's DjangoModelPermissions maps HTTP verbs to the permission codenames
```

### Option B: Membership-based roles (Better Base's Account/Membership pattern)

If the project uses an Account/Membership model (as Better Base does), the "moderation team" is an Account and moderators are Members of that account with specific roles:

```python
class ModerationMembership(models.Model):
    class Role(models.TextChoices):
        MODERATOR = "moderator"
        SENIOR_MODERATOR = "senior_moderator"
        LEAD = "lead"

    account = models.ForeignKey("accounts.Account", on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=32, choices=Role.choices)
    active = models.BooleanField(default=True)
```

A DRF permission class:

```python
class IsModerator(BasePermission):
    required_roles = {"moderator", "senior_moderator", "lead"}

    def has_permission(self, request, view):
        return ModerationMembership.objects.filter(
            user=request.user,
            active=True,
            role__in=self.required_roles,
            account__role="moderation",
        ).exists()


class IsSeniorModerator(IsModerator):
    required_roles = {"senior_moderator", "lead"}
```

Option B is the right fit when you already have an account/membership model and want moderation to be one of several team contexts. Option A is simpler if moderators are just a Django group and nothing more.

---

## 4. The queue: moderator view of pending work

Moderators need a fast, filterable list of records waiting for their action. Key design rules:

- **Claim, don't just view.** Two moderators picking up the same record simultaneously is wasted work. Either serialize picks via `select_for_update` on read, or add an explicit `claimed_by` / `claimed_at` field that expires after N minutes.
- **Hide self-created work.** A moderator who somehow authored a review they're about to moderate should never see it in their own queue.
- **Paired-mod visibility.** The second-review queue should show only records in `FIRST_APPROVED` status, and filter out records the current moderator was the first on.

```python
# moderation/api/views/queue.py
class FirstReviewQueueViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsModerator]
    serializer_class = ModerationQueueSerializer

    def get_queryset(self):
        return (
            ReviewModeration.objects
            .filter(status=Status.PENDING)
            .exclude(review__reviewer=self.request.user)
            .select_related("review", "review__production")
            .order_by("created_at")   # oldest first (FIFO)
        )


class SecondReviewQueueViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsModerator]
    serializer_class = ModerationQueueSerializer

    def get_queryset(self):
        return (
            ReviewModeration.objects
            .filter(status=Status.FIRST_APPROVED)
            .exclude(first_moderator=self.request.user)  # paired-mod invariant
            .exclude(review__reviewer=self.request.user)
            .select_related("review", "review__production", "first_moderator")
            .order_by("first_decision_at")   # oldest first-approval first
        )


class EscalationQueueViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsSeniorModerator]
    serializer_class = ModerationQueueSerializer

    def get_queryset(self):
        return ReviewModeration.objects.filter(status=Status.ESCALATED)
```

For large backlogs, add database-level indexes on `(status, created_at)` so the queue queries stay cheap under pressure.

---

## 5. Audit trail: append-only events

Every transition should generate an immutable event record. Do not try to reconstruct audit history from the current state of the moderation record — fields get overwritten.

```python
class ModerationEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid7)
    record = models.ForeignKey(ReviewModeration, on_delete=models.PROTECT, related_name="events")
    actor = models.ForeignKey(User, on_delete=models.PROTECT, null=True)
    from_status = models.CharField(max_length=20)
    to_status = models.CharField(max_length=20)
    note = models.TextField(blank=True)
    metadata = models.JSONField(default=dict)   # e.g. IP, user-agent, client version
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["record", "-created_at"])]
```

Two rules:

1. **No updates.** ModerationEvent rows are never modified after creation. Use model-level tooling (override `save()` to raise on updates, or Postgres trigger) to enforce this.
2. **`on_delete=PROTECT`** everywhere so you can't accidentally lose audit history by deleting a record or a moderator user.

When a moderator account is deactivated, the FK stays intact because `PROTECT` forces a soft-delete pattern — flip `User.is_active` to `False`, keep the row.

---

## 6. Notifications

Moderation is asynchronous and cross-timezone. Build the notification layer from the start.

```python
# moderation/notifications.py
def notify_second_review_available(record: ReviewModeration) -> None:
    recipients = (
        User.objects
        .filter(groups__name="moderators", is_active=True)
        .exclude(id=record.first_moderator_id)
    )
    for user in recipients:
        send_email.delay(
            to=user.email,
            subject="A moderation record is ready for second review",
            template="moderation/second_review_ready.html",
            context={"record_id": str(record.id)},
        )
```

Patterns worth applying:

- **Opt-in channels.** Let each moderator pick email, Slack, or push. Store preferences on their profile.
- **Digest, not spam.** If the queue has ten pending records, don't send ten emails. Batch per moderator per hour.
- **Explicit pings for escalations.** Senior moderators need to know about escalations in real-time, but should not be CC'd on every first-approval event.
- **SLA reminders.** If a record sits in `FIRST_APPROVED` for more than 24 hours, remind the whole pool, then auto-escalate at 72 hours.

---

## 7. Metrics

A moderation team runs on observable metrics. Expose these via an admin dashboard or a `/api/moderation/metrics/` endpoint:

- **Queue depth by status**: how many pending, first-approved, escalated. Target is steady-state near zero.
- **Time-to-first-decision**: histogram of (created_at → first_decision_at).
- **Time-to-final-decision**: histogram of (created_at → second_decision_at).
- **Rejection rate by reason.** If one reason dominates, it's a signal that reviewer UX is confusing or that the rule is too strict.
- **Disagreement rate.** When the second moderator rejects after a first approval, that's a signal of inconsistency in the moderator pool — worth reviewing together.
- **Moderator workload distribution.** Per moderator: records touched this week. If one moderator is carrying 80% of the queue, you have a bus factor problem.
- **Escalation rate.** High escalation rate from specific moderators may indicate under-confidence or under-training; from specific case types, a policy gap.

```python
# moderation/ops/metrics.py
def queue_depth_by_status() -> dict[str, int]:
    return dict(
        ReviewModeration.objects
        .values("status")
        .annotate(n=Count("id"))
        .values_list("status", "n")
    )


def time_to_first_decision_percentiles(window_days: int = 30) -> dict[str, float]:
    since = timezone.now() - timedelta(days=window_days)
    decided = ReviewModeration.objects.filter(first_decision_at__gte=since).annotate(
        lag_seconds=ExpressionWrapper(
            F("first_decision_at") - F("created_at"),
            output_field=DurationField(),
        )
    )
    return {
        "p50": percentile(decided, "lag_seconds", 0.50),
        "p90": percentile(decided, "lag_seconds", 0.90),
        "p99": percentile(decided, "lag_seconds", 0.99),
    }
```

(Postgres 16+ has `percentile_cont` directly via `django.db.models.aggregates` with the right raw SQL.)

---

## 8. Moderator UX in the frontend

Two rules tend to drive good paired-approval UIs:

1. **Surface what was decided before.** The second moderator should see the first moderator's identity, timestamp, and any notes they left — but not influence the content of their own decision by default. Some teams hide the first notes until the second mod has already clicked approve/reject to prevent anchoring.
2. **One-click plus confirmation, not just one click.** Approval is a terminal action. Require a confirm modal that restates the decision and the rationale. It slows things down by two seconds and prevents accidental terminal actions under fatigue.

Status badges should be consistent across queues:

- 🟡 Pending first review
- 🟠 Awaiting second review
- 🟢 Approved
- 🔴 Rejected
- 🔷 Needs info
- ⬆️ Escalated

For accessibility, don't use color alone — always pair with a text label.

---

## 9. Anti-collusion and rotation

If moderators can repeatedly pair with the same peer across records, two sympathetic moderators can effectively act as one. Mitigations:

- **Randomized queue ordering** within each status bucket for the second-review queue. The paired moderator for a given record is not predictable.
- **Pair-frequency metrics.** Track how often moderator A completes the second step for records first-approved by moderator B. If the distribution is meaningfully non-uniform, surface it for review.
- **Term limits on moderator roles.** Rotate responsibilities; a moderator role should be reviewed every N months. Document this in the moderator onboarding.

These measures are soft defenses. Hard defense is the escalation path — any moderator who suspects bad-faith pairing can escalate a record out of the normal pipeline.

---

## 10. Testing

```python
@pytest.mark.django_db
class TestPairedApproval:
    def test_single_moderator_cannot_complete_both_steps(self):
        record = ReviewModerationFactory(status=Status.PENDING)
        mod = ModeratorFactory()
        first_approve(record, moderator=mod)
        record.refresh_from_db()
        assert record.status == Status.FIRST_APPROVED
        with pytest.raises(PermissionDenied):
            final_approve(record, moderator=mod)

    def test_distinct_moderators_complete_approval(self):
        record = ReviewModerationFactory(status=Status.PENDING)
        m1, m2 = ModeratorFactory(), ModeratorFactory()
        first_approve(record, moderator=m1)
        final_approve(record, moderator=m2)
        record.refresh_from_db()
        assert record.status == Status.APPROVED
        assert record.first_moderator == m1
        assert record.second_moderator == m2

    def test_second_queue_excludes_first_approver(self):
        m1 = ModeratorFactory()
        record = ReviewModerationFactory(status=Status.FIRST_APPROVED, first_moderator=m1)
        # From m1's perspective, this record should not be in their second-review queue
        client.force_authenticate(m1)
        resp = client.get("/api/moderation/second-review/")
        assert record.id not in [r["id"] for r in resp.json()["results"]]

    def test_invalid_transition_raises(self):
        record = ReviewModerationFactory(status=Status.APPROVED)
        with pytest.raises(InvalidTransition):
            transition(record, Status.PENDING)

    def test_audit_event_created_on_transition(self):
        record = ReviewModerationFactory(status=Status.PENDING)
        first_approve(record, moderator=ModeratorFactory())
        assert record.events.filter(to_status=Status.FIRST_APPROVED).exists()

    def test_rejected_is_terminal(self):
        record = ReviewModerationFactory(status=Status.REJECTED)
        with pytest.raises(InvalidTransition):
            transition(record, Status.FIRST_APPROVED)

    def test_concurrent_second_approval_is_race_safe(self):
        """Two moderators racing on the second step — only one wins."""
        record = ReviewModerationFactory(status=Status.FIRST_APPROVED, first_moderator=ModeratorFactory())
        m2, m3 = ModeratorFactory(), ModeratorFactory()
        # Run final_approve in parallel threads
        with ThreadPoolExecutor(max_workers=2) as ex:
            futures = [ex.submit(final_approve, record, m2), ex.submit(final_approve, record, m3)]
            results = [f.exception() for f in futures]
        # Exactly one should succeed, the other should raise InvalidTransition
        assert sum(1 for r in results if r is None) == 1
        assert sum(1 for r in results if isinstance(r, InvalidTransition)) == 1
```

Concurrency tests are especially important for the paired-approval invariant. `select_for_update` is doing the heavy lifting; the test confirms it.

---

## 11. Decision summary

- Model moderation state as an explicit finite state machine; enforce transitions in ops, not views.
- Use paired approval whenever a single moderator's decision has irrevocable consequences. Enforce the distinct-actor rule in the op layer with `select_for_update` to eliminate races.
- Keep a separate append-only audit table. Never rewrite transition history.
- Build the queue views with exclusions baked in (self-authored records, self-approved in the second queue, etc.).
- Invest in notifications, SLA tracking, and metrics from day one — these make the team sustainable.
- Add soft anti-collusion measures (randomized queues, pair-frequency metrics, rotation) but rely on escalation paths for hard defense.
- Test the state machine, the paired-approval invariant, and concurrent races explicitly.

---

## Sources

- Django permissions and groups: https://docs.djangoproject.com/en/5.2/topics/auth/default/
- django-fsm: https://github.com/viewflow/django-fsm
- django-fsm-2 (actively maintained fork): https://github.com/pfouque/django-fsm-2
- Postgres `SELECT ... FOR UPDATE`: https://www.postgresql.org/docs/current/sql-select.html#SQL-FOR-UPDATE-SHARE
- "Four-eyes principle" overview: https://en.wikipedia.org/wiki/Two-person_rule
- DRF permissions: https://www.django-rest-framework.org/api-guide/permissions/

Last updated: 2026-04-14
