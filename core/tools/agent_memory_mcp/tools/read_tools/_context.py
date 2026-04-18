"""Read tools - context injector helpers and tool registrations."""

from __future__ import annotations

import hashlib
import json
import re
import time
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterable, Iterator, cast

import yaml  # type: ignore[import-untyped]

from ...errors import ValidationError
from ...frontmatter_utils import (
    extract_project_cold_start_sections,
    read_with_frontmatter,
)
from ...identity_paths import normalize_user_id, working_file_path
from ...path_policy import validate_slug
from ...plan_utils import budget_status, load_plan, next_action, phase_payload, resolve_phase

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

    from ...session_state import SessionState


class _TimingCollector:
    """Accumulate per-section duration samples for context-injector tools.

    Each recorded span carries a stable name (the section label) and its
    measured wall-clock duration in milliseconds. The collector is intended to
    be short-lived — one per tool invocation — and is threading-naive by
    design: callers serialize through the injector already.
    """

    __slots__ = ("_spans", "_started_at_ns")

    def __init__(self) -> None:
        self._spans: list[dict[str, Any]] = []
        self._started_at_ns: int = time.perf_counter_ns()

    def record(self, name: str, duration_ms: float, *, status: str = "ok") -> None:
        self._spans.append(
            {
                "name": name,
                "duration_ms": round(duration_ms, 3),
                "status": status,
            }
        )

    def spans(self) -> list[dict[str, Any]]:
        return list(self._spans)

    def total_ms(self) -> float:
        return round((time.perf_counter_ns() - self._started_at_ns) / 1_000_000, 3)


@contextmanager
def _span(collector: _TimingCollector, name: str) -> Iterator[None]:
    """Time a code block and append the result to ``collector``."""
    start_ns = time.perf_counter_ns()
    status = "ok"
    try:
        yield
    except Exception:
        status = "error"
        raise
    finally:
        duration_ms = (time.perf_counter_ns() - start_ns) / 1_000_000
        collector.record(name, duration_ms, status=status)


_PLACEHOLDER_MARKERS = (
    "{{PLACEHOLDER}}",
    "[TEMPLATE]",
)
_HEADING_ONLY_RE = re.compile(r"^#{1,6}\s+.+$")
_PROJECT_STATUS_ORDER = {
    "active": 0,
    "draft": 1,
    "blocked": 2,
    "paused": 3,
    "completed": 4,
    "abandoned": 5,
}
_PHASE_PRIORITY = {"in-progress": 0, "pending": 1, "blocked": 2, "completed": 3, "skipped": 4}


def _coerce_bool(value: object, *, field_name: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() not in {"", "0", "false", "no"}
    raise ValidationError(f"{field_name} must be a boolean")


def _coerce_optional_bool(value: object, *, field_name: str) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"", "auto", "none", "null"}:
            return None
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    raise ValidationError(f"{field_name} must be true, false, or null/auto")


def _coerce_max_context_chars(value: object) -> int:
    try:
        max_context_chars = int(cast(Any, value))
    except (TypeError, ValueError) as exc:
        raise ValidationError("max_context_chars must be an integer >= 0") from exc
    if max_context_chars < 0:
        raise ValidationError("max_context_chars must be >= 0")
    return max_context_chars


# Default server-side time budget for ``memory_context_project``. Chosen to
# finish well inside the 60s MCP transport timeout so cold-start callers get a
# partial-but-useful response rather than a hard timeout. See cold-start
# roadmap P0-A step 3 for rationale.
_DEFAULT_TIME_BUDGET_MS = 5000


def _coerce_time_budget_ms(value: object) -> int:
    """Normalize the ``time_budget_ms`` parameter.

    Semantics:
    - ``None`` → use the module default (currently 5000ms).
    - ``0`` or a negative integer → disable the budget entirely; the tool
      runs until completion regardless of elapsed time. Useful for offline
      regeneration paths that don't mind waiting.
    - Positive integer → enforce that many milliseconds.
    """
    if value is None:
        return _DEFAULT_TIME_BUDGET_MS
    try:
        coerced = int(cast(Any, value))
    except (TypeError, ValueError) as exc:
        raise ValidationError(
            "time_budget_ms must be an integer, 0/negative to disable, or null"
        ) from exc
    return coerced


def _is_time_exhausted(collector: _TimingCollector, budget_ms: int) -> bool:
    """Return True when the time budget has been consumed.

    A non-positive ``budget_ms`` disables the budget and always returns False,
    matching the coercion contract above.
    """
    if budget_ms <= 0:
        return False
    return collector.total_ms() >= budget_ms


# IN-manifest rendering mode. Cold-start calls want a one-liner ("N files
# staged, newest is foo.md") rather than a full frontmatter-parsed table,
# which is the single largest latency source for projects that snapshot
# whole external codebases. Callers who explicitly want the full manifest
# pass ``"full"`` (or legacy ``True``). See cold-start roadmap P0-A step 5.
_IN_MANIFEST_MODES = frozenset({"off", "summary", "full"})


def _coerce_in_manifest_flag(value: object) -> str:
    """Normalize ``include_in_manifest`` into one of ``{off, summary, full}``.

    Accepts:
    - ``None`` or ``"summary"`` → ``"summary"`` (cold-start default).
    - ``True`` or ``"full"`` → ``"full"`` (legacy full-table behavior).
    - ``False``, ``"off"``, ``"none"`` → ``"off"`` (skip the section).
    """
    if value is None:
        return "summary"
    if isinstance(value, bool):
        return "full" if value else "off"
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"", "summary"}:
            return "summary"
        if normalized in {"full", "true", "yes", "on", "1"}:
            return "full"
        if normalized in {"off", "false", "no", "none", "0"}:
            return "off"
    raise ValidationError(
        "include_in_manifest must be one of: false, 'off', 'summary', 'full', true"
    )


def _resolve_repo_relative_path(root: Path, repo_relative_path: str) -> Path | None:
    normalized = repo_relative_path.replace("\\", "/").strip().lstrip("/")
    if not normalized:
        return None

    candidates: list[Path] = []
    direct = root / normalized
    candidates.append(direct)

    root_name = root.name
    if root_name and normalized.startswith(f"{root_name}/"):
        candidates.append(root / normalized.split("/", 1)[1])

    repo_root = root.parent
    candidates.append(repo_root / normalized)

    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _read_file_content(root: Path, repo_relative_path: str) -> str | None:
    """Read a file and return the body without frontmatter, or None when missing."""
    abs_path = _resolve_repo_relative_path(root, repo_relative_path)
    if abs_path is None or not abs_path.is_file():
        return None

    try:
        _, body = read_with_frontmatter(abs_path)
    except Exception:
        try:
            body = abs_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return None
    return body.strip()


def _resolved_user_id(session_state: "SessionState | None") -> str | None:
    if session_state is None:
        return None
    return normalize_user_id(getattr(session_state, "user_id", None))


def _is_placeholder(content: str) -> bool:
    """Return True when a body still looks like a template or placeholder stub."""
    stripped = content.strip()
    if not stripped:
        return True
    if any(marker in stripped for marker in _PLACEHOLDER_MARKERS):
        return True

    non_empty_lines = [line.strip() for line in stripped.splitlines() if line.strip()]
    if len(stripped) < 50 and len(non_empty_lines) <= 2:
        return all(_HEADING_ONLY_RE.match(line) for line in non_empty_lines)
    return False


def _read_section_status(
    root: Path,
    repo_relative_path: str,
    remaining_chars: int,
) -> tuple[str | None, int, str]:
    content = _read_file_content(root, repo_relative_path)
    if content is None:
        return None, 0, "missing"
    if _is_placeholder(content):
        return None, 0, "placeholder"
    if remaining_chars > 0 and len(content) > remaining_chars:
        return None, 0, "over_budget"
    return content, len(content), "included"


