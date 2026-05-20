---
source: agent-generated
type: knowledge
created: 2026-04-14
last_verified: 2026-04-14
trust: low
related:
  - ../../software-engineering/django/django-storages.md
  - ../../software-engineering/django/celery-worker-beat-ops.md
  - ../../software-engineering/django/django-security.md
  - moderation-workflows-paired-approval.md
origin_session: memory/activity/2026/04/14/chat-002
---

# Verification Upload Lifecycle: Ephemeral Private Files with Audit Hashes

Some systems accept files from users, show them briefly to a moderator to verify a claim, and then must destroy the file while keeping proof that the verification happened. This is the shape of Rate My Set's booking-confirmation flow: reviewer uploads a call sheet, moderator confirms the reviewer worked on the production, the file is destroyed at +24h, and only a SHA-256 hash persists as an audit artifact. The pattern shows up elsewhere too — identity verification, expense receipts for one-time reimbursement, "upload your lease for review" flows. This note covers the full lifecycle.

---

## 1. The five states

```
    (Upload)        (Review)         (Approve/Reject)    (Destroy)
UPLOADED ─────► UNDER_REVIEW ─────► DECIDED ──────────► DESTROYED
                                      │
                                      └── on reject: immediate destroy
```

- **UPLOADED** — the object is in the private bucket, awaiting moderator pickup.
- **UNDER_REVIEW** — a moderator has claimed the record; a short-lived download URL may have been issued.
- **DECIDED** — approved or rejected; the decision is recorded; for approvals, a destruction timer is armed.
- **DESTROYED** — the object is gone from the bucket; only the hash and decision metadata persist.

Every state transition is audit-logged with timestamp and actor. Transitions happen via ops functions — never by direct ORM mutation.

---

## 2. Storage design

### Bucket separation

Use a dedicated bucket (or at minimum a dedicated prefix in a dedicated IAM boundary) for verification uploads. Mixing these with general media storage leaks blast radius: a misconfigured public policy on the main media bucket shouldn't make booking confirmations world-readable.

```python
# settings/base.py
STORAGES = {
    "default": {                          # general media
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "bucket_name": env("AWS_STORAGE_BUCKET_NAME"),
            "default_acl": None,
            "querystring_auth": True,
        },
    },
    "verification_uploads": {             # private, ephemeral, audited
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "bucket_name": env("AWS_VERIFICATION_BUCKET"),
            "default_acl": None,
            "querystring_auth": True,
            "querystring_expire": 900,     # 15-minute moderator access
            "object_parameters": {
                "ServerSideEncryption": "AES256",
            },
        },
    },
    "staticfiles": {...},
}
```

### Encryption at rest

Three options, in order of operational complexity:

1. **SSE-S3 (AES-256, AWS-managed keys)**: default and free; keys are AWS-owned. Best starting point.
2. **SSE-KMS (customer master key)**: the bucket encrypts with a KMS key you control. You can *revoke access to the KMS key* to make all objects unreadable without deleting them — useful for emergency response. Every GET costs a KMS API call.
3. **Client-side envelope encryption**: the Django app encrypts the file locally before upload using a data key wrapped by a KMS master key. Highest control, highest operational cost; use when the threat model includes AWS insiders.

For Rate My Set, SSE-KMS is the right middle ground: AWS never sees plaintext except briefly in memory, and a key-policy change can render all in-flight verification data unreadable if something goes wrong.

### Bucket policy guardrails

Every verification bucket should have at minimum:

- **Block all public access** at the bucket level (AWS account-level setting).
- **Deny non-TLS requests** via bucket policy (`aws:SecureTransport: "false"`).
- **Server-side logging** to a separate log bucket (with its own retention).
- **Object lock or versioning disabled**, or you'll fight your own destruction logic. Do not enable MFA delete on a bucket whose objects you intend to delete on a schedule.
- **Lifecycle rule as backup**: an S3 lifecycle rule that deletes all objects older than 7 days. Defense-in-depth against a Celery outage.

```json
{
  "Rules": [{
    "ID": "SweepVerificationUploads",
    "Status": "Enabled",
    "Prefix": "",
    "Expiration": {"Days": 7}
  }]
}
```

The app-level destruction at +24h is the primary mechanism; the lifecycle rule is a floor so no object ever outlives the moderator decision window by more than a week.

