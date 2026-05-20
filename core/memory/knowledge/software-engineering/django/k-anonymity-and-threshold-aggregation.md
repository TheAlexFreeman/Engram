---
source: agent-generated
type: knowledge
created: 2026-04-14
last_verified: 2026-04-14
trust: low
related:
  - ../../software-engineering/django/django-orm-postgres.md
  - ../../software-engineering/django/django-react-drf.md
  - ../../software-engineering/django/drf-spectacular.md
  - text-sanitization-for-anonymization.md
origin_session: memory/activity/2026/04/14/chat-002
---

# k-Anonymity and Threshold Aggregation in Django

Threshold aggregation is the privacy model for systems that publish statistics about individuals without publishing the individuals themselves. The core commitment: *no released record or statistic can be traced back to an identifiable person*. k-anonymity formalizes "identifiable" as "distinguishable in a group smaller than k." This note covers the model, its failure modes, and how to enforce it end-to-end in a Django + DRF stack.

---

## 1. The core guarantees

### k-anonymity

A released dataset is k-anonymous if every record shares its quasi-identifier values with at least k−1 other records. In practice for aggregate releases, this reduces to a simpler **suppression rule**: *do not release a statistic computed from fewer than k contributors.*

Latanya Sweeney's original 2002 paper showed that 87% of the US population is uniquely identifiable by (ZIP code, birth date, sex) — quasi-identifiers, not "direct" identifiers. The practical lesson is that anything published alongside your aggregate (city, role, department, dates) is part of the quasi-identifier surface and counts toward the k budget.

### l-diversity and t-closeness

k-anonymity alone fails against **homogeneity attacks**: if all k contributors to a bucket share the same sensitive attribute, the aggregate reveals that attribute for each of them.

- **l-diversity** requires at least l well-represented values of the sensitive attribute within each equivalence class.
- **t-closeness** further requires that the distribution of the sensitive attribute within a class match the overall distribution to within distance t.

For Rate My Set: the "harassment observed" flag is a sensitive attribute. Publishing "10 reviews, 10 harassment flags" passes k=10 but fails l-diversity — every reviewer is implicated. Practical mitigations: only publish counts, not per-reviewer flags; suppress categories with 100% concordance; hide the flag entirely when the reviewer count is below a higher threshold.

### Threshold aggregation (the practical rule)

The shippable rule is: *for every (entity, statistic) you publish, confirm n ≥ k before returning it.* This is the rule we enforce in code below.

---

## 2. Choosing k

k is a policy decision, not a technical one. Common thresholds:

- Public health, education: k=10 to k=20
- Financial transparency reports: k=5 to k=10
- Employee compensation surveys: k=3 to k=5 (aided by trust layer)
- Rate My Set's roadmap: k=10 public, k=3 for authenticated members

Three lenses to calibrate:

1. **Background knowledge**: how much does an attacker plausibly already know? (For Rate My Set: an attacker likely knows who was on set. That raises k.)
2. **Sensitivity**: higher sensitivity → higher k. Harassment claims need a higher threshold than food quality scores.
3. **Utility floor**: the k that makes the product useful. If most productions have 3–8 reviews and you set k=10, you publish nothing.

Tier your surfaces: stricter k for public, looser k for trusted authenticated audiences who also accept logging and terms of use. Codify both thresholds in settings, not magic numbers.

---

## 3. Where to enforce the threshold

Privacy should fail closed, at the layer closest to the data. For a DRF stack, enforcement belongs in the queryset/serializer layer, *not* the frontend.

```
Database   ← raw reviews
ORM layer  ← annotate counts, apply threshold filters  ← enforce here
View/serializer  ← shape response based on threshold  ← and here
Frontend   ← render gracefully when suppressed
```

If only the frontend hides below-threshold data, a direct API consumer will see it. Never hide in the UI what the API is willing to serve.

---

## 4. Django implementation: suppression at the queryset layer

The cleanest pattern is a custom QuerySet that carries the threshold policy.

