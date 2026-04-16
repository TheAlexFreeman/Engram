"""Read tools - context injector helpers and tool registrations."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import yaml  # type: ignore[import-untyped]

from ...errors import ValidationError
from ...frontmatter_utils import read_with_frontmatter
from ...identity_paths import normalize_user_id, working_file_path
from ...path_policy import validate_slug
from ...plan_utils import budget_status, load_plan, next_action, phase_payload, resolve_phase

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

    from ...session_state import SessionState


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


def _render_in_manifest(project_root: Path, root: Path) -> tuple[str, list[str]]:
    in_root = project_root / "IN"
    if not in_root.is_dir():
        return "No staged files.", []

    rows: list[str] = [
        "| Path | Trust | Source | Created |",
        "|---|---|---|---|",
    ]
    loaded_files: list[str] = []
    for file_path in sorted(path for path in in_root.rglob("*") if path.is_file()):
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
    if len(rows) == 2:
        return "No staged files.", []
    return "\n".join(rows), loaded_files


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
        include_plan_sources: bool = True,
        include_user_profile: bool | None = None,
    ) -> str:
        """Load project-focused context in one Markdown response with JSON metadata."""
        project_id = validate_slug(project, field_name="project")
        max_chars = _coerce_max_context_chars(max_context_chars)
        include_sources = _coerce_bool(include_plan_sources, field_name="include_plan_sources")
        include_profile_preference = _coerce_optional_bool(
            include_user_profile,
            field_name="include_user_profile",
        )

        root = get_root()
        resolved_user_id = _resolved_user_id(session_state)
        projects_root = root / "memory" / "working" / "projects"
        project_root = projects_root / project_id
        if not project_root.is_dir():
            available = ", ".join(_list_project_ids(projects_root)) or "none"
            raise ValidationError(
                f"Unknown project '{project_id}'. Available projects: {available}"
            )

        selected_plan_path, plan_context = _select_current_plan(project_root, root)
        effective_include_profile = (
            include_profile_preference
            if include_profile_preference is not None
            else plan_context is None
        )
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
            else:
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
        else:
            project_summary, chars_used, reason = _read_section_status(
                root,
                project_summary_path,
                remaining_chars,
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
                        "reason": "included",
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
                for source in cast(list[dict[str, Any]], plan_context.get("sources") or []):
                    source_path = str(source.get("path") or "")
                    name = f"Source: {source_path}"
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
                    if remaining_chars > 0:
                        remaining_chars = max(remaining_chars - source_chars, 0)

        if budget_exhausted and max_chars > 0:
            section_records.append(
                {
                    "name": "IN Staging",
                    "path": f"memory/working/projects/{project_id}/IN/",
                    "chars": 0,
                    "included": False,
                    "reason": "over_budget",
                }
            )
        else:
            in_manifest, manifest_files = _render_in_manifest(project_root, root)
            remaining_chars, reason = _append_section(
                sections,
                section_records,
                name="IN Staging",
                path=f"memory/working/projects/{project_id}/IN/",
                content=in_manifest,
                remaining_chars=remaining_chars,
            )
            if reason == "over_budget":
                budget_exhausted = True
            else:
                loaded_files.extend(manifest_files)

        current_path = working_file_path("CURRENT.md", user_id=resolved_user_id)
        if budget_exhausted and max_chars > 0:
            section_records.append(
                {
                    "name": "Current Session Notes",
                    "path": current_path,
                    "chars": 0,
                    "included": False,
                    "reason": "over_budget",
                }
            )
        else:
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
        }
        return _assemble_markdown_response(metadata, sections)

    return {
        "memory_context_home": memory_context_home,
        "memory_context_project": memory_context_project,
    }
