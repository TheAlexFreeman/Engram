# syntax=docker/dockerfile:1.22.0
# check=skip=SecretsUsedInArgOrEnv;error=true
FROM oven/bun:1.3.11 AS bun_base

# Install CA certificates to ensure that the sentry-cli source maps upload doesn't run
# into certificate/https errors, etc.
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
  --mount=type=cache,target=/var/lib/apt,sharing=locked \
  set -euox pipefail && \
  rm -f /etc/apt/apt.conf.d/docker-clean && \
  echo 'Binary::apt::APT::Keep-Downloaded-Packages "true";' > /etc/apt/apt.conf.d/keep-cache && \
  apt-get update && \
  apt-get install -y --no-install-recommends ca-certificates && \
  rm -rf /var/lib/apt/lists/*

WORKDIR /app

# For Python/JS/Bun/UV, etc., some helpful references:
# - https://hynek.me/articles/docker-uv/
# - https://andrich.me/2024/09/my-ideal-uv-based-dockerfile/
# - https://depot.dev/docs/languages/python
# - https://depot.dev/docs/languages/python-uv-dockerfile
# - https://github.com/astral-sh/uv-docker-example?tab=readme-ov-file
# - https://docs.astral.sh/uv/guides/integration/docker/#configuring-watch-with-docker-compose
# - https://mkennedy.codes/posts/python-docker-images-using-uv-s-new-python-features/
# - https://bun.sh/guides/ecosystem/docker
# - https://depot.dev/docs/languages/node
# - https://depot.dev/docs/languages/node-pnpm-dockerfile
#
# ^ Direct code and/or ideas are used from ^ these references potentially throughout
# this Dockerfile, along with some of our own stuff.

# Reference - https://bun.sh/guides/ecosystem/docker
# Thanks to - https://github.com/oven-sh/bun/blob/2c1dea818ca299474ad98c962b9c037b212dfc0b/docs/guides/ecosystem/docker.md

##########################################################################
# """
# install dependencies into temp directory
# this will cache them and speed up future builds
# """
FROM bun_base AS bun_install

RUN mkdir -p /temp/dev
# Copy dependency files and configs needed for `bun install` (which runs `bun theme`).
# Only copy `frontend/theme/` directory, not the entire `frontend/` to improve layer
# caching - source file changes won't invalidate the `bun install` cache.
COPY package.json bun.lock tsconfig.json tsconfig.app.json tsconfig.node.json tsr.config.json vite.config.ts /temp/dev/
COPY frontend/theme/ /temp/dev/frontend/theme/
RUN --mount=type=cache,id=better-base-bun-install-cache,sharing=locked,target=/home/bun/.bun/install/cache \
  cd /temp/dev && bun install --frozen-lockfile

##########################################################################
# """
# copy node_modules from temp directory
# then copy all (non-ignored) project files into the image
# """
FROM bun_base AS bun_prerelease

COPY --link --from=bun_install /temp/dev/node_modules node_modules
COPY --link package.json /app/package.json
COPY --link tsconfig.json tsconfig.app.json tsconfig.node.json tsr.config.json vite.config.ts /app/
COPY --link public/ /app/public/
COPY --link frontend/ /app/frontend/
# Keep the Vite static-copy target path present even in slimmed-down build contexts.
RUN mkdir -p /app/backend/static/js/jsoneditor/img

# Self-hosted builds can pass these values through BuildKit secrets, while direct
# `docker build` callers can use build args. Prefer the secret mount when both are
# present, and only require the Sentry-specific values when frontend Sentry is enabled.
ARG VITE_SENTRY_IS_ENABLED
ARG VITE_SENTRY_AUTH_TOKEN
ARG VITE_SENTRY_DSN
ARG VITE_SENTRY_ORG
ARG VITE_SENTRY_PROJECT
ARG VITE_SENTRY_RELEASE
ARG RENDER_GIT_COMMIT
RUN --mount=type=secret,id=vite_sentry_is_enabled,required=false \
  --mount=type=secret,id=vite_sentry_auth_token,required=false \
  --mount=type=secret,id=vite_sentry_dsn,required=false \
  --mount=type=secret,id=vite_sentry_org,required=false \
  --mount=type=secret,id=vite_sentry_project,required=false \
  --mount=type=secret,id=vite_sentry_release,required=false \
  # Do not enable xtrace in this step because it would echo secret-backed exports into
  # Docker build logs.
  set -euo pipefail && \
  pick_value() { \
    local arg_value="${1:-}"; \
    local secret_path="$2"; \
    if [ -f "${secret_path}" ]; then \
      tr -d '\r\n' < "${secret_path}"; \
    elif [ -n "${arg_value}" ]; then \
      printf '%s' "${arg_value}"; \
    fi; \
  } && \
  require_value_if_enabled() { \
    local key_name="$1"; \
    local value="$2"; \
    if [ "${sentry_is_enabled}" = "true" ] && [ -z "${value}" ]; then \
      printf 'Missing required production frontend build value: %s\n' "${key_name}" >&2; \
      exit 1; \
    fi; \
  } && \
  sentry_is_enabled="$(pick_value "${VITE_SENTRY_IS_ENABLED:-}" /run/secrets/vite_sentry_is_enabled)" && \
  sentry_auth_token="$(pick_value "${VITE_SENTRY_AUTH_TOKEN:-}" /run/secrets/vite_sentry_auth_token)" && \
  sentry_dsn="$(pick_value "${VITE_SENTRY_DSN:-}" /run/secrets/vite_sentry_dsn)" && \
  sentry_org="$(pick_value "${VITE_SENTRY_ORG:-}" /run/secrets/vite_sentry_org)" && \
  sentry_project="$(pick_value "${VITE_SENTRY_PROJECT:-}" /run/secrets/vite_sentry_project)" && \
  release_value="$(pick_value "${VITE_SENTRY_RELEASE:-}" /run/secrets/vite_sentry_release)" && \
  sentry_release="${RENDER_GIT_COMMIT:-${release_value}}" && \
  sentry_is_enabled="${sentry_is_enabled:-false}" && \
  require_value_if_enabled VITE_SENTRY_AUTH_TOKEN "${sentry_auth_token}" && \
  require_value_if_enabled VITE_SENTRY_DSN "${sentry_dsn}" && \
  require_value_if_enabled VITE_SENTRY_ORG "${sentry_org}" && \
  require_value_if_enabled VITE_SENTRY_PROJECT "${sentry_project}" && \
  require_value_if_enabled VITE_SENTRY_RELEASE "${sentry_release}" && \
  export VITE_SENTRY_IS_ENABLED="${sentry_is_enabled}" && \
  export VITE_SENTRY_AUTH_TOKEN="${sentry_auth_token}" && \
  export VITE_SENTRY_DSN="${sentry_dsn}" && \
  export VITE_SENTRY_ORG="${sentry_org}" && \
  export VITE_SENTRY_PROJECT="${sentry_project}" && \
  export VITE_SENTRY_RELEASE="${sentry_release}" && \
  export ENVIRONMENT=prod VITE_ENVIRONMENT=prod NODE_ENV=production && \
  bun run build && \
  printf '%s' "${VITE_SENTRY_RELEASE}" > .sentry-release

# Remove source map files and any references to them.
RUN \
  bash -c ' \
  set -euox pipefail && \
  # Delete source map files. \
  find ./dist -type f -name "*.map" -delete && \
  # Remove source map references from CSS files. \
  find ./dist -type f -name "*.css" -exec sed -i -E "s/sourceMappingURL=[^ ]*\.map//g" {} + && \
  # Remove source map references from JS files. \
  find ./dist -type f -name "*.js" -exec sed -i -E "s/sourceMappingURL=[^ ]*\.map//g" {} + \
  '

##########################################################################
FROM ubuntu:25.10 AS python_build

# -----
# Thank you to
# Hynek - <https://hynek.me/articles/docker-uv/>
# Depot - <https://depot.dev/docs/languages/python-uv-dockerfile>
#
# NOTE that Hynek updates that article every once and a while. The last version we've
# based this Dockerfile off of is from Hynek's 2024-11-22 update.
# -----

SHELL ["bash", "-exc"]

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
  --mount=type=cache,target=/var/lib/apt,sharing=locked \
  set -euox pipefail && \
  rm -f /etc/apt/apt.conf.d/docker-clean && \
  echo 'Binary::apt::APT::Keep-Downloaded-Packages "true";' > /etc/apt/apt.conf.d/keep-cache && \
  apt-get update -qy && \
  apt-get install -qyy \
  -o APT::Install-Recommends=false \
  -o APT::Install-Suggests=false \
  build-essential \
  ca-certificates \
  tzdata \
  python3-setuptools \
  python3.14-dev \
  libpq5 \
  libpq-dev

COPY --from=ghcr.io/astral-sh/uv:0.11.0 /uv /usr/local/bin/uv

# - Assure UTF-8 encoding is used.
# - Silence uv complaining about not being able to use hard links,
# - tell uv to byte-compile packages for faster application startups,
# - prevent uv from accidentally downloading isolated Python builds,
# - pick a Python,
# - and finally declare `/app` as the target for `uv sync`.
ENV LC_CTYPE=C.utf8 \
  UV_LINK_MODE=copy \
  UV_COMPILE_BYTECODE=1 \
  UV_PYTHON_DOWNLOADS=never \
  UV_PYTHON=/usr/bin/python3.14 \
  UV_PROJECT_ENVIRONMENT=/app

# Since there's no point in shipping lock files, we move them into a directory that is
# NOT copied into the runtime image. The trailing slash makes COPY create `/_lock/`
# automagically.
COPY pyproject.toml /_lock/
COPY uv.lock /_lock/

# Synchronize DEPENDENCIES without the application itself. This layer is cached until
# uv.lock or pyproject.toml change. You can create `/app` using `uv venv` in a separate
# `RUN` step to have it cached, but with uv it's so fast, it's not worth it, so we let
# `uv sync` create it for us automagically.
RUN --mount=type=cache,id=better-base-uv-cache,sharing=locked,target=/root/.cache/uv \
  set -euox pipefail && \
  cd /_lock && \
  uv sync \
  --locked \
  --no-install-project \
  --no-dev \
  --group=prod

##########################################################################
FROM ubuntu:25.10 AS app

SHELL ["bash", "-exc"]

ENV PATH=/app/bin:$PATH \
  PYTHONUNBUFFERED=1 \
  PYTHONDONTWRITEBYTECODE=0

# Don't run your app as root.
RUN set -euox pipefail && \
  groupadd -r app && \
  useradd -r -d /app -g app -N app

# Note how the runtime dependencies differ from build-time ones. Notably, there is no uv
# either!
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
  --mount=type=cache,target=/var/lib/apt,sharing=locked \
  set -euox pipefail && \
  rm -f /etc/apt/apt.conf.d/docker-clean && \
  echo 'Binary::apt::APT::Keep-Downloaded-Packages "true";' > /etc/apt/apt.conf.d/keep-cache && \
  apt-get update -qy && \
  apt-get install -qyy \
  -o APT::Install-Recommends=false \
  -o APT::Install-Suggests=false \
  apt-utils \
  tzdata \
  python3.14 \
  libpython3.14 \
  libpcre3 \
  libxml2-16 \
  libpq5 \
  libpq-dev \
  gettext \
  tini && \
  apt-get clean && \
  rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Copy the pre-built `/app` directory to the runtime container and change the ownership
# to user app and group app in one step.
COPY --from=python_build --chown=app:app /app /app

# Copy only the application paths the runtime actually needs.
COPY --parents --chown=app:app ./backend ./config ./emails ./locale ./manage.py ./public /app/

# Copy over the entrypoint and start scripts.
COPY --chown=app:app ./compose/prod/django/entrypoint /app/entrypoint
COPY --chown=app:app ./compose/prod/django/start /app/start
COPY --chown=app:app ./compose/prod/django/celery/worker/start /app/start-celeryworker
COPY --chown=app:app ./compose/prod/django/celery/beat/start /app/start-celerybeat
COPY --chown=app:app ./compose/prod/django/celery/flower/start /app/start-flower
# And, make sure they are cleaned up if someone was developing from a Windows
# environment, etc.
RUN sed -i 's/\r$//g' /app/entrypoint /app/start /app/start-celery* /app/start-flower \
  && chmod +x /app/entrypoint /app/start /app/start-celery* /app/start-flower \
  # Ensure the non-root runtime user can write directories Django populates at startup.
  && chown app:app /app \
  && install -d -o app -g app /app/staticfiles \
  && install -d -o app -g app /app/backend/media/public /app/backend/media/private

# Copy the bun build results to `/app`.
COPY --link --from=bun_prerelease /app/dist /app/dist
# Copy frontend-generated vendor assets that are written into `backend/static/`.
COPY --link --from=bun_prerelease /app/backend/static/js/jsoneditor /app/backend/static/js/jsoneditor
# Copy the Sentry release file (contains git commit SHA for release tracking).
COPY --link --from=bun_prerelease /app/.sentry-release /app/.sentry-release

USER app
WORKDIR /app

# This is an optional smoke test/sanity check.
#
# NOTE: Hynek's article uses python -IC 'import backend' but for how our codebase is
# currently structured, we need to get rid of the I flag because `backend` isn't a
# "proper" python package per-say. To understand what I mean by proper, you might want
# to read Hynek's article and potentially dig a bit deeper.
RUN set -euox pipefail && \
  python -V && \
  python -Im site && \
  python -c 'import backend'

# Use `tini` to provide better PID 1 process management and signal handling. See
# <https://hynek.me/articles/docker-signals/>
ENTRYPOINT ["/usr/bin/tini", "-v", "--", "/app/entrypoint"]

# NOTE: This is optional, but potentially helpful (also in conjunction with `/tini`
# above): See <https://hynek.me/articles/docker-signals/>.
#
# (NOTE: To my current knowledge, SIGTERM is the default stop signal so this line is
# probably redundant. Still worth reading the article and knowing which which stop
# signal you might want in some cases. For Gunicorn AND Celery we explicitly want
# SIGTERM, so keeping it as that.)
STOPSIGNAL SIGTERM