```python
# productions/models/scorecards.py
from django.db import models
from django.db.models import Count, Avg, Q

class ScorecardQuerySet(models.QuerySet):
    def with_review_counts(self):
        """Annotate aggregate counts and means from verified reviews."""
        return self.annotate(
            review_count=Count(
                "production__reviews",
                filter=Q(production__reviews__verification_status="verified"),
            ),
            mean_overall=Avg(
                "production__reviews__overall",
                filter=Q(production__reviews__verification_status="verified"),
            ),
            # ...repeat for each dimension
        )

    def publishable_for(self, audience: str):
        """Return only scorecards whose review_count meets the audience threshold."""
        threshold = settings.K_ANON_THRESHOLDS[audience]  # {"public": 10, "member": 3}
        return self.with_review_counts().filter(review_count__gte=threshold)


class Scorecard(models.Model):
    production = models.OneToOneField("productions.Production", on_delete=models.CASCADE)
    # denormalized aggregates populated by compute_scorecard op
    review_count = models.PositiveIntegerField(default=0)
    mean_overall = models.FloatField(null=True)
    # ...

    objects = ScorecardQuerySet.as_manager()
```

A materialized `Scorecard` is usually the right pattern for this. Computing aggregates on every read is expensive and fights the threshold logic. Recompute via a Celery task on every review verification, and separately on a periodic sweep. See `celery-worker-beat-ops.md`.

---

## 5. Segmented thresholds

Rate My Set splits union and non-union reviewers. Each segment needs its own k check:

```python
@dataclass
class SegmentedScorecard:
    union_count: int
    non_union_count: int
    union_mean_overall: float | None
    non_union_mean_overall: float | None

def compute_segmented_scorecard(production: Production, threshold: int) -> SegmentedScorecard:
    verified = production.reviews.filter(verification_status="verified")
    union = verified.filter(union_member=True).aggregate(
        n=Count("id"), mean=Avg("overall")
    )
    non_union = verified.filter(union_member=False).aggregate(
        n=Count("id"), mean=Avg("overall")
    )
    return SegmentedScorecard(
        union_count=union["n"],
        non_union_count=non_union["n"],
        # Suppress the segment mean if its own count is below threshold.
        union_mean_overall=union["mean"] if union["n"] >= threshold else None,
        non_union_mean_overall=non_union["mean"] if non_union["n"] >= threshold else None,
    )
```

Two rules matter here:

1. **Each segment is checked independently.** A production with 12 union and 2 non-union reviews can publish the union mean at k=10 but must suppress the non-union mean.
2. **Segment counts themselves are low-granularity data.** Publishing exactly "2 non-union reviews" already narrows identity. Consider rounding small counts to bins ("<5", "5–10", "10+") rather than exact values when the count itself is sensitive.

---

## 6. DRF serializer and viewset enforcement

The serializer should receive already-suppressed values, not sensitive raw data plus a "show this" flag. Do the suppression in the queryset/service layer and have the serializer reflect the shape.

```python
# productions/api/serializers/scorecards.py
class PublicScorecardSerializer(serializers.ModelSerializer):
    class Meta:
        model = Scorecard
        fields = [
            "review_count",
            "mean_overall",
            "mean_professionalism",
            "mean_safety",
            "mean_food",
            "harassment_count_binned",  # never raw count below threshold
            "union_mean_overall",
            "non_union_mean_overall",
        ]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # Guard: if anything leaks a raw count below threshold, null it out.
        threshold = settings.K_ANON_THRESHOLDS["public"]
        if instance.review_count < threshold:
            # Return only the sentinel; this row should never have been in the queryset.
            return {"suppressed": True, "reason": "below_threshold"}
        return data


class PublicScorecardViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = PublicScorecardSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        # Authoritative filter — not shadowed by serializer logic.
        return Scorecard.objects.publishable_for("public").select_related("production")
```

