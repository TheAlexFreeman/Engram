---
source: agent-generated
type: knowledge
created: 2026-03-19
last_verified: 2026-03-20
trust: medium
related:
  - django-production-stack.md
  - django-gunicorn-uvicorn.md
  - django-security.md
  - django-react-drf.md
origin_session: unknown
---

# Django File Storage — django-storages, S3, Signed URLs, Direct Upload

Django's storage abstraction (`django.core.files.storage`) makes it possible to swap between local filesystem, S3, GCS, and Azure without changing model code. In production, the standard choice is S3 (or a compatible object store like Cloudflare R2 or MinIO).

---

## 1. Django's storage system

### The STORAGES setting (Django 4.2+)

```python
# settings.py
STORAGES = {
    "default": {                    # for FileField / ImageField uploads
        "BACKEND": "storages.backends.s3.S3Storage",
    },
    "staticfiles": {                # for collectstatic
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}
```

Django 4.2 deprecated `DEFAULT_FILE_STORAGE` and `STATICFILES_STORAGE` in favor of the `STORAGES` dict. The old strings still work but emit deprecation warnings.

### File storage in models

```python
class UserProfile(models.Model):
    avatar = models.ImageField(upload_to="avatars/")        # path within the storage backend
    resume = models.FileField(upload_to="resumes/%Y/%m/")  # strftime-format paths
```

`upload_to` works the same regardless of storage backend — it becomes the key prefix in S3 or the subdirectory on the local filesystem.

---

## 2. django-storages with S3

```bash
pip install django-storages[s3]   # installs boto3 automatically
```

### Settings

```python
# settings.py
AWS_STORAGE_BUCKET_NAME = env("AWS_STORAGE_BUCKET_NAME")
AWS_S3_REGION_NAME = env("AWS_S3_REGION_NAME", default="us-east-1")
AWS_S3_SIGNATURE_VERSION = "s3v4"

# For CDN / CloudFront distribution:
AWS_S3_CUSTOM_DOMAIN = env("AWS_CLOUDFRONT_DOMAIN", default=None)
# e.g. "d1234567890.cloudfront.net"

# Access control
AWS_DEFAULT_ACL = None      # bucket-owner-full-control; don't set ACL if bucket has ACLs disabled
AWS_S3_OBJECT_PARAMETERS = {
    "CacheControl": "max-age=86400",  # 1-day browser cache for uploaded files
}

# Credentials — in production, prefer IAM role (no keys needed)
# In local dev, use:
AWS_ACCESS_KEY_ID = env("AWS_ACCESS_KEY_ID", default=None)
AWS_SECRET_ACCESS_KEY = env("AWS_SECRET_ACCESS_KEY", default=None)

STORAGES = {
    "default": {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "bucket_name": AWS_STORAGE_BUCKET_NAME,
            "region_name": AWS_S3_REGION_NAME,
            "custom_domain": AWS_S3_CUSTOM_DOMAIN,
            "default_acl": AWS_DEFAULT_ACL,
            "object_parameters": AWS_S3_OBJECT_PARAMETERS,
        },
    },
}
```

### IAM permissions (least-privilege)

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject",
        "s3:DeleteObject",
        "s3:PutObjectAcl"
      ],
      "Resource": "arn:aws:s3:::my-bucket/*"
    },
    {
      "Effect": "Allow",
      "Action": "s3:ListBucket",
      "Resource": "arn:aws:s3:::my-bucket"
    }
  ]
}
```

In production, attach this policy to the EC2 instance role or ECS task role — no explicit `AWS_ACCESS_KEY_ID` needed.

---

## 3. Signed URLs — time-limited private access

By default, `django-storages`'s `S3Storage` stores files publicly if `AWS_DEFAULT_ACL = "public-read"`. For private files (user documents, internal assets), files should have no public ACL and access should be via signed URLs.

### Generating signed URLs

```python
import boto3

def generate_signed_url(s3_key: str, expiration_seconds: int = 3600) -> str:
    s3 = boto3.client(
        "s3",
        region_name=settings.AWS_S3_REGION_NAME,
    )
    return s3.generate_presigned_url(
        "get_object",
        Params={
            "Bucket": settings.AWS_STORAGE_BUCKET_NAME,
            "Key": s3_key,
        },
        ExpiresIn=expiration_seconds,
    )
