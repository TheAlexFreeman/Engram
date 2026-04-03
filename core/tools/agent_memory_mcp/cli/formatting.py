"""Shared CLI helpers for Engram terminal commands."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

_IGNORED_NAMES = frozenset(
    {
        ".git",
        ".pytest_cache",
        ".ruff_cache",
        "__pycache__",
    }
)

_NAMESPACE_ALIASES = {
    "knowledge": "memory/knowledge",
    "users": "memory/users",
    "identity": "memory/users",
    "skills": "memory/skills",
    "plans": "memory/working/projects",
    "projects": "memory/working/projects",
    "activity": "memory/activity",
    "chats": "memory/activity",
}


@dataclass(frozen=True, slots=True)
class AccessEntry:
    access_file: str
    file: str
    date: str | None = None
    task: str | None = None
    note: str | None = None
    helpfulness: float | None = None
    session_id: str | None = None
    mode: str | None = None
    task_id: str | None = None
    raw: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = dict(self.raw or {})
        payload["access_file"] = self.access_file
        payload.setdefault("file", self.file)
        if self.date is not None:
            payload["date"] = self.date
        if self.task is not None:
            payload["task"] = self.task
        if self.note is not None:
            payload["note"] = self.note
        if self.helpfulness is not None:
            payload["helpfulness"] = self.helpfulness
        if self.session_id is not None:
            payload["session_id"] = self.session_id
        if self.mode is not None:
            payload["mode"] = self.mode
        if self.task_id is not None:
            payload["task_id"] = self.task_id
        return payload


def read_text(path: Path, *, errors: str = "replace") -> str:
    try:
        return path.read_text(encoding="utf-8", errors=errors)
    except OSError:
        return ""


def _split_frontmatter(text: str) -> tuple[dict[str, str], str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text

    metadata: dict[str, str] = {}
    closing_index: int | None = None
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            closing_index = index
            break
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        metadata[key.strip()] = value.strip().strip('"').strip("'")

    if closing_index is None:
        return {}, text

    body = "\n".join(lines[closing_index + 1 :]).lstrip("\n")
    return metadata, body


def parse_scalar_frontmatter(path: Path) -> dict[str, str]:
    metadata, _body = _split_frontmatter(read_text(path))
    return metadata


def read_markdown(path: Path) -> tuple[dict[str, Any], str]:
    text = read_text(path)
    if not text:
        return {}, ""

    try:
        from ..frontmatter_utils import read_with_frontmatter
    except ModuleNotFoundError:
        return _split_frontmatter(text)

    try:
        return read_with_frontmatter(path)
    except Exception:
        return _split_frontmatter(text)


def parse_iso_date(raw_value: object) -> date | None:
    if raw_value is None:
        return None
    try:
        return datetime.strptime(str(raw_value), "%Y-%m-%d").date()
    except ValueError:
        return None


def effective_date(frontmatter: Mapping[str, Any]) -> date | None:
    for key in ("last_verified", "created"):
        parsed = parse_iso_date(frontmatter.get(key))
        if parsed is not None:
            return parsed
    return None


def age_days(frontmatter: Mapping[str, Any], *, today: date | None = None) -> int | None:
    effective = effective_date(frontmatter)
    if effective is None:
        return None
    return ((today or date.today()) - effective).days


def format_snippet(text: str, *, limit: int = 200) -> str:
    snippet = " ".join(text.strip().split())
    if len(snippet) <= limit:
        return snippet
    return snippet[: limit - 1].rstrip() + "…"


def iter_markdown_files(scope_path: Path, *, include_summary: bool = True) -> list[Path]:
    if scope_path.is_file():
        if scope_path.suffix != ".md":
            return []
        if not include_summary and scope_path.name == "SUMMARY.md":
            return []
        return [scope_path]

    if not scope_path.exists():
        return []

    files: list[Path] = []
    for path in sorted(scope_path.rglob("*.md")):
        if any(part in _IGNORED_NAMES for part in path.parts):
            continue
        if not include_summary and path.name == "SUMMARY.md":
            continue
        files.append(path)
    return files


def relativize_path(path: Path, *, repo_root: Path, content_root: Path) -> str:
    for base in (content_root, repo_root):
        try:
            return path.relative_to(base).as_posix()
        except ValueError:
            continue
    return path.as_posix()


def _candidate_relative_targets(raw_target: str) -> list[str]:
    normalized = raw_target.replace("\\", "/").strip().lstrip("/")
    if not normalized or normalized == ".":
        return []

    candidates: list[str] = []

    def _add(candidate: str) -> None:
        value = candidate.replace("\\", "/").strip().lstrip("/")
        if value and value not in candidates:
            candidates.append(value)

    _add(normalized)
    if normalized.startswith("core/"):
        _add(normalized[len("core/") :])

    direct_alias = _NAMESPACE_ALIASES.get(normalized)
    if direct_alias is not None:
        _add(direct_alias)

    top_level, separator, remainder = normalized.partition("/")
    prefix_alias = _NAMESPACE_ALIASES.get(top_level)
    if prefix_alias is not None:
        _add(f"{prefix_alias}/{remainder}" if separator else prefix_alias)

    return candidates


def resolve_target_path(repo_root: Path, content_root: Path, raw_target: str) -> Path | None:
    explicit = Path(raw_target).expanduser()
    if explicit.is_absolute():
        resolved = explicit.resolve()
        if resolved.exists():
            return resolved
        if resolved.suffix != ".md":
            markdown_candidate = resolved.with_suffix(".md")
            if markdown_candidate.exists():
                return markdown_candidate
        return None

    for rel_target in _candidate_relative_targets(raw_target):
        for base in (content_root, repo_root):
            candidate = (base / rel_target).resolve()
            if candidate.exists():
                return candidate
            if candidate.suffix != ".md":
                markdown_candidate = candidate.with_suffix(".md")
                if markdown_candidate.exists():
                    return markdown_candidate
    return None


def load_access_entries(content_root: Path) -> list[AccessEntry]:
    memory_root = content_root / "memory"
    if not memory_root.exists():
        return []

    entries: list[AccessEntry] = []
    for access_file in sorted(memory_root.rglob("ACCESS.jsonl")):
        rel_path = access_file.relative_to(content_root).as_posix()
        if any(part.startswith(".") for part in access_file.relative_to(content_root).parts):
            continue
        if not rel_path.startswith("memory/"):
            continue

        for raw_line in read_text(access_file).splitlines():
            line = raw_line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, dict):
                continue

            file_path = str(payload.get("file", "")).strip()
            if not file_path:
                continue

            helpfulness: float | None = None
            raw_helpfulness = payload.get("helpfulness")
            if isinstance(raw_helpfulness, (int, float, str)):
                try:
                    helpfulness = float(raw_helpfulness)
                except ValueError:
                    helpfulness = None

            entries.append(
                AccessEntry(
                    access_file=rel_path,
                    file=file_path,
                    date=str(payload.get("date")).strip()
                    if payload.get("date") is not None
                    else None,
                    task=str(payload.get("task")).strip()
                    if payload.get("task") is not None
                    else None,
                    note=str(payload.get("note")).strip()
                    if payload.get("note") is not None
                    else None,
                    helpfulness=helpfulness,
                    session_id=(
                        str(payload.get("session_id")).strip()
                        if payload.get("session_id") is not None
                        else None
                    ),
                    mode=str(payload.get("mode")).strip()
                    if payload.get("mode") is not None
                    else None,
                    task_id=(
                        str(payload.get("task_id")).strip()
                        if payload.get("task_id") is not None
                        else None
                    ),
                    raw=dict(payload),
                )
            )

    return entries


def build_access_index(entries: Sequence[AccessEntry]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for entry in entries:
        current = index.setdefault(entry.file, {"count": 0, "last_date": None})
        current["count"] += 1

        current_last = parse_iso_date(current["last_date"])
        candidate_last = parse_iso_date(entry.date)
        if candidate_last is not None and (current_last is None or candidate_last > current_last):
            current["last_date"] = entry.date
    return index


def namespace_prefixes(namespace: str | None) -> tuple[str, ...]:
    if not namespace:
        return ()

    normalized = namespace.replace("\\", "/").strip().strip("/")
    if not normalized:
        return ()

    direct_alias = _NAMESPACE_ALIASES.get(normalized)
    if direct_alias is not None:
        return (direct_alias,)

    top_level, separator, remainder = normalized.partition("/")
    prefix_alias = _NAMESPACE_ALIASES.get(top_level)
    if prefix_alias is not None:
        return (f"{prefix_alias}/{remainder}" if separator else prefix_alias,)

    return (normalized,)


def filter_access_entries(
    entries: Sequence[AccessEntry],
    *,
    namespace: str | None = None,
    since: str | None = None,
    until: str | None = None,
    file_path: str | None = None,
) -> list[AccessEntry]:
    prefixes = namespace_prefixes(namespace)
    since_date = parse_iso_date(since) if since else None
    until_date = parse_iso_date(until) if until else None
    normalized_file_path = file_path.replace("\\", "/") if file_path else None

    filtered: list[AccessEntry] = []
    for entry in entries:
        if prefixes and not any(
            entry.file == prefix
            or entry.file.startswith(f"{prefix}/")
            or entry.access_file == f"{prefix}/ACCESS.jsonl"
            or entry.access_file.startswith(f"{prefix}/")
            for prefix in prefixes
        ):
            continue

        if normalized_file_path is not None and entry.file != normalized_file_path:
            continue

        entry_date = parse_iso_date(entry.date)
        if since_date is not None and (entry_date is None or entry_date < since_date):
            continue
        if until_date is not None and (entry_date is None or entry_date > until_date):
            continue

        filtered.append(entry)

    return filtered


def visible_namespace(path: str) -> str:
    normalized = path.replace("\\", "/").lstrip("/")
    if normalized.startswith(("memory/knowledge/", "knowledge/")):
        return "knowledge"
    if normalized.startswith(("memory/working/projects/", "plans/")):
        return "plans"
    if normalized.startswith(("memory/users/", "identity/")):
        return "identity"
    if normalized.startswith(("memory/skills/", "skills/")):
        return "skills"
    if normalized.startswith("memory/activity/"):
        return "chats"
    return normalized.split("/", 1)[0] if normalized else "unknown"


def render_ranked_results(
    mode: str,
    results: Sequence[object],
    fallback_note: str | None = None,
) -> str:
    banner = f"Mode: {mode}"
    if fallback_note:
        banner = f"{banner} ({fallback_note})"

    if not results:
        return banner + "\n\nNo results found."

    lines = [banner, ""]
    for index, item in enumerate(results, start=1):
        path = _item_value(item, "path")
        trust = _item_value(item, "trust")
        snippet = _item_value(item, "snippet") or ""
        score = _item_value(item, "score")

        trust_suffix = f" [{trust}]" if trust else ""
        header = f"{index}. {path}{trust_suffix}"
        if score is not None:
            header = f"{header} ({float(score):.3f})"
        lines.append(header)
        lines.append(f"   {snippet}")

    return "\n".join(lines)


def _item_value(item: object, key: str) -> Any:
    if isinstance(item, Mapping):
        return item.get(key)
    return getattr(item, key, None)


def render_governed_preview(preview: Mapping[str, Any]) -> str:
    lines = [
        f"Mode: {preview.get('mode', 'preview')}",
        f"Change class: {preview.get('change_class', 'automatic')}",
        f"Summary: {preview.get('summary', '')}",
    ]

    reasoning = str(preview.get("reasoning") or "").strip()
    if reasoning:
        lines.extend(["", "Reasoning:", reasoning])

    target_files = preview.get("target_files")
    if isinstance(target_files, Sequence):
        lines.extend(["", "Targets:"])
        for item in target_files:
            if not isinstance(item, Mapping):
                continue
            details = str(item.get("details") or "").strip()
            prefix = f"  - {item.get('change', 'update')}: {item.get('path', '')}"
            lines.append(prefix)
            if details:
                lines.append(f"    {details}")

    effects = preview.get("invariant_effects")
    if isinstance(effects, Sequence):
        lines.extend(["", "Effects:"])
        for effect in effects:
            lines.append(f"  - {effect}")

    commit_suggestion = preview.get("commit_suggestion")
    if isinstance(commit_suggestion, Mapping) and commit_suggestion.get("message"):
        lines.extend(["", f"Commit: {commit_suggestion['message']}"])

    resulting_state = preview.get("resulting_state")
    if isinstance(resulting_state, Mapping) and resulting_state:
        lines.extend(["", "Resulting state:"])
        for key, value in resulting_state.items():
            lines.append(f"  - {key}: {value}")

    warnings = preview.get("warnings")
    if isinstance(warnings, Sequence) and warnings:
        lines.extend(["", "Warnings:"])
        for warning in warnings:
            lines.append(f"  - {warning}")

    content_preview = str(preview.get("content_preview") or "").rstrip()
    if content_preview:
        lines.extend(["", "Content preview:", content_preview])

    return "\n".join(lines)


def render_write_result(payload: Mapping[str, Any]) -> str:
    new_state = payload.get("new_state") if isinstance(payload.get("new_state"), Mapping) else {}
    lines: list[str] = []

    path = new_state.get("path") if isinstance(new_state, Mapping) else None
    if path:
        lines.append(f"Added: {path}")

    commit_sha = payload.get("commit_sha")
    if commit_sha:
        lines.append(f"Commit: {commit_sha}")

    commit_message = payload.get("commit_message")
    if commit_message:
        lines.append(f"Message: {commit_message}")

    if isinstance(new_state, Mapping):
        if new_state.get("access_jsonl"):
            lines.append(f"ACCESS log: {new_state['access_jsonl']}")
        if new_state.get("version_token"):
            lines.append(f"Version token: {new_state['version_token']}")

    warnings = payload.get("warnings")
    if isinstance(warnings, Sequence) and warnings:
        lines.append("")
        lines.append("Warnings:")
        for warning in warnings:
            lines.append(f"  - {warning}")

    if not lines:
        return json.dumps(dict(payload), indent=2, default=str)
    return "\n".join(lines)
