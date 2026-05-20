from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

# Output / scan bounds (single tool call cannot exceed these without truncation).
MAX_READ_CHARS = 1_000_000
MAX_LIST_ENTRIES = 10_000
MAX_GLOB_RESULTS = 5_000
MAX_GREP_MATCHES = 2_000
MAX_GREP_FILES_SCANNED = 8_000
MAX_GREP_BYTES_PER_FILE = 512_000
TRUNCATION_SUFFIX = "\n\n[harness: output truncated]"


def truncate_text(text: str, max_chars: int) -> tuple[str, bool]:
    if max_chars <= 0 or len(text) <= max_chars:
        return text, False
    budget = max_chars - len(TRUNCATION_SUFFIX)
    if budget <= 0:
        return TRUNCATION_SUFFIX.strip(), True
    return text[:budget] + TRUNCATION_SUFFIX, True


@dataclass
class WorkspaceScope:
    """Confines filesystem operations under ``root``.

    ``resolve()`` joins ``relative`` to ``root`` and calls ``Path.resolve()``,
    which follows symbolic links. The resolved path must be ``root`` or a
    descendant; otherwise a ``ValueError`` is raised. This blocks ``..`` and
    symlink chains that escape the workspace.
    """

    root: Path

    def _root_resolved(self) -> Path:
        return self.root.resolve()

    def resolve(self, relative: str) -> Path:
        p = (self.root / relative).resolve()
        root_r = self._root_resolved()
        if root_r not in p.parents and p != root_r:
            raise ValueError(f"path {relative!r} escapes workspace {self.root}")
        return p

    def describe_path(self, path: Path) -> str:
        """Stable relative path string for messages (POSIX-style)."""
        try:
            cr = path.resolve()
        except OSError:
            cr = path
        try:
            rel = cr.relative_to(self._root_resolved())
            return rel.as_posix()
        except ValueError:
            return path.name