def _read_section_with_budget(
    root: Path, repo_relative_path: str, remaining_chars: int
) -> tuple[str | None, int]:
    """Read a file if it fits within the remaining character budget."""
    content, chars_used, _ = _read_section_status(root, repo_relative_path, remaining_chars)
    return content, chars_used


def _read_project_summary_with_cold_start_fallback(
    root: Path,
    repo_relative_path: str,
    remaining_chars: int,
) -> tuple[str | None, int, str]:
    """Read a project SUMMARY.md, falling back to cold-start subsections.

    When the full body does not fit in ``remaining_chars``, attempt to extract
    just the Layout / Canonical source / How to continue subsections. If that
    extracted payload also overflows, return ``over_budget`` as usual. The
    returned reason is one of ``"included"``, ``"included_cold_start_only"``,
    ``"missing"``, ``"placeholder"``, or ``"over_budget"``.
    """
    content = _read_file_content(root, repo_relative_path)
    if content is None:
        return None, 0, "missing"
    if _is_placeholder(content):
        return None, 0, "placeholder"
    if remaining_chars <= 0 or len(content) <= remaining_chars:
        return content, len(content), "included"

    cold_start = extract_project_cold_start_sections(content)
    if cold_start is None or len(cold_start) > remaining_chars:
        return None, 0, "over_budget"
    return cold_start, len(cold_start), "included_cold_start_only"


def _build_budget_report(
    sections: list[dict[str, Any]], *, max_context_chars: int
) -> dict[str, Any]:
    """Summarize which sections were included or dropped under the soft budget."""
    included = [item for item in sections if item.get("included")]
    dropped = [item for item in sections if not item.get("included")]
    total_chars = sum(int(item.get("chars", 0)) for item in included)
    report: dict[str, Any] = {
        "max_context_chars": max_context_chars,
        "unbounded": max_context_chars == 0,
        "total_chars": total_chars,
        "sections_included": [str(item.get("name")) for item in included],
        "sections_dropped": [
            {
                "name": item.get("name"),
                "path": item.get("path"),
                "reason": item.get("reason"),
            }
            for item in dropped
        ],
        "details": sections,
    }
    if max_context_chars > 0:
        report["remaining_chars"] = max(max_context_chars - total_chars, 0)
    return report