---

## 3. Upload: presigned POST

The upload path should not pass through Django. Gunicorn workers should not be tied up proxying large files, and the Django process doesn't need to hold the plaintext in memory.

```python
# productions/ops/initiate_upload.py
import uuid
import boto3
from django.conf import settings

def initiate_verification_upload(
    review_id: UUID,
    filename: str,
    content_type: str,
    byte_size: int,
) -> dict:
    if content_type not in {"application/pdf", "image/jpeg", "image/png"}:
        raise ValidationError("Unsupported file type.")
    if byte_size > 10 * 1024 * 1024:
        raise ValidationError("File exceeds 10MB limit.")

    key = f"verifications/{review_id}/{uuid.uuid4()}/{filename}"

    s3 = boto3.client("s3", region_name=settings.AWS_S3_REGION_NAME)
    presigned = s3.generate_presigned_post(
        Bucket=settings.AWS_VERIFICATION_BUCKET,
        Key=key,
        Fields={
            "Content-Type": content_type,
            "x-amz-server-side-encryption": "aws:kms",
            "x-amz-server-side-encryption-aws-kms-key-id": settings.AWS_KMS_KEY_ID,
        },
        Conditions=[
            {"Content-Type": content_type},
            ["content-length-range", 1, 10 * 1024 * 1024],
            {"x-amz-server-side-encryption": "aws:kms"},
        ],
        ExpiresIn=300,    # 5 minutes to complete the upload
    )
    return {"url": presigned["url"], "fields": presigned["fields"], "key": key}
```

Security rules that should be codified in tests:

- **Content-Type is pinned** by the presigned policy; the client cannot change it.
- **Size range is pinned** by the policy.
- **Encryption headers are required** by the policy; the upload fails if omitted.
- **Keys are namespaced** by review_id so a reviewer can't upload into another review's slot.
- **TTL is short** — 5 minutes is enough for a normal upload, short enough that a leaked presigned URL expires before it can be abused at scale.

### Confirming the upload

When the client calls back to `/confirm-upload/`, the server MUST verify the object actually exists (the client could have skipped the upload entirely) and compute the hash:

```python
def confirm_verification_upload(review: Review, key: str) -> VerificationUpload:
    if not key.startswith(f"verifications/{review.id}/"):
        raise PermissionDenied("Key does not belong to this review.")

    s3 = boto3.client("s3", region_name=settings.AWS_S3_REGION_NAME)
    try:
        head = s3.head_object(Bucket=settings.AWS_VERIFICATION_BUCKET, Key=key)
    except s3.exceptions.ClientError:
        raise NotFound("Upload not found.")

    # Compute SHA-256 by streaming the object (don't hold the whole file in memory).
    digest = hashlib.sha256()
    obj = s3.get_object(Bucket=settings.AWS_VERIFICATION_BUCKET, Key=key)
    for chunk in obj["Body"].iter_chunks(chunk_size=64 * 1024):
        digest.update(chunk)

    return VerificationUpload.objects.create(
        review=review,
        s3_key=key,
        byte_size=head["ContentLength"],
        content_type=head["ContentType"],
        sha256=digest.hexdigest(),
        uploaded_at=timezone.now(),
        state=VerificationUpload.State.UPLOADED,
    )
```

The hash is computed server-side after upload confirmation, not client-side. A client-computed hash is useless as an audit artifact because the client could have lied.

---

## 4. Model shape

```python
# productions/models/verification_uploads.py
class VerificationUpload(models.Model):
    class State(models.TextChoices):
        UPLOADED = "uploaded"
        UNDER_REVIEW = "under_review"
        APPROVED = "approved"
        REJECTED = "rejected"
        DESTROYED = "destroyed"

    id = models.UUIDField(primary_key=True, default=uuid7)
    review = models.OneToOneField(
        "productions.Review",
        on_delete=models.CASCADE,
        related_name="verification_upload",
    )
    # Before destruction:
    s3_key = models.CharField(max_length=512, blank=True)
    byte_size = models.PositiveBigIntegerField()
    content_type = models.CharField(max_length=128)
    # Always persisted:
    sha256 = models.CharField(max_length=64)          # 64 hex chars
    uploaded_at = models.DateTimeField()
    decided_at = models.DateTimeField(null=True)
    destroyed_at = models.DateTimeField(null=True)
    state = models.CharField(max_length=20, choices=State.choices, default=State.UPLOADED)

    class Meta:
        indexes = [
            models.Index(fields=["state", "decided_at"]),  # destruction sweep
        ]

    def mark_destroyed(self):
        """Clear the S3 key field; the actual S3 delete happens in the op."""
        self.s3_key = ""
        self.destroyed_at = timezone.now()
        self.state = self.State.DESTROYED
        self.save(update_fields=["s3_key", "destroyed_at", "state"])
```

