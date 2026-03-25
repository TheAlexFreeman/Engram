---
origin_session: unknown
source: agent-generated
type: knowledge
created: 2026-03-19
last_verified: 2026-03-20
trust: medium
related:
  - docker-compose-local-dev.md
  - docker-production-config.md
  - ../react/vite-react-build.md
  - ../django/django-gunicorn-uvicorn.md
  - ../web-fundamentals/http-protocol-reference.md
  - ../web-fundamentals/dns-tls-and-networking.md
---

# Nginx as the Composition Layer: Django + React

In this stack, nginx sits in front of everything: it terminates TLS, serves the React SPA's static build, and reverse-proxies API and admin requests to gunicorn. This keeps gunicorn focused purely on Python request handling and lets nginx do what it's good at — static files, caching headers, compression, rate limiting, and WebSocket upgrades.

---

## 1. nginx in Docker Compose

```yaml
# docker-compose.yml
services:
  nginx:
    image: nginx:1.27-alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      # nginx configuration
      - ./nginx/conf.d:/etc/nginx/conf.d:ro
      # React production build (from a named volume populated by the react build stage,
      # or a bind mount to the dist/ output)
      - react_build:/usr/share/nginx/html:ro
      # TLS certificates (certbot populates this)
      - ./nginx/certs:/etc/nginx/certs:ro
      - ./nginx/dhparam.pem:/etc/nginx/dhparam.pem:ro
    depends_on:
      web:
        condition: service_healthy
    restart: unless-stopped

volumes:
  react_build:
```

---

## 2. Core nginx.conf structure

A clean separation: `/api/` and `/admin/` proxy to Django; `/` serves the React SPA. Order matters — more specific locations must come before less specific ones.

```nginx
# nginx/conf.d/default.conf

upstream django {
    server web:8000;
    # keepalive: reuse connections to gunicorn (reduces TCP overhead)
    keepalive 32;
}

server {
    listen 80;
    server_name example.com www.example.com;

    # Redirect HTTP to HTTPS (production only)
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name example.com www.example.com;

    # TLS config (see section 6)
    ssl_certificate     /etc/nginx/certs/fullchain.pem;
    ssl_certificate_key /etc/nginx/certs/privkey.pem;
    ssl_dhparam         /etc/nginx/dhparam.pem;
    ssl_protocols       TLSv1.2 TLSv1.3;
    ssl_ciphers         ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;
    ssl_session_cache   shared:SSL:10m;
    ssl_session_timeout 1d;

    # Security headers
    add_header Strict-Transport-Security "max-age=63072000; includeSubDomains; preload" always;
    add_header X-Frame-Options SAMEORIGIN always;
    add_header X-Content-Type-Options nosniff always;
    add_header Referrer-Policy strict-origin-when-cross-origin always;

    # Gzip (see section 7)
    gzip on;
    gzip_types text/plain text/css application/javascript application/json image/svg+xml;
    gzip_min_length 1024;
    gzip_comp_level 5;
    gzip_vary on;

    # Rate limiting zones (defined at http{} level; see section 8)
    # limit_req zone=login burst=5 nodelay;

    # --- Django API ---
    location /api/ {
        proxy_pass         http://django;
        proxy_http_version 1.1;
        proxy_set_header   Connection "";  # enable keepalive to upstream
        proxy_set_header   Host              $host;
        proxy_set_header   X-Real-IP         $remote_addr;
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;  # increase for long-running views
        proxy_send_timeout 120s;

        # Forward CSRF cookie
        proxy_cookie_path / "/; SameSite=Strict; Secure; HttpOnly";
    }

    # --- Django admin ---
    location /admin/ {
        proxy_pass         http://django;
        proxy_http_version 1.1;
        proxy_set_header   Connection "";
        proxy_set_header   Host              $host;
        proxy_set_header   X-Real-IP         $remote_addr;
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
    }

    # --- Django static files (for admin, DRF browsable API) ---
    location /static/ {
        alias /usr/share/nginx/django-static/;
        expires 30d;
        add_header Cache-Control "public, max-age=2592000";
    }

    # --- React SPA ---
    root /usr/share/nginx/html;
    index index.html;

    # Fingerprinted JS/CSS/image assets — immutable caching
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot|webp|avif)$ {
        expires 1y;
        add_header Cache-Control "public, max-age=31536000, immutable";
        try_files $uri =404;
    }

    # index.html — no cache (must always be fresh for hashed asset names to update)
    location = /index.html {
        add_header Cache-Control "no-cache, no-store, must-revalidate";
        add_header Pragma no-cache;
        add_header Expires 0;
    }

    # SPA fallback: all other paths serve index.html (client-side routing)
    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

---

## 3. Reverse proxy to gunicorn — details

### Required headers

```nginx
proxy_set_header Host              $host;
proxy_set_header X-Real-IP         $remote_addr;
proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
proxy_set_header X-Forwarded-Proto $scheme;
```

Django must be configured to trust these headers:

```python
# settings.py
USE_X_FORWARDED_HOST = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Trust only the nginx container IP (or the entire subnet)
ALLOWED_HOSTS = ["example.com", "www.example.com"]
```

### Keepalive to upstream

```nginx
upstream django {
    server web:8000;
    keepalive 32;  # pool of 32 keepalive connections
}

