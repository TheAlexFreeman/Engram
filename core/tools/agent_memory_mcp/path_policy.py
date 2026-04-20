"""Shared path validation helpers for MCP tool inputs."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

from .errors import MemoryPermissionError, ValidationError

_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_SESSION_ID_RE = re.compile(
    r"^memory/activity/(?:(?P<user_id>[a-z0-9]+(?:-[a-z0-9]+)*)/)?(?P<year>\d{4})/(?P<month>\d{2})/(?P<day>\d{2})/(?P<type>chat|act)-(?P<number>\d{3})$"
)

# Shared commit-prefix vocabulary used by both read_tools and write_tools.
KNOWN_COMMIT_PREFIXES: frozenset[str] = frozenset(
    {
        "[knowledge]",
        "[plan]",
        "[project]",
        "[skill]",
        "[user]",
        "[chat]",
        "[curation]",
        "[working]",
        "[system]",
        "[access]",
    }
)

_PROTECTED_ROOTS = ("memory/users", "governance", "memory/activity", "memory/skills")
_RAW_MUTATION_ROOTS = ("memory/knowledge", "memory/working")
_KNOWLEDGE_ROOT = "memory/knowledge"
_UNVERIFIED_KNOWLEDGE_ROOT = "memory/knowledge/_unverified"
_ARCHIVED_KNOWLEDGE_ROOT = "memory/knowledge/_archive"


def _matches_any_prefix(rel_path: str, prefixes: tuple[str, ...]) -> str | None:
    """Return the first matching prefix if *rel_path* starts with any, else ``None``."""
    for prefix in prefixes:
        if rel_path == prefix or rel_path.startswith(prefix + "/"):
            return prefix
    return None


def resolve_repo_path(repo, raw_path: str, *, field_name: str = "path") -> tuple[str, Path]:
    """Normalize an input path to a repo-relative POSIX path plus abs path."""
    if not isinstance(raw_path, str) or not raw_path.strip():
        raise ValidationError(f"{field_name} must be a non-empty repo-relative path")

    abs_path = repo.abs_path(raw_path)
    rel_path = repo.rel_path(abs_path).replace("\\", "/")
    return rel_path, abs_path


def validate_raw_write_target(repo, raw_path: str, *, field_name: str = "path") -> tuple[str, Path]:
    """Normalize and validate write targets against the protected-directory policy.

    Protected directories (memory/users/, governance/, memory/activity/,
    memory/skills/) are blocked for raw Tier 2 writes. Tier 2 writes must stay
    under memory/knowledge/ or memory/working/. Use Tier 1 semantic tools for
    governed writes to protected directories (e.g. memory_update_identity_trait,
    memory_record_chat_summary).

    Returns the repo-relative path and absolute path on success.
    """
    rel_path, abs_path = resolve_repo_path(repo, raw_path, field_name=field_name)

    matched_protected = _matches_any_prefix(rel_path, _PROTECTED_ROOTS)
    if matched_protected is not None:
        raise MemoryPermissionError(
            f"Cannot raw-write to '{rel_path}': '{matched_protected}/' is a protected directory. "
            f"Use the appropriate Tier 1 semantic tool instead. "
            f"Protected directories: {sorted(_PROTECTED_ROOTS)}",
            path=rel_path,
        )

    if _matches_any_prefix(rel_path, _RAW_MUTATION_ROOTS) is None:
        allowed = ", ".join(f"{root}/" for root in _RAW_MUTATION_ROOTS)
        raise MemoryPermissionError(
            f"Cannot raw-write to '{rel_path}': path must be under {allowed}.",
            path=rel_path,
        )

    return rel_path, abs_path


def validate_raw_move_destination(
    repo,
    raw_path: str,
    *,
    field_name: str = "dest",
) -> tuple[str, Path]:
    """Normalize and validate move destinations against the protected-directory policy.

    Tier 2 moves must not target protected directories and must stay under
    the raw mutation roots (memory/knowledge/, memory/working/), matching the
    same restriction applied to writes and deletes.
    """
    rel_path, abs_path = resolve_repo_path(repo, raw_path, field_name=field_name)

    matched_protected = _matches_any_prefix(rel_path, _PROTECTED_ROOTS)
    if matched_protected is not None:
        raise MemoryPermissionError(
            f"Cannot move to '{rel_path}': '{matched_protected}/' is a protected directory. "
            f"Use the appropriate Tier 1 semantic tool instead. "
            f"Protected directories: {sorted(_PROTECTED_ROOTS)}",
            path=rel_path,
        )

    if _matches_any_prefix(rel_path, _RAW_MUTATION_ROOTS) is None:
        allowed = ", ".join(f"{root}/" for root in _RAW_MUTATION_ROOTS)
        raise MemoryPermissionError(
            f"Cannot move to '{rel_path}': destination must be under {allowed}.",
            path=rel_path,
        )

    return rel_path, abs_path


def require_under_prefix(
    rel_path: str,
    prefix: str,
    *,
    field_name: str = "path",
) -> str:
    """Require that *rel_path* is inside the exact directory prefix."""
    normalized_prefix = prefix.rstrip("/") + "/"
    if not rel_path.startswith(normalized_prefix):
        raise ValidationError(f"{field_name} must be under {normalized_prefix}: {rel_path}")
    return rel_path


def forbid_prefix(
    rel_path: str,
    prefix: str,
    *,
    field_name: str = "path",
) -> str:
    """Reject repo-relative paths inside the exact directory prefix."""
    normalized_prefix = prefix.rstrip("/") + "/"
    if rel_path.startswith(normalized_prefix):
        raise ValidationError(f"{field_name} must not be under {normalized_prefix}: {rel_path}")
    return rel_path


def validate_slug(value: str, *, field_name: str) -> str:
    """Validate a bare kebab-case identifier."""
    if not isinstance(value, str) or not _SLUG_RE.fullmatch(value):
        raise ValidationError(f"{field_name} must be a bare kebab-case slug: {value!r}")
    return value


def session_id_user_id(session_id: str) -> str | None:
    match = _SESSION_ID_RE.fullmatch(validate_session_id(session_id))
    if match is None:
        return None
    return match.group("user_id")


def session_id_day_key(session_id: str) -> str:
    match = _SESSION_ID_RE.fullmatch(validate_session_id(session_id))
    if match is None:
        raise ValidationError("session_id must match memory/activity[/user-id]/YYYY/MM/DD/{chat|act}-NNN")
    return f"{match.group('year')}/{match.group('month')}/{match.group('day')}"


def namespace_session_id(session_id: str, *, user_id: str | None) -> str:
    normalized = validate_session_id(session_id)
    if user_id is None:
        return normalized

    stripped_user_id = user_id.strip()
    if not stripped_user_id:
        return normalized
    resolved_user_id = validate_slug(stripped_user_id, field_name="user_id")

    match = _SESSION_ID_RE.fullmatch(normalized)
    if match is None:
        raise ValidationError("session_id must match memory/activity[/user-id]/YYYY/MM/DD/{chat|act}-NNN")

    existing_user_id = match.group("user_id")
    if existing_user_id is not None:
        if existing_user_id != resolved_user_id:
            raise ValidationError(
                f"session_id is already namespaced for user '{existing_user_id}', expected '{resolved_user_id}'"
            )
        return normalized

    return f"memory/activity/{resolved_user_id}/{match.group('year')}/{match.group('month')}/{match.group('day')}/{match.group('type')}-{match.group('number')}"


def validate_session_id(session_id: str) -> str:
    """Validate canonical session ids: memory/activity[/user-id]/YYYY/MM/DD/{chat|act}-NNN."""
    if not isinstance(session_id, str) or not _SESSION_ID_RE.fullmatch(session_id):
        raise ValidationError("session_id must match memory/activity[/user-id]/YYYY/MM/DD/{chat|act}-NNN")
    return session_id


def validate_raw_mutation_source(repo, raw_path: str, *, operation: str) -> tuple[str, Path]:
    """Normalize and validate raw delete/move source paths."""
    rel_path, abs_path = resolve_repo_path(repo, raw_path)

    matched_protected = _matches_any_prefix(rel_path, _PROTECTED_ROOTS)
    if matched_protected is not None:
        raise MemoryPermissionError(
            f"Cannot {operation} '{rel_path}': '{matched_protected}/' is a protected directory. "
            f"Protected directories: {sorted(_PROTECTED_ROOTS)}",
            path=rel_path,
        )

    if _matches_any_prefix(rel_path, _RAW_MUTATION_ROOTS) is None:
        allowed = ", ".join(f"{root}/" for root in _RAW_MUTATION_ROOTS)
        raise MemoryPermissionError(
            f"Cannot {operation} '{rel_path}': source must be under {allowed}.",
            path=rel_path,
        )

    return rel_path, abs_path


def validate_top_level_root(
    rel_path: str,
    *,
    allowed_roots: Iterable[str],
    field_name: str = "path",
) -> str:
    """Require a normalized repo path to start under one of the allowed root prefixes."""
    allowed = tuple(root.rstrip("/") for root in allowed_roots)
    if _matches_any_prefix(rel_path, allowed) is None:
        pretty = ", ".join(f"{root}/" for root in allowed)
        raise ValidationError(f"{field_name} must be under one of {pretty}: {rel_path}")
    return rel_path


def validate_knowledge_path(
    repo,
    raw_path: str,
    *,
    field_name: str = "path",
    allow_unverified: bool = False,
    allow_archive: bool = False,
) -> tuple[str, Path]:
    """Normalize and validate repo paths within the governed knowledge surface."""
    rel_path, abs_path = resolve_repo_path(repo, raw_path, field_name=field_name)

    if _matches_any_prefix(rel_path, (_KNOWLEDGE_ROOT,)) is None:
        allowed_roots = [_KNOWLEDGE_ROOT]
        if allow_archive:
            allowed_roots.append(_ARCHIVED_KNOWLEDGE_ROOT)
        pretty = ", ".join(f"{root}/" for root in allowed_roots)
        raise ValidationError(f"{field_name} must stay under {pretty}: {rel_path}")

    if not allow_unverified and _matches_any_prefix(rel_path, (_UNVERIFIED_KNOWLEDGE_ROOT,)):
        raise ValidationError(
            f"{field_name} must not point into {_UNVERIFIED_KNOWLEDGE_ROOT}/: {rel_path}"
        )

    if not allow_archive and _matches_any_prefix(rel_path, (_ARCHIVED_KNOWLEDGE_ROOT,)):
        raise ValidationError(
            f"{field_name} must not point into {_ARCHIVED_KNOWLEDGE_ROOT}/: {rel_path}"
        )

    return rel_path, abs_path
