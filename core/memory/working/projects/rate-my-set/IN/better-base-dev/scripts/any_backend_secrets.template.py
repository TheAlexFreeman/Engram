from __future__ import annotations

ENV_CELERY_FLOWER_PASSWORD = (
    'GENERATE | python -c "import secrets; print(secrets.token_urlsafe(40)[:40])"'
)
# NOTE: Make sure to end with a trailing slash. I.E. something like `secret-admin-url-23423098/`.
ENV_DJANGO_ADMIN_URL = "FILL_IN | {{django_admin_url}}"
ENV_DJANGO_AWS_ACCESS_KEY_ID = "FILL_IN | {{cloudflare_access_key_id}}"
ENV_DJANGO_AWS_S3_CUSTOM_DOMAIN = (
    "FILL_IN | {{cloudflare_account_id}}.r2.cloudflarestorage.com"
)
ENV_DJANGO_AWS_S3_ENDPOINT_URL = (
    "FILL_IN | https://{{cloudflare_account_id}}.r2.cloudflarestorage.com"
)
ENV_DJANGO_AWS_S3_PRIVATE_CUSTOM_DOMAIN = (
    "FILL_IN | {{cloudflare_account_id}}.r2.cloudflarestorage.com"
)
ENV_DJANGO_AWS_S3_PRIVATE_ENDPOINT_URL = (
    "FILL_IN | https://{{cloudflare_account_id}}.r2.cloudflarestorage.com"
)
ENV_DJANGO_AWS_S3_PUBLIC_ENDPOINT_URL = (
    "FILL_IN | https://{{cloudflare_account_id}}.r2.cloudflarestorage.com"
)
ENV_DJANGO_AWS_SECRET_ACCESS_KEY = "FILL_IN | {{cloudflare_secret_access_key}}"
ENV_DJANGO_SECRET_KEY = (
    'GENERATE | python -c "import secrets; print(secrets.token_urlsafe(50)[:50])"'
)
ENV_MAILGUN_API_KEY = "FILL_IN | {{mailgun_api_key}}"
ENV_MAILGUN_WEBHOOK_SIGNING_KEY = "FILL_IN | {{mailgun_webhook_signing_key}}"
ENV_SENTRY_DSN = "FILL_IN | {{sentry_dsn}}"