# In the location block:
proxy_http_version 1.1;
proxy_set_header Connection "";  # clear Connection: close header (required for keepalive)
```

### Timeouts

```nginx
proxy_connect_timeout 10s;  # time to connect to upstream
proxy_send_timeout    120s; # time to send request to upstream
proxy_read_timeout    120s; # time waiting for upstream response
```

Increase `proxy_read_timeout` for long-polling endpoints or Django views that do slow DB operations.

---

## 4. Cache-control strategy for the React SPA

The React SPA produces two categories of output files:

| File type | Cache strategy |
|---|---|
| `index.html` | `no-cache, no-store` — tells browser to always revalidate |
| `assets/main-abc123.js`, `assets/vendor-def456.js` | `max-age=31536000, immutable` — cache forever, filename ensures freshness |

This works because Vite hashes filenames based on content. When you deploy a new build, `index.html` (uncached) loads with new `<script>` tags pointing to new hashed filenames — users always get the latest JS without a full cache bust.

```nginx
# In the nginx server block:
location = /index.html {
    add_header Cache-Control "no-cache, no-store, must-revalidate";
}

location ~* \.(js|css|woff2|png|svg)$ {
    expires 1y;
    add_header Cache-Control "public, max-age=31536000, immutable";
}
```

---

## 5. WebSocket proxying (Django Channels)

If using Django Channels or any WebSocket endpoint at `/ws/`:

```nginx
# In the server block, before the /api/ and / locations:
location /ws/ {
    proxy_pass         http://django;
    proxy_http_version 1.1;

    # Required for WebSocket protocol upgrade
    proxy_set_header Upgrade    $http_upgrade;
    proxy_set_header Connection "upgrade";

    proxy_set_header Host            $host;
    proxy_set_header X-Real-IP       $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;

    # Keep WebSocket connections open longer
    proxy_read_timeout 3600s;
    proxy_send_timeout 3600s;
}
```

Django Channels uses ASGI; gunicorn must be configured with a uvicorn worker class for WS support (see `django-gunicorn-uvicorn.md`).

---

## 6. TLS with Let's Encrypt and Certbot

### Certbot in Docker Compose

```yaml
# docker-compose.yml
services:
  certbot:
    image: certbot/certbot:latest
    volumes:
      - ./nginx/certs:/etc/letsencrypt
      - ./nginx/www:/var/www/certbot  # webroot challenge
    entrypoint: "/bin/sh -c 'trap exit TERM; while :; do certbot renew; sleep 12h & wait $${!}; done'"
