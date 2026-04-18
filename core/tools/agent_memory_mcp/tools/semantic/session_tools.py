"""Session and governance semantic tools."""

from __future__ import annotations

import json
import os
import re
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Any, cast

from ...identity_paths import (
    normalize_user_id,
    resolve_working_scratchpad_target,
    working_file_path,
)
from ...path_policy import (
    KNOWN_COMMIT_PREFIXES,
    namespace_session_id,
    resolve_repo_path,
    session_id_day_key,
    session_id_user_id,
    validate_session_id,
    validate_slug,
)
from ...preview_contract import (
    attach_approval_requirement,
    attach_preview_requirement,
    build_governed_preview,
    preview_target,
    require_approval_token,
    require_preview_token,
)
from ...session_state import SessionState
from ...tool_schemas import ACCESS_MODES, REVIEW_PRIORITIES

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def _tool_annotations(**kwargs: object) -> Any:
    return cast(Any, kwargs)


_ACCESS_ROOTS = (
    "memory/users",
    "memory/knowledge",
    "memory/skills",
    "memory/working/projects",
    "memory/activity",
)
_ACCESS_TASK_ID_MANIFEST = PurePosixPath("HUMANS/tooling/agent-memory-capabilities.toml")
_ACCESS_SCANS_FILENAME = "ACCESS_SCANS.jsonl"
_CATEGORY_CODE_RE = re.compile(r"`([a-z0-9]+(?:-[a-z0-9]+)*)`")
_CATEGORY_LIST_RE = re.compile(r"^(?:[-*]|\d+\.)\s+([a-z0-9]+(?:-[a-z0-9]+)*)\s*$")
_CURRENT_SESSION_SENTINEL = PurePosixPath("memory/activity/CURRENT_SESSION")
_DIALOGUE_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_REVIEW_QUEUE_HEADING_RE = re.compile(
    r"(?m)^### (?:\[(?P<date>\d{4}-\d{2}-\d{2})\] (?P<title>.+)|(?P<legacy_date>\d{4}-\d{2}-\d{2}) — (?P<legacy_title>.+))$"
)
_REVIEW_QUEUE_FIELD_RE = re.compile(r"(?m)^\*\*(.+?):\*\*\s*(.+)$")
_REVERT_ALLOWED_ROOTS = (
    "memory/users",
    "memory/knowledge",
    "memory/skills",
    "memory/working",
    "memory/activity",
    "governance",
)
_REVERT_ALLOWED_FILES = frozenset({"CHANGELOG.md"})
_REVERT_SYSTEM_ROOTS = ("governance",)
_REVERT_SYSTEM_FILES = frozenset(
    {"AGENTS.md", "CHANGELOG.md", "CLAUDE.md", "README.md", "agent-bootstrap.toml"}
)
_PERIODIC_REVIEW_STAGE_SETTINGS: dict[str, dict[str, str | int]] = {
    "Exploration": {
        "Low-trust retirement threshold": 120,
        "Medium-trust flagging threshold": 180,
        "Staleness trigger (no access)": 120,
        "Aggregation trigger": 15,
        "Identity churn alarm": 5,
        "Knowledge flooding alarm": 5,
        "Task similarity method": "Session co-occurrence",
        "Cluster co-retrieval threshold": 3,
    },
    "Calibration": {
        "Low-trust retirement threshold": 60,
        "Medium-trust flagging threshold": 120,
        "Staleness trigger (no access)": 90,
        "Aggregation trigger": 20,
        "Identity churn alarm": 3,
        "Knowledge flooding alarm": 3,
        "Task similarity method": "Task-string normalization",
        "Cluster co-retrieval threshold": 3,
    },
    "Consolidation": {
        "Low-trust retirement threshold": 45,
        "Medium-trust flagging threshold": 90,
        "Staleness trigger (no access)": 60,
        "Aggregation trigger": 25,
        "Identity churn alarm": 2,
        "Knowledge flooding alarm": 2,
        "Task similarity method": "Controlled category vocabulary",
        "Cluster co-retrieval threshold": 4,
    },
}


def _resolve_governance_rel(root: Path, relative_path: str) -> str:
    """Prefer current core/governance paths but keep legacy fallback support."""
    current = f"core/governance/{relative_path}"
    if (root / current).exists():
        return current
    return f"governance/{relative_path}"


def _resolve_live_router_rel(root: Path) -> str:
    """Prefer core/INIT.md, fall back to legacy core/HOME.md or root HOME.md."""
    if (root / "core" / "INIT.md").exists():
        return "core/INIT.md"
    if (root / "INIT.md").exists():
        return "INIT.md"
    if (root / "core" / "HOME.md").exists():
        return "core/HOME.md"
    if (root / "HOME.md").exists():
        return "HOME.md"
    return "core/INIT.md"


def _access_jsonl_for(rel_path: str) -> str | None:
    # Special case: knowledge/_unverified gets its own ACCESS.jsonl
    if (
        rel_path.startswith("memory/knowledge/_unverified/")
        or rel_path == "memory/knowledge/_unverified"
    ):
        return "memory/knowledge/_unverified/ACCESS.jsonl"
    for root in _ACCESS_ROOTS:
        if rel_path == root or rel_path.startswith(root + "/"):
            return f"{root}/ACCESS.jsonl"
    return None


def _load_task_categories(root: Path) -> set[str]:
    categories_path = root / _resolve_governance_rel(root, "task-categories.md")
    if not categories_path.exists():
        return set()

    text = categories_path.read_text(encoding="utf-8")
    categories = set(_CATEGORY_CODE_RE.findall(text))
    if categories:
        return categories

    for line in text.splitlines():
        stripped = line.strip()
        match = _CATEGORY_LIST_RE.match(stripped)
        if match:
            categories.add(match.group(1))
    return categories


def _load_access_task_ids(root: Path) -> set[str]:
    manifest_path = None
    for candidate in (root / _ACCESS_TASK_ID_MANIFEST, root.parent / _ACCESS_TASK_ID_MANIFEST):
        if candidate.exists():
            manifest_path = candidate
            break
    if manifest_path is None:
        return set()

    try:
        import tomllib

        data = tomllib.loads(manifest_path.read_text(encoding="utf-8"))
    except ModuleNotFoundError:  # pragma: no cover - Python < 3.11 fallback
        import tomli  # type: ignore[import-not-found]

        data = tomli.loads(manifest_path.read_text(encoding="utf-8"))
    access_logging = data.get("access_logging")
    if not isinstance(access_logging, dict):
        return set()
    task_ids = access_logging.get("task_ids")
    if not isinstance(task_ids, list):
        return set()
    return {str(task_id).strip() for task_id in task_ids if str(task_id).strip()}


def _normalize_min_helpfulness(min_helpfulness: object) -> float | None:
    from ...errors import ValidationError

    if min_helpfulness is None:
        return None
    if not isinstance(min_helpfulness, (int, float)):
        raise ValidationError("min_helpfulness must be a float between 0.0 and 1.0")
    threshold = float(min_helpfulness)
    if not (0.0 <= threshold <= 1.0):
        raise ValidationError(f"min_helpfulness must be between 0.0 and 1.0, got {threshold}")
    return threshold


def _access_scans_jsonl_for(access_jsonl: str) -> str:
    access_path = PurePosixPath(access_jsonl)
    parent = access_path.parent.as_posix()
    if parent == ".":
        return _ACCESS_SCANS_FILENAME
    return f"{parent}/{_ACCESS_SCANS_FILENAME}"


def _append_markdown_block(existing: str, block: str) -> str:
    trimmed_existing = existing.rstrip()
    trimmed_block = block.strip()
    if not trimmed_block:
        return existing
    if not trimmed_existing:
        return trimmed_block + "\n"
    return trimmed_existing + "\n\n---\n\n" + trimmed_block + "\n"


def _compute_trace_metrics(root: "Path", session_id: str) -> dict[str, object] | None:
    """Read session trace file and return a metrics dict, or None if unavailable."""
    import json as _json

    from ...plan_utils import trace_file_path

    abs_trace = root / trace_file_path(session_id)
    if not abs_trace.exists():
        return None

    tool_calls = 0
    plan_actions = 0
    retrievals = 0
    errors = 0
    total_duration_ms = 0
    verification_passes = 0
    verification_failures = 0

    try:
        for line in abs_trace.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                span = _json.loads(line)
            except _json.JSONDecodeError:
                continue
            stype = span.get("span_type", "")
            sstatus = span.get("status", "")
            if stype == "tool_call":
                tool_calls += 1
            elif stype == "plan_action":
                plan_actions += 1
            elif stype == "retrieval":
                retrievals += 1
            elif stype == "verification":
                meta = span.get("metadata") or {}
                verification_passes += int(meta.get("passed", 0))
                verification_failures += int(meta.get("failed", 0))
            if sstatus == "error":
                errors += 1
            total_duration_ms += span.get("duration_ms") or 0
    except OSError:
        return None

    return {
        "tool_calls": tool_calls,
        "plan_actions": plan_actions,
        "retrievals": retrievals,
        "errors": errors,
        "total_duration_ms": total_duration_ms,
        "verification_passes": verification_passes,
        "verification_failures": verification_failures,
    }


def _build_chat_summary_content(
    session_id: str,
    summary: str,
    key_topics: str = "",
    root: "Path | None" = None,
    recorded_date: str | None = None,
    session_metrics: dict[str, object] | None = None,
    user_id: str | None = None,
) -> str:
    from ...frontmatter_utils import today_str

    today = recorded_date or today_str()
    fm_dict: dict[str, object] = {
        "session": session_id,
        "date": today,
        "trust": "medium",
        "source": "agent-generated",
    }
    if user_id is not None:
        fm_dict["user_id"] = user_id
    topics = [topic.strip() for topic in key_topics.split(",") if topic.strip()]
    if topics:
        fm_dict["key_topics"] = topics

    trace_metrics: dict[str, object] | None = None
    if root is not None:
        trace_metrics = _compute_trace_metrics(root, session_id)

    if session_metrics is not None:
        merged: dict[str, object] = dict(session_metrics)
        if trace_metrics:
            for key, value in trace_metrics.items():
                merged.setdefault(key, value)
        fm_dict["metrics"] = merged
    elif trace_metrics is not None:
        fm_dict["metrics"] = trace_metrics

    import frontmatter as fmlib  # type: ignore[import-untyped]

    post = fmlib.Post(summary, **fm_dict)
    return fmlib.dumps(post)


def _build_session_recording_state(
    session_id: str,
    summary_path: str,
    *,
    recording_outcome: str,
    reflection_path: str | None = None,
    access_jsonls: list[str] | None = None,
    user_id: str | None = None,
) -> dict[str, object]:
    state: dict[str, object] = {
        "session_id": session_id,
        "summary_path": summary_path,
        "recording_outcome": recording_outcome,
    }
    if reflection_path is not None:
        state["reflection_path"] = reflection_path
    if access_jsonls:
        state["access_jsonls"] = access_jsonls
    if user_id is not None:
        state["user_id"] = user_id
    return state


def _summary_recorded_date(abs_session_summary: Path) -> str | None:
    from ...frontmatter_utils import read_with_frontmatter

    if not abs_session_summary.exists():
        return None
    frontmatter, _ = read_with_frontmatter(abs_session_summary)
    recorded_date = frontmatter.get("date")
    if recorded_date is None:
        return None
    normalized = str(recorded_date).strip()
    return normalized or None


def _summary_metrics_from_frontmatter(abs_session_summary: Path) -> dict[str, object] | None:
    from ...frontmatter_utils import read_with_frontmatter

    if not abs_session_summary.exists():
        return None
    frontmatter, _ = read_with_frontmatter(abs_session_summary)
    metrics = frontmatter.get("metrics")
    return dict(metrics) if isinstance(metrics, dict) else None