Notes:

- `sha256` is a `CharField`, not `BinaryField`. Hex is grep-able in logs and admin; 64 chars is fine.
- `s3_key` is blanked on destroy, not deleted from the row. The row itself persists as audit.
- State is always updated with `update_fields` so concurrent mutations don't silently race.

---

## 5. Moderator access: short-lived GETs

Moderators need to view the upload to verify. Access should be time-limited and logged.

```python
def issue_moderator_download_url(
    upload: VerificationUpload, moderator: User, ttl_seconds: int = 900
) -> str:
    if upload.state not in {VerificationUpload.State.UPLOADED, VerificationUpload.State.UNDER_REVIEW}:
        raise ValidationError("Upload is no longer viewable.")

    # Audit log: who accessed what, when.
    VerificationUploadAccess.objects.create(
        upload=upload,
        moderator=moderator,
        issued_at=timezone.now(),
        ttl_seconds=ttl_seconds,
    )

    # Claim the upload for this moderator (state transition).
    upload.state = VerificationUpload.State.UNDER_REVIEW
    upload.save(update_fields=["state"])

    s3 = boto3.client("s3", region_name=settings.AWS_S3_REGION_NAME)
    return s3.generate_presigned_url(
        "get_object",
        Params={
            "Bucket": settings.AWS_VERIFICATION_BUCKET,
            "Key": upload.s3_key,
            # Force download as attachment (prevents in-browser view caching for PDFs)
            "ResponseContentDisposition": f'attachment; filename="verification.pdf"',
        },
        ExpiresIn=ttl_seconds,
    )
```

Two audit surfaces are kept:

1. **Access log** — every URL issuance, who requested it, when.
2. **CloudTrail / S3 access log** — infrastructure-side record of every GET.

Cross-referencing both lets you detect moderator account compromise. If CloudTrail shows GETs for objects whose app-side audit log has no corresponding issuance, something is wrong.

---

## 6. The destruction pipeline

### Primary: scheduled Celery task

After an approval, schedule a destruction task with a delay.

```python
# productions/ops/approve_verification.py
def approve_verification(upload: VerificationUpload, moderator: User) -> None:
    upload.state = VerificationUpload.State.APPROVED
    upload.decided_at = timezone.now()
    upload.save(update_fields=["state", "decided_at"])
    # ... record Verification record with moderator, reason, etc.

    # Arm destruction for +24h.
    destroy_verification_upload.apply_async(
        kwargs={"upload_id": str(upload.id)},
        countdown=24 * 3600,
    )
```

### The destruction task

```python
# productions/tasks.py
@shared_task(
    bind=True,
    max_retries=5,
    default_retry_delay=300,
    autoretry_for=(botocore.exceptions.ClientError,),
    retry_backoff=True,
)
def destroy_verification_upload(self, upload_id: str):
    upload = VerificationUpload.objects.select_for_update().get(id=upload_id)
    if upload.state == VerificationUpload.State.DESTROYED:
        return  # idempotent: already done

    s3 = boto3.client("s3", region_name=settings.AWS_S3_REGION_NAME)
    s3.delete_object(
        Bucket=settings.AWS_VERIFICATION_BUCKET,
        Key=upload.s3_key,
    )
    # Confirm the object is gone (S3 delete is eventually consistent on older buckets;
    # modern buckets are strongly consistent but cheap to double-check).
    try:
        s3.head_object(Bucket=settings.AWS_VERIFICATION_BUCKET, Key=upload.s3_key)
        raise RuntimeError(f"S3 object still exists after delete: {upload.s3_key}")
    except s3.exceptions.ClientError as e:
        if e.response["Error"]["Code"] != "404":
            raise

    upload.mark_destroyed()
```