def _compact_next_action(next_action_info: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(next_action_info, dict):
        return None

    compact: dict[str, Any] = {}
    for key in (
        "id",
        "title",
        "requires_approval",
        "attempt_number",
        "has_prior_failures",
        "suggest_revision",
    ):
        if key not in next_action_info or next_action_info[key] is None:
            continue
        compact[key] = next_action_info[key]
    return compact or None


def _section_anchor(name: str) -> str:
    anchor = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return anchor or "section"


def _assemble_markdown_response(metadata: dict[str, Any], sections: list[dict[str, str]]) -> str:
    """Render a JSON metadata header followed by Markdown content sections."""
    body_sections = [
        {
            "name": section["name"],
            "path": section["path"],
            "anchor": _section_anchor(section["name"]),
            "chars": len(section["content"]),
        }
        for section in sections
    ]
    response_metadata = dict(metadata)
    response_metadata.setdefault("format", "markdown+json-header")
    response_metadata.setdefault("format_version", 1)
    response_metadata["body_sections"] = body_sections

    parts = ["```json", json.dumps(response_metadata, indent=2, ensure_ascii=False), "```", ""]
    for section in sections:
        title = section["name"]
        path = section["path"]
        content = section["content"]
        anchor = _section_anchor(title)
        parts.append(f"<!-- context-section: {anchor} -->")
        parts.append("")
        parts.append(f"## {title}")
        parts.append("")
        parts.append(f"_Source: {path}_")
        parts.append("")
        parts.append(content.rstrip())
        parts.append("")
        parts.append(f"<!-- /context-section: {anchor} -->")
        parts.append("")
    return "\n".join(parts).rstrip() + "\n"


def _extract_markdown_section(content: str, heading: str) -> list[str]:
    marker = f"## {heading}"
    lines = content.splitlines()
    capture = False
    captured: list[str] = []
    for line in lines:
        if line.strip() == marker:
            capture = True
            continue
        if capture and line.startswith("## "):
            break
        if capture:
            captured.append(line)
    return captured


def _extract_top_of_mind(content: str) -> list[str]:
    items: list[str] = []
    for line in _extract_markdown_section(content, "Top of mind"):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith(("- ", "* ")):
            items.append(stripped[2:].strip())
        else:
            items.append(stripped)
    return items


def _append_section(
    sections: list[dict[str, str]],
    section_records: list[dict[str, Any]],
    *,
    name: str,
    path: str,
    content: str,
    remaining_chars: int,
) -> tuple[int, str]:
    chars = len(content)
    if remaining_chars > 0 and chars > remaining_chars:
        section_records.append(
            {
                "name": name,
                "path": path,
                "chars": chars,
                "included": False,
                "reason": "over_budget",
            }
        )
        return remaining_chars, "over_budget"

    sections.append({"name": name, "path": path, "content": content})
    section_records.append(
        {
            "name": name,
            "path": path,
            "chars": chars,
            "included": True,
            "reason": "included",
        }
    )
    if remaining_chars > 0:
        return max(remaining_chars - chars, 0), "included"
    return remaining_chars, "included"


def _render_plan_section(plan_context: dict[str, Any]) -> str:
    lines = [
        f"**Plan:** {plan_context['plan_id']}",
        f"**Status:** {plan_context['plan_status']}",
        "",
        "### Purpose",
        "",
        str(plan_context.get("purpose_summary") or "No purpose summary."),
    ]
    if plan_context.get("purpose_context"):
        lines.extend(["", str(plan_context["purpose_context"])])

    if plan_context.get("current_phase_id"):
        lines.extend(["", "### Current Phase", ""])
        lines.append(f"- ID: {plan_context['current_phase_id']}")
        lines.append(f"- Title: {plan_context.get('current_phase_title') or 'Untitled phase'}")
        lines.append(f"- Status: {plan_context.get('current_phase_status') or 'unknown'}")
    else:
        lines.extend(["", "### Current Phase", "", "No actionable phase is available."])

    blockers = [
        blocker
        for blocker in cast(list[dict[str, Any]], plan_context.get("blockers") or [])
        if not bool(blocker.get("satisfied"))
    ]
    if blockers:
        lines.extend(["", "### Blockers", ""])
        for blocker in blockers:
            detail = blocker.get("detail") or blocker.get("reference") or "Unknown blocker"
            lines.append(f"- {detail} ({blocker.get('status', 'unknown')})")

    postconditions = cast(list[dict[str, Any]], plan_context.get("postconditions") or [])
    if postconditions:
        lines.extend(["", "### Postconditions", ""])
        for item in postconditions:
            description = item.get("description") or item.get("target") or "Unnamed postcondition"
            postcondition_type = item.get("type") or "manual"
            lines.append(f"- [{postcondition_type}] {description}")

    sources = cast(list[dict[str, Any]], plan_context.get("sources") or [])
    if sources:
        lines.extend(["", "### Sources", ""])
        for source in sources:
            lines.append(f"- {source.get('path')} ({source.get('type', 'unknown')})")

    next_action_info = cast(dict[str, Any] | None, plan_context.get("next_action"))
    if next_action_info is not None:
        lines.extend(["", "### Next Action", ""])
        lines.append(f"- {next_action_info.get('title', next_action_info.get('id', 'unknown'))}")
        if next_action_info.get("requires_approval"):
            lines.append("- Requires approval")

    budget_info = cast(dict[str, Any] | None, plan_context.get("budget_status"))
    if budget_info is not None:
        lines.extend(["", "### Budget", ""])
        for key in ("deadline", "days_remaining", "max_sessions", "sessions_remaining"):
            if key in budget_info:
                lines.append(f"- {key.replace('_', ' ')}: {budget_info[key]}")
        if "over_budget" in budget_info:
            lines.append(f"- over budget: {budget_info['over_budget']}")

    if plan_context.get("plan_source") == "raw_yaml_fallback":
        lines.extend(
            [
                "",
                "### Loader note",
                "",
                "Loaded from raw YAML fallback because strict plan validation failed.",
            ]
        )

    return "\n".join(lines).strip()


def _render_no_plan_section(project_id: str) -> str:
    return (
        f"No active plan found for `{project_id}`. "
        "If planning work exists, inspect the project's `plans/` folder directly."
    )


def _list_project_ids(projects_root: Path) -> list[str]:
    if not projects_root.is_dir():
        return []
    return sorted(
        project_dir.name
        for project_dir in projects_root.iterdir()
        if project_dir.is_dir()
        and project_dir.name != "OUT"
        and not project_dir.name.startswith("_")
    )


def _coerce_raw_phase(raw_plan: dict[str, Any]) -> dict[str, Any] | None:
    work = raw_plan.get("work")
    if not isinstance(work, dict):
        return None
    phases = work.get("phases")
    if not isinstance(phases, list) or not phases:
        return None

    candidates = [phase for phase in phases if isinstance(phase, dict)]
    if not candidates:
        return None
    candidates.sort(
        key=lambda phase: (
            _PHASE_PRIORITY.get(str(phase.get("status", "pending")), 99),
            str(phase.get("id", "")),
        )
    )
    return candidates[0]


def _coerce_raw_postconditions(raw_phase: dict[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for item in cast(list[Any], raw_phase.get("postconditions") or []):
        if isinstance(item, str):
            result.append({"description": item, "type": "manual"})
            continue
        if not isinstance(item, dict):
            continue
        description = item.get("description") or item.get("target") or "Unnamed postcondition"
        payload = {
            "description": str(description),
            "type": str(item.get("type") or "manual"),
        }
        if item.get("target"):
            payload["target"] = str(item["target"])
        result.append(payload)
    return result


def _coerce_raw_sources(raw_phase: dict[str, Any]) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    for item in cast(list[Any], raw_phase.get("sources") or []):
        if not isinstance(item, dict) or not item.get("path"):
            continue
        payload = {
            "path": str(item["path"]),
            "type": str(item.get("type") or "internal"),
            "intent": str(item.get("intent") or "").strip(),
        }
        if item.get("uri"):
            payload["uri"] = str(item["uri"])
        sources.append(payload)
    return sources


def _coerce_raw_blockers(raw_phase: dict[str, Any]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    for blocker in cast(list[Any], raw_phase.get("blockers") or []):
        blockers.append(
            {
                "reference": str(blocker),
                "kind": "declared",
                "satisfied": False,
                "status": "listed",
                "detail": str(blocker),
            }
        )
    return blockers


def _coerce_raw_budget(raw_plan: dict[str, Any]) -> dict[str, Any] | None:
    budget = raw_plan.get("budget")
    if not isinstance(budget, dict):
        return None
    result: dict[str, Any] = {
        "advisory": bool(budget.get("advisory", True)),
    }
    if budget.get("deadline") is not None:
        result["deadline"] = str(budget["deadline"])
    if budget.get("max_sessions") is not None:
        result["max_sessions"] = budget["max_sessions"]
    if raw_plan.get("sessions_used") is not None:
        result["sessions_used"] = raw_plan.get("sessions_used")
    return result


def _build_raw_plan_context(plan_file: Path, load_error: Exception) -> dict[str, Any] | None:
    try:
        raw_plan = yaml.safe_load(plan_file.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(raw_plan, dict):
        return None

    raw_phase = _coerce_raw_phase(raw_plan)
    purpose_value = raw_plan.get("purpose")
    purpose = purpose_value if isinstance(purpose_value, dict) else {}
    next_action_info: dict[str, Any] | None = None
    if raw_phase is not None:
        next_action_info = {
            "id": str(raw_phase.get("id") or ""),
            "title": str(raw_phase.get("title") or raw_phase.get("id") or "Untitled phase"),
            "requires_approval": bool(raw_phase.get("requires_approval")),
        }

    return {
        "plan_id": str(raw_plan.get("id") or plan_file.stem),
        "plan_status": str(raw_plan.get("status") or "draft"),
        "plan_source": "raw_yaml_fallback",
        "plan_load_error": str(load_error),
        "purpose_summary": str(purpose.get("summary") or "No purpose summary."),
        "purpose_context": str(purpose.get("context") or "").strip(),
        "current_phase_id": None if raw_phase is None else str(raw_phase.get("id") or ""),
        "current_phase_title": None
        if raw_phase is None
        else str(raw_phase.get("title") or raw_phase.get("id") or "Untitled phase"),
        "current_phase_status": None
        if raw_phase is None
        else str(raw_phase.get("status") or "pending"),
        "blockers": [] if raw_phase is None else _coerce_raw_blockers(raw_phase),
        "postconditions": [] if raw_phase is None else _coerce_raw_postconditions(raw_phase),
        "sources": [] if raw_phase is None else _coerce_raw_sources(raw_phase),
        "next_action": next_action_info,
        "budget_status": _coerce_raw_budget(raw_plan),
    }


def _build_validated_plan_context(plan: Any, root: Path) -> dict[str, Any]:
    directive = next_action(plan)
    if directive is None:
        return {
            "plan_id": plan.id,
            "plan_status": plan.status,
            "plan_source": "validated",
            "plan_load_error": None,
            "purpose_summary": plan.purpose.summary,
            "purpose_context": plan.purpose.context,
            "current_phase_id": None,
            "current_phase_title": None,
            "current_phase_status": None,
            "blockers": [],
            "postconditions": [],
            "sources": [],
            "next_action": None,
            "budget_status": budget_status(plan),
        }

    phase = resolve_phase(plan, str(directive["id"]))
    phase_info = phase_payload(plan, phase, root)
    return {
        "plan_id": plan.id,
        "plan_status": plan.status,
        "plan_source": "validated",
        "plan_load_error": None,
        "purpose_summary": plan.purpose.summary,
        "purpose_context": plan.purpose.context,
        "current_phase_id": phase.id,
        "current_phase_title": phase.title,
        "current_phase_status": phase.status,
        "blockers": cast(list[dict[str, Any]], phase_info["phase"].get("blockers") or []),
        "postconditions": cast(
            list[dict[str, Any]], phase_info["phase"].get("postconditions") or []
        ),
        "sources": cast(list[dict[str, Any]], phase_info["phase"].get("sources") or []),
        "next_action": directive,
        "budget_status": budget_status(plan),
    }


def _select_current_plan(
    project_root: Path, root: Path
) -> tuple[Path | None, dict[str, Any] | None]:
    plans_root = project_root / "plans"
    if not plans_root.is_dir():
        return None, None

    plan_entries: list[tuple[int, str, Path, dict[str, Any]]] = []
    for plan_file in sorted(plans_root.glob("*.yaml")):
        try:
            plan = load_plan(plan_file, root)
            plan_context = _build_validated_plan_context(plan, root)
        except Exception as exc:
            fallback_context = _build_raw_plan_context(plan_file, exc)
            if fallback_context is None:
                continue
            plan_context = fallback_context
        plan_entries.append(
            (
                _PROJECT_STATUS_ORDER.get(str(plan_context["plan_status"]), 99),
                str(plan_context["plan_id"]),
                plan_file,
                plan_context,
            )
        )
    if not plan_entries:
        return None, None
    plan_entries.sort(key=lambda item: (item[0], item[1]))
    _, _, plan_path, plan_context = plan_entries[0]
    return plan_path, plan_context


# Cap the IN/ manifest at this many rows. Cold-start callers want a quick
# recency survey, not a full listing — full listings belong to
# ``memory_list_folder``. Projects with hundreds of staged files (e.g.,
# ``rate-my-set`` which snapshots an entire external codebase) were reading
# and YAML-parsing every file on every context_project call before this cap.
_IN_MANIFEST_MAX_ITEMS = 20

# Plan-sources caps. A plan can list arbitrarily many internal sources, and
# each is inlined as its own context section. Without a cap, a plan with 50
# referenced files would blow the time budget and the per-call char budget.
# Whichever limit trips first stops the loop; additional sources are recorded
# in ``section_records`` with reason ``"plan_sources_cap"`` and counted in
# ``more_plan_sources`` on the response metadata. See cold-start roadmap
# P0-A step 4.
_PLAN_SOURCES_MAX_COUNT = 10
_PLAN_SOURCES_MAX_CHARS = 8 * 1024

# On-disk cache for memory_context_project. The schema version is bumped
# whenever the stored payload shape changes (metadata keys, section fields,
# hash algorithm, etc.) so old caches are treated as misses after a server
# upgrade. Content hash covers (rel_path, mtime_ns) of every file under the
# project subtree *plus* the external files that can be inlined into the
# bundle (memory/working/CURRENT.md for session notes, memory/users/SUMMARY.md
# for the user profile, and each internal plan-source file when
# include_plan_sources is on). Without folding those extras in the bundle
# would stay stale after the external files change until some project-local
# file happened to bump its mtime. Params key hashes the shape-affecting
# parameters (include flags, max_chars, user_profile preference) so two
# callers with different opt-ins don't share a bundle. See cold-start
# roadmap P0-A step 6.
# Schema version bumped to 2 because the hash algorithm now covers external
# files; v1 caches would hit incorrectly on an upgraded server.
_CONTEXT_CACHE_SCHEMA_VERSION = 2
_CONTEXT_CACHE_FILENAME = ".context-cache.json"


def _compute_project_content_hash(
    project_root: Path,
    *,
    extra_paths: Iterable[Path] = (),
) -> str:
    """Hash every file under ``project_root`` by (rel_path, mtime_ns).

    The cache file itself is suppressed — otherwise writing the cache would
    invalidate it on the next read. Symlinks and non-regular files are
    skipped. Path separators are normalized to ``/`` so the hash is stable
    across Windows and POSIX.

    ``extra_paths`` folds in the mtimes of files *outside* the project
    subtree whose content can end up inlined in the bundle (session notes,
    user profile, internal plan sources). Missing paths contribute a stable
    absent-marker so a later appearance invalidates the cache. Paths are
    de-duplicated by their absolute-resolved form, and the extras block is
    delimited so it cannot collide with a project-local file of the same
    relative name.
    """
    hasher = hashlib.sha256()
    entries: list[tuple[str, int]] = []
    for file_path in project_root.rglob("*"):
        if not file_path.is_file():
            continue
        if file_path.name == _CONTEXT_CACHE_FILENAME:
            continue
        try:
            mtime_ns = file_path.stat().st_mtime_ns
        except OSError:
            continue
        rel = file_path.relative_to(project_root).as_posix()
        entries.append((rel, mtime_ns))
    entries.sort()
    for rel, mtime_ns in entries:
        hasher.update(rel.encode("utf-8"))
        hasher.update(b"\x00")
        hasher.update(str(mtime_ns).encode("ascii"))
        hasher.update(b"\n")

    extras: list[tuple[str, int | None]] = []
    seen: set[str] = set()
    for raw_path in extra_paths:
        key = str(raw_path.resolve() if raw_path.is_absolute() else raw_path).replace("\\", "/")
        if key in seen:
            continue
        seen.add(key)
        try:
            mtime_ns = raw_path.stat().st_mtime_ns
        except OSError:
            extras.append((key, None))
            continue
        extras.append((key, mtime_ns))
    if extras:
        extras.sort()
        hasher.update(b"\x1fextras\x1f")
        for key, mtime_ns in extras:
            hasher.update(key.encode("utf-8"))
            hasher.update(b"\x00")
            hasher.update(b"missing" if mtime_ns is None else str(mtime_ns).encode("ascii"))
            hasher.update(b"\n")
    return hasher.hexdigest()


def _compute_params_key(
    *,
    max_chars: int,
    include_sources: bool,
    in_manifest_mode: str,
    include_notes: bool,
    include_profile_preference: bool | None,
    time_budget_ms: int,
) -> str:
    """Hash the response-shape-affecting parameters.

    ``time_budget_ms`` is included because different budgets can legitimately
    produce different ``sections_omitted`` lists for the same project state;
    returning a bundle built under one budget to a caller asking under another
    would mislabel truncation.
    """
    payload = json.dumps(
        {
            "max_chars": max_chars,
            "include_plan_sources": include_sources,
            "in_manifest_mode": in_manifest_mode,
            "include_session_notes": include_notes,
            "include_user_profile": include_profile_preference,
            "time_budget_ms": time_budget_ms,
        },
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _cache_path_for(project_root: Path) -> Path:
    return project_root / _CONTEXT_CACHE_FILENAME


def _load_cached_bundle(
    cache_path: Path, *, content_hash: str, params_key: str
) -> dict[str, Any] | None:
    """Return cached {metadata, sections} if the cache hits, else None.

    Any IO or parse error is treated as a miss rather than a hard failure —
    a stale or corrupt cache file must not break the tool.
    """
    if not cache_path.is_file():
        return None
    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None
    if payload.get("schema_version") != _CONTEXT_CACHE_SCHEMA_VERSION:
        return None
    if payload.get("content_hash") != content_hash:
        return None
    if payload.get("params_key") != params_key:
        return None
    metadata = payload.get("metadata")
    sections = payload.get("sections")
    if not isinstance(metadata, dict) or not isinstance(sections, list):
        return None
    return {"metadata": metadata, "sections": sections}


def _write_cached_bundle(
    cache_path: Path,
    *,
    content_hash: str,
    params_key: str,
    metadata: dict[str, Any],
    sections: list[dict[str, str]],
) -> None:
    """Persist the rendered bundle. IO failures are swallowed — caching is
    best-effort and must never break the tool's primary response."""
    payload = {
        "schema_version": _CONTEXT_CACHE_SCHEMA_VERSION,
        "content_hash": content_hash,
        "params_key": params_key,
        "metadata": metadata,
        "sections": sections,
    }
    try:
        cache_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError:
        return


def _lite_plan_listing(project_root: Path) -> list[dict[str, str]]:
    """Enumerate plans under ``project_root`` by top-level ``id``/``status`` only.

    Used by ``memory_context_project_lite``. Skips the full
    :func:`load_plan` validation path (which parses phases, blockers, sources,
    and postconditions) and does a single ``yaml.safe_load`` per file,
    reading only the top-level keys. Files that fail to parse as a mapping
    are skipped silently — lite is best-effort and must never raise.

    Returned entries carry ``id``, ``status``, and ``file`` (the plan's basename).
    Sorted so active plans come first, then alphabetically by ID so the caller
    sees a stable ordering.
    """
    plans_root = project_root / "plans"
    if not plans_root.is_dir():
        return []

    results: list[dict[str, str]] = []
    for plan_file in sorted(plans_root.glob("*.yaml")):
        try:
            doc = yaml.safe_load(plan_file.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError):
            continue
        if not isinstance(doc, dict):
            continue
        results.append(
            {
                "id": str(doc.get("id") or plan_file.stem),
                "status": str(doc.get("status") or "unknown"),
                "file": plan_file.name,
            }
        )
    results.sort(
        key=lambda entry: (
            _PROJECT_STATUS_ORDER.get(entry["status"], 99),
            entry["id"],
        )
    )
    return results


def _render_in_manifest(project_root: Path, root: Path) -> tuple[str, list[str], int]:
    """Render an ``IN/`` manifest capped at the most recent files.

    Returns a ``(markdown, loaded_files, more_count)`` triple where:
    - ``markdown`` is the rendered manifest, including a trailing row with
      the count of omitted items when truncated.
    - ``loaded_files`` lists only the files whose frontmatter was actually
      read (the kept top-N), so callers can track read coverage.
    - ``more_count`` is the number of additional ``IN/`` files not shown;
      always ``0`` when the staging folder has ``<= _IN_MANIFEST_MAX_ITEMS``
      entries.

    Ordering is newest-first by file mtime. mtime is chosen over frontmatter
    ``created`` because mtime is always present and reflects actual staging
    recency; ``created`` is informational and may lag the real snapshot date.
    """
    in_root = project_root / "IN"
    if not in_root.is_dir():
        return "No staged files.", [], 0

    # Enumerate once, sort by mtime descending. Using mtime_ns for stable
    # comparisons on filesystems with low-resolution timestamps.
    candidates: list[tuple[int, Path]] = []
    for file_path in in_root.rglob("*"):
        if not file_path.is_file():
            continue
        try:
            mtime_ns = file_path.stat().st_mtime_ns
        except OSError:
            continue
        candidates.append((mtime_ns, file_path))

    if not candidates:
        return "No staged files.", [], 0

    candidates.sort(key=lambda item: (-item[0], str(item[1])))
    total_count = len(candidates)
    kept = candidates[:_IN_MANIFEST_MAX_ITEMS]
    more_count = max(total_count - len(kept), 0)

    rows: list[str] = [
        "| Path | Trust | Source | Created |",
        "|---|---|---|---|",
    ]
    loaded_files: list[str] = []
    for _, file_path in kept:
        try:
            frontmatter, _ = read_with_frontmatter(file_path)
        except Exception:
            frontmatter = {}
        rel_path = file_path.relative_to(root).as_posix()
        loaded_files.append(rel_path)
        rows.append(
            "| {path} | {trust} | {source} | {created} |".format(
                path=rel_path,
                trust=frontmatter.get("trust", ""),
                source=frontmatter.get("source", ""),
                created=frontmatter.get("created", ""),
            )
        )
    if more_count > 0:
        rows.append(
            f"| _…{more_count} more — use memory_list_folder for the full IN/ listing_ |  |  |  |"
        )
    return "\n".join(rows), loaded_files, more_count


def _render_in_manifest_summary(project_root: Path, root: Path) -> tuple[str, int]:
    """Render a one-liner count summary of the ``IN/`` folder.

    Returns ``(markdown, total_count)``. Does **not** parse frontmatter or stat
    individual files beyond an ``rglob`` count plus a single ``stat()`` on the
    newest file for the hint line. This is the cold-start default because the
    full manifest was the single largest latency source on projects that
    snapshot large external codebases.
    """
    in_root = project_root / "IN"
    if not in_root.is_dir():
        return "No staged files.", 0

    newest_mtime_ns = -1
    newest_path: Path | None = None
    total_count = 0
    for file_path in in_root.rglob("*"):
        if not file_path.is_file():
            continue
        total_count += 1
        try:
            mtime_ns = file_path.stat().st_mtime_ns
        except OSError:
            continue
        if mtime_ns > newest_mtime_ns:
            newest_mtime_ns = mtime_ns
            newest_path = file_path

    if total_count == 0:
        return "No staged files.", 0

    lines: list[str] = [
        f"**{total_count} file{'s' if total_count != 1 else ''} staged** in "
        f"`{in_root.relative_to(root).as_posix()}/`.",
        "",
        "For the full listing, call `memory_list_folder` on the IN/ path; for "
        "the previous per-file manifest, call this tool with "
        '`include_in_manifest="full"`.',
    ]
    if newest_path is not None:
        lines.insert(
            1,
            f"Newest: `{newest_path.relative_to(root).as_posix()}`.",
        )
    return "\n".join(lines), total_count


def register_context(
    mcp: "FastMCP",
    get_repo,
    get_root,
    H,
    session_state: "SessionState | None" = None,
) -> dict[str, object]:
    """Register context injector read tools and return their callables."""
    _tool_annotations = H._tool_annotations

    @mcp.tool(
        name="memory_context_home",
        annotations=_tool_annotations(
            title="Home Context Injector",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def memory_context_home(
        max_context_chars: int = 16000,
        include_project_index: bool = True,
        include_knowledge_index: bool = False,
        include_skills_index: bool = False,
    ) -> str:
        """Load compact home-context state in one Markdown response with JSON metadata."""
        max_chars = _coerce_max_context_chars(max_context_chars)
        include_project = _coerce_bool(include_project_index, field_name="include_project_index")
        include_knowledge = _coerce_bool(
            include_knowledge_index,
            field_name="include_knowledge_index",
        )
        include_skills = _coerce_bool(include_skills_index, field_name="include_skills_index")

        root = get_root()
        resolved_user_id = _resolved_user_id(session_state)
        remaining_chars = max_chars
        budget_exhausted = False
        sections: list[dict[str, str]] = []
        section_records: list[dict[str, Any]] = []
        loaded_files = ["memory/HOME.md"]

        home_content = _read_file_content(root, "memory/HOME.md") or ""
        top_of_mind = _extract_top_of_mind(home_content)

        home_sections = [
            ("User Summary", "memory/users/SUMMARY.md"),
            ("Recent Activity", "memory/activity/SUMMARY.md"),
            ("User Priorities", working_file_path("USER.md", user_id=resolved_user_id)),
            ("Working State", working_file_path("CURRENT.md", user_id=resolved_user_id)),
        ]
        if include_project:
            home_sections.append(("Projects Index", "memory/working/projects/SUMMARY.md"))
        if include_knowledge:
            home_sections.append(("Knowledge Index", "memory/knowledge/SUMMARY.md"))
        if include_skills:
            home_sections.append(("Skills Index", "memory/skills/SUMMARY.md"))

        for name, path in home_sections:
            if budget_exhausted and max_chars > 0:
                section_records.append(
                    {
                        "name": name,
                        "path": path,
                        "chars": 0,
                        "included": False,
                        "reason": "over_budget",
                    }
                )
                continue
            content, chars_used, reason = _read_section_status(root, path, remaining_chars)
            if content is None:
                section_records.append(
                    {
                        "name": name,
                        "path": path,
                        "chars": 0,
                        "included": False,
                        "reason": reason,
                    }
                )
                if reason == "over_budget":
                    budget_exhausted = True
                continue
            sections.append({"name": name, "path": path, "content": content})
            section_records.append(
                {
                    "name": name,
                    "path": path,
                    "chars": chars_used,
                    "included": True,
                    "reason": "included",
                }
            )
            loaded_files.append(path)
            if remaining_chars > 0:
                remaining_chars = max(remaining_chars - chars_used, 0)

        metadata = {
            "tool": "memory_context_home",
            "loaded_files": loaded_files,
            "top_of_mind": top_of_mind,
            "budget_report": _build_budget_report(section_records, max_context_chars=max_chars),
        }
        return _assemble_markdown_response(metadata, sections)

    @mcp.tool(
        name="memory_context_project",
        annotations=_tool_annotations(
            title="Project Context Injector",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def memory_context_project(
        project: str,
        max_context_chars: int = 24000,
        include_plan_sources: bool = False,
        include_in_manifest: str | bool | None = "summary",
        include_session_notes: bool = True,
        include_user_profile: bool | None = None,
        time_budget_ms: int | None = None,
    ) -> str:
        """Load project-focused context in one Markdown response with JSON metadata.

        Cold-start fast path by default: ``include_plan_sources`` is off and
        ``include_in_manifest`` is ``"summary"`` so the first response is
        cheap. Callers who need the full bundle opt in explicitly via
        ``include_plan_sources=True`` and/or ``include_in_manifest="full"``.
        """
        project_id = validate_slug(project, field_name="project")
        max_chars = _coerce_max_context_chars(max_context_chars)
        include_sources = _coerce_bool(include_plan_sources, field_name="include_plan_sources")
        in_manifest_mode = _coerce_in_manifest_flag(include_in_manifest)
        include_notes = _coerce_bool(include_session_notes, field_name="include_session_notes")
        include_profile_preference = _coerce_optional_bool(
            include_user_profile,
            field_name="include_user_profile",
        )
        effective_time_budget_ms = _coerce_time_budget_ms(time_budget_ms)

        timings = _TimingCollector()
        sections_omitted: list[str] = []
        more_plan_sources = 0

        root = get_root()
        resolved_user_id = _resolved_user_id(session_state)
        projects_root = root / "memory" / "working" / "projects"
        project_root = projects_root / project_id
        if not project_root.is_dir():
            available = ", ".join(_list_project_ids(projects_root)) or "none"
            raise ValidationError(
                f"Unknown project '{project_id}'. Available projects: {available}"
            )

        # ---- Plan selection (runs before cache lookup) ----------------------
        # The cache hash must cover every file whose content can land in the
        # bundle, including internal plan sources that live outside the project
        # subtree. We therefore select the plan first so its source list is
        # available when we fold extras into the content hash. Plan selection
        # is a small number of YAML reads from the project's plans/ folder, so
        # paying this cost on every call (including cache hits) is cheap
        # relative to a silently stale bundle.
        with _span(timings, "plan_selection"):
            selected_plan_path, plan_context = _select_current_plan(project_root, root)
        effective_include_profile = (
            include_profile_preference
            if include_profile_preference is not None
            else plan_context is None
        )

        # ---- Cache lookup ----------------------------------------------------
        # Content hash folds in external files that can be inlined: session
        # notes, user profile, and internal plan sources. The conditioning
        # mirrors what the renderer below actually reads, so we do not bust
        # the cache on files we never read. A miss falls through to the
        # normal render path and the bundle is persisted at the end of the
        # function.
        with _span(timings, "cache_lookup"):
            extra_hash_paths: list[Path] = []
            if include_notes:
                cur_rel = working_file_path("CURRENT.md", user_id=resolved_user_id)
                cur_resolved = _resolve_repo_relative_path(root, cur_rel)
                extra_hash_paths.append(
                    cur_resolved if cur_resolved is not None else (root / cur_rel)
                )
            if effective_include_profile:
                extra_hash_paths.append(root / "memory" / "users" / "SUMMARY.md")
            if include_sources and plan_context is not None:
                plan_sources = cast(list[dict[str, Any]], plan_context.get("sources") or [])
                for source in plan_sources:
                    if source.get("type") != "internal":
                        continue
                    source_rel = str(source.get("path") or "")
                    if not source_rel:
                        continue
                    # Plan source paths are stored with the content prefix
                    # (e.g. "core/tools/context-source.md") while `root` is
                    # already the content root. Reuse the same resolver the
                    # renderer uses below so the hash tracks the exact file
                    # the bundle would inline — or a stable "missing" marker
                    # when the source doesn't resolve.
                    resolved = _resolve_repo_relative_path(root, source_rel)
                    extra_hash_paths.append(resolved if resolved is not None else root / source_rel)
            content_hash = _compute_project_content_hash(project_root, extra_paths=extra_hash_paths)
            params_key = _compute_params_key(
                max_chars=max_chars,
                include_sources=include_sources,
                in_manifest_mode=in_manifest_mode,
                include_notes=include_notes,
                include_profile_preference=include_profile_preference,
                time_budget_ms=effective_time_budget_ms,
            )
            cache_path = _cache_path_for(project_root)
            cached = _load_cached_bundle(
                cache_path, content_hash=content_hash, params_key=params_key
            )
        if cached is not None:
            cached_metadata = cast(dict[str, Any], dict(cached["metadata"]))
            cached_sections = cast(list[dict[str, str]], cached["sections"])
            # Runtime-specific fields must be refreshed on every hit so the
            # caller sees *this* call's timings rather than the original
            # render's. Everything else (loaded_files, next_action, plan_id,
            # budget_report) is safe to replay from cache because it's
            # derived from the content we hashed.
            cached_metadata["cache_hit"] = True
            cached_metadata["timings"] = {
                "total_ms": timings.total_ms(),
                "spans": timings.spans(),
                "budget_ms": effective_time_budget_ms,
            }
            return _assemble_markdown_response(cached_metadata, cached_sections)
        next_action_metadata = _compact_next_action(
            None
            if plan_context is None
            else cast(dict[str, Any] | None, plan_context.get("next_action"))
        )

        remaining_chars = max_chars
        budget_exhausted = False
        sections: list[dict[str, str]] = []
        section_records: list[dict[str, Any]] = []
        loaded_files: list[str] = []
        selected_plan_id: str | None = None
        selected_plan_status: str | None = None
        selected_plan_source: str | None = None
        selected_plan_error: str | None = None
        active_plan_id: str | None = None
        current_phase_id: str | None = None
        current_phase_title: str | None = None

        if effective_include_profile:
            if budget_exhausted and max_chars > 0:
                section_records.append(
                    {
                        "name": "User Profile",
                        "path": "memory/users/SUMMARY.md",
                        "chars": 0,
                        "included": False,
                        "reason": "over_budget",
                    }
                )
            elif _is_time_exhausted(timings, effective_time_budget_ms):
                sections_omitted.append("User Profile")
                section_records.append(
                    {
                        "name": "User Profile",
                        "path": "memory/users/SUMMARY.md",
                        "chars": 0,
                        "included": False,
                        "reason": "time_budget_exceeded",
                    }
                )
            else:
                with _span(timings, "user_profile"):
                    content, chars_used, reason = _read_section_status(
                        root,
                        "memory/users/SUMMARY.md",
                        remaining_chars,
                    )
                if content is None:
                    section_records.append(
                        {
                            "name": "User Profile",
                            "path": "memory/users/SUMMARY.md",
                            "chars": 0,
                            "included": False,
                            "reason": reason,
                        }
                    )
                    if reason == "over_budget":
                        budget_exhausted = True
                else:
                    sections.append(
                        {
                            "name": "User Profile",
                            "path": "memory/users/SUMMARY.md",
                            "content": content,
                        }
                    )
                    section_records.append(
                        {
                            "name": "User Profile",
                            "path": "memory/users/SUMMARY.md",
                            "chars": chars_used,
                            "included": True,
                            "reason": "included",
                        }
                    )
                    loaded_files.append("memory/users/SUMMARY.md")
                    if remaining_chars > 0:
                        remaining_chars = max(remaining_chars - chars_used, 0)
        else:
            omission_reason = (
                "omitted_by_request" if include_profile_preference is False else "auto_omitted"
            )
            section_records.append(
                {
                    "name": "User Profile",
                    "path": "memory/users/SUMMARY.md",
                    "chars": 0,
                    "included": False,
                    "reason": omission_reason,
                }
            )

        project_summary_path = f"memory/working/projects/{project_id}/SUMMARY.md"
        if budget_exhausted and max_chars > 0:
            section_records.append(
                {
                    "name": "Project Summary",
                    "path": project_summary_path,
                    "chars": 0,
                    "included": False,
                    "reason": "over_budget",
                }
            )
        elif _is_time_exhausted(timings, effective_time_budget_ms):
            sections_omitted.append("Project Summary")
            section_records.append(
                {
                    "name": "Project Summary",
                    "path": project_summary_path,
                    "chars": 0,
                    "included": False,
                    "reason": "time_budget_exceeded",
                }
            )
        else:
            with _span(timings, "project_summary"):
                project_summary, chars_used, reason = (
                    _read_project_summary_with_cold_start_fallback(
                        root,
                        project_summary_path,
                        remaining_chars,
                    )
                )
            if project_summary is None:
                section_records.append(
                    {
                        "name": "Project Summary",
                        "path": project_summary_path,
                        "chars": 0,
                        "included": False,
                        "reason": reason,
                    }
                )
                if reason == "over_budget":
                    budget_exhausted = True
            else:
                sections.append(
                    {
                        "name": "Project Summary",
                        "path": project_summary_path,
                        "content": project_summary,
                    }
                )
                section_records.append(
                    {
                        "name": "Project Summary",
                        "path": project_summary_path,
                        "chars": chars_used,
                        "included": True,
                        "reason": reason,
                    }
                )
                loaded_files.append(project_summary_path)
                if remaining_chars > 0:
                    remaining_chars = max(remaining_chars - chars_used, 0)

        if budget_exhausted and max_chars > 0:
            section_records.append(
                {
                    "name": "Plan State",
                    "path": f"memory/working/projects/{project_id}/plans/",
                    "chars": 0,
                    "included": False,
                    "reason": "over_budget",
                }
            )
        elif _is_time_exhausted(timings, effective_time_budget_ms):
            sections_omitted.append("Plan State")
            section_records.append(
                {
                    "name": "Plan State",
                    "path": f"memory/working/projects/{project_id}/plans/",
                    "chars": 0,
                    "included": False,
                    "reason": "time_budget_exceeded",
                }
            )
        elif plan_context is None or selected_plan_path is None:
            remaining_chars, reason = _append_section(
                sections,
                section_records,
                name="Plan State",
                path=f"memory/working/projects/{project_id}/plans/",
                content=_render_no_plan_section(project_id),
                remaining_chars=remaining_chars,
            )
            if reason == "over_budget":
                budget_exhausted = True
        else:
            selected_plan_id = cast(str, plan_context["plan_id"])
            selected_plan_status = cast(str, plan_context["plan_status"])
            selected_plan_source = cast(str, plan_context["plan_source"])
            selected_plan_error = cast(str | None, plan_context.get("plan_load_error"))
            current_phase_id = cast(str | None, plan_context.get("current_phase_id"))
            current_phase_title = cast(str | None, plan_context.get("current_phase_title"))
            if selected_plan_status == "active":
                active_plan_id = selected_plan_id
            loaded_files.append(selected_plan_path.relative_to(root).as_posix())
            plan_section = _render_plan_section(plan_context)
            remaining_chars, reason = _append_section(
                sections,
                section_records,
                name="Plan State",
                path=selected_plan_path.relative_to(root).as_posix(),
                content=plan_section,
                remaining_chars=remaining_chars,
            )
            if reason == "over_budget":
                budget_exhausted = True

            if include_sources:
                plan_sources = cast(list[dict[str, Any]], plan_context.get("sources") or [])
                # Caps apply to *included* sources only. Non-internal and
                # missing sources are free — they do not inline content, so
                # they don't consume the budget we're trying to bound.
                sources_included = 0
                sources_chars_used = 0
                cap_tripped = False
                with _span(timings, "plan_sources"):
                    for source in plan_sources:
                        source_path = str(source.get("path") or "")
                        name = f"Source: {source_path}"
                        if cap_tripped:
                            section_records.append(
                                {
                                    "name": name,
                                    "path": source_path,
                                    "chars": 0,
                                    "included": False,
                                    "reason": "plan_sources_cap",
                                }
                            )
                            more_plan_sources += 1
                            continue
                        if budget_exhausted and max_chars > 0:
                            section_records.append(
                                {
                                    "name": name,
                                    "path": source_path,
                                    "chars": 0,
                                    "included": False,
                                    "reason": "over_budget",
                                }
                            )
                            continue
                        if _is_time_exhausted(timings, effective_time_budget_ms):
                            sections_omitted.append(name)
                            section_records.append(
                                {
                                    "name": name,
                                    "path": source_path,
                                    "chars": 0,
                                    "included": False,
                                    "reason": "time_budget_exceeded",
                                }
                            )
                            continue
                        if source.get("type") != "internal":
                            section_records.append(
                                {
                                    "name": name,
                                    "path": source_path,
                                    "chars": 0,
                                    "included": False,
                                    "reason": "not_internal",
                                }
                            )
                            continue
                        content, source_chars, source_reason = _read_section_status(
                            root,
                            source_path,
                            remaining_chars,
                        )
                        if content is None:
                            section_records.append(
                                {
                                    "name": name,
                                    "path": source_path,
                                    "chars": 0,
                                    "included": False,
                                    "reason": source_reason,
                                }
                            )
                            if source_reason == "over_budget":
                                budget_exhausted = True
                            continue
                        sections.append({"name": name, "path": source_path, "content": content})
                        section_records.append(
                            {
                                "name": name,
                                "path": source_path,
                                "chars": source_chars,
                                "included": True,
                                "reason": "included",
                            }
                        )
                        loaded_files.append(source_path)
                        sources_included += 1
                        sources_chars_used += source_chars
                        if remaining_chars > 0:
                            remaining_chars = max(remaining_chars - source_chars, 0)
                        if (
                            sources_included >= _PLAN_SOURCES_MAX_COUNT
                            or sources_chars_used >= _PLAN_SOURCES_MAX_CHARS
                        ):
                            cap_tripped = True

        more_in_items = 0
        in_manifest_path = f"memory/working/projects/{project_id}/IN/"
        if in_manifest_mode == "off":
            section_records.append(
                {
                    "name": "IN Staging",
                    "path": in_manifest_path,
                    "chars": 0,
                    "included": False,
                    "reason": "omitted_by_request",
                }
            )
        elif budget_exhausted and max_chars > 0:
            section_records.append(
                {
                    "name": "IN Staging",
                    "path": in_manifest_path,
                    "chars": 0,
                    "included": False,
                    "reason": "over_budget",
                }
            )
        elif _is_time_exhausted(timings, effective_time_budget_ms):
            sections_omitted.append("IN Staging")
            section_records.append(
                {
                    "name": "IN Staging",
                    "path": in_manifest_path,
                    "chars": 0,
                    "included": False,
                    "reason": "time_budget_exceeded",
                }
            )
        elif in_manifest_mode == "summary":
            with _span(timings, "in_manifest"):
                summary_markdown, total_count = _render_in_manifest_summary(project_root, root)
            # ``more_in_items`` in summary mode is "items not shown as rows",
            # which is every file — the summary deliberately hides the table.
            more_in_items = total_count
            remaining_chars, reason = _append_section(
                sections,
                section_records,
                name="IN Staging",
                path=in_manifest_path,
                content=summary_markdown,
                remaining_chars=remaining_chars,
            )
            if reason == "over_budget":
                budget_exhausted = True
        else:
            with _span(timings, "in_manifest"):
                in_manifest, manifest_files, more_in_items = _render_in_manifest(project_root, root)
            remaining_chars, reason = _append_section(
                sections,
                section_records,
                name="IN Staging",
                path=in_manifest_path,
                content=in_manifest,
                remaining_chars=remaining_chars,
            )
            if reason == "over_budget":
                budget_exhausted = True
            else:
                loaded_files.extend(manifest_files)

        current_path = working_file_path("CURRENT.md", user_id=resolved_user_id)
        if not include_notes:
            section_records.append(
                {
                    "name": "Current Session Notes",
                    "path": current_path,
                    "chars": 0,
                    "included": False,
                    "reason": "omitted_by_request",
                }
            )
        elif budget_exhausted and max_chars > 0:
            section_records.append(
                {
                    "name": "Current Session Notes",
                    "path": current_path,
                    "chars": 0,
                    "included": False,
                    "reason": "over_budget",
                }
            )
        elif _is_time_exhausted(timings, effective_time_budget_ms):
            sections_omitted.append("Current Session Notes")
            section_records.append(
                {
                    "name": "Current Session Notes",
                    "path": current_path,
                    "chars": 0,
                    "included": False,
                    "reason": "time_budget_exceeded",
                }
            )
        else:
            with _span(timings, "session_notes"):
                current_content = _read_file_content(root, current_path)
            if current_content is None:
                section_records.append(
                    {
                        "name": "Current Session Notes",
                        "path": current_path,
                        "chars": 0,
                        "included": False,
                        "reason": "missing",
                    }
                )
            elif project_id.casefold() not in current_content.casefold():
                section_records.append(
                    {
                        "name": "Current Session Notes",
                        "path": current_path,
                        "chars": 0,
                        "included": False,
                        "reason": "not_relevant",
                    }
                )
            elif _is_placeholder(current_content):
                section_records.append(
                    {
                        "name": "Current Session Notes",
                        "path": current_path,
                        "chars": 0,
                        "included": False,
                        "reason": "placeholder",
                    }
                )
            else:
                remaining_chars, reason = _append_section(
                    sections,
                    section_records,
                    name="Current Session Notes",
                    path=current_path,
                    content=current_content,
                    remaining_chars=remaining_chars,
                )
                if reason == "included":
                    loaded_files.append(current_path)

        # Snapshot timings before rendering: the render span itself is not
        # tracked (it would need to be included in the very JSON it produces),
        # but consumers can still compute render self-time as
        # ``total_ms - sum(spans[*].duration_ms)`` after receiving the response.
        metadata = {
            "tool": "memory_context_project",
            "project": project_id,
            "plan_id": selected_plan_id,
            "plan_status": selected_plan_status,
            "plan_source": selected_plan_source,
            "plan_load_error": selected_plan_error,
            "active_plan_id": active_plan_id,
            "active_phase_id": current_phase_id if active_plan_id is not None else None,
            "current_phase_id": current_phase_id,
            "current_phase_title": current_phase_title,
            "next_action": next_action_metadata,
            "loaded_files": loaded_files,
            "budget_report": _build_budget_report(section_records, max_context_chars=max_chars),
            "timings": {
                "total_ms": timings.total_ms(),
                "spans": timings.spans(),
                "budget_ms": effective_time_budget_ms,
            },
            "truncated": bool(sections_omitted),
            "sections_omitted": sections_omitted,
            "more_in_items": more_in_items,
            "more_plan_sources": more_plan_sources,
            "cache_hit": False,
        }

        # Persist the cache after a clean render. Writing a partial (truncated)
        # bundle would mean that subsequent callers under the same params-key
        # receive truncated content even when the cause (time pressure,
        # over-budget char limit) is transient. Only cache complete bundles.
        if not sections_omitted:
            # Store a timing-stripped copy so cache hits don't mislabel
            # previously-measured latency as if it were this call's.
            cacheable_metadata = dict(metadata)
            cacheable_metadata.pop("timings", None)
            _write_cached_bundle(
                cache_path,
                content_hash=content_hash,
                params_key=params_key,
                metadata=cacheable_metadata,
                sections=sections,
            )

        return _assemble_markdown_response(metadata, sections)

    @mcp.tool(
        name="memory_context_project_lite",
        annotations=_tool_annotations(
            title="Project Context Injector (Lite)",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def memory_context_project_lite(
        project: str,
        max_context_chars: int = 8000,
    ) -> str:
        """Strictly-bounded project briefing — SUMMARY.md and plan IDs only.

        Safety valve for :func:`memory_context_project`. Does exactly two things:
        reads ``memory/working/projects/<project>/SUMMARY.md`` and enumerates
        plans by top-level ``id``/``status`` (no phase/source/blocker expansion).
        Every expensive step in the enriched tool — IN/ manifest walk, plan
        sources inlining, session notes, user profile, content-hash cache —
        is skipped. Intended to run well under 500ms on projects of any size
        because it touches a bounded, pre-known set of files.

        Use when:
        - ``memory_session_bootstrap`` needs a guaranteed-responsive briefing,
        - ``memory_context_project`` has tripped its time budget twice in a
          row and the caller wants to make forward progress anyway, or
        - the caller just needs a plan-name directory and can fetch
          per-plan detail via :func:`memory_plan_briefing` afterward.

        Not a replacement for ``memory_context_project``: it deliberately
        omits context an agent needs to *do* the work. It only gives you
        enough to choose the next tool call.
        """
        project_id = validate_slug(project, field_name="project")
        max_chars = _coerce_max_context_chars(max_context_chars)

        timings = _TimingCollector()
        root = get_root()
        projects_root = root / "memory" / "working" / "projects"
        project_root = projects_root / project_id
        if not project_root.is_dir():
            available = ", ".join(_list_project_ids(projects_root)) or "none"
            raise ValidationError(
                f"Unknown project '{project_id}'. Available projects: {available}"
            )

        sections: list[dict[str, str]] = []
        section_records: list[dict[str, Any]] = []
        loaded_files: list[str] = []
        remaining_chars = max_chars

        summary_rel = f"memory/working/projects/{project_id}/SUMMARY.md"
        with _span(timings, "project_summary"):
            summary_content, summary_chars_used, summary_reason = _read_section_status(
                root, summary_rel, remaining_chars
            )
        if summary_content is None:
            section_records.append(
                {
                    "name": "Project Summary",
                    "path": summary_rel,
                    "chars": 0,
                    "included": False,
                    "reason": summary_reason,
                }
            )
        else:
            sections.append(
                {"name": "Project Summary", "path": summary_rel, "content": summary_content}
            )
            section_records.append(
                {
                    "name": "Project Summary",
                    "path": summary_rel,
                    "chars": summary_chars_used,
                    "included": True,
                    "reason": "included",
                }
            )
            loaded_files.append(summary_rel)
            if remaining_chars > 0:
                remaining_chars = max(remaining_chars - summary_chars_used, 0)

        with _span(timings, "plan_listing"):
            plan_entries = _lite_plan_listing(project_root)

        plans_rel = f"memory/working/projects/{project_id}/plans/"
        if plan_entries:
            lines = ["| Plan ID | Status | File |", "|---|---|---|"]
            for entry in plan_entries:
                lines.append(f"| {entry['id']} | {entry['status']} | {entry['file']} |")
            plans_content = "\n".join(lines)
            remaining_chars, reason = _append_section(
                sections,
                section_records,
                name="Plans",
                path=plans_rel,
                content=plans_content,
                remaining_chars=remaining_chars,
            )
            # Even when the table overflows the char budget the caller still
            # gets the machine-readable list in ``metadata.plans``. No further
            # handling needed.
            del reason
        else:
            section_records.append(
                {
                    "name": "Plans",
                    "path": plans_rel,
                    "chars": 0,
                    "included": False,
                    "reason": "missing",
                }
            )

        active_plan_ids = [entry["id"] for entry in plan_entries if entry["status"] == "active"]

        metadata = {
            "tool": "memory_context_project_lite",
            "project": project_id,
            "plan_count": len(plan_entries),
            "active_plan_count": len(active_plan_ids),
            "active_plan_ids": active_plan_ids,
            "plans": plan_entries,
            "loaded_files": loaded_files,
            "budget_report": _build_budget_report(section_records, max_context_chars=max_chars),
            "timings": {
                "total_ms": timings.total_ms(),
                "spans": timings.spans(),
            },
        }
        return _assemble_markdown_response(metadata, sections)

    return {
        "memory_context_home": memory_context_home,
        "memory_context_project": memory_context_project,
        "memory_context_project_lite": memory_context_project_lite,
    }