```

### DRF endpoint for signed URLs

```python
class ResumeSignedUrlView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        profile = get_object_or_404(UserProfile, pk=pk, user=request.user)
        if not profile.resume:
            return Response({"detail": "No resume uploaded."}, status=404)
        
        # profile.resume.name is the S3 key
        url = generate_signed_url(profile.resume.name, expiration_seconds=900)
        return Response({"url": url, "expires_in": 900})
```

### Getting the S3 key from a FileField

```python
# profile.resume is a FieldFile; .name is the storage key (not the URL)
s3_key = profile.resume.name  # e.g. "resumes/2026/03/john_doe_resume.pdf"

# profile.resume.url calls storage.url() which may be public or signed
# depending on how S3Storage is configured
public_url = profile.resume.url
```

Configure `S3Storage` to return signed URLs automatically via `querystring_auth=True`:

```python
STORAGES = {
    "default": {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "querystring_auth": True,               # all .url() calls return signed URLs
            "querystring_expire": 3600,             # 1-hour signatures
        },
    },
}
```

With `querystring_auth=True`, every time a template or serializer calls `file_field.url`, it generates a fresh signed URL — convenient but adds latency since it calls AWS on every access. Cache the URL if rendering it frequently.

---

## 4. Direct upload to S3 (presigned POST)

For large files, routing the upload through Django wastes bandwidth and ties up a gunicorn worker. The preferred pattern: the frontend uploads **directly to S3** and informs Django of the completed upload.

### Flow

```
Client → POST /api/upload-url/ → Django → S3 presigned POST fields
Client → POST directly to S3 (using presigned fields)
Client → POST /api/confirm-upload/ { s3_key } → Django validates and saves
```

### Presigned POST endpoint

```python
import boto3
from botocore.config import Config

class PresignedUploadUrlView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        filename = request.data.get("filename", "")
        content_type = request.data.get("content_type", "application/octet-stream")
        
        # Validate file type early
        allowed_types = {"image/jpeg", "image/png", "application/pdf"}
        if content_type not in allowed_types:
            return Response({"detail": "File type not allowed."}, status=400)
        
        s3_key = f"uploads/{request.user.pk}/{uuid.uuid4()}/{filename}"
        
        s3 = boto3.client("s3", region_name=settings.AWS_S3_REGION_NAME)
        presigned = s3.generate_presigned_post(
            Bucket=settings.AWS_STORAGE_BUCKET_NAME,
            Key=s3_key,
            Fields={
                "Content-Type": content_type,
                "x-amz-meta-uploaded-by": str(request.user.pk),
            },
            Conditions=[
                {"Content-Type": content_type},
                ["content-length-range", 1, 10 * 1024 * 1024],  # 1B – 10MB
            ],
            ExpiresIn=600,  # 10 minutes to complete the upload
        )
        
        return Response({
            "url": presigned["url"],
            "fields": presigned["fields"],
            "key": s3_key,
        })
```

Frontend uses:
```javascript
const formData = new FormData();
Object.entries(presigned.fields).forEach(([k, v]) => formData.append(k, v));
formData.append("file", file);   // must be last
await fetch(presigned.url, { method: "POST", body: formData });
// Then notify Django:
await api.post("/api/confirm-upload/", { s3_key: presigned.key });
```

### Confirm upload endpoint

```python
class ConfirmUploadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        s3_key = request.data.get("s3_key", "")
        
        # Validate the key belongs to this user's upload namespace
        if not s3_key.startswith(f"uploads/{request.user.pk}/"):
            return Response({"detail": "Invalid key."}, status=400)
        
        # Verify the object exists in S3 before saving the reference
        s3 = boto3.client("s3", region_name=settings.AWS_S3_REGION_NAME)
        try:
            s3.head_object(Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=s3_key)
        except s3.exceptions.NoSuchKey:
            return Response({"detail": "Upload not found."}, status=404)
        
        # Save the reference to the model
        request.user.profile.resume.name = s3_key
        request.user.profile.save(update_fields=["resume"])
        
        return Response({"detail": "Upload confirmed."})