Rejections destroy immediately, not on a timer:

```python
def reject_verification(upload: VerificationUpload, moderator: User, reason: str) -> None:
    upload.state = VerificationUpload.State.REJECTED
    upload.decided_at = timezone.now()
    upload.save(update_fields=["state", "decided_at"])
    # No delay — destroy now.
    destroy_verification_upload.delay(str(upload.id))
```

### Secondary: periodic sweep

The Celery delayed task can fail silently — broker loss, worker restart at exactly the wrong moment, retry exhaustion. A periodic sweep is the second line of defense:

```python
@shared_task
def sweep_overdue_verification_uploads():
    """Destroy any upload that's been in a terminal state for more than 36h."""
    overdue = timezone.now() - timedelta(hours=36)
    stale = VerificationUpload.objects.filter(
        state__in=[VerificationUpload.State.APPROVED, VerificationUpload.State.REJECTED],
        decided_at__lte=overdue,
    ).exclude(s3_key="")

    for upload in stale:
        logger.warning(
            "Sweep destroying overdue verification upload",
            extra={"upload_id": str(upload.id), "decided_at": upload.decided_at},
        )
        destroy_verification_upload.delay(str(upload.id))
```

Schedule via `CELERY_BEAT_SCHEDULE`:

```python
CELERY_BEAT_SCHEDULE = {
    "sweep-overdue-verification-uploads": {
        "task": "productions.tasks.sweep_overdue_verification_uploads",
        "schedule": crontab(minute=0, hour="*"),   # hourly
    },
}
```

### Tertiary: the S3 lifecycle rule

Already described in §2. A 7-day expiration on the bucket is the floor. If the app and Celery are both broken, the bucket itself does the right thing.

---

## 7. Monitoring and alerts

A failed destruction is a privacy incident. Treat it that way in the monitoring layer.

```python
# Wire to Sentry / Logfire / Prometheus
EXPECTED_DESTRUCTION_SLA_HOURS = 25   # 24h delay + 1h buffer

def upload_destruction_health():
    overdue = VerificationUpload.objects.filter(
        state=VerificationUpload.State.APPROVED,
        decided_at__lte=timezone.now() - timedelta(hours=EXPECTED_DESTRUCTION_SLA_HOURS),
    ).exclude(s3_key="").count()
    return {"overdue_count": overdue}
```

Page the team if `overdue_count > 0`. Not an email — a page. The longer an approved upload persists, the worse the violation.

Adjacent metrics worth tracking:

- Median time from approval → destruction (should be tight around 24h).
- Percentage of destructions triggered by the sweep rather than the scheduled task (sweep triggers are a leading indicator of Celery health issues).
- Count of moderator download URL issuances per upload (>1 is normal; >5 is suspicious).
- Bucket object count (should trend at roughly (pending + under_review + approved_within_24h)).

---

## 8. Testing the destruction guarantee

```python
@pytest.mark.django_db
class TestVerificationUploadLifecycle:
    @mock_aws  # moto
    def test_approval_destroys_after_delay(self, celery_eager):
        upload = VerificationUploadFactory(state=VerificationUpload.State.UPLOADED)
        # Put a dummy object in moto's S3.
        s3 = boto3.client("s3")
        s3.create_bucket(Bucket=settings.AWS_VERIFICATION_BUCKET)
        s3.put_object(Bucket=settings.AWS_VERIFICATION_BUCKET, Key=upload.s3_key, Body=b"pdf")

        approve_verification(upload, moderator=UserFactory())
        # With CELERY_TASK_ALWAYS_EAGER=True, the countdown still delays. Advance time.
        freezer.tick(timedelta(hours=25))
        run_due_tasks()

        upload.refresh_from_db()
        assert upload.state == VerificationUpload.State.DESTROYED
        assert upload.s3_key == ""
        assert upload.sha256  # hash persists

        # Object is actually gone from S3.
        with pytest.raises(s3.exceptions.ClientError):
            s3.head_object(Bucket=settings.AWS_VERIFICATION_BUCKET, Key=upload.s3_key)

    def test_rejection_destroys_immediately(self, celery_eager, s3_mocked):
        upload = VerificationUploadFactory(state=VerificationUpload.State.UPLOADED)
        reject_verification(upload, moderator=UserFactory(), reason="not matching")

        upload.refresh_from_db()
        assert upload.state == VerificationUpload.State.DESTROYED

    def test_sweep_catches_celery_failure(self):
        # Simulate an upload that was approved but whose scheduled task never ran.
        upload = VerificationUploadFactory(
            state=VerificationUpload.State.APPROVED,
            decided_at=timezone.now() - timedelta(hours=48),
            s3_key="verifications/abc/file.pdf",
        )
        sweep_overdue_verification_uploads()
        # The sweep enqueues destruction; with eager mode that destroys now.
        upload.refresh_from_db()
        assert upload.state == VerificationUpload.State.DESTROYED

    def test_destruction_is_idempotent(self, s3_mocked):
        upload = VerificationUploadFactory(state=VerificationUpload.State.DESTROYED, s3_key="")
        # Should not raise, should not flip any state back.
        destroy_verification_upload(str(upload.id))
        upload.refresh_from_db()
        assert upload.state == VerificationUpload.State.DESTROYED

    def test_moderator_url_respects_state(self):
        destroyed = VerificationUploadFactory(state=VerificationUpload.State.DESTROYED)
        with pytest.raises(ValidationError):
            issue_moderator_download_url(destroyed, moderator=UserFactory())
```