def _existing_chat_summary_matches(
    root: Path,
    abs_session_summary: Path,
    *,
    session_id: str,
    summary: str,
    key_topics: str,
    session_metrics: dict[str, object] | None = None,
    user_id: str | None = None,
) -> bool:
    resolved_metrics = (
        session_metrics
        if session_metrics is not None
        else _summary_metrics_from_frontmatter(abs_session_summary)
    )
    expected_content = _build_chat_summary_content(
        session_id,
        summary,
        key_topics,
        root=root,
        recorded_date=_summary_recorded_date(abs_session_summary),
        session_metrics=resolved_metrics,
        user_id=user_id,
    )
    existing = abs_session_summary.read_text(encoding="utf-8")
    if existing == expected_content:
        return True
    if user_id is None:
        return False
    legacy_expected = _build_chat_summary_content(
        session_id,
        summary,
        key_topics,
        root=root,
        recorded_date=_summary_recorded_date(abs_session_summary),
        session_metrics=resolved_metrics,
        user_id=None,
    )
    return existing == legacy_expected


def _access_entry_signature(payload: dict[str, object]) -> str:
    comparable = {key: value for key, value in payload.items() if key not in {"date", "user_id"}}
    return json.dumps(comparable, sort_keys=True, ensure_ascii=False)


def _expected_access_entry_signatures(
    repo,
    root: Path,
    *,
    session_id: str,
    access_entries: list[dict[str, object]],
    user_id: str | None,
    aggregate_validation_errors: bool = False,
) -> dict[str, Counter[str]]:
    expected: dict[str, Counter[str]] = {}
    normalized_entries = _normalize_access_entries(
        repo,
        root,
        access_entries,
        session_id=session_id,
        user_id=user_id,
        aggregate_validation_errors=aggregate_validation_errors,
    )
    for access_jsonl, line, _ in normalized_entries:
        payload = json.loads(line)
        expected.setdefault(access_jsonl, Counter())[_access_entry_signature(payload)] += 1
    return expected


def _recorded_access_entry_signatures(
    abs_access: Path,
    *,
    session_id: str,
) -> Counter[str]:
    recorded: Counter[str] = Counter()
    if not abs_access.exists():
        return recorded
    for raw_line in abs_access.read_text(encoding="utf-8").splitlines():
        stripped = raw_line.strip()
        if not stripped:
            continue
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict) or payload.get("session_id") != session_id:
            continue
        recorded[_access_entry_signature(payload)] += 1
    return recorded


def _validate_replayed_access_entries(
    repo,
    root: Path,
    *,
    session_id: str,
    access_entries: list[dict[str, object]] | None,
    user_id: str | None,
) -> list[str]:
    from ...errors import ValidationError

    if not access_entries:
        return []

    expected_by_jsonl = _expected_access_entry_signatures(
        repo,
        root,
        session_id=session_id,
        access_entries=access_entries,
        user_id=user_id,
        aggregate_validation_errors=True,
    )
    for access_jsonl, expected_signatures in expected_by_jsonl.items():
        recorded_signatures = _recorded_access_entry_signatures(
            root / access_jsonl,
            session_id=session_id,
        )
        for signature, count in expected_signatures.items():
            if recorded_signatures.get(signature, 0) < count:
                raise ValidationError(
                    f"Session {session_id} is already recorded but the provided ACCESS entries do not match the existing log state. Use memory_log_access or memory_log_access_batch for additional retrieval logging."
                )
    return sorted(expected_by_jsonl)


def _update_chats_summary_index(content: str, session_id: str, recorded_date: str) -> str | None:
    if session_id in content:
        return None
    mention = f"\nSee `{session_id}/` for session recorded {recorded_date}"
    resolved_user_id = session_id_user_id(session_id)
    if resolved_user_id is not None:
        mention += f" (user `{resolved_user_id}`)"
    mention += ".\n"
    if "## Structure" in content:
        return content.replace("## Structure", mention + "\n## Structure", 1)
    return content.rstrip() + mention


def _build_reflection_content(reflection: str) -> str:
    trimmed = reflection.strip()
    if trimmed.startswith("## "):
        return trimmed + "\n"
    return "## Session reflection\n\n" + trimmed + "\n"


def _build_structured_reflection_content(
    memory_retrieved: str,
    memory_influence: str,
    outcome_quality: str,
    gaps_noticed: str,
    system_observations: str = "",
) -> str:
    lines = [
        "## Session reflection\n",
        "\n",
        f"**Memory retrieved:** {memory_retrieved}\n",
        f"**Memory influence:** {memory_influence}\n",
        f"**Outcome quality:** {outcome_quality}\n",
        f"**Gaps noticed:** {gaps_noticed}\n",
    ]
    if system_observations:
        lines.append(f"**System observations:** {system_observations}\n")
    return "".join(lines)


def _iter_dialogue_files(
    root: Path,
    *,
    sessions: list[str] | None,
    date_from: str | None,
    date_to: str | None,
) -> list[tuple[str, Path]]:
    from ...errors import ValidationError

    results: list[tuple[str, Path]] = []
    if sessions:
        for sid in sessions:
            validate_session_id(sid)
            path = root / sid / "dialogue.jsonl"
            if path.is_file():
                results.append((sid, path))
        return results

    activity = root / "memory" / "activity"
    if not activity.is_dir():
        return []
    for path in sorted(activity.rglob("dialogue.jsonl"), reverse=True):
        rel = path.relative_to(root)
        parts = rel.parts
        if len(parts) < 7 or parts[-1] != "dialogue.jsonl":
            continue
        session_id = str(PurePosixPath(*parts[:-1]).as_posix())
        try:
            file_date = session_id_day_key(session_id).replace("/", "-")
        except ValidationError:
            continue
        if date_from is not None and file_date < date_from:
            continue
        if date_to is not None and file_date > date_to:
            continue
        results.append((session_id, path))
    return results