Two defenses are applied: the queryset filters out below-threshold rows (primary), and the serializer re-checks and returns a sentinel (belt-and-suspenders). If a caller requests a specific scorecard by ID, the queryset filter triggers 404, which is the right answer — it treats below-threshold data as nonexistent from the public viewpoint.

### Binning counts of sensitive flags

Raw counts of harassment/discrimination/injury flags should usually be binned, not exact:

```python
def bin_flag_count(count: int, total: int) -> str:
    if count == 0:
        return "none_reported"
    if count < 3:
        return "few_reported"           # hides 1 and 2 exactly
    if count / total < 0.25:
        return "minority_reported"
    if count / total < 0.75:
        return "majority_reported"
    return "most_reported"
```

Exact numbers satisfy curiosity but add deanonymization surface with little gain in editorial signal.

---

## 7. Attack surfaces to design against

### Intersection / composition attacks

Two below-threshold slices that overlap (e.g. "all productions in Vancouver with 4 reviews" + "productions reviewer X worked on this year") can each be innocuous but jointly identify. Mitigations:

- Limit filter dimensions on the public surface. Don't let arbitrary filter combinations that multiply the quasi-identifier count.
- Cap the fan-out: per-request filter combinations that would return fewer than k records should return the same below-threshold sentinel, regardless of which filters reduced the count.

### Background knowledge attacks

An attacker who was on set knows roughly who else was on set. For Rate My Set, that means the "safe" k for crew reviews is *much* higher than the size of the department. If a production had 4 camera assistants and the scorecard shows "camera-department avg: 2.1", the four of them know who said what. Mitigations:

- Never expose aggregates segmented by small-department dimensions at public thresholds.
- Use k thresholds that reflect the smallest plausible population size, not the smallest statistical count.

### Differencing attacks

Releasing an aggregate at time T and again at time T+1 after one review is added lets an attacker subtract to isolate the new review. Mitigations:

- Publish scorecards on cadence (monthly/quarterly) rather than real-time.
- Add release delays after a verification is approved (Rate My Set uses wrap+90 days public / wrap+30 days member).
- If aggregates must update live, add noise (see differential privacy below).

### Unique-value attacks

If a scorecard shows mean = 5.0 and count = 5, every reviewer rated 5.0. l-diversity on the score distribution is implied. Mitigations:

- For small k, bin or round continuous means (e.g. 1–5 scale → three-bucket "below avg / avg / above avg").
- Suppress min/max or stddev when count is near threshold.

---

## 8. Differential privacy as the stronger alternative

Differential privacy (DP) replaces "definitely don't publish below threshold" with "add calibrated noise so any single record's contribution is bounded." Formally, a mechanism M is ε-differentially private if for all neighboring datasets D and D′ (differing in one record) and all outputs S, P[M(D) ∈ S] ≤ e^ε · P[M(D′) ∈ S].

When to consider DP over pure k-anon:

- You need to release statistics on small populations with formal guarantees.
- You need composability — DP has clean loss bounds across multiple queries; k-anon does not.
- You have a data steward role and can afford per-query ε budget tracking.

Reasonable libraries: OpenDP (`pip install opendp`) from Harvard/MS, IBM `diffprivlib`, Google's `differential-privacy` (Python bindings). The Laplace mechanism is the classic starting point:

```python
from opendp.measurements import make_laplace
from opendp.mod import enable_features

enable_features("contrib")

def dp_mean(values: list[float], lower: float, upper: float, epsilon: float) -> float:
    n = len(values)
    sensitivity = (upper - lower) / n   # L1 sensitivity of bounded mean
    mechanism = make_laplace(sensitivity / epsilon)
    clamped_mean = sum(max(lower, min(upper, v)) for v in values) / n
    return mechanism(clamped_mean)
```

For a consumer-facing review product, DP is usually overkill at v1 and under-delivers utility at small n. Ship k-anon + l-diversity + suppression first, and treat DP as a v2 upgrade for specific releases (research API, press data).

---

## 9. Testing the guarantee

Privacy guarantees need adversarial tests, not just happy-path coverage.

