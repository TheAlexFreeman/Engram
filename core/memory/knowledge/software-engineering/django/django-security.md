---
source: agent-generated
type: knowledge
created: 2026-03-19
last_verified: 2026-03-20
trust: medium
related:
  - django-react-drf.md
  - django-production-stack.md
  - django-6.0-whats-new.md
  - django-observability-structlog-sentry.md
  - ../web-fundamentals/cors-in-depth.md
  - django-database-pooling.md
  - drf-testing-pytest-django-perf-rec.md
  - ../web-fundamentals/http-protocol-reference.md
  - django-migrations-advanced.md
origin_session: unknown
---

# Django Security — Auth, HTTPS, Rate Limiting, Secrets, CSP

Security in a Django/DRF application spans authentication, transport security, input handling, rate limiting, and secrets management. This file covers the production-relevant depth that `django-react-drf.md` and `django-production-stack.md` touch only briefly.

---

## 1. Authentication backends

### The auth backend contract

Django resolves `authenticate()` by calling each backend in `AUTHENTICATION_BACKENDS` in order, stopping at the first that returns a user:

```python
# settings.py
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]
```

A custom backend must implement two methods:

```python
class EmailOrUsernameBackend:
    def authenticate(self, request, username=None, password=None, **kwargs):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        try:
            # Allow login by email or username
            user = User.objects.get(email__iexact=username)
        except User.DoesNotExist:
            try:
                user = User.objects.get(username=username)
            except User.DoesNotExist:
                return None
        return user if user.check_password(password) else None

    def get_user(self, user_id):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
```

`AUTHENTICATION_BACKENDS` short-circuits — if `ModelBackend` is last and a custom backend raises `PermissionDenied`, the default backend is skipped entirely. Use `PermissionDenied` only when you want to hard-block a user (e.g. disabled account overriding all other backends).

### Object-level permissions

`ModelBackend` only handles model-level permissions. For row-level or object-level permissions implement `has_perm(user_obj, perm, obj=None)`:

```python
class ProjectMemberBackend:
    def has_perm(self, user_obj, perm, obj=None):
        if perm == "projects.change_project" and obj is not None:
            return obj.members.filter(pk=user_obj.pk).exists()
        return False

    def get_user(self, user_id):
        ...
```

In DRF, call `request.user.has_perm("projects.change_project", project_instance)` in permission classes.

---

## 2. django-allauth

### Setup — headless mode for DRF/SPA

```bash
pip install django-allauth[socialaccount]         # social providers
pip install django-allauth[headless]              # DRF/SPA REST API mode
```

```python
# settings.py
INSTALLED_APPS = [
    "django.contrib.sites",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
    "allauth.socialaccount.providers.github",
    "allauth.headless",  # REST API surface
]

SITE_ID = 1
HEADLESS_ONLY = True  # disables all template-based views
HEADLESS_FRONTEND_URLS = {
    "account_confirm_email": "/auth/verify-email/{key}",
    "account_reset_password_from_key": "/auth/reset-password/{uid}/{token}",
}
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_USERNAME_REQUIRED = False
ACCOUNT_AUTHENTICATION_METHOD = "email"
ACCOUNT_EMAIL_VERIFICATION = "mandatory"  # or "optional" / "none"
```

```python
# urls.py
from allauth.headless.urls import headless_urlpatterns

urlpatterns = [
    path("api/auth/", include(headless_urlpatterns("app"))),
    ...
]
```

This exposes JSON endpoints at `/api/auth/signup`, `/api/auth/login`, `/api/auth/logout`, `/api/auth/email/verify`, etc.

### Social auth providers

```python
# settings.py (for Google)
SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "APP": {
            "client_id": env("GOOGLE_CLIENT_ID"),
            "secret": env("GOOGLE_CLIENT_SECRET"),
        },
        "SCOPE": ["profile", "email"],
        "AUTH_PARAMS": {"access_type": "online"},
    },
}
```

