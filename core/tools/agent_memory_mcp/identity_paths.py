"""Helpers for per-user memory path resolution."""

from __future__ import annotations

from .errors import ValidationError
from .path_policy import validate_slug


def normalize_user_id(user_id: str | None) -> str | None:
    if user_id is None:
        return None
    if not isinstance(user_id, str):
        return None
    normalized = user_id.strip()
    if not normalized:
        return None
    return validate_slug(normalized, field_name="user_id")


def working_root(*, user_id: str | None) -> str:
    resolved_user_id = normalize_user_id(user_id)
    if resolved_user_id is None:
        return "memory/working"
    return f"memory/working/{resolved_user_id}"


def working_file_path(filename: str, *, user_id: str | None) -> str:
    if filename not in {"USER.md", "CURRENT.md"}:
        raise ValueError(f"Unsupported working file: {filename}")
    return f"{working_root(user_id=user_id)}/{filename}"


def working_notes_root(*, user_id: str | None) -> str:
    return f"{working_root(user_id=user_id)}/notes"


def working_note_path(slug: str, *, user_id: str | None) -> str:
    resolved_slug = validate_slug(slug, field_name="target")
    return f"{working_notes_root(user_id=user_id)}/{resolved_slug}.md"


def resolve_working_scratchpad_target(target: str, *, user_id: str | None) -> str:
    if not isinstance(target, str) or not target.strip():
        raise ValidationError(
            "target must be 'user', 'current', or 'memory/working/notes/{slug}.md' with a bare kebab-case slug"
        )

    normalized = target.strip().replace("\\", "/")
    resolved_user_id = normalize_user_id(user_id)

    aliases = {
        "user": working_file_path("USER.md", user_id=resolved_user_id),
        "current": working_file_path("CURRENT.md", user_id=resolved_user_id),
    }
    if normalized in aliases:
        return aliases[normalized]

    direct_targets = {
        "memory/working/USER.md": working_file_path("USER.md", user_id=resolved_user_id),
        "memory/working/CURRENT.md": working_file_path("CURRENT.md", user_id=resolved_user_id),
    }
    if resolved_user_id is not None:
        direct_targets[working_file_path("USER.md", user_id=resolved_user_id)] = working_file_path(
            "USER.md",
            user_id=resolved_user_id,
        )
        direct_targets[working_file_path("CURRENT.md", user_id=resolved_user_id)] = (
            working_file_path("CURRENT.md", user_id=resolved_user_id)
        )
    if normalized in direct_targets:
        return direct_targets[normalized]

    note_prefixes = ["memory/working/notes/"]
    if resolved_user_id is not None:
        note_prefixes.append(working_notes_root(user_id=resolved_user_id) + "/")
    for prefix in note_prefixes:
        if normalized.startswith(prefix) and normalized.endswith(".md"):
            slug = normalized[len(prefix) : -len(".md")]
            return working_note_path(slug, user_id=resolved_user_id)

    raise ValidationError(
        "target must be 'user', 'current', or 'memory/working/notes/{slug}.md' with a bare kebab-case slug"
    )


def is_working_scratchpad_path(path: str) -> bool:
    if not isinstance(path, str):
        return False
    normalized = path.replace("\\", "/").strip().lstrip("/")
    if normalized.startswith("core/"):
        normalized = normalized[len("core/") :]

    if normalized in {"memory/working/USER.md", "memory/working/CURRENT.md"}:
        return True
    if normalized.startswith("memory/working/notes/"):
        return normalized.endswith(".md")

    parts = normalized.split("/")
    if len(parts) < 4 or parts[0] != "memory" or parts[1] != "working":
        return False
    try:
        validate_slug(parts[2], field_name="user_id")
    except ValidationError:
        return False
    if len(parts) == 4 and parts[3] in {"USER.md", "CURRENT.md"}:
        return True
    return len(parts) >= 5 and parts[3] == "notes" and normalized.endswith(".md")


__all__ = [
    "is_working_scratchpad_path",
    "normalize_user_id",
    "resolve_working_scratchpad_target",
    "working_file_path",
    "working_note_path",
    "working_notes_root",
    "working_root",
]
