# syntax=docker/dockerfile:1.22.0
FROM ubuntu:25.10 AS python_build

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
  --no-group prod

##########################################################################
FROM ubuntu:25.10 AS app

SHELL ["bash", "-exc"]

ENV PATH=/app/bin:$PATH \
  PYTHONUNBUFFERED=1 \
  PYTHONDONTWRITEBYTECODE=0

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

WORKDIR /app

# Copy the pre-built `/app` directory to the runtime container and change the ownership
# to user app and group app in one step.
COPY --from=python_build /app /app

# Copy the application code to `/app`.
COPY . /app

# Copy over the entrypoint and start scripts.
COPY ./compose/prod/django/entrypoint /app/entrypoint
COPY ./compose/dev/django/start /app/start
COPY ./compose/dev/django/celery/worker/start /app/start-celeryworker
COPY ./compose/dev/django/celery/beat/start /app/start-celerybeat
COPY ./compose/dev/django/celery/flower/start /app/start-flower
# And, make sure they are cleaned up if someone was developing from a Windows
# environment, etc.
RUN sed -i 's/\r$//g' /app/entrypoint /app/start /app/start-celery* /app/start-flower \
  && chmod +x /app/entrypoint /app/start /app/start-celery* /app/start-flower \
  # NOTE: `collectstatic` will give a warning about `dist/` not existing if it doesn't, so
  # we'll ensure it exists here.
  && mkdir -p /app/dist \
  # NOTE: Running the tests will give a warning about `staticfiles/` not existing if it
  # doesn't, so we'll ensure it exists here.
  && mkdir -p /app/staticfiles \
  # Keep runtime media directories present without baking local uploads into the image.
  && mkdir -p /app/backend/media/public /app/backend/media/private


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

ENTRYPOINT ["/app/entrypoint"]