The headless flow: frontend redirects to `/api/auth/provider/redirect/` → Google OAuth → allauth exchanges code → returns session or token. For token-based (SPA): configure `HEADLESS_TOKEN_STRATEGY = "allauth.headless.tokens.sessions.SessionTokenStrategy"` or use a JWT strategy.

### Custom account adapter

```python
# adapters.py
from allauth.account.adapter import DefaultAccountAdapter

class CustomAccountAdapter(DefaultAccountAdapter):
    def is_open_for_signup(self, request):
        # Return False to disable public signup (invite-only)
        return getattr(settings, "ACCOUNT_ALLOW_REGISTRATION", True)

    def save_user(self, request, user, form, commit=True):
        user = super().save_user(request, user, form, commit=False)
        user.company = form.cleaned_data.get("company", "")
        if commit:
            user.save()
        return user

# settings.py
ACCOUNT_ADAPTER = "myapp.adapters.CustomAccountAdapter"
```

---

## 3. Password security

### Password hashers

Django uses PBKDF2 (SHA-256) by default. Switch to Argon2 for stronger hashing (memory-hard, recommended by OWASP):

```bash
pip install argon2-cffi
```

```python
# settings.py
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",  # new passwords
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",  # migrate old ones on next login
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
]
```

Existing passwords stay hashed with their original algorithm. On the next successful login, Django **automatically upgrades** the hash to the first hasher (Argon2), requiring no bulk migration.

### Argon2 tuning (Django 5.1+)

```python
PASSWORD_HASHERS = [
    {
        "NAME": "django.contrib.auth.hashers.Argon2PasswordHasher",
        "TIME_COST": 2,
        "MEMORY_COST": 65536,  # 64 MB
        "PARALLELISM": 2,
    },
]
```

### Built-in password validators

```python
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
     "OPTIONS": {"min_length": 12}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
```

In DRF serializers, call validators explicitly:

```python
from django.contrib.auth.password_validation import validate_password

class PasswordChangeSerializer(serializers.Serializer):
    password = serializers.CharField(write_only=True)

    def validate_password(self, value):
        validate_password(value, self.context["request"].user)
        return value
```

---

## 4. HTTPS and security headers in production

### Required settings

```python
# settings/production.py
SECURE_SSL_REDIRECT = True          # redirect all HTTP → HTTPS
SECURE_HSTS_SECONDS = 31536000      # 1 year — tell browsers to always use HTTPS
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True          # submit to browser preload lists
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")  # trust nginx's header

SESSION_COOKIE_SECURE = True        # session cookie only over HTTPS
CSRF_COOKIE_SECURE = True           # CSRF cookie only over HTTPS
SESSION_COOKIE_HTTPONLY = True      # no JS access to session cookie
CSRF_COOKIE_HTTPONLY = False        # must be False for SPA to read and send the token
CSRF_COOKIE_SAMESITE = "Lax"        # or "Strict"; "None" only if cross-origin + Secure
SESSION_COOKIE_SAMESITE = "Lax"

SECURE_CONTENT_TYPE_NOSNIFF = True  # X-Content-Type-Options: nosniff
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"           # clickjacking protection
```

### Deploy check

```bash
python manage.py check --deploy
```

This runs Django's system checks for production-relevant settings. Fix all warnings before going live. Pipe into CI to catch regressions:

```yaml
# .github/workflows/ci.yml
- run: python manage.py check --deploy --settings=config.settings.production
  env:
    DJANGO_SECRET_KEY: ci-placeholder-key
    DATABASE_URL: sqlite:///ci.db
```

### Certificate handling

Django itself doesn't handle TLS — that's nginx's job. Ensure nginx terminates SSL and passes `X-Forwarded-Proto: https` so `SECURE_PROXY_SSL_HEADER` works.

---

## 5. Rate limiting

### django-ratelimit

```bash
pip install django-ratelimit
```

View-level decorator:

```python
from django_ratelimit.decorators import ratelimit

@ratelimit(key="ip", rate="5/m", method="POST", block=True)
def login_view(request):
    ...
```

DRF — use as method decorator inside viewsets or APIViews:

```python
from django_ratelimit.decorators import ratelimit
from django.utils.decorators import method_decorator

class LoginView(APIView):
    @method_decorator(ratelimit(key="ip", rate="10/m", block=True))
    def post(self, request):
        ...
```

Key types:
- `"ip"` — client IP (use `RATELIMIT_IP_ALGORITHM` to choose IPv4 vs. /64 prefix for IPv6)
- `"user"` — `request.user.pk` (authenticated users only)
- `"user_or_ip"` — authenticated users get their user key, anonymous users get IP
- `"header:X-Api-Key"` — arbitrary header
- A callable `lambda request: request.user.pk` for custom keys

Backends: default is Django's cache. Set `CACHES["ratelimit"]` to use a dedicated Redis cache for ratelimit state separate from application cache.

### nginx-level rate limiting

Nginx rate limiting happens before Django even receives the request — preferred for hard DoS mitigation:

```nginx
# Rate limit: 10 requests/second per IP, burst of 20
limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;

server {
    location /api/ {
        limit_req zone=api burst=20 nodelay;
        limit_req_status 429;
        proxy_pass http://django;
    }
}
```

Use both layers: nginx for coarse DoS protection, `django-ratelimit` for fine-grained application-level limits (per user, per endpoint).

### Rate limiting Celery task submission

Celery has built-in per-worker rate limits, not per-user. For user-facing task submission, apply rate limits at the view layer (before calling `.delay()`) using `django-ratelimit`. The view acts as the submission gate:

```python
@ratelimit(key="user", rate="10/m", block=True)
def submit_report(request):
    generate_report.delay(request.user.pk, request.data["params"])
    return Response({"status": "queued"})
```

Celery's `rate_limit` task attribute (`@shared_task(rate_limit="100/m")`) limits how fast workers *consume* tasks, not how fast users *submit* them. Combine both when needed.

---

## 6. Secrets management

### django-environ (recommended baseline)

```bash
pip install django-environ
```

```python
# settings.py
import environ

env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, []),
)
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("SECRET_KEY")
DEBUG = env("DEBUG")
DATABASE_URL = env.db()            # parses DATABASE_URL into DATABASES dict
CACHE_URL = env.cache()            # parses CACHE_URL into CACHES dict
EMAIL_CONFIG = env.email()         # parses EMAIL_URL
```

`.env` file (never committed):
```
SECRET_KEY=your-256-bit-random-key
DATABASE_URL=postgres://user:pass@localhost:5432/mydb
CACHE_URL=redis://localhost:6379/1
```

### Generating a strong SECRET_KEY

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

### AWS Secrets Manager integration

For production where environment variables alone aren't enough:

```python
# settings/production.py
import boto3, json

def get_secret(secret_arn: str) -> dict:
    client = boto3.client("secretsmanager")
    return json.loads(client.get_secret_value(SecretId=secret_arn)["SecretString"])

_secrets = get_secret(env("SECRETS_ARN"))
SECRET_KEY = _secrets["SECRET_KEY"]
DATABASES = {"default": dj_database_url.parse(_secrets["DATABASE_URL"])}
```

Cache the result at process startup — don't call Secrets Manager on every request.

### Rotating secrets without downtime

Strategy for `SECRET_KEY` rotation:
1. Django supports `SECRET_KEY_FALLBACKS` (Django 4.1+) — old keys for reading, new key for writing:
   ```python
   SECRET_KEY = env("SECRET_KEY_NEW")
   SECRET_KEY_FALLBACKS = [env("SECRET_KEY_OLD")]
   ```
2. Deploy with both keys — existing sessions/tokens remain valid.
3. After all old sessions expire (or are invalidated), remove `SECRET_KEY_FALLBACKS`.

For database credentials: use pgBouncer or a connection proxy that supports credential rotation without connection drops.

---

## 7. Content Security Policy

### Django 6.0 built-in CSP

Django 6.0 added `django.middleware.csp.CSPMiddleware` — the first built-in CSP. Add to middleware and configure in settings:

```python
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.csp.CSPMiddleware",  # add after SecurityMiddleware
    ...
]

# settings.py
CONTENT_SECURITY_POLICY = {
    "EXCLUDE_URL_PREFIXES": ["/admin/"],  # skip CSP for Django admin (inline scripts)
    "DIRECTIVES": {
        "default-src": ["'self'"],
        "script-src": ["'self'", "cdn.jsdelivr.net"],
        "style-src": ["'self'", "'unsafe-inline'"],  # Chakra UI inline styles
        "img-src": ["'self'", "data:", "https:"],
        "font-src": ["'self'"],
        "connect-src": ["'self'", "api.sentry.io"],
        "frame-ancestors": ["'none'"],
        "base-uri": ["'self'"],
        "form-action": ["'self'"],
    },
}
```

### Nonce-based CSP (for inline scripts)

Nonces eliminate `'unsafe-inline'` while still allowing specific inline scripts:

```python
# CSP config
"script-src": ["'self'", "'nonce-{nonce}'"],  # Django auto-substitutes

# In template
<script nonce="{{ request.csp_nonce }}">...inline script...</script>
```

Django 6.0's CSP middleware generates a cryptographically random nonce per request, injects it into the CSP header, and exposes it as `request.csp_nonce`.

### Report-only mode (deploy safely)

Before enforcing CSP, observe violations without blocking:

```python
CONTENT_SECURITY_POLICY_REPORT_ONLY = {
    "DIRECTIVES": {
        "default-src": ["'self'"],
        "report-uri": ["/csp-report/"],
    },
}
```

`report-uri` points to a Django view or a third-party service (Sentry handles CSP reports natively). Monitor violation reports, then switch from `REPORT_ONLY` to enforcing once clean.

---

## 8. SQL injection surface

### ORM safety

Django's ORM is safe by default — all QuerySet operations use parameterized queries:

```python
# Safe — Django parameterizes "username"
User.objects.filter(username=username)  # → WHERE username = %s
```

### Dangerous patterns to avoid

```python
# UNSAFE — never interpolate user input into raw SQL
User.objects.raw(f"SELECT * FROM auth_user WHERE username = '{username}'")

# SAFE — always use parameterized raw queries
User.objects.raw("SELECT * FROM auth_user WHERE username = %s", [username])

# UNSAFE — .extra() is deprecated and risky
User.objects.extra(where=[f"username = '{username}'"])

# SAFE — use RawSQL carefully with params
from django.db.models.expressions import RawSQL
qs.annotate(score=RawSQL("custom_score(%s)", [user_id]))
```

`extra()` is deprecated since Django 3.2 and should be replaced with `annotate()` + `RawSQL`, `FilteredRelation`, or proper subqueries.

### Template XSS

Django templates auto-escape HTML by default. The risk surfaces with:

```html
<!-- UNSAFE — disables escaping -->
{{ user_content|safe }}
{% autoescape off %}{{ user_content }}{% endautoescape %}

<!-- UNSAFE in DRF response — returning unserialized HTML as JSON string and then
     rendering it with dangerouslySetInnerHTML in React -->
```

In DRF, return structured data (not HTML strings) and render safely on the frontend.

---

## Security checklist summary

| Category | Key setting / tool |
|---|---|
| HTTPS | `SECURE_SSL_REDIRECT`, `SECURE_HSTS_*`, `SECURE_PROXY_SSL_HEADER` |
| Cookies | `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `*_SAMESITE` |
| Headers | `SECURE_CONTENT_TYPE_NOSNIFF`, `X_FRAME_OPTIONS`, CSP |
| Auth | Custom backends, `django-allauth` headless, `AUTHENTICATION_BACKENDS` |
| Passwords | Argon2 hasher, `AUTH_PASSWORD_VALIDATORS`, `SECRET_KEY_FALLBACKS` |
| Rate limiting | `django-ratelimit` per-view + nginx `limit_req_zone` |
| Secrets | `django-environ`, AWS Secrets Manager, `SECRET_KEY_FALLBACKS` |
| SQL | ORM parameterized queries, no `extra()`, no f-string interpolation |
| Deploy | `manage.py check --deploy` in CI |