def query_dialogue_entries(
    root: Path,
    *,
    sessions: list[str] | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    keyword: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> dict[str, Any]:
    from ...errors import ValidationError

    if date_from is not None and not _DIALOGUE_DATE_RE.fullmatch(date_from):
        raise ValidationError("date_from must be in YYYY-MM-DD format")
    if date_to is not None and not _DIALOGUE_DATE_RE.fullmatch(date_to):
        raise ValidationError("date_to must be in YYYY-MM-DD format")
    if limit < 1:
        raise ValidationError("limit must be >= 1")
    if offset < 0:
        raise ValidationError("offset must be >= 0")

    kw = keyword.strip().lower() if isinstance(keyword, str) and keyword.strip() else None
    collected: list[dict[str, Any]] = []
    for session_id, path in _iter_dialogue_files(
        root, sessions=sessions, date_from=date_from, date_to=date_to
    ):
        try:
            raw_lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for line in raw_lines:
            stripped = line.strip()
            if not stripped:
                continue
            try:
                row = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            if not isinstance(row, dict):
                continue
            first_line = str(row.get("first_line") or "")
            if kw is not None and kw not in first_line.lower():
                continue
            collected.append({"session_id": session_id, **row})

    collected.sort(key=lambda item: str(item.get("timestamp") or ""), reverse=True)
    total_matched = len(collected)
    page = collected[offset : offset + limit]
    return {
        "entries": page,
        "total_matched": total_matched,
        "limit": limit,
        "offset": offset,
    }


def _resolve_session_id_for_user(session_id: str, user_id: str | None) -> str:
    return namespace_session_id(validate_session_id(session_id), user_id=user_id)


def _current_session_sentinel_paths(user_id: str | None) -> list[PurePosixPath]:
    if user_id is None:
        return [_CURRENT_SESSION_SENTINEL]
    return [
        PurePosixPath("memory/activity") / user_id / "CURRENT_SESSION",
        _CURRENT_SESSION_SENTINEL,
    ]


def _resolve_access_session_id(
    root: Path,
    session_id: str | None,
    *,
    user_id: str | None,
) -> str | None:
    if session_id is not None:
        return _resolve_session_id_for_user(session_id, user_id)

    env_session_id = os.environ.get("MEMORY_SESSION_ID", "").strip()
    if env_session_id:
        return _resolve_session_id_for_user(env_session_id, user_id)

    for sentinel_rel in _current_session_sentinel_paths(user_id):
        sentinel_path = root / sentinel_rel
        if not sentinel_path.exists():
            continue

        sentinel_session_id = sentinel_path.read_text(encoding="utf-8").strip()
        if not sentinel_session_id:
            continue
        return _resolve_session_id_for_user(sentinel_session_id, user_id)
    return None


def _resolved_user_id(session_state: SessionState | None) -> str | None:
    if session_state is None:
        return None
    return normalize_user_id(session_state.user_id)


def _normalize_access_entry(
    repo,
    root: Path,
    raw_entry: object,
    *,
    resolved_session_id: str | None,
    resolved_user_id: str | None,
) -> tuple[str, str, bool]:
    import json as _json

    from ...errors import ValidationError
    from ...frontmatter_utils import today_str

    if not isinstance(raw_entry, dict):
        raise ValidationError("access_entries must contain objects with file/task/helpfulness/note")

    file_value = raw_entry.get("file")
    task_value = raw_entry.get("task")
    helpfulness_value = raw_entry.get("helpfulness")
    note_value = raw_entry.get("note")
    category_value = raw_entry.get("category")
    mode_value = raw_entry.get("mode")
    task_id_value = raw_entry.get("task_id")
    estimator_value = raw_entry.get("estimator")
    min_helpfulness_value = raw_entry.get("min_helpfulness")

    if not isinstance(task_value, str) or not task_value.strip():
        raise ValidationError("access entry task must be a non-empty string")
    if not isinstance(note_value, str) or not note_value.strip():
        raise ValidationError("access entry note must be a non-empty string")
    if not isinstance(helpfulness_value, (int, float)):
        raise ValidationError("access entry helpfulness must be a float between 0.0 and 1.0")
    helpfulness = float(helpfulness_value)
    if not (0.0 <= helpfulness <= 1.0):
        raise ValidationError(
            f"access entry helpfulness must be between 0.0 and 1.0, got {helpfulness}"
        )

    if not isinstance(file_value, str) or not file_value.strip():
        raise ValidationError("access entry file must be a non-empty repo-relative path")
    file_path, _ = resolve_repo_path(repo, file_value, field_name="file")
    access_jsonl = _access_jsonl_for(file_path)
    if access_jsonl is None:
        raise ValidationError(
            f"Cannot log access for '{file_path}': not under an access-tracked directory. Supported roots: {sorted(_ACCESS_ROOTS)}"
        )

    if category_value is not None:
        category = validate_slug(str(category_value), field_name="category")
        categories = _load_task_categories(root)
        if not categories:
            raise ValidationError(
                "category cannot be set until the controlled vocabulary file exists in governance/task-categories.md"
            )
        if category not in categories:
            raise ValidationError(f"category must be one of {sorted(categories)}, got: {category}")
    else:
        category = None

    if mode_value is not None:
        if not isinstance(mode_value, str) or not mode_value.strip():
            raise ValidationError("access entry mode must be a non-empty string when provided")
        mode = mode_value.strip()
        if mode not in ACCESS_MODES:
            raise ValidationError(
                f"access entry mode must be one of {sorted(ACCESS_MODES)}, got: {mode}"
            )
    else:
        mode = None

    if task_id_value is not None:
        task_id = validate_slug(str(task_id_value), field_name="task_id")
        task_ids = _load_access_task_ids(root)
        if not task_ids:
            raise ValidationError(
                "task_id cannot be set until HUMANS/tooling/agent-memory-capabilities.toml defines access_logging.task_ids"
            )
        if task_id not in task_ids:
            raise ValidationError(f"task_id must be one of {sorted(task_ids)}, got: {task_id}")
    else:
        task_id = None

    if estimator_value is not None:
        if not isinstance(estimator_value, str) or not estimator_value.strip():
            raise ValidationError("access entry estimator must be a non-empty string when provided")
        estimator = validate_slug(estimator_value, field_name="estimator")
    else:
        estimator = None

    min_helpfulness = _normalize_min_helpfulness(min_helpfulness_value)

    entry: dict[str, object] = {
        "event_type": "retrieval",
        "file": file_path,
        "date": today_str(),
        "task": task_value.strip(),
        "helpfulness": round(helpfulness, 2),
        "note": note_value.strip(),
    }
    if resolved_session_id is not None:
        entry["session_id"] = resolved_session_id
    if resolved_user_id is not None:
        entry["user_id"] = resolved_user_id
    if category is not None:
        entry["category"] = category
    if mode is not None:
        entry["mode"] = mode
    if task_id is not None:
        entry["task_id"] = task_id
    if estimator is not None:
        entry["estimator"] = estimator
    routed_to_scans = min_helpfulness is not None and helpfulness < min_helpfulness
    target_jsonl = _access_scans_jsonl_for(access_jsonl) if routed_to_scans else access_jsonl
    return target_jsonl, _json.dumps(entry, ensure_ascii=False), routed_to_scans


def _access_entry_label(raw_entry: object, index: int) -> str:
    if isinstance(raw_entry, dict):
        file_value = raw_entry.get("file")
        if isinstance(file_value, str) and file_value.strip():
            return file_value.strip()
    return f"access_entries[{index}]"


def _normalize_access_entries(
    repo,
    root: Path,
    access_entries: list[dict[str, object]],
    *,
    session_id: str | None,
    user_id: str | None,
    aggregate_validation_errors: bool = False,
) -> list[tuple[str, str, bool]]:
    from ...errors import ValidationError

    normalized_entries: list[tuple[str, str, bool]] = []
    validation_errors: list[str] = []
    for index, raw_entry in enumerate(access_entries):
        try:
            normalized_entries.append(
                _normalize_access_entry(
                    repo,
                    root,
                    raw_entry,
                    resolved_session_id=session_id,
                    resolved_user_id=user_id,
                )
            )
        except ValidationError as exc:
            if not aggregate_validation_errors:
                raise
            validation_errors.append(f"{_access_entry_label(raw_entry, index)}: {exc}")

    if validation_errors:
        joined = "\n".join(f"- {message}" for message in validation_errors)
        raise ValidationError(f"ACCESS entry validation failed:\n{joined}")

    return normalized_entries


def _append_access_entries(
    repo,
    root: Path,
    access_entries: list[dict[str, object]] | None,
    *,
    session_id: str | None,
    user_id: str | None,
    aggregate_validation_errors: bool = False,
) -> tuple[list[str], int]:
    if not access_entries:
        return [], 0

    grouped: dict[str, list[str]] = {}
    scan_entry_count = 0
    normalized_entries = _normalize_access_entries(
        repo,
        root,
        access_entries,
        session_id=session_id,
        user_id=user_id,
        aggregate_validation_errors=aggregate_validation_errors,
    )
    for access_jsonl, line, routed_to_scans in normalized_entries:
        grouped.setdefault(access_jsonl, []).append(line)
        if routed_to_scans:
            scan_entry_count += 1

    changed_files: list[str] = []
    for access_jsonl, lines in grouped.items():
        abs_access = root / access_jsonl
        abs_access.parent.mkdir(parents=True, exist_ok=True)
        existing = abs_access.read_text(encoding="utf-8") if abs_access.exists() else ""
        payload = "\n".join(lines)
        updated = (
            existing.rstrip("\n") + "\n" + payload + "\n" if existing.strip() else payload + "\n"
        )
        abs_access.write_text(updated, encoding="utf-8")
        repo.add(access_jsonl)
        changed_files.append(access_jsonl)
    return changed_files, scan_entry_count


def _aggregation_summary_folder_for_file(file_path: str) -> str:
    """Map memory/skills/<slug>/SKILL.md to memory/skills for SUMMARY aggregation."""
    path = PurePosixPath(str(file_path))
    parts = path.parts
    if (
        len(parts) >= 4
        and parts[0] == "memory"
        and parts[1] == "skills"
        and path.name == "SKILL.md"
    ):
        return "memory/skills"
    return path.parent.as_posix()


def _normalize_aggregation_folders(folders: list[str] | None) -> list[str] | None:
    from ...errors import ValidationError

    if folders is None:
        return None
    if not isinstance(folders, list) or not all(isinstance(item, str) for item in folders):
        raise ValidationError("folders must be a list of repo folder prefixes")

    normalized: list[str] = []
    allowed = {
        "memory/users",
        "memory/knowledge",
        "memory/knowledge/_unverified",
        "memory/skills",
        "memory/working/projects",
        "memory/activity",
    }
    for raw_folder in folders:
        folder = raw_folder.strip().rstrip("/")
        if folder not in allowed:
            raise ValidationError(f"Unsupported aggregation folder: {raw_folder}")
        if folder not in normalized:
            normalized.append(folder)
    return normalized


def _filter_aggregation_entries(
    entries: list[dict[str, Any]],
    folders: list[str] | None,
) -> list[dict[str, Any]]:
    if folders is None:
        return entries

    filtered: list[dict[str, Any]] = []
    for entry in entries:
        access_file = str(entry.get("_access_file", ""))
        folder = access_file.rsplit("/", 1)[0] if "/" in access_file else ""
        if folder in folders:
            filtered.append(entry)
    return filtered


def _build_aggregation_session_groups(
    entries: list[dict[str, Any]],
) -> tuple[dict[str, set[str]], int]:
    groups: dict[str, set[str]] = {}
    legacy_fallback_entries = 0
    for entry in entries:
        file_path = entry.get("file")
        if not file_path:
            continue
        session_id = entry.get("session_id")
        if session_id:
            group_id = str(session_id)
        else:
            legacy_fallback_entries += 1
            group_id = f"legacy:{entry.get('date', 'unknown')}"
        groups.setdefault(group_id, set()).add(str(file_path))
    return groups, legacy_fallback_entries


def _build_phase1_clusters(
    entries: list[dict[str, Any]],
    threshold: int,
) -> tuple[list[dict[str, Any]], int, int]:
    session_groups, legacy_fallback_entries = _build_aggregation_session_groups(entries)
    pair_sessions: dict[tuple[str, str], set[str]] = {}

    for group_id, group_files in session_groups.items():
        ordered_files = sorted(group_files)
        for index, left in enumerate(ordered_files):
            for right in ordered_files[index + 1 :]:
                pair_sessions.setdefault((left, right), set()).add(group_id)

    adjacency: dict[str, set[str]] = {}
    for (left, right), supporting_groups in pair_sessions.items():
        if len(supporting_groups) < threshold:
            continue
        adjacency.setdefault(left, set()).add(right)
        adjacency.setdefault(right, set()).add(left)

    maximal_cliques: list[set[str]] = []

    def bron_kerbosch(r_set: set[str], p_set: set[str], x_set: set[str]) -> None:
        if not p_set and not x_set:
            if len(r_set) >= 3:
                maximal_cliques.append(set(r_set))
            return

        for node in list(p_set):
            bron_kerbosch(
                r_set | {node},
                p_set & adjacency.get(node, set()),
                x_set & adjacency.get(node, set()),
            )
            p_set.remove(node)
            x_set.add(node)

    bron_kerbosch(set(), set(adjacency), set())

    clusters: list[dict[str, Any]] = []
    seen: set[tuple[str, ...]] = set()
    for clique in maximal_cliques:
        clique_files = sorted(clique)
        folders = sorted({PurePosixPath(file_path).parent.as_posix() for file_path in clique_files})
        if len(folders) < 2:
            continue
        key = tuple(clique_files)
        if key in seen:
            continue
        seen.add(key)

        pair_counts: list[int] = []
        supporting_session_groups: set[str] = set()
        for index, left in enumerate(clique_files):
            for right in clique_files[index + 1 :]:
                sessions = (
                    pair_sessions.get((left, right)) or pair_sessions.get((right, left)) or set()
                )
                pair_counts.append(len(sessions))
                supporting_session_groups.update(sessions)
        clusters.append(
            {
                "files": clique_files,
                "folders": folders,
                "co_retrieval_count": min(pair_counts) if pair_counts else 0,
                "session_groups": sorted(supporting_session_groups),
            }
        )

    clusters.sort(key=lambda item: (-int(item["co_retrieval_count"]), item["files"]))
    return clusters, len(session_groups), legacy_fallback_entries


def _render_usage_patterns_section(
    *,
    folder: str,
    entries: list[dict[str, Any]],
    clusters: list[dict[str, Any]],
    aggregation_date: str,
    legacy_fallback_entries: int,
) -> str:
    from ..read_tools._helpers import _summarize_access_by_file

    file_summaries = _summarize_access_by_file(entries)
    high_value_files = [
        item
        for item in file_summaries
        if int(item["entry_count"]) >= 5
        and item["mean_helpfulness"] is not None
        and float(item["mean_helpfulness"]) >= 0.7
    ]
    low_value_files = [
        item
        for item in file_summaries
        if int(item["entry_count"]) >= 3
        and item["mean_helpfulness"] is not None
        and float(item["mean_helpfulness"]) <= 0.3
    ]
    relevant_clusters = [
        cluster for cluster in clusters if folder in cast(list[str], cluster["folders"])
    ]
    session_groups, _ = _build_aggregation_session_groups(entries)

    high_line = (
        "; ".join(
            f"{item['file']} ({item['entry_count']} retrievals, mean {item['mean_helpfulness']})"
            for item in high_value_files
        )
        if high_value_files
        else "none."
    )
    low_line = (
        "; ".join(
            f"{item['file']} ({item['entry_count']} retrievals, mean {item['mean_helpfulness']})"
            for item in low_value_files
        )
        if low_value_files
        else "none."
    )
    cluster_line = (
        "; ".join(
            f"{' + '.join(cast(list[str], cluster['files']))} ({cluster['co_retrieval_count']} session groups)"
            for cluster in relevant_clusters
        )
        if relevant_clusters
        else "none."
    )

    lines = [
        "## Usage patterns",
        "",
        f"- Last aggregation: {aggregation_date}",
        f"- Entries processed: {len(entries)}",
        f"- Session groups processed: {len(session_groups)}",
        f"- High-value files: {high_line}",
        f"- Low-value files: {low_line}",
        f"- Co-retrieval clusters: {cluster_line}",
    ]
    if legacy_fallback_entries:
        lines.append(
            f"- Legacy fallback entries: {legacy_fallback_entries} entries lacked session_id and were grouped by date."
        )
    return "\n".join(lines).rstrip() + "\n"


def _replace_usage_patterns_section(content: str, new_section: str) -> str:
    match = re.search(r"(?m)^## Usage patterns\s*$", content)
    if match is None:
        return content.rstrip() + "\n\n" + new_section

    start = match.start()
    following = re.search(r"(?m)^## ", content[match.end() :])
    end = match.end() + following.start() if following else len(content)
    prefix = content[:start].rstrip()
    suffix = content[end:].lstrip("\n")
    rebuilt = prefix + "\n\n" + new_section.rstrip() + "\n"
    if suffix:
        rebuilt += "\n" + suffix
    return rebuilt


def _archive_segment_name(entries: list[dict[str, Any]]) -> str:
    dates = sorted(str(entry.get("date", "")) for entry in entries if entry.get("date"))
    source_date = dates[-1] if dates else str(date.today())
    return f"ACCESS.archive.{source_date[:7]}.jsonl"


def _archive_target_for_access_file(access_file: str, entries: list[dict[str, Any]]) -> str:
    return f"{access_file.rsplit('/', 1)[0]}/{_archive_segment_name(entries)}"


def _resolve_scratchpad_target(target: str, *, user_id: str | None) -> str:
    return resolve_working_scratchpad_target(target, user_id=user_id)


def _format_checkpoint_entry(
    content: str,
    *,
    label: str = "",
    session_id: str = "",
    user_id: str = "",
) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M")
    label_text = label.strip()
    heading = f"### [{timestamp}] {label_text}".rstrip()
    lines = [heading]
    if session_id:
        lines.append(f"<!-- session_id: {session_id} -->")
    if user_id:
        lines.append(f"<!-- user_id: {user_id} -->")
    body = content.strip()
    if body:
        lines.append(body)
    return "\n".join(lines).rstrip() + "\n"


def _count_checkpoint_entries(content: str) -> int:
    return len(re.findall(r"(?m)^### \[\d{4}-\d{2}-\d{2}T\d{2}:\d{2}\](?: .*)?$", content))


def _build_compaction_flush_commit_message(summary: str, *, label: str, trigger: str) -> str:
    descriptor = label.strip()
    if not descriptor:
        descriptor = next((line.strip() for line in summary.splitlines() if line.strip()), "")
    if not descriptor:
        descriptor = trigger.replace("_", " ")
    if len(descriptor) > 72:
        descriptor = descriptor[:69].rstrip() + "..."
    return f"[chat] Context-pressure flush - {descriptor}"


def _review_item_slug(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return normalized or "review-item"


def _build_review_item_id(review_date: str, title: str) -> str:
    return f"{review_date}-{_review_item_slug(title)}"


def _split_review_queue_sections(content: str) -> tuple[str, str]:
    match = re.search(r"(?m)^## Resolved\s*$", content)
    if match is None:
        return content, ""
    return content[: match.start()], content[match.start() :]


def _parse_review_queue_blocks(content: str) -> tuple[str, list[dict[str, str]]]:
    matches = list(_REVIEW_QUEUE_HEADING_RE.finditer(content))
    if not matches:
        return content, []

    prefix = content[: matches[0].start()]
    blocks: list[dict[str, str]] = []
    for index, match in enumerate(matches):
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(content)
        raw_block = content[start:end].strip()
        review_date = match.group("date") or match.group("legacy_date") or ""
        title = (match.group("title") or match.group("legacy_title") or "").strip()
        fields = {
            field_match.group(1).strip().lower().replace(" ", "_"): field_match.group(2).strip()
            for field_match in _REVIEW_QUEUE_FIELD_RE.finditer(raw_block)
        }
        item_id = fields.get("item_id", _build_review_item_id(review_date, title))
        blocks.append(
            {
                "date": review_date,
                "title": title,
                "item_id": item_id,
                "raw": raw_block,
            }
        )
    return prefix, blocks


def _render_review_queue(prefix: str, pending_blocks: list[str], resolved_section: str) -> str:
    cleaned_prefix = re.sub(r"(?m)^_No pending items\._\s*$\n?", "", prefix).rstrip()
    sections: list[str] = []
    if cleaned_prefix:
        sections.append(cleaned_prefix)
    if pending_blocks:
        sections.append("\n\n---\n\n".join(block.strip() for block in pending_blocks))
    else:
        sections.append("_No pending items._")
    rendered = "\n\n".join(section for section in sections if section).rstrip() + "\n"
    if resolved_section.strip():
        rendered += "\n" + resolved_section.strip() + "\n"
    return rendered


def _append_review_resolution(
    resolved_section: str,
    *,
    resolved_on: str,
    item_id: str,
    resolution_note: str | None,
) -> str:
    entry = f"- {resolved_on} — {item_id}"
    if resolution_note and resolution_note.strip():
        entry += f": {resolution_note.strip()}"
    if resolved_section.strip():
        return resolved_section.rstrip() + "\n" + entry + "\n"
    return "## Resolved\n\n" + entry + "\n"


def _update_last_periodic_review_date(content: str, review_date: str) -> str | None:
    updated = re.sub(
        r"(## Last periodic review\s*\n\s*\n\*\*Date:\*\*\s*)([^\n]+)",
        rf"\g<1>{review_date}",
        content,
        count=1,
    )
    return updated if updated != content else None


def _update_current_stage_block(
    content: str,
    review_date: str,
    active_stage: str,
    assessment_summary: str,
) -> str:
    settings = _PERIODIC_REVIEW_STAGE_SETTINGS[active_stage]
    updated = re.sub(
        r"(?m)^## Current active stage:\s*.+$",
        f"## Current active stage: {active_stage}",
        content,
        count=1,
    )
    assessed_line = f"_Last assessed: {review_date} — {assessment_summary}_"
    if re.search(r"(?m)^_Last assessed: .*_$", updated):
        updated = re.sub(r"(?m)^_Last assessed: .*_$", assessed_line, updated, count=1)
    else:
        updated = updated.replace(
            f"## Current active stage: {active_stage}\n",
            f"## Current active stage: {active_stage}\n\n{assessed_line}\n",
            1,
        )

    for label, value in settings.items():
        value_str = f"{value} entries" if label == "Aggregation trigger" else str(value)
        if label in {
            "Low-trust retirement threshold",
            "Medium-trust flagging threshold",
            "Staleness trigger (no access)",
        }:
            value_str = f"{value} days"
        if label in {"Identity churn alarm", "Knowledge flooding alarm"}:
            value_str = (
                f"{value} traits/session"
                if label == "Identity churn alarm"
                else f"{value} files/day"
            )
        if label == "Cluster co-retrieval threshold":
            value_str = f"{value} sessions"
        updated = re.sub(
            rf"(?m)^\| {re.escape(label)} \| .* \| .* \|$",
            f"| {label} | {value_str} | {active_stage} |",
            updated,
            count=1,
        )

    updated = re.sub(
        r"(?m)^\*\*Method:\*\*\s*.+$",
        f"**Method:** {settings['Task similarity method']}",
        updated,
        count=1,
    )
    return updated


def _is_revertable_memory_path(rel_path: str) -> bool:
    if not rel_path:
        return False
    if rel_path in _REVERT_ALLOWED_FILES:
        return True
    for root in _REVERT_ALLOWED_ROOTS:
        if rel_path == root or rel_path.startswith(root + "/"):
            return True
    return False


def _is_revertable_system_path(rel_path: str) -> bool:
    if not rel_path:
        return False
    if rel_path in _REVERT_SYSTEM_FILES:
        return True
    for root in _REVERT_SYSTEM_ROOTS:
        if rel_path == root or rel_path.startswith(root + "/"):
            return True
    return False


def _build_revert_preview(repo, sha: str) -> dict[str, object]:
    from ...errors import ValidationError

    try:
        commit = repo.inspect_commit(sha)
    except Exception as exc:
        raise ValidationError(f"Commit not found or not inspectable: {sha}") from exc

    resolved_sha = str(commit["sha"])
    message = str(commit["message"])
    parents = [str(parent) for parent in cast(list[object], commit["parents"])]
    files_changed = [str(path) for path in cast(list[object], commit["files_changed"])]

    prefix_match = re.match(r"^\[[^\]]+\]", message)
    prefix = prefix_match.group(0) if prefix_match else None
    if prefix == "[system]":
        disallowed_files = [
            path
            for path in files_changed
            if not (_is_revertable_memory_path(path) or _is_revertable_system_path(path))
        ]
    else:
        disallowed_files = [path for path in files_changed if not _is_revertable_memory_path(path)]
    disallowed_system_files = (
        [path for path in files_changed if not _is_revertable_system_path(path)]
        if prefix == "[system]"
        else []
    )
    preview_status = repo.revert_preview_status(resolved_sha)
    applies_cleanly = bool(preview_status["applies_cleanly"])
    conflict_details = str(preview_status["details"] or "")

    reasons: list[str] = []
    if len(parents) > 1:
        reasons.append("merge commits are not supported")
    if prefix is None:
        reasons.append("commit message is missing a recognized [category] prefix")
    elif prefix not in KNOWN_COMMIT_PREFIXES:
        reasons.append(f"commit prefix {prefix!r} is not in the allowed memory prefix set")
    if disallowed_files:
        reasons.append(
            "commit touches files outside the governed memory surface: "
            + ", ".join(disallowed_files)
        )
    if disallowed_system_files:
        reasons.append(
            "[system] commits may only touch governance files: "
            + ", ".join(disallowed_system_files)
        )
    if not applies_cleanly:
        reasons.append("revert does not apply cleanly at the current HEAD")

    return {
        "resolved_sha": resolved_sha,
        "target_message": message,
        "target_prefix": prefix,
        "target_parents": parents,
        "files_changed": files_changed,
        "preview_token": repo.current_head(),
        "applies_cleanly": applies_cleanly,
        "conflict_details": conflict_details,
        "eligible": not reasons,
        "policy_reasons": reasons,
    }


def register_tools(
    mcp: "FastMCP",
    get_repo,
    get_root,
    session_state: SessionState | None = None,
) -> dict[str, object]:
    """Register session and governance semantic tools."""

    def _maybe_fast_forward_publication_base(
        repo,
        *,
        commit_sha: str | None,
        blocked_action: str,
    ) -> tuple[dict[str, object] | None, list[str]]:
        if (
            session_state is None
            or not session_state.publication_base_ref
            or not session_state.publication_session_branch_ref
            or session_state.publication_base_ref == session_state.publication_session_branch_ref
        ):
            return None, []

        try:
            merge_result = repo.fast_forward_ref(
                target_ref=session_state.publication_base_ref,
                source_ref=session_state.publication_session_branch_ref,
            )
            merge_payload = merge_result.to_dict()
        except Exception as merge_error:
            merge_payload = {
                "operation": "fast-forward",
                "status": "blocked",
                "target_ref": session_state.publication_base_ref,
                "source_ref": session_state.publication_session_branch_ref,
                "target_sha": None,
                "source_sha": commit_sha,
                "applied_sha": None,
                "reason": str(merge_error),
                "warnings": [],
            }

        merge_payload["base_branch"] = session_state.publication_base_branch
        merge_payload["session_branch"] = session_state.publication_session_branch
        merge_warnings = list(cast(list[str], merge_payload.get("warnings", [])))
        if merge_payload.get("status") == "blocked":
            merge_warnings.append(
                f"{blocked_action} was committed, but the preserved base branch was not advanced: "
                f"{merge_payload.get('reason', 'fast-forward was blocked')}"
            )
        return merge_payload, merge_warnings

    @mcp.tool(
        name="memory_checkpoint",
        annotations=_tool_annotations(
            title="Record Checkpoint",
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=False,
            openWorldHint=False,
        ),
    )
    async def memory_checkpoint(content: str, label: str = "", session_id: str = "") -> str:
        """Append a timestamped checkpoint entry to the active CURRENT.md scratchpad.

        label and session_id are optional. The write is staged but not
        committed, so use memory_tool_schema with tool_name="memory_checkpoint"
        for the full machine-readable contract.
        """
        from ...models import MemoryWriteResult

        repo = get_repo()
        root = get_root()

        if session_state is not None:
            session_state.record_tool_call()
        resolved_user_id = _resolved_user_id(session_state)
        resolved_session_id = (
            _resolve_session_id_for_user(session_id, resolved_user_id) if session_id else ""
        )

        rel_path = working_file_path("CURRENT.md", user_id=resolved_user_id)
        abs_path = root / rel_path
        abs_path.parent.mkdir(parents=True, exist_ok=True)

        existing = abs_path.read_text(encoding="utf-8") if abs_path.exists() else ""
        entry = _format_checkpoint_entry(
            content,
            label=label,
            session_id=resolved_session_id,
            user_id=resolved_user_id or "",
        )
        if existing.strip():
            new_content = existing.rstrip() + "\n\n---\n\n" + entry
        else:
            new_content = entry

        abs_path.write_text(new_content, encoding="utf-8")
        repo.add(rel_path)
        if session_state is not None:
            session_state.record_write(rel_path)
            session_state.record_checkpoint()

        result = MemoryWriteResult(
            files_changed=[rel_path],
            commit_sha=None,
            commit_message=None,
            new_state={
                "target": rel_path,
                "entry_count": _count_checkpoint_entries(new_content),
                "session_id": resolved_session_id or None,
                "user_id": resolved_user_id,
                "staged": True,
            },
        )
        return result.to_json(session_state=session_state)

    @mcp.tool(
        name="memory_session_flush",
        annotations=_tool_annotations(
            title="Record Context-Pressure Flush",
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=False,
            openWorldHint=False,
        ),
    )
    async def memory_session_flush(
        summary: str,
        session_id: str = "",
        label: str = "",
        trigger: str = "context_pressure",
    ) -> str:
        """Persist a committed mid-session checkpoint for context-pressure recovery.

        session_id resolves from the explicit argument first, then
        MEMORY_SESSION_ID, then memory/activity/CURRENT_SESSION. trigger may use
        underscores or hyphens and is normalized before validation. Call
        memory_tool_schema with tool_name="memory_session_flush" for the full
        machine-readable contract.
        """

        from ...errors import ValidationError
        from ...models import MemoryWriteResult

        repo = get_repo()
        root = get_root()

        body = summary.strip()
        if not body:
            raise ValidationError("summary must be a non-empty string")

        normalized_trigger = validate_slug(trigger.replace("_", "-"), field_name="trigger")
        resolved_user_id = _resolved_user_id(session_state)
        resolved_session_id = _resolve_access_session_id(
            root,
            session_id or None,
            user_id=resolved_user_id,
        )
        if resolved_session_id is None:
            raise ValidationError(
                "session_id is required when MEMORY_SESSION_ID and memory/activity/CURRENT_SESSION are unset"
            )
        if session_state is not None:
            session_state.record_tool_call()

        checkpoint_rel, abs_checkpoint = resolve_repo_path(
            repo,
            f"{resolved_session_id}/checkpoint.md",
            field_name="session_id",
        )
        abs_checkpoint.parent.mkdir(parents=True, exist_ok=True)

        existing = abs_checkpoint.read_text(encoding="utf-8") if abs_checkpoint.exists() else ""
        entry_label = label.strip() or "Context-pressure flush"
        entry = _format_checkpoint_entry(
            body,
            label=entry_label,
            session_id=resolved_session_id,
            user_id=resolved_user_id or "",
        )
        if existing.strip():
            new_content = existing.rstrip() + "\n\n---\n\n" + entry
        else:
            new_content = entry

        abs_checkpoint.write_text(new_content, encoding="utf-8")
        repo.add(checkpoint_rel)

        commit_msg = _build_compaction_flush_commit_message(
            body,
            label=label,
            trigger=normalized_trigger,
        )
        commit_result = repo.commit(commit_msg)
        if session_state is not None:
            session_state.record_write(checkpoint_rel)
            session_state.record_checkpoint()
            session_state.record_flush()
        merge_state, merge_warnings = _maybe_fast_forward_publication_base(
            repo,
            commit_sha=commit_result.sha,
            blocked_action="Session branch flush",
        )
        result = MemoryWriteResult.from_commit(
            files_changed=[checkpoint_rel],
            commit_result=commit_result,
            commit_message=commit_msg,
            new_state={
                "session_id": resolved_session_id,
                "checkpoint_path": checkpoint_rel,
                "entry_count": _count_checkpoint_entries(new_content),
                "trigger": normalized_trigger,
                "user_id": resolved_user_id,
            },
            warnings=merge_warnings,
        )
        if merge_state is not None:
            result.new_state["merge"] = merge_state
        return result.to_json(session_state=session_state)

    @mcp.tool(
        name="memory_append_scratchpad",
        annotations=_tool_annotations(
            title="Append to Scratchpad",
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=False,
            openWorldHint=False,
        ),
    )
    async def memory_append_scratchpad(
        target: str, content: str, section: str | None = None
    ) -> str:
        """Append content to the active USER/CURRENT scratchpad or a working note.

        target must be "user", "current", or memory/working/notes/{slug}.md.
        When section is provided, the runtime creates the H2 heading if needed
        before appending. Call memory_tool_schema with
        tool_name="memory_append_scratchpad" for the full target contract.
        """
        from ...models import MemoryWriteResult

        repo = get_repo()
        root = get_root()

        rel_path = _resolve_scratchpad_target(target, user_id=_resolved_user_id(session_state))
        abs_path = root / rel_path
        abs_path.parent.mkdir(parents=True, exist_ok=True)
        existing = abs_path.read_text(encoding="utf-8") if abs_path.exists() else ""

        if section:
            section_heading = f"## {section}"
            if section_heading in existing:
                idx = existing.index(section_heading)
                next_heading = re.search(r"\n## ", existing[idx + 1 :])
                if next_heading:
                    insert_at = idx + 1 + next_heading.start() + 1
                    new_content = (
                        existing[:insert_at] + "\n" + content.strip() + "\n" + existing[insert_at:]
                    )
                else:
                    new_content = existing.rstrip() + "\n\n" + content.strip() + "\n"
            else:
                sep = "\n\n---\n\n" if existing.strip() else ""
                new_content = existing + sep + section_heading + "\n\n" + content.strip() + "\n"
        else:
            sep = "\n\n---\n\n" if existing.strip() else ""
            new_content = existing + sep + content.strip() + "\n"

        abs_path.write_text(new_content, encoding="utf-8")
        repo.add(rel_path)
        commit_msg = f"[scratchpad] Append to {rel_path}"
        commit_result = repo.commit(commit_msg)
        merge_state, merge_warnings = _maybe_fast_forward_publication_base(
            repo,
            commit_sha=commit_result.sha,
            blocked_action="Session branch scratchpad append",
        )

        result = MemoryWriteResult.from_commit(
            files_changed=[rel_path],
            commit_result=commit_result,
            commit_message=commit_msg,
            new_state={"target": rel_path},
            warnings=merge_warnings,
        )
        if merge_state is not None:
            result.new_state["merge"] = merge_state
        return result.to_json()

    @mcp.tool(
        name="memory_record_chat_summary",
        annotations=_tool_annotations(
            title="Record Chat Session Summary",
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def memory_record_chat_summary(
        session_id: str, summary: str, key_topics: str = ""
    ) -> str:
        """Record a chat summary.

        For full session wrap-up, prefer memory_record_session so summary,
        reflection, and ACCESS writes land in a single commit. Call
        memory_tool_schema with tool_name="memory_record_chat_summary" for the
        exact session_id and key_topics contract.
        """
        from ...errors import ValidationError
        from ...frontmatter_utils import today_str
        from ...models import MemoryWriteResult

        repo = get_repo()
        root = get_root()
        warnings: list[str] = []
        resolved_user_id = _resolved_user_id(session_state)
        resolved_session_id = _resolve_session_id_for_user(session_id, resolved_user_id)

        session_summary_rel, abs_session_summary = resolve_repo_path(
            repo, f"{resolved_session_id}/SUMMARY.md", field_name="session_id"
        )
        abs_session_summary.parent.mkdir(parents=True, exist_ok=True)

        if abs_session_summary.exists():
            if not _existing_chat_summary_matches(
                root,
                abs_session_summary,
                session_id=resolved_session_id,
                summary=summary,
                key_topics=key_topics,
                user_id=resolved_user_id,
            ):
                raise ValidationError(
                    f"Session summary already exists for {resolved_session_id} with different content. Edit the existing summary directly if an update is needed."
                )
            result = MemoryWriteResult(
                files_changed=[],
                commit_sha=None,
                commit_message=None,
                new_state=_build_session_recording_state(
                    resolved_session_id,
                    session_summary_rel,
                    recording_outcome="already_recorded",
                    user_id=resolved_user_id,
                ),
                warnings=warnings,
            )
            return result.to_json()

        today = today_str()
        abs_session_summary.write_text(
            _build_chat_summary_content(
                resolved_session_id,
                summary,
                key_topics,
                root=root,
                user_id=resolved_user_id,
            ),
            encoding="utf-8",
        )
        repo.add(session_summary_rel)

        files_changed = [session_summary_rel]
        chats_summary_rel = "memory/activity/SUMMARY.md"
        abs_chats_summary = root / chats_summary_rel
        if abs_chats_summary.exists():
            chats_content = abs_chats_summary.read_text(encoding="utf-8")
            updated_chats_content = _update_chats_summary_index(
                chats_content,
                resolved_session_id,
                today,
            )
            if updated_chats_content is not None:
                abs_chats_summary.write_text(updated_chats_content, encoding="utf-8")
                repo.add(chats_summary_rel)
                files_changed.append(chats_summary_rel)

        commit_msg = f"[chat] Record summary for {resolved_session_id}"
        commit_result = repo.commit(commit_msg)
        merge_state, merge_warnings = _maybe_fast_forward_publication_base(
            repo,
            commit_sha=commit_result.sha,
            blocked_action="Session branch chat summary",
        )
        result = MemoryWriteResult.from_commit(
            files_changed=files_changed,
            commit_result=commit_result,
            commit_message=commit_msg,
            new_state=_build_session_recording_state(
                resolved_session_id,
                session_summary_rel,
                recording_outcome="recorded",
                user_id=resolved_user_id,
            ),
            warnings=warnings + merge_warnings,
        )
        if merge_state is not None:
            result.new_state["merge"] = merge_state
        return result.to_json()

    @mcp.tool(
        name="memory_flag_for_review",
        annotations=_tool_annotations(
            title="Flag File for Review",
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=False,
            openWorldHint=False,
        ),
    )
    async def memory_flag_for_review(path: str, reason: str, priority: str = "normal") -> str:
        """Add a file to the governance review queue.

        priority must be "normal" or "urgent". The tool accepts any
        repo-relative path, generates a stable queue item id, appends a pending
        entry to the governance review queue, and commits the update
        immediately.
        """
        from ...errors import ValidationError
        from ...frontmatter_utils import today_str
        from ...models import MemoryWriteResult

        repo = get_repo()
        root = get_root()
        if priority not in REVIEW_PRIORITIES:
            raise ValidationError(
                f"priority must be one of {sorted(REVIEW_PRIORITIES)}: {priority}"
            )

        review_queue_rel = _resolve_governance_rel(root, "review-queue.md")
        abs_queue = root / review_queue_rel
        if not abs_queue.exists():
            raise ValidationError(f"Review queue not found: {review_queue_rel}")

        path, _ = resolve_repo_path(repo, path, field_name="path")
        today = today_str()
        title = f"Review {path}"
        item_id = _build_review_item_id(today, title)
        entry = "\n".join(
            [
                f"### [{today}] {title}",
                f"**Item ID:** {item_id}",
                "**Type:** proposed",
                f"**File:** {path}",
                f"**Priority:** {priority}",
                f"**Reason:** {reason}",
                "**Status:** pending",
            ]
        )
        content = abs_queue.read_text(encoding="utf-8")
        pending_section, resolved_section = _split_review_queue_sections(content)
        prefix, blocks = _parse_review_queue_blocks(pending_section)
        blocks.append(
            {
                "date": today,
                "title": title,
                "item_id": item_id,
                "raw": entry,
            }
        )
        abs_queue.write_text(
            _render_review_queue(prefix, [block["raw"] for block in blocks], resolved_section),
            encoding="utf-8",
        )
        repo.add(review_queue_rel)

        commit_msg = f"[curation] Flag {path} for review ({priority})"
        commit_result = repo.commit(commit_msg)
        merge_state, merge_warnings = _maybe_fast_forward_publication_base(
            repo,
            commit_sha=commit_result.sha,
            blocked_action="Session branch review flag",
        )
        result = MemoryWriteResult.from_commit(
            files_changed=[review_queue_rel],
            commit_result=commit_result,
            commit_message=commit_msg,
            new_state={"flagged_path": path, "priority": priority, "item_id": item_id},
            warnings=merge_warnings,
        )
        if merge_state is not None:
            result.new_state["merge"] = merge_state
        return result.to_json()

    @mcp.tool(
        name="memory_resolve_review_item",
        annotations=_tool_annotations(
            title="Resolve Review Queue Item",
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=False,
            openWorldHint=False,
        ),
    )
    async def memory_resolve_review_item(
        item_id: str,
        resolution_note: str | None = None,
        version_token: str | None = None,
        preview: bool = False,
    ) -> str:
        """Resolve a pending governance review-queue item.

        item_id must be the canonical slug recorded in the queue. preview
        returns the governed preview envelope, and version_token is an optional
        optimistic-lock token for the queue file. Call memory_tool_schema with
        tool_name="memory_resolve_review_item" for the full contract.
        """
        from ...errors import NotFoundError, ValidationError
        from ...frontmatter_utils import today_str
        from ...models import MemoryWriteResult

        repo = get_repo()
        root = get_root()

        item_id = validate_slug(item_id, field_name="item_id")
        review_queue_rel = _resolve_governance_rel(root, "review-queue.md")
        abs_queue = root / review_queue_rel
        if not abs_queue.exists():
            raise NotFoundError(f"Review queue not found: {review_queue_rel}")

        repo.check_version_token(review_queue_rel, version_token)
        content = abs_queue.read_text(encoding="utf-8")
        pending_section, resolved_section = _split_review_queue_sections(content)
        prefix, blocks = _parse_review_queue_blocks(pending_section)

        remaining_blocks: list[str] = []
        matched_block: dict[str, str] | None = None
        for block in blocks:
            if block["item_id"] == item_id:
                matched_block = block
                continue
            remaining_blocks.append(block["raw"])

        if matched_block is None:
            raise NotFoundError(f"Review queue item not found: {item_id}")

        status_match = _REVIEW_QUEUE_FIELD_RE.findall(matched_block["raw"])
        field_map = {
            key.strip().lower().replace(" ", "_"): value.strip() for key, value in status_match
        }
        if field_map.get("status") != "pending":
            raise ValidationError(f"Review queue item is not pending: {item_id}")

        updated_resolved = _append_review_resolution(
            resolved_section,
            resolved_on=today_str(),
            item_id=item_id,
            resolution_note=resolution_note,
        )
        commit_msg = f"[curation] Resolve review item: {item_id}"
        new_state = {"item_id": item_id}
        preview_payload = build_governed_preview(
            mode="preview" if preview else "apply",
            change_class="proposed",
            summary=f"Resolve pending review item {item_id}.",
            reasoning="Review-queue resolution is a proposed governance write because it removes a pending item from the active queue.",
            target_files=[preview_target(review_queue_rel, "update")],
            invariant_effects=[
                "Moves the item from the pending section to the resolved section.",
                "Appends the supplied resolution note when one is provided.",
            ],
            commit_message=commit_msg,
            resulting_state=new_state,
        )
        if preview:
            result = MemoryWriteResult(
                files_changed=[review_queue_rel],
                commit_sha=None,
                commit_message=None,
                new_state=new_state,
                preview=preview_payload,
            )
            return result.to_json()

        abs_queue.write_text(
            _render_review_queue(prefix, remaining_blocks, updated_resolved),
            encoding="utf-8",
        )
        repo.add(review_queue_rel)
        commit_result = repo.commit(commit_msg)
        merge_state, merge_warnings = _maybe_fast_forward_publication_base(
            repo,
            commit_sha=commit_result.sha,
            blocked_action="Session branch review resolve",
        )
        result = MemoryWriteResult.from_commit(
            files_changed=[review_queue_rel],
            commit_result=commit_result,
            commit_message=commit_msg,
            new_state=new_state,
            warnings=merge_warnings,
            preview=preview_payload,
        )
        if merge_state is not None:
            result.new_state["merge"] = merge_state
        return result.to_json()

    @mcp.tool(
        name="memory_log_access",
        annotations=_tool_annotations(
            title="Log Memory File Access",
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=False,
            openWorldHint=False,
        ),
    )
    async def memory_log_access(
        file: str,
        task: str,
        helpfulness: float,
        note: str,
        session_id: str | None = None,
        category: str | None = None,
        mode: str | None = None,
        task_id: str | None = None,
        estimator: str | None = None,
        min_helpfulness: float | None = None,
    ) -> str:
        """Record a single ACCESS entry and commit it immediately.

        session_id resolves from the explicit argument first, then
        MEMORY_SESSION_ID, then memory/activity/CURRENT_SESSION. category,
        mode, task_id, and estimator are optional controlled fields; use
        memory_tool_schema with tool_name="memory_log_access" for the complete
        input contract and routing semantics.
        """
        from ...models import MemoryWriteResult

        repo = get_repo()
        root = get_root()
        resolved_user_id = _resolved_user_id(session_state)
        resolved_session_id = _resolve_access_session_id(
            root,
            session_id,
            user_id=resolved_user_id,
        )
        changed_files, scan_entry_count = _append_access_entries(
            repo,
            root,
            [
                {
                    "file": file,
                    "task": task,
                    "helpfulness": helpfulness,
                    "note": note,
                    "category": category,
                    "mode": mode,
                    "task_id": task_id,
                    "estimator": estimator,
                    "min_helpfulness": min_helpfulness,
                }
            ],
            session_id=resolved_session_id,
            user_id=resolved_user_id,
        )

        commit_msg = f"[access] Log retrieval of {Path(file).name} (h={float(helpfulness):.1f})"
        commit_result = repo.commit(commit_msg)
        merge_state, merge_warnings = _maybe_fast_forward_publication_base(
            repo,
            commit_sha=commit_result.sha,
            blocked_action="Session branch access log",
        )
        result = MemoryWriteResult.from_commit(
            files_changed=changed_files,
            commit_result=commit_result,
            commit_message=commit_msg,
            new_state={
                "access_jsonl": changed_files[0],
                "entry_count": 1,
                "scan_entry_count": scan_entry_count,
            },
            warnings=merge_warnings,
        )
        if merge_state is not None:
            result.new_state["merge"] = merge_state
        return result.to_json()

    @mcp.tool(
        name="memory_log_access_batch",
        annotations=_tool_annotations(
            title="Log Memory File Access In Batch",
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=False,
            openWorldHint=False,
        ),
    )
    async def memory_log_access_batch(
        access_entries: list[dict[str, object]],
        session_id: str | None = None,
        min_helpfulness: float | None = None,
    ) -> str:
        """Log multiple ACCESS entries in one commit.

                access_entries must be a non-empty list of objects with file, task,
                helpfulness, and note.

                Optional per-entry fields:
                - category: freeform access category string
                - mode: "read" | "write" | "update" | "create"
                - task_id: optional value from the configured access_logging.task_ids set
                - estimator: optional provenance string for the helpfulness score

        Batch-level fields:
                - session_id: optional canonical session id resolved from the explicit
                    argument first, then MEMORY_SESSION_ID, then
                    memory/activity/CURRENT_SESSION; the resolved value is applied to
                    every entry
                - min_helpfulness: optional routing threshold applied to the whole
                    batch; below-threshold entries are routed to ACCESS_SCANS.jsonl

        Use memory_tool_schema for the full machine-readable entry contract.
        """
        from ...errors import ValidationError
        from ...models import MemoryWriteResult

        repo = get_repo()
        root = get_root()

        if not isinstance(access_entries, list) or not access_entries:
            raise ValidationError("access_entries must be a non-empty list of access entry objects")

        resolved_user_id = _resolved_user_id(session_state)
        resolved_session_id = _resolve_access_session_id(
            root,
            session_id,
            user_id=resolved_user_id,
        )
        threshold = _normalize_min_helpfulness(min_helpfulness)
        normalized_entries = [{**entry, "min_helpfulness": threshold} for entry in access_entries]

        changed_files, scan_entry_count = _append_access_entries(
            repo,
            root,
            normalized_entries,
            session_id=resolved_session_id,
            user_id=resolved_user_id,
            aggregate_validation_errors=True,
        )

        entry_count = len(access_entries)
        label = "entry" if entry_count == 1 else "entries"
        commit_msg = f"[access] Log {entry_count} access {label}"
        commit_result = repo.commit(commit_msg)
        merge_state, merge_warnings = _maybe_fast_forward_publication_base(
            repo,
            commit_sha=commit_result.sha,
            blocked_action="Session branch access batch",
        )
        result = MemoryWriteResult.from_commit(
            files_changed=changed_files,
            commit_result=commit_result,
            commit_message=commit_msg,
            new_state={
                "access_jsonls": changed_files,
                "entry_count": entry_count,
                "scan_entry_count": scan_entry_count,
            },
            warnings=merge_warnings,
        )
        if merge_state is not None:
            result.new_state["merge"] = merge_state
        return result.to_json()

    @mcp.tool(
        name="memory_record_session",
        annotations=_tool_annotations(
            title="Record Full Session",
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def memory_record_session(
        session_id: str,
        summary: str,
        reflection: str | None = None,
        key_topics: str = "",
        access_entries: list[dict[str, object]] | None = None,
        metrics: dict[str, object] | None = None,
        dialogue_entries: list[dict[str, object]] | None = None,
    ) -> str:
        """Record a full session in one commit.

        Required top-level fields:
        - session_id: canonical memory/activity/YYYY/MM/DD/chat-NNN id
        - summary: non-empty session summary body

        Optional top-level fields:
        - reflection: markdown text written to reflection.md
        - key_topics: summary index topics string
        - access_entries: ACCESS entries to append under the same session id
        - metrics: optional session activity metrics dict merged into SUMMARY frontmatter
        - dialogue_entries: optional compressed dialogue rows written to dialogue.jsonl

        The tool writes the session summary, optional reflection, chat index
        update, and optional ACCESS entries atomically under a single [chat]
        commit. Replaying the exact same payload for an already-recorded
        session is idempotent and returns an already_recorded state instead of
        mutating files.

        access_entries uses the same payload shape as memory_log_access_batch:
        every entry requires file, task, helpfulness, and note, with optional
        category, mode ("read" | "write" | "update" | "create"), task_id,
        and estimator fields. The outer session_id is applied to all supplied
        access entries.
        """
        from ...errors import ValidationError
        from ...frontmatter_utils import today_str
        from ...models import MemoryWriteResult

        repo = get_repo()
        root = get_root()
        resolved_user_id = _resolved_user_id(session_state)
        resolved_session_id = _resolve_session_id_for_user(session_id, resolved_user_id)

        session_summary_rel, abs_session_summary = resolve_repo_path(
            repo, f"{resolved_session_id}/SUMMARY.md", field_name="session_id"
        )
        abs_session_summary.parent.mkdir(parents=True, exist_ok=True)

        normalized_reflection = reflection.strip() if reflection is not None else ""
        reflection_rel = f"{resolved_session_id}/reflection.md"
        access_jsonls: list[str] = []

        if abs_session_summary.exists():
            if not _existing_chat_summary_matches(
                root,
                abs_session_summary,
                session_id=resolved_session_id,
                summary=summary,
                key_topics=key_topics,
                session_metrics=metrics,
                user_id=resolved_user_id,
            ):
                raise ValidationError(
                    f"Session summary already exists for {resolved_session_id} with different content. Edit the existing session files directly if an update is needed."
                )

            matching_reflection_path: str | None = None
            if normalized_reflection:
                reflection_abs = root / reflection_rel
                expected_reflection = _build_reflection_content(normalized_reflection)
                if (
                    not reflection_abs.exists()
                    or reflection_abs.read_text(encoding="utf-8") != expected_reflection
                ):
                    raise ValidationError(
                        f"Session {resolved_session_id} is already recorded but the provided reflection does not match the existing reflection.md content. Use memory_record_reflection or edit the reflection directly if an update is needed."
                    )
                matching_reflection_path = reflection_rel

            access_jsonls = _validate_replayed_access_entries(
                repo,
                root,
                session_id=resolved_session_id,
                access_entries=access_entries,
                user_id=resolved_user_id,
            )
            result = MemoryWriteResult(
                files_changed=[],
                commit_sha=None,
                commit_message=None,
                new_state=_build_session_recording_state(
                    resolved_session_id,
                    session_summary_rel,
                    recording_outcome="already_recorded",
                    reflection_path=matching_reflection_path,
                    access_jsonls=access_jsonls,
                    user_id=resolved_user_id,
                ),
            )
            return result.to_json()

        if access_entries:
            _normalize_access_entries(
                repo,
                root,
                access_entries,
                session_id=resolved_session_id,
                user_id=resolved_user_id,
                aggregate_validation_errors=True,
            )

        files_changed = [session_summary_rel]
        abs_session_summary.write_text(
            _build_chat_summary_content(
                resolved_session_id,
                summary,
                key_topics,
                root=root,
                session_metrics=metrics,
                user_id=resolved_user_id,
            ),
            encoding="utf-8",
        )
        repo.add(session_summary_rel)

        dialogue_rows = dialogue_entries or []
        if dialogue_rows:
            dialogue_rel = f"{resolved_session_id}/dialogue.jsonl"
            dialogue_abs = root / dialogue_rel
            dialogue_abs.parent.mkdir(parents=True, exist_ok=True)
            dialogue_abs.write_text(
                "\n".join(json.dumps(row, ensure_ascii=False) for row in dialogue_rows) + "\n",
                encoding="utf-8",
            )
            repo.add(dialogue_rel)
            files_changed.append(dialogue_rel)

        applied_reflection_path: str | None = None
        if normalized_reflection:
            reflection_abs = root / reflection_rel
            reflection_abs.parent.mkdir(parents=True, exist_ok=True)
            reflection_abs.write_text(
                _build_reflection_content(normalized_reflection),
                encoding="utf-8",
            )
            repo.add(reflection_rel)
            files_changed.append(reflection_rel)
            applied_reflection_path = reflection_rel

        chats_summary_rel = "memory/activity/SUMMARY.md"
        abs_chats_summary = root / chats_summary_rel
        if abs_chats_summary.exists():
            updated_chats_content = _update_chats_summary_index(
                abs_chats_summary.read_text(encoding="utf-8"),
                resolved_session_id,
                today_str(),
            )
            if updated_chats_content is not None:
                abs_chats_summary.write_text(updated_chats_content, encoding="utf-8")
                repo.add(chats_summary_rel)
                files_changed.append(chats_summary_rel)

        access_files_changed, _ = _append_access_entries(
            repo,
            root,
            access_entries,
            session_id=resolved_session_id,
            user_id=resolved_user_id,
            aggregate_validation_errors=True,
        )

        files_changed.extend(path for path in access_files_changed if path not in files_changed)

        commit_msg = f"[chat] Record session {resolved_session_id}"
        commit_result = repo.commit(commit_msg)
        merge_state, merge_warnings = _maybe_fast_forward_publication_base(
            repo,
            commit_sha=commit_result.sha,
            blocked_action="Session branch session record",
        )
        result = MemoryWriteResult.from_commit(
            files_changed=files_changed,
            commit_result=commit_result,
            commit_message=commit_msg,
            new_state=_build_session_recording_state(
                resolved_session_id,
                session_summary_rel,
                recording_outcome="recorded",
                reflection_path=applied_reflection_path,
                access_jsonls=access_files_changed,
                user_id=resolved_user_id,
            ),
            warnings=merge_warnings,
        )
        if merge_state is not None:
            result.new_state["merge"] = merge_state
        return result.to_json()

    @mcp.tool(
        name="memory_run_aggregation",
        annotations=_tool_annotations(
            title="Run ACCESS Aggregation",
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=False,
            openWorldHint=False,
        ),
    )
    async def memory_run_aggregation(
        folders: list[str] | None = None,
        dry_run: bool = True,
    ) -> str:
        """Aggregate hot ACCESS logs into summary updates and archive segments.

        Phase 1 uses session_id as the primary grouping key and falls back to
        date-based legacy grouping for older ACCESS entries that do not include
        session_id. Use dry_run=True to preview summary/archive targets before
        applying the aggregation commit. Call memory_tool_schema with
        tool_name="memory_run_aggregation" for the supported folder set and
        preview semantics.
        """
        from ...models import MemoryWriteResult

        repo = get_repo()
        root = get_root()
        selected_folders = _normalize_aggregation_folders(folders)
        default_access_folders = [
            "memory/users",
            "memory/knowledge",
            "memory/knowledge/_unverified",
            "memory/skills",
            "memory/working/projects",
            "memory/activity",
        ]

        access_files = [
            f"{folder}/ACCESS.jsonl" for folder in (selected_folders or default_access_folders)
        ]

        raw_entries: list[dict[str, Any]] = []
        entries_by_access_file: dict[str, list[dict[str, Any]]] = {}
        for access_file in access_files:
            abs_access = root / access_file
            if not abs_access.exists():
                continue
            file_entries: list[dict[str, Any]] = []
            for line in abs_access.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                entry = json.loads(line)
                if isinstance(entry, dict) and entry.get("file"):
                    file_entries.append(entry)
            normalized_entries: list[dict[str, Any]] = []
            for entry in file_entries:
                normalized = dict(entry)
                normalized["_access_file"] = access_file
                normalized_entries.append(normalized)
            if normalized_entries:
                entries_by_access_file[access_file] = normalized_entries
                raw_entries.extend(normalized_entries)

        filtered_entries = _filter_aggregation_entries(raw_entries, selected_folders)
        clusters, session_group_count, legacy_fallback_entries = _build_phase1_clusters(
            filtered_entries,
            threshold=3,
        )

        entries_by_folder: dict[str, list[dict[str, Any]]] = {}
        for entry in filtered_entries:
            folder = _aggregation_summary_folder_for_file(str(entry["file"]))
            entries_by_folder.setdefault(folder, []).append(entry)

        summary_targets = [
            f"{folder}/SUMMARY.md"
            for folder, folder_entries in sorted(entries_by_folder.items())
            if folder_entries and (root / folder / "SUMMARY.md").exists()
        ]
        hot_access_targets = sorted(
            access_file
            for access_file, entries in entries_by_access_file.items()
            if _filter_aggregation_entries(entries, selected_folders)
        )
        archive_targets = sorted(
            {
                _archive_target_for_access_file(access_file, entries)
                for access_file, entries in entries_by_access_file.items()
                if _filter_aggregation_entries(entries, selected_folders)
            }
        )

        preview_state = {
            "mode": "dry_run" if dry_run else "apply",
            "access_scope": "hot_only",
            "folders": selected_folders or sorted(entries_by_folder),
            "entries_processed": len(filtered_entries),
            "session_groups_processed": session_group_count,
            "legacy_fallback_entries": legacy_fallback_entries,
            "summary_update_targets": summary_targets,
            "summary_materialization_targets": summary_targets,
            "hot_access_targets": hot_access_targets,
            "hot_access_reset_targets": hot_access_targets,
            "archive_targets": archive_targets,
            "clusters": clusters,
        }

        if dry_run or not filtered_entries:
            result = MemoryWriteResult(
                files_changed=summary_targets + archive_targets + hot_access_targets,
                commit_sha=None,
                commit_message=None,
                new_state=preview_state,
            )
            return result.to_json()

        changed_files: list[str] = []
        aggregation_date = str(date.today())

        for summary_rel in summary_targets:
            folder = PurePosixPath(summary_rel).parent.as_posix()
            abs_summary = root / summary_rel
            updated_content = _replace_usage_patterns_section(
                abs_summary.read_text(encoding="utf-8"),
                _render_usage_patterns_section(
                    folder=folder,
                    entries=entries_by_folder.get(folder, []),
                    clusters=clusters,
                    aggregation_date=aggregation_date,
                    legacy_fallback_entries=legacy_fallback_entries,
                ),
            )
            abs_summary.write_text(updated_content, encoding="utf-8")
            repo.add(summary_rel)
            changed_files.append(summary_rel)

        for access_file, file_entries in entries_by_access_file.items():
            filtered_file_entries = _filter_aggregation_entries(file_entries, selected_folders)
            if not filtered_file_entries:
                continue
            abs_access = root / access_file
            archive_rel = _archive_target_for_access_file(access_file, filtered_file_entries)
            abs_archive = root / archive_rel
            archive_existing = (
                abs_archive.read_text(encoding="utf-8") if abs_archive.exists() else ""
            )
            hot_content = abs_access.read_text(encoding="utf-8")
            appended_archive = (
                archive_existing.rstrip("\n") + "\n" + hot_content.strip("\n") + "\n"
                if archive_existing.strip()
                else hot_content.strip("\n") + ("\n" if hot_content.strip() else "")
            )
            abs_archive.parent.mkdir(parents=True, exist_ok=True)
            abs_archive.write_text(appended_archive, encoding="utf-8")
            abs_access.write_text("", encoding="utf-8")
            repo.add(archive_rel)
            repo.add(access_file)
            changed_files.extend([archive_rel, access_file])

        commit_msg = f"[curation] Aggregate ACCESS logs ({aggregation_date})"
        commit_result = repo.commit(commit_msg)
        merge_state, merge_warnings = _maybe_fast_forward_publication_base(
            repo,
            commit_sha=commit_result.sha,
            blocked_action="Session branch aggregation",
        )
        result = MemoryWriteResult.from_commit(
            files_changed=changed_files,
            commit_result=commit_result,
            commit_message=commit_msg,
            new_state=preview_state,
            warnings=merge_warnings,
        )
        if merge_state is not None:
            result.new_state["merge"] = merge_state
        return result.to_json()

    @mcp.tool(
        name="memory_record_reflection",
        annotations=_tool_annotations(
            title="Record Session Reflection",
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=False,
            openWorldHint=False,
        ),
    )
    async def memory_record_reflection(
        session_id: str,
        memory_retrieved: str,
        memory_influence: str,
        outcome_quality: str,
        gaps_noticed: str,
        system_observations: str = "",
    ) -> str:
        """Record a structured reflection.

        For full session wrap-up, prefer memory_record_session so summary,
        reflection, and ACCESS writes land in a single commit. The session
        summary must already exist; call memory_tool_schema with
        tool_name="memory_record_reflection" for the required reflection fields.
        """
        from ...errors import ValidationError
        from ...models import MemoryWriteResult

        repo = get_repo()
        root = get_root()
        resolved_user_id = _resolved_user_id(session_state)
        resolved_session_id = _resolve_session_id_for_user(session_id, resolved_user_id)

        session_dir = root / resolved_session_id
        if not session_dir.is_dir():
            raise ValidationError(
                f"Session folder does not exist: {resolved_session_id}. Create the chat summary first with memory_record_chat_summary."
            )

        reflection_rel = f"{resolved_session_id}/reflection.md"
        reflection_abs = root / reflection_rel
        if reflection_abs.exists():
            raise ValidationError(
                f"Reflection already exists for {resolved_session_id}. Edit it directly with memory_edit if an update is needed."
            )

        reflection_abs.write_text(
            _build_structured_reflection_content(
                memory_retrieved,
                memory_influence,
                outcome_quality,
                gaps_noticed,
                system_observations,
            ),
            encoding="utf-8",
        )
        repo.add(reflection_rel)
        commit_msg = f"[chat] Add session reflection for {resolved_session_id}"
        commit_result = repo.commit(commit_msg)
        merge_state, merge_warnings = _maybe_fast_forward_publication_base(
            repo,
            commit_sha=commit_result.sha,
            blocked_action="Session branch reflection",
        )
        result = MemoryWriteResult.from_commit(
            files_changed=[reflection_rel],
            commit_result=commit_result,
            commit_message=commit_msg,
            new_state={"reflection_path": reflection_rel},
            warnings=merge_warnings,
        )
        if merge_state is not None:
            result.new_state["merge"] = merge_state
        return result.to_json()

    @mcp.tool(
        name="memory_record_periodic_review",
        annotations=_tool_annotations(
            title="Record Periodic Review Outputs",
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=False,
            openWorldHint=False,
        ),
    )
    async def memory_record_periodic_review(
        review_date: str,
        assessment_summary: str,
        belief_diff_entry: str,
        review_queue_entries: str = "",
        active_stage: str = "",
        preview: bool = False,
        approval_token: str | None = None,
    ) -> str:
        """Record approved periodic-review outputs in one protected commit.

        Updates the live router's last-review date and active-stage assessment,
        appends the supplied belief-diff entry, and optionally appends review
        queue follow-up items. active_stage may be blank to retain the current
        stage from the live router. Use preview=True first to receive the
        approval_token required for apply mode. Use memory_tool_schema for the
        machine-readable contract.
        """
        from ...errors import NotFoundError, ValidationError
        from ...models import MemoryWriteResult

        repo = get_repo()
        root = get_root()
        try:
            date.fromisoformat(review_date)
        except ValueError as exc:
            raise ValidationError(f"review_date must be YYYY-MM-DD, got: {review_date!r}") from exc
        if not assessment_summary.strip():
            raise ValidationError("assessment_summary must be non-empty")
        if not belief_diff_entry.strip():
            raise ValidationError("belief_diff_entry must be non-empty")

        normalized_stage = active_stage.strip()
        if normalized_stage and normalized_stage not in _PERIODIC_REVIEW_STAGE_SETTINGS:
            raise ValidationError(
                "active_stage must be one of Exploration, Calibration, Consolidation"
            )

        quick_reference_rel = _resolve_live_router_rel(root)
        belief_diff_rel = _resolve_governance_rel(root, "belief-diff-log.md")
        review_queue_rel = _resolve_governance_rel(root, "review-queue.md")

        abs_quick_reference = root / quick_reference_rel
        abs_belief_diff = root / belief_diff_rel
        abs_review_queue = root / review_queue_rel
        for rel_path, abs_path in (
            (quick_reference_rel, abs_quick_reference),
            (belief_diff_rel, abs_belief_diff),
            (review_queue_rel, abs_review_queue),
        ):
            if not abs_path.exists():
                raise NotFoundError(f"Required periodic-review file not found: {rel_path}")

        quick_reference_content = abs_quick_reference.read_text(encoding="utf-8")
        updated_quick_reference = _update_last_periodic_review_date(
            quick_reference_content, review_date
        )
        if updated_quick_reference is None:
            raise ValidationError(
                "Could not locate the 'Last periodic review' date block in the live router (core/INIT.md or core/HOME.md)"
            )

        current_stage_match = re.search(
            r"(?m)^## Current active stage:\s*([^\n]+)$", quick_reference_content
        )
        current_stage = (
            current_stage_match.group(1).strip() if current_stage_match else "Exploration"
        )
        stage_to_record = normalized_stage or current_stage
        updated_quick_reference = _update_current_stage_block(
            updated_quick_reference,
            review_date,
            stage_to_record,
            assessment_summary,
        )
        belief_diff_content = abs_belief_diff.read_text(encoding="utf-8")
        updated_belief_diff = _append_markdown_block(belief_diff_content, belief_diff_entry)

        files_changed = [quick_reference_rel, belief_diff_rel]
        review_queue_written = False
        updated_review_queue: str | None = None
        if review_queue_entries.strip():
            review_queue_content = abs_review_queue.read_text(encoding="utf-8")
            updated_review_queue = _append_markdown_block(
                review_queue_content, review_queue_entries
            )
            files_changed.append(review_queue_rel)
            review_queue_written = True

        commit_msg = f"[system] Record periodic review {review_date}"
        new_state = {
            "review_date": review_date,
            "active_stage": stage_to_record,
            "belief_diff_written": True,
            "review_queue_written": review_queue_written,
        }
        operation_arguments = {
            "review_date": review_date,
            "assessment_summary": assessment_summary,
            "belief_diff_entry": belief_diff_entry,
            "review_queue_entries": review_queue_entries,
            "active_stage": active_stage,
        }
        preview_payload = build_governed_preview(
            mode="preview" if preview else "apply",
            change_class="protected",
            summary=f"Record approved periodic-review outputs for {review_date}.",
            reasoning="Periodic-review recording is a protected governance write because it edits authoritative meta surfaces.",
            target_files=[preview_target(path, "update") for path in files_changed],
            invariant_effects=[
                "Updates the last periodic review date and active-stage assessment in the live router (core/INIT.md or core/HOME.md).",
                "Appends the belief-diff entry and any queued follow-up review items in one governed commit.",
                "Protected apply mode requires the approval_token returned by preview mode.",
            ],
            commit_message=commit_msg,
            resulting_state=new_state,
        )
        preview_payload, protected_token = attach_approval_requirement(
            preview_payload,
            repo,
            tool_name="memory_record_periodic_review",
            operation_arguments=operation_arguments,
        )
        if preview:
            result = MemoryWriteResult(
                files_changed=files_changed,
                commit_sha=None,
                commit_message=None,
                new_state={**new_state, "approval_token": protected_token},
                preview=preview_payload,
            )
            return result.to_json()

        require_approval_token(
            repo,
            tool_name="memory_record_periodic_review",
            operation_arguments=operation_arguments,
            approval_token=approval_token,
        )
        abs_quick_reference.write_text(updated_quick_reference, encoding="utf-8")
        repo.add(quick_reference_rel)
        abs_belief_diff.write_text(updated_belief_diff, encoding="utf-8")
        repo.add(belief_diff_rel)
        if updated_review_queue is not None:
            abs_review_queue.write_text(updated_review_queue, encoding="utf-8")
            repo.add(review_queue_rel)
        commit_result = repo.commit(commit_msg)
        merge_state, merge_warnings = _maybe_fast_forward_publication_base(
            repo,
            commit_sha=commit_result.sha,
            blocked_action="Session branch periodic review",
        )
        result = MemoryWriteResult.from_commit(
            files_changed=files_changed,
            commit_result=commit_result,
            commit_message=commit_msg,
            new_state=new_state,
            warnings=merge_warnings,
            preview=preview_payload,
        )
        if merge_state is not None:
            result.new_state["merge"] = merge_state
        return result.to_json()

    @mcp.tool(
        name="memory_revert_commit",
        annotations=_tool_annotations(
            title="Revert a Memory Commit",
            readOnlyHint=False,
            destructiveHint=True,
            idempotentHint=False,
            openWorldHint=False,
        ),
    )
    async def memory_revert_commit(
        sha: str,
        confirm: bool = False,
        preview_token: str | None = None,
    ) -> str:
        """Preview or confirm reversion of a governed commit.

        Call with confirm=False first to receive eligibility details,
        conflict metadata, and the preview_token required for apply mode.
        confirm=True requires that preview_token from a fresh preview at the
        current HEAD. Use memory_tool_schema for the machine-readable contract.
        """
        import re as _re

        from ...errors import ValidationError
        from ...models import MemoryWriteResult

        if not _re.fullmatch(r"[0-9a-f]{4,64}", sha, _re.IGNORECASE):
            raise ValidationError(f"Invalid SHA: {sha!r}. Must be a 4–64 character hex string.")

        repo = get_repo()
        preview = _build_revert_preview(repo, sha)
        operation_arguments = {"sha": str(preview["resolved_sha"])}
        preview_payload = build_governed_preview(
            mode="preview" if not confirm else "apply",
            change_class="protected",
            summary=f"Revert governed commit {preview['resolved_sha']}.",
            reasoning="Revert uses a preview-first flow so callers can inspect eligibility, conflicts, and touched files before mutation.",
            target_files=[
                preview_target(path, "revert") for path in cast(list[str], preview["files_changed"])
            ],
            invariant_effects=[
                "Requires a fresh preview token before apply.",
                "Rejects commits outside the governed memory surface or with unresolved conflicts.",
            ],
            commit_message=f"Revert {preview['resolved_sha']}",
            resulting_state=cast(dict[str, Any], preview),
            warnings=cast(list[str], preview["policy_reasons"]),
        )
        preview_payload, required_preview_token = attach_preview_requirement(
            preview_payload,
            repo,
            tool_name="memory_revert_commit",
            operation_arguments=operation_arguments,
        )
        if not confirm:
            result = MemoryWriteResult(
                files_changed=cast(list[str], preview["files_changed"]),
                commit_sha=None,
                commit_message=None,
                new_state={"mode": "preview", **preview, "preview_token": required_preview_token},
                warnings=cast(list[str], preview["policy_reasons"]),
                preview=preview_payload,
            )
            return result.to_json()

        require_preview_token(
            repo,
            tool_name="memory_revert_commit",
            operation_arguments=operation_arguments,
            preview_token=preview_token,
        )

        if not bool(preview["applies_cleanly"]):
            conflict_details = str(preview["conflict_details"] or "")
            detail_suffix = f" Details: {conflict_details}" if conflict_details else ""
            raise ValidationError(
                "Revert preview indicates conflicts at the current HEAD. Review conflict_details from preview output and re-run preview after resolving competing changes."
                + detail_suffix
            )

        policy_reasons = cast(list[str], preview["policy_reasons"])
        if policy_reasons:
            raise ValidationError(
                "Commit cannot be reverted by memory_revert_commit: " + "; ".join(policy_reasons)
            )

        resolved_sha = str(preview["resolved_sha"])
        commit_result = repo.revert(resolved_sha)
        merge_state, merge_warnings = _maybe_fast_forward_publication_base(
            repo,
            commit_sha=commit_result.sha,
            blocked_action="Session branch revert",
        )
        result = MemoryWriteResult.from_commit(
            files_changed=cast(list[str], preview["files_changed"]),
            commit_result=commit_result,
            commit_message=f"Revert {resolved_sha}",
            new_state={
                "mode": "confirm",
                "reverted_sha": resolved_sha,
                "new_sha": commit_result.sha,
                "preview_token": preview_token,
            },
            warnings=merge_warnings,
            preview=preview_payload,
        )
        if merge_state is not None:
            result.new_state["merge"] = merge_state
        return result.to_json()

    @mcp.tool(
        name="memory_query_dialogue",
        annotations=_tool_annotations(
            title="Query Compressed Dialogue Logs",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def memory_query_dialogue(
        sessions: list[str] | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        keyword: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> str:
        """Read sidecar-written dialogue.jsonl rows across sessions.

        Filter by explicit session ids, optional activity date range (YYYY-MM-DD),
        or keyword substring match on first_line. Paginate with offset/limit.
        Call memory_tool_schema with tool_name=\"memory_query_dialogue\" for fields.
        """
        root = get_root()
        payload = query_dialogue_entries(
            root,
            sessions=sessions,
            date_from=date_from,
            date_to=date_to,
            keyword=keyword,
            limit=limit,
            offset=offset,
        )
        return json.dumps(payload, indent=2)

    return {
        "memory_checkpoint": memory_checkpoint,
        "memory_session_flush": memory_session_flush,
        "memory_append_scratchpad": memory_append_scratchpad,
        "memory_record_chat_summary": memory_record_chat_summary,
        "memory_flag_for_review": memory_flag_for_review,
        "memory_resolve_review_item": memory_resolve_review_item,
        "memory_log_access": memory_log_access,
        "memory_log_access_batch": memory_log_access_batch,
        "memory_record_session": memory_record_session,
        "memory_query_dialogue": memory_query_dialogue,
        "memory_run_aggregation": memory_run_aggregation,
        "memory_record_reflection": memory_record_reflection,
        "memory_record_periodic_review": memory_record_periodic_review,
        "memory_revert_commit": memory_revert_commit,
    }


__all__ = ["register_tools"]
