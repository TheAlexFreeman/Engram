---
created: '2026-04-22'
origin_session: memory/activity/2026/04/22/chat-001
source: external-research
trust: low
---

# Django Settings for Custom Domains on Render

## Required Settings

When serving a Django app from a custom subdomain (e.g., `demo.example.com`) on Render, these settings must be updated in `settings.py` (or via environment variables):

### ALLOWED_HOSTS

```python
ALLOWED_HOSTS = [
    'demo.example.com',         # your custom subdomain
    'myapp.onrender.com',       # Render's default domain (keep for fallback)
    'localhost',                 # local dev
]
# Or use env var:
# ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', 'localhost').split(',')
```

If `ALLOWED_HOSTS` doesn't include the incoming `Host` header, Django returns a **400 Bad Request** — no error page, just a blank 400.

### CSRF_TRUSTED_ORIGINS (Django 4.0+)

```python
CSRF_TRUSTED_ORIGINS = [
    'https://demo.example.com',
    'https://myapp.onrender.com',
]
```

**Key change in Django 4.0+:** entries must include the scheme (`https://`). Without it, POST requests (login, admin, forms) fail with "CSRF verification failed. Origin checking failed."

### CSRF_COOKIE_DOMAIN (optional, for cross-subdomain cookies)

Only needed if you want CSRF cookies shared across subdomains:

```python
CSRF_COOKIE_DOMAIN = '.example.com'
```

Most single-subdomain setups do **not** need this.

## Security-Related Settings for Production

```python
SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# HSTS (optional, be careful — hard to undo)
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
```

**SECURE_PROXY_SSL_HEADER** is critical on Render. Render terminates TLS at its load balancer and forwards requests to your app over HTTP internally. Without this header, Django thinks all requests are HTTP and `SECURE_SSL_REDIRECT` causes an infinite redirect loop.

## Common Pitfalls

1. **Infinite redirect loop:** Forgot `SECURE_PROXY_SSL_HEADER` while `SECURE_SSL_REDIRECT = True`.
2. **CSRF failures on admin/login:** Forgot to add `https://` prefix in `CSRF_TRUSTED_ORIGINS`.
3. **400 Bad Request with no error details:** Custom domain not in `ALLOWED_HOSTS`.
4. **Works on Render default domain but not custom domain:** `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS` only include the `.onrender.com` hostname.

## Official Docs

- Django Settings Reference: https://docs.djangoproject.com/en/6.0/ref/settings/
- CSRF Protection: https://docs.djangoproject.com/en/5.0/ref/csrf/
- Render Django Deploy Guide: https://render.com/docs/deploy-django