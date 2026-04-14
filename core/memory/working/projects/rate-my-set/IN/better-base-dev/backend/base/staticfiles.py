from __future__ import annotations

from urllib.parse import unquote, urlsplit

from whitenoise.storage import CompressedManifestStaticFilesStorage


class ViteManifestStaticFilesStorage(CompressedManifestStaticFilesStorage):
    """Skip re-hashing Vite assets under `bundler/` while keeping manifest behavior."""

    _vite_prefix = "bundler/"

    def hashed_name(self, name, *args, **kwargs):
        clean_name = urlsplit(unquote(name)).path.strip().lstrip("/")
        if clean_name.startswith(self._vite_prefix):
            return name
        return super().hashed_name(name, *args, **kwargs)