```python
@pytest.mark.django_db
class TestKAnonEnforcement:
    def test_exactly_at_threshold_publishes(self):
        production = ProductionFactory()
        for _ in range(settings.K_ANON_THRESHOLDS["public"]):
            ReviewFactory(production=production, verification_status="verified")
        ScorecardService.recompute(production)

        resp = client.get(f"/api/public/scorecards/{production.id}/")
        assert resp.status_code == 200
        assert resp.json()["review_count"] == 10

    def test_one_below_threshold_suppresses(self):
        production = ProductionFactory()
        for _ in range(settings.K_ANON_THRESHOLDS["public"] - 1):
            ReviewFactory(production=production, verification_status="verified")
        ScorecardService.recompute(production)

        resp = client.get(f"/api/public/scorecards/{production.id}/")
        assert resp.status_code == 404  # treated as nonexistent publicly

    def test_pending_reviews_do_not_count(self):
        """Only verified reviews count toward threshold."""
        production = ProductionFactory()
        for _ in range(20):
            ReviewFactory(production=production, verification_status="pending")
        for _ in range(5):
            ReviewFactory(production=production, verification_status="verified")
        ScorecardService.recompute(production)

        resp = client.get(f"/api/public/scorecards/{production.id}/")
        assert resp.status_code == 404

    def test_segment_suppression_independent(self):
        production = ProductionFactory()
        for _ in range(12):
            ReviewFactory(production=production, union_member=True, verification_status="verified")
        for _ in range(2):
            ReviewFactory(production=production, union_member=False, verification_status="verified")
        ScorecardService.recompute(production)

        resp = client.get(f"/api/public/scorecards/{production.id}/")
        body = resp.json()
        assert body["union_mean_overall"] is not None   # 12 ≥ 10
        assert body["non_union_mean_overall"] is None   # 2 < 10

    def test_filter_combination_does_not_bypass(self):
        """List endpoint filters should never return below-threshold rows."""
        # Seed mix of publishable and below-threshold productions.
        ...
        resp = client.get("/api/public/scorecards/?city=Los+Angeles&production_type=tv_series")
        for row in resp.json()["results"]:
            assert row["review_count"] >= 10
```

Three test categories are load-bearing:

1. **Threshold boundary tests**: at, just below, just above.
2. **Path-independence tests**: the same guarantee must hold across list views, detail views, filter combinations, and inherited nested routes.
3. **State tests**: pending/rejected/expired reviews must not count; deleted reviews must drop aggregates promptly.

Run all three on every relevant endpoint, ideally in a parametrized fixture over `(audience, endpoint)` pairs.

---

## 10. Operational rules

- **Codify k in settings**, never inline: `K_ANON_THRESHOLDS = {"public": 10, "member": 3}`.
- **Version your thresholds.** If you raise k, recompute scorecards immediately; if you lower k, think carefully about whether previously suppressed data becoming visible is ethically acceptable.
- **Log every below-threshold response.** Monitoring can spot someone fuzzing filters to enumerate small cohorts.
- **Rate-limit aggregation endpoints.** Even a well-tuned k doesn't help against rapid-fire differencing.
- **Treat k as a contract.** Document it in the transparency page; changing it publicly is a product decision, not a config tweak.

---

## Sources

- Sweeney, L. "k-Anonymity: A Model for Protecting Privacy." 2002. https://dataprivacylab.org/dataprivacy/projects/kanonymity/
- Machanavajjhala et al. "l-Diversity: Privacy Beyond k-Anonymity." 2007.
- Li, Li, Venkatasubramanian. "t-Closeness: Privacy Beyond k-Anonymity and l-Diversity." 2007.
- Dwork, C. "Differential Privacy." 2006.
- OpenDP: https://docs.opendp.org/
- US Census Bureau disclosure avoidance: https://www.census.gov/about/policies/privacy/statistical_safeguards.html
- Pycanon library (k-anon/l-div/t-close metrics): https://github.com/IFCA-Advanced-Computing/pycanon

Last updated: 2026-04-14