```

```nginx
# Webroot challenge (nginx must serve /.well-known/ for renewal):
location /.well-known/acme-challenge/ {
    root /var/www/certbot;
}
```

### Initial certificate issuance

```bash
docker compose run --rm certbot certonly \
  --webroot \
  --webroot-path=/var/www/certbot \
  -d example.com \
  -d www.example.com \
  --email admin@example.com \
  --agree-tos \
  --non-interactive
```

### DH parameters (generate once, commit to repo)

```bash
openssl dhparam -out nginx/dhparam.pem 4096
```

---

## 7. Gzip and Brotli compression

```nginx
# http{} block (in nginx.conf) or inside server {}:
gzip on;
gzip_types
    text/plain
    text/css
    text/javascript
    application/javascript
    application/json
    application/xml
    image/svg+xml
    font/woff2;
gzip_min_length 1024;  # don't compress tiny responses
gzip_comp_level 5;     # balance between CPU and compression ratio (1-9)
gzip_vary on;           # Vary: Accept-Encoding header for proxies/CDNs
gzip_proxied any;       # compress proxied responses too
```

**Brotli** offers better compression but requires the `ngx_brotli` module not in the standard nginx image. Use `fholzer/nginx-brotli` image or compile a custom build if brotli is a priority.

---

## 8. Rate limiting

```nginx
# At the http{} level (define zones):
limit_req_zone $binary_remote_addr zone=login_zone:10m rate=5r/m;
limit_req_zone $binary_remote_addr zone=api_zone:10m   rate=60r/m;

# In the server {} block:
location /api/auth/login/ {
    limit_req zone=login_zone burst=3 nodelay;
    limit_req_status 429;  # return 429 Too Many Requests (not default 503)
    proxy_pass http://django;
    # ... other proxy headers
}

location /api/ {
    limit_req zone=api_zone burst=20 nodelay;
    limit_req_status 429;
    proxy_pass http://django;
    # ...
}
```

`burst`: allows this many excess requests before rate limiting kicks in.
`nodelay`: processes burst requests immediately (no queuing delay); excess after burst gets 429.

---

## 9. Static files: nginx vs. Whitenoise

| Approach | Pros | Cons |
|---|---|---|
| **nginx serving `/static/`** | Fastest, zero Python overhead, proper cache headers | Requires Django `collectstatic` to produce files nginx can serve; correct volume/bind mount setup needed |
| **Whitenoise** | Zero additional config; works with `python manage.py runserver` and gunicorn without nginx | Slightly slower (Python process serves files); adds a dependency per request to the app process |

For small deployments (< a few hundred concurrent users), Whitenoise is perfectly adequate. For high-traffic production where nginx serves tens of thousands of requests per second, let nginx serve static files directly.

### nginx static files setup

```python
# settings.py
STATIC_ROOT = BASE_DIR / "staticfiles"  # collectstatic destination
STATIC_URL = "/static/"
```

```dockerfile
# In the Django Dockerfile (production stage):
RUN python manage.py collectstatic --no-input

# Or in entrypoint.sh (for dynamic environments with different settings):
python manage.py collectstatic --no-input
```

```yaml
# In docker-compose.yml:
services:
  nginx:
    volumes:
      - django_static:/usr/share/nginx/django-static:ro

  web:
    volumes:
      - django_static:/app/staticfiles  # matches STATIC_ROOT
    # collectstatic runs in entrypoint
```

---

## 10. Nginx in development vs. production

**Development**: typically no nginx — Vite dev server runs on the host and proxies `/api/` to Django (`vite.config.ts` `server.proxy`). This avoids nginx overhead and preserves HMR. See `docker-compose-local-dev.md`.

**Production**: nginx handles everything — TLS, static files, routing, rate limiting. The dev proxy is completely replaced.

**Staging/CI**: may use nginx without TLS (self-signed cert or `localhost` only) to validate the nginx config before production deploy.