Use `moto` (`pip install moto[s3]`) to mock S3 in tests — real credentials and real buckets don't belong in CI. For time advancement, `freezegun` or `time-machine` both work with Celery's `apply_async(countdown=...)` if you also control the Celery clock.

---

## 9. Legal and subpoena posture

The hash-only audit artifact is the point: if compelled to produce "the file reviewer X uploaded", you can only produce the hash and the decision metadata. The file is not retained and not recoverable. Documenting this posture publicly is part of the product's trust story.

Two caveats worth raising with counsel:

1. **Retention laws.** Some jurisdictions have minimum retention requirements for certain record types. Booking confirmations are unlikely to trigger these for a review platform, but confirm.
2. **Preservation orders.** If served before destruction, a preservation order overrides the automated pipeline for the affected records. Build a manual freeze mechanism: a `preservation_hold` flag on `VerificationUpload` that short-circuits the destruction task and forces indefinite retention. The flag must be settable only by authorized staff.

```python
class VerificationUpload(models.Model):
    # ...
    preservation_hold = models.BooleanField(default=False)
    preservation_hold_reason = models.TextField(blank=True)

@shared_task
def destroy_verification_upload(self, upload_id: str):
    upload = VerificationUpload.objects.get(id=upload_id)
    if upload.preservation_hold:
        logger.warning("Upload under preservation hold; skipping destruction",
                       extra={"upload_id": str(upload.id)})
        return
    # ... destruction proceeds otherwise
```

---

## 10. Decision summary

- Use a dedicated bucket for verification uploads with encryption at rest (SSE-KMS) and block-all-public-access enforced at the account level.
- Uploads go directly to S3 via presigned POST with TTL, size, type, and encryption-header pinning.
- Compute SHA-256 server-side on upload confirmation. The hash is the permanent audit artifact.
- Moderator access is always via short-lived presigned GET URLs, logged both in the app and via CloudTrail.
- Destroy via three layers: Celery scheduled task (primary), Celery periodic sweep (secondary), S3 lifecycle rule (floor).
- Alert on any overdue destruction.
- Test destruction with moto; test sweep by forging stale records.
- Plan for preservation holds before you need one.

---

## Sources

- AWS S3 server-side encryption options: https://docs.aws.amazon.com/AmazonS3/latest/userguide/UsingServerSideEncryption.html
- AWS S3 presigned POST policy: https://docs.aws.amazon.com/AmazonS3/latest/userguide/PresignedUrlUploadObject.html
- AWS S3 lifecycle rules: https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lifecycle-mgmt.html
- boto3 `generate_presigned_post`: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/client/generate_presigned_post.html
- Celery task retry reference: https://docs.celeryq.dev/en/stable/userguide/tasks.html#retrying
- moto (AWS mock for tests): https://docs.getmoto.org/
- django-storages S3 backend: https://django-storages.readthedocs.io/en/latest/backends/amazon-S3.html

Last updated: 2026-04-14
