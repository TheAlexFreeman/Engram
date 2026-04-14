# syntax=docker/dockerfile:1.22.0
# check=error=true
FROM oven/bun:1.3.11 AS bun_base

WORKDIR /app

# Reference - https://bun.sh/guides/ecosystem/docker
# Thanks to - https://github.com/oven-sh/bun/blob/2c1dea818ca299474ad98c962b9c037b212dfc0b/docs/guides/ecosystem/docker.md

# """
# install dependencies into temp directory
# this will cache them and speed up future builds
# """
FROM bun_base AS install

# Changed from template, only do the regular + dev dependencies, no need to do prod only
# for the dev Dockerfile).
RUN mkdir -p /temp/dev
# Copy dependency files and configs needed for `bun install` (which runs `bun theme`).
# Only copy `frontend/theme/` directory, not the entire `frontend/` to improve layer
# caching - source file changes won't invalidate the `bun install` cache.
COPY package.json bun.lock tsconfig.json tsconfig.app.json tsconfig.node.json tsr.config.json vite.config.ts /temp/dev/
COPY frontend/theme/ /temp/dev/frontend/theme/
RUN --mount=type=cache,id=better-base-bun-install-cache,sharing=locked,target=/home/bun/.bun/install/cache \
    cd /temp/dev && bun install --frozen-lockfile

# """
# copy node_modules from temp directory
# then copy all (non-ignored) project files into the image
# """
FROM bun_base AS dev

COPY --link --from=install /temp/dev/node_modules node_modules
COPY --link package.json /app/package.json
COPY --link tsconfig.json tsconfig.app.json tsconfig.node.json tsr.config.json vite.config.ts /app/
COPY --link public/ /app/public/
COPY --link frontend/ /app/frontend/
# Keep the Vite static-copy target path present even in slimmed-down build contexts.
RUN mkdir -p /app/backend/static/js/jsoneditor/img

ENV PATH=./node_modules/.bin/:$PATH