```

---

## 5. User upload handling and validation

### File type validation (magic bytes, not just extension)

Extensions can be spoofed. Always validate the file's actual content:

```bash
pip install python-magic       # wraps libmagic
# or on systems without libmagic:
pip install python-magic-bin   # pure Python fallback
```

```python
import magic

def validate_file_type(file, allowed_types: set[str]) -> None:
    """Validate file MIME type by reading magic bytes, not trusting the extension."""
    # Read the first 2048 bytes for magic byte detection
    header = file.read(2048)
    file.seek(0)
    
    mime = magic.from_buffer(header, mime=True)
    if mime not in allowed_types:
        raise ValidationError(f"File type '{mime}' is not allowed.")

class ResumeSerializer(serializers.ModelSerializer):
    def validate_resume(self, value):
        validate_file_type(value, {"application/pdf"})
        
        max_size = 10 * 1024 * 1024  # 10MB
        if value.size > max_size:
            raise ValidationError("File size cannot exceed 10MB.")
        
        return value
```

### Size limits in Django settings

```python
# Maximum in-memory upload size before writing to disk (default 2.5MB)
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024  # 5MB

# Maximum total upload size for any single request
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10MB
```

### Cleaning up orphaned files with django-cleanup

```bash
pip install django-cleanup
```

```python
INSTALLED_APPS = [
    "django_cleanup.apps.CleanupConfig",  # must come after apps that define FileField models
    ...
]
```

`django-cleanup` automatically calls `storage.delete(name)` whenever a `FileField` value is replaced or a model instance is deleted. Without it, old files accumulate in S3 indefinitely.

---

## 6. Local development with FileSystemStorage

Avoid hitting S3 in local development:

```python
# settings/development.py
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
        "OPTIONS": {
            "location": BASE_DIR / "media",
            "base_url": "/media/",
        },
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
```

```python
# urls.py (development only)
from django.conf import settings
from django.conf.urls.static import static

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
```

### Environment-gated storage backend

Use a single settings file with conditional backend selection:

```python
if env.bool("USE_S3", default=False):
    STORAGES = {
        "default": {"BACKEND": "storages.backends.s3.S3Storage", "OPTIONS": {...}},
        ...
    }
else:
    STORAGES = {
        "default": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
            "OPTIONS": {"location": BASE_DIR / "media", "base_url": "/media/"},
        },
        ...
    }
```

---

## 7. GCS alternative (django-storages[google])

```bash
pip install django-storages[google]
```

```python
STORAGES = {
    "default": {
        "BACKEND": "storages.backends.gcloud.GoogleCloudStorage",
        "OPTIONS": {
            "bucket_name": env("GCS_BUCKET_NAME"),
            "project_id": env("GCS_PROJECT_ID"),
            # Service account key (dev/CI only — prefer Workload Identity in production):
            "credentials": env.path("GOOGLE_APPLICATION_CREDENTIALS", default=None),
            "default_acl": None,  # use uniform bucket-level IAM, not per-object ACLs
        },
    },
}
```

**Workload Identity** (GKE production): no service account key file needed. The pod's service account is bound to a GCS IAM role. `google-auth` discovers credentials automatically via the metadata server. `django-storages` calls `google.auth.default()` which finds these credentials transparently.

---

## 8. Cloudflare R2 (S3-compatible, no egress fees)

R2 is increasingly popular as an S3 replacement — it's S3-compatible (same boto3 API) with no egress fees:

```python
STORAGES = {
    "default": {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "bucket_name": env("R2_BUCKET_NAME"),
            "access_key": env("R2_ACCESS_KEY_ID"),
            "secret_key": env("R2_SECRET_ACCESS_KEY"),
            "endpoint_url": f"https://{env('R2_ACCOUNT_ID')}.r2.cloudflarestorage.com",
            "region_name": "auto",   # R2 uses "auto" as the region
            "querystring_auth": True,
        },
    },
}
```

All other patterns (signed URLs, presigned POST, `django-cleanup`) work identically with R2 since `django-storages` uses boto3's S3 API throughout.
