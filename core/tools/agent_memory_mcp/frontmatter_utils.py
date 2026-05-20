"""
Frontmatter parsing/writing and SUMMARY.md manipulation utilities.

Anchor conventions:
    SUMMARY.md in projects   → BEGIN/END pairs wrapping each plan block
    memory/knowledge/SUMMARY.md      → single <!-- section: {id} --> anchors above ### headings
    memory/knowledge/_unverified/SUMMARY.md → same

Project-scoped helpers generate the top-level projects navigator from
memory/working/projects/*/SUMMARY.md frontmatter.

These utilities are intentionally side-effect-free: they take content strings
and return new content strings. Callers handle reading/writing and staging.
"""

from __future__ import annotations

import logging
import re
from datetime import date
from pathlib import Path
from typing import Any

import frontmatter as fm

_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Frontmatter read/write
# ---------------------------------------------------------------------------


def read_with_frontmatter(abs_path: Path) -> tuple[dict[str, Any], str]:
    """Parse a file's YAML frontmatter.

    Returns:
        (frontmatter_dict, body_string) — body does not include the ---
        delimiters. If no frontmatter is present, returns ({}, full_content).
    """
    text = abs_path.read_text(encoding="utf-8")
    post = fm.loads(text)
    return dict(post.metadata), post.content


def write_with_frontmatter(
    abs_path: Path,
    fm_dict: dict[str, Any],
    body: str,
) -> None:
    """Serialise frontmatter + body back to disk."""
    abs_path.parent.mkdir(parents=True, exist_ok=True)
    post = fm.Post(body, **fm_dict)
    text = fm.dumps(post)
    abs_path.write_text(text, encoding="utf-8")


def render_with_frontmatter(fm_dict: dict[str, Any], body: str) -> str:
    """Return serialized frontmatter + body without writing it to disk."""
    post = fm.Post(body, **fm_dict)
    return fm.dumps(post)


def merge_frontmatter_fields(
    current_frontmatter: dict[str, Any],
    updates: dict[str, Any],
    *,
    create_missing_keys: bool = True,
    auto_last_verified: bool = False,
) -> tuple[dict[str, Any], bool]:
    """Merge updates into a frontmatter mapping and report whether anything changed."""
    merged = dict(current_frontmatter)
    changed = False

    for key, value in updates.items():
        if key not in merged and not create_missing_keys:
            continue
        if value is None:
            if key in merged:
                merged.pop(key, None)
                changed = True
            continue
        if merged.get(key) != value:
            merged[key] = value
            changed = True

    if changed and auto_last_verified and "last_verified" not in updates:
        current_last_verified = merged.get("last_verified")
        new_last_verified = str(date.today())
        if current_last_verified != new_last_verified:
            merged["last_verified"] = new_last_verified

    return merged, changed


def update_frontmatter_fields(
    abs_path: Path,
    updates: dict[str, Any],
    auto_last_verified: bool = False,
) -> dict[str, Any]:
    """Merge *updates* into the file's frontmatter and rewrite the file.

    If auto_last_verified is True and 'last_verified' is not in updates,
    sets last_verified to today's date.

    Returns the full updated frontmatter dict.
    """
    current_fm, body = read_with_frontmatter(abs_path)
    merged_fm, _ = merge_frontmatter_fields(
        current_fm,
        updates,
        auto_last_verified=auto_last_verified,
    )
    write_with_frontmatter(abs_path, merged_fm, body)
    return merged_fm


def today_str() -> str:
    return str(date.today())


def _coerce_int(value: Any, default: int = 0) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value.strip())
        except ValueError:
            return default
    return default


_PROJECT_STATUS_ORDER = {
    "active": 0,
    "ongoing": 1,
    "blocked": 2,
    "completed": 3,
    "archived": 4,
}


def collect_project_entries(root: Path) -> list[dict[str, Any]]:
    """Collect project-routing fields from project-local SUMMARY.md files."""
    projects_root = root / "memory" / "working" / "projects"
    if not projects_root.is_dir():
        return []

    entries: list[dict[str, Any]] = []
    for project_dir in sorted(projects_root.iterdir()):
        if not project_dir.is_dir():
            continue
        if project_dir.name == "OUT" or project_dir.name.startswith("_"):
            continue

        summary_path = project_dir / "SUMMARY.md"
        if not summary_path.is_file():
            continue

        try:
            fm_dict, _ = read_with_frontmatter(summary_path)
        except Exception:
            _log.warning("Failed to parse frontmatter in %s", summary_path, exc_info=True)
            fm_dict = {}

        entries.append(
            {
                "project_id": project_dir.name,
                "status": str(fm_dict.get("status", "unknown")),
                "cognitive_mode": str(fm_dict.get("cognitive_mode", "unknown")),
                "open_questions": _coerce_int(fm_dict.get("open_questions"), 0),
                "current_focus": str(fm_dict.get("current_focus", "")),
                "last_activity": str(fm_dict.get("last_activity", "")),
            }
        )

    entries.sort(
        key=lambda item: (
            _PROJECT_STATUS_ORDER.get(str(item["status"]), 99),
            str(item["project_id"]),
        )
    )
    return entries


def render_projects_navigator(
    project_entries: list[dict[str, Any]],
    generated_at: str | None = None,
) -> str:
    """Render the derived memory/working/projects/SUMMARY.md navigator."""
    generated = generated_at or today_str()
    has_active_or_ongoing = any(
        str(entry.get("status")) in {"active", "ongoing"} for entry in project_entries
    )

    lines = [
        "---",
        "type: projects-navigator",
        f"generated: {generated}",
        f"project_count: {len(project_entries)}",
        "---",
        "",
        "# Projects",
        "",
    ]

    if not has_active_or_ongoing:
        lines.append("_No active or ongoing projects._")
        lines.append("")
        return "\n".join(lines)

    lines.extend(
        [
            "| Project | Status | Mode | Open Qs | Focus | Last activity |",
            "|---|---|---|---|---|---|",
        ]
    )
    for entry in project_entries:
        lines.append(
            "| {project_id} | {status} | {mode} | {open_questions} | {focus} | {last_activity} |".format(
                project_id=str(entry.get("project_id", "")),
                status=str(entry.get("status", "unknown")),
                mode=str(entry.get("cognitive_mode", "unknown")),
                open_questions=_coerce_int(entry.get("open_questions"), 0),
                focus=str(entry.get("current_focus", "")).replace("|", "\\|"),
                last_activity=str(entry.get("last_activity", "")),
            )
        )
    lines.append("")
    return "\n".join(lines)


def count_active_project_plans(root: Path, project_id: str) -> int:
    """Count active plans within one project-local memory/working/projects/.../plans/ directory."""
    plans_dir = root / "memory" / "working" / "projects" / project_id / "plans"
    if not plans_dir.is_dir():
        return 0

    active_count = 0
    for plan_file in sorted(list(plans_dir.glob("*.yaml")) + list(plans_dir.glob("*.md"))):
        if not plan_file.is_file():
            continue
        if plan_file.suffix == ".yaml":
            try:
                import yaml  # type: ignore[import-untyped]

                raw = yaml.safe_load(plan_file.read_text(encoding="utf-8"))
            except Exception:
                _log.debug("Skipping unparseable plan YAML: %s", plan_file, exc_info=True)
                continue
            if not isinstance(raw, dict):
                continue
            status = str(raw.get("status", "unknown"))
            if status == "active":
                active_count += 1
            continue
        try:
            fm_dict, _ = read_with_frontmatter(plan_file)
            status = str(fm_dict.get("status", "unknown"))
        except Exception:
            _log.debug("Skipping unparseable plan MD: %s", plan_file, exc_info=True)
            continue
        if status == "active":
            active_count += 1
    return active_count


def count_project_plans(root: Path, project_id: str) -> int:
    """Count all YAML or legacy markdown plans within one project directory."""
    plans_dir = root / "memory" / "working" / "projects" / project_id / "plans"
    if not plans_dir.is_dir():
        return 0
    return sum(1 for plan_file in plans_dir.iterdir() if plan_file.suffix in {".yaml", ".md"})


# ---------------------------------------------------------------------------
# Project SUMMARY.md cold-start subsection helpers
# ---------------------------------------------------------------------------

# Headings produced by `build_project_cold_start_sections`. Consumers use these
# to detect and preserve the cold-start payload under budget pressure.
PROJECT_COLD_START_HEADINGS: tuple[str, ...] = (
    "Layout",
    "Canonical source",
    "How to continue",
)


def build_project_cold_start_sections(
    *,
    project_id: str,
    canonical_source: str | None = None,
    active_plan_paths: list[str] | None = None,
    questions_file_exists: bool = False,
    open_questions_count: int = 0,
    recent_in_items: list[str] | None = None,
    last_activity_date: str | None = None,
) -> list[str]:
    """Return body lines for Layout + optional Canonical source + How to continue.

    Signals are supplied by the caller: at project-creation time they come
    directly from input; at regeneration they are scanned from disk. Missing
    signals degrade gracefully — the output always contains the three (or two,
    when no canonical source is set) cold-start subsections a cold-starting
    agent needs.
    """
    project_base = f"memory/working/projects/{project_id}"
    lines: list[str] = [
        "",
        "## Layout",
        f"- [IN/]({project_base}/IN/) -- staged external material (snapshots from upstream)",
        f"- [OUT/]({project_base}/OUT/) -- artifacts emitted from this project",
        f"- [docs/]({project_base}/docs/) -- citation-grade references",
        f"- [notes/]({project_base}/notes/) -- working notes (lower trust)",
        f"- [plans/]({project_base}/plans/) -- active and completed YAML plans",
        f"- [questions.md]({project_base}/questions.md) -- open questions, if any",
        "",
        "See [memory/working/projects/README.md](memory/working/projects/README.md) for the full lifecycle.",
    ]

    if canonical_source:
        lines.extend(
            [
                "",
                "## Canonical source",
                f"- {canonical_source.strip()}",
            ]
        )

    lines.extend(["", "## How to continue"])
    continue_entries: list[str] = []
    for plan_path in active_plan_paths or []:
        continue_entries.append(f"- Active plan: [{plan_path}]({plan_path})")
    if questions_file_exists or open_questions_count:
        q_path = f"{project_base}/questions.md"
        suffix = f" ({open_questions_count} open)" if open_questions_count else ""
        continue_entries.append(f"- Open questions: [{q_path}]({q_path}){suffix}")
    for in_item in (recent_in_items or [])[:3]:
        continue_entries.append(f"- Recent IN/: [{in_item}]({in_item})")
    if last_activity_date:
        continue_entries.append(f"- Last activity: {last_activity_date}")
    if not continue_entries:
        continue_entries.append("- _Empty project -- add a plan with `memory_plan_create`._")
    lines.extend(continue_entries)
    return lines


def extract_project_cold_start_sections(body: str) -> str | None:
    """Return just the Layout / Canonical source / How to continue subsections.

    Used by ``memory_context_project`` to preserve the cold-start payload when
    the full SUMMARY.md body overflows the remaining character budget. Returns
    ``None`` when none of the cold-start headings are present.
    """
    lines = body.splitlines()
    section_starts: list[int] = []
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("## "):
            heading = stripped[3:].strip()
            if heading in PROJECT_COLD_START_HEADINGS:
                section_starts.append(idx)
    if not section_starts:
        return None

    collected: list[str] = []
    for start in section_starts:
        end = len(lines)
        for idx in range(start + 1, len(lines)):
            if lines[idx].lstrip().startswith("## "):
                end = idx
                break
        segment = lines[start:end]
        # Trim trailing blank lines inside each segment to keep output tight.
        while segment and not segment[-1].strip():
            segment.pop()
        collected.extend(segment)
        collected.append("")
    # Trim a single trailing blank if one leaked in.
    while collected and not collected[-1].strip():
        collected.pop()
    return "\n".join(collected) + "\n"


def collect_project_cold_start_signals(
    root: Path,
    project_id: str,
    *,
    canonical_source: str | None = None,
) -> dict[str, Any]:
    """Scan a project folder and return kwargs for ``build_project_cold_start_sections``.

    Returns a dict ready to splat into ``build_project_cold_start_sections``.
    Graceful under partial state — missing subfolders, empty plans/, and absent
    operations logs all produce sensible defaults instead of raising.
    """
    project_root = root / "memory" / "working" / "projects" / project_id
    active_plan_paths: list[str] = []
    plans_dir = project_root / "plans"
    if plans_dir.is_dir():
        for plan_file in sorted(plans_dir.glob("*.yaml")):
            try:
                import yaml  # type: ignore[import-untyped]

                raw = yaml.safe_load(plan_file.read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001 - degrade gracefully
                continue
            if not isinstance(raw, dict):
                continue
            status = str(raw.get("status") or "").lower()
            if status in {"active", "draft", "planning", "in_progress"}:
                rel = plan_file.relative_to(root).as_posix()
                active_plan_paths.append(rel)

    questions_path = project_root / "questions.md"
    questions_file_exists = questions_path.is_file()
    open_questions_count = 0
    if questions_file_exists:
        try:
            fm_dict, _ = read_with_frontmatter(questions_path)
            open_questions_count = _coerce_int(fm_dict.get("open_questions"), 0)
        except Exception:  # noqa: BLE001
            open_questions_count = 0
        if open_questions_count == 0:
            # Fall back to counting ## q-### headings if frontmatter is absent.
            try:
                text = questions_path.read_text(encoding="utf-8")
            except OSError:
                text = ""
            open_questions_count = sum(
                1 for ln in text.splitlines() if ln.lstrip().startswith("## q-")
            )

    recent_in_items: list[str] = []
    in_dir = project_root / "IN"
    if in_dir.is_dir():
        candidates = [entry for entry in in_dir.iterdir() if entry.is_file()]
        candidates.sort(key=lambda item: item.stat().st_mtime, reverse=True)
        for entry in candidates[:3]:
            recent_in_items.append(entry.relative_to(root).as_posix())

    last_activity_date: str | None = None
    summary_path = project_root / "SUMMARY.md"
    if summary_path.is_file():
        try:
            fm_dict, _ = read_with_frontmatter(summary_path)
            value = fm_dict.get("last_activity")
            if value:
                last_activity_date = str(value)
        except Exception:  # noqa: BLE001
            last_activity_date = None

    return {
        "project_id": project_id,
        "canonical_source": canonical_source,
        "active_plan_paths": active_plan_paths,
        "questions_file_exists": questions_file_exists,
        "open_questions_count": open_questions_count,
        "recent_in_items": recent_in_items,
        "last_activity_date": last_activity_date,
    }


# ---------------------------------------------------------------------------
# Plan file parsing and manipulation
# ---------------------------------------------------------------------------

# Matches: "### Phase 2 — High-value semantic tools · ☐ 0/3 complete"
_PHASE_HEADING_RE = re.compile(
    r"^(### Phase \d+ —[^·]+·\s*)(☐|☑)\s*(\d+)/(\d+)\s*complete",
    re.MULTILINE,
)
# Matches: "1. ☐ Some item text"  or  "1. ☑ Some item text"
_ITEM_RE = re.compile(r"^(\d+)\.\s+(☐|☑)\s+(.+)$")

# Matches progress log table rows: "| date | ... |"
_PROGRESS_LOG_TABLE_RE = re.compile(r"^\| \d{4}-\d{2}-\d{2} \|", re.MULTILINE)


def _split_into_phases(lines: list[str]) -> list[tuple[int, int]]:
    """Return (start_line, end_line) slices for each ### Phase heading block.

    end_line is exclusive (like Python slice indexing).
    """
    phase_starts = [i for i, line in enumerate(lines) if _PHASE_HEADING_RE.match(line)]
    bounds = []
    for idx, start in enumerate(phase_starts):
        end = phase_starts[idx + 1] if idx + 1 < len(phase_starts) else len(lines)
        bounds.append((start, end))
    return bounds


def parse_plan_items(
    content: str,
) -> list[dict]:
    """Parse all phases and items from a plan file.

    Returns a list of phases, each:
    {
      "phase_index": int,
      "heading_line": int,         # 0-based line number of the ### Phase heading
      "done": int,
      "total": int,
      "complete": bool,            # True if checkbox is ☑
      "items": [
          {"item_index": int, "line": int, "done": bool, "text": str}
      ]
    }
    """
    lines = content.splitlines()
    phase_bounds = _split_into_phases(lines)
    phases = []

    for phase_idx, (start, end) in enumerate(phase_bounds):
        heading = lines[start]
        m = _PHASE_HEADING_RE.match(heading)
        if not m:
            continue
        checkbox, done_str, total_str = m.group(2), m.group(3), m.group(4)
        items = []
        item_idx = 0
        for line_no in range(start + 1, end):
            im = _ITEM_RE.match(lines[line_no])
            if im:
                items.append(
                    {
                        "item_index": item_idx,
                        "line": line_no,
                        "done": im.group(2) == "☑",
                        "text": im.group(3).strip(),
                    }
                )
                item_idx += 1
        phases.append(
            {
                "phase_index": phase_idx,
                "heading_line": start,
                "done": int(done_str),
                "total": int(total_str),
                "complete": checkbox == "☑",
                "items": items,
            }
        )
    return phases


def mark_plan_item_complete(
    content: str,
    phase_index: int,
    item_index: int,
) -> tuple[str, dict]:
    """Mark a plan item ☐→☑, update phase counter, return (new_content, stats).

    stats = {
        "next_action": str | None,   # text of first remaining unchecked item
        "phase_progress": [done, total],
        "plan_progress": [done, total],
        "all_complete": bool,
    }

    Raises:
        NotFoundError  — phase_index or item_index out of range
        AlreadyDoneError — item is already ☑
    """
    from .errors import AlreadyDoneError, NotFoundError

    phases = parse_plan_items(content)

    # Validate indices
    if phase_index >= len(phases):
        raise NotFoundError(
            f"Phase index {phase_index} out of range (plan has {len(phases)} phases)"
        )
    phase = phases[phase_index]
    if item_index >= len(phase["items"]):
        raise NotFoundError(
            f"Item index {item_index} out of range (phase {phase_index} has "
            f"{len(phase['items'])} items)"
        )
    item = phase["items"][item_index]
    if item["done"]:
        raise AlreadyDoneError(f"Item {phase_index}.{item_index} is already complete")

    lines = content.splitlines(keepends=True)

    # 1. Mark item ☐ → ☑
    item_line_no = item["line"]
    lines[item_line_no] = _ITEM_RE.sub(
        lambda m: f"{m.group(1)}. ☑ {m.group(3)}",
        lines[item_line_no].rstrip("\n"),
    ) + ("\n" if lines[item_line_no].endswith("\n") else "")

    # 2. Update phase counter
    new_done = phase["done"] + 1
    new_total = phase["total"]
    heading_line_no = phase["heading_line"]
    new_phase_checkbox = "☑" if new_done == new_total else "☐"
    lines[heading_line_no] = _PHASE_HEADING_RE.sub(
        lambda m: f"{m.group(1)}{new_phase_checkbox} {new_done}/{new_total} complete",
        lines[heading_line_no].rstrip("\n"),
    ) + ("\n" if lines[heading_line_no].endswith("\n") else "")

    new_content = "".join(lines)

    # 3. Find next unchecked item (re-parse updated content)
    updated_phases = parse_plan_items(new_content)
    next_action = None
    plan_done = 0
    plan_total = 0
    for ph in updated_phases:
        plan_total += ph["total"]
        for it in ph["items"]:
            plan_done += 1 if it["done"] else 0
            if next_action is None and not it["done"]:
                next_action = it["text"]

    all_complete = next_action is None

    stats = {
        "next_action": next_action,
        "phase_progress": [new_done, new_total],
        "plan_progress": [plan_done, plan_total],
        "all_complete": all_complete,
    }
    return new_content, stats


def add_progress_log_row(content: str, action_description: str) -> str:
    """Append a row to the progress log table at the bottom of a plan file."""
    today = today_str()
    new_row = f"| {today} | {action_description} |"
    # Find the last | date | line and insert after it
    lines = content.splitlines(keepends=True)
    last_table_line = -1
    for i, line in enumerate(lines):
        if re.match(r"^\| \d{4}-\d{2}-\d{2} \|", line):
            last_table_line = i
    if last_table_line >= 0:
        lines.insert(last_table_line + 1, new_row + "\n")
    else:
        # No table yet — append at end
        lines.append("\n" + new_row + "\n")
    return "".join(lines)


# ---------------------------------------------------------------------------
# memory/working/projects/SUMMARY.md — BEGIN/END anchor manipulation
# ---------------------------------------------------------------------------


def find_begin_end_block(content: str, block_id: str) -> tuple[int, int] | None:
    """Find (begin_line_idx, end_line_idx) inclusive for a BEGIN/END pair.

    Returns None if the block is not found.
    """
    lines = content.splitlines()
    begin_tag = f"<!-- BEGIN: {block_id} -->"
    end_tag = f"<!-- END: {block_id} -->"
    begin_idx = None
    for i, line in enumerate(lines):
        if begin_tag in line:
            begin_idx = i
        elif begin_idx is not None and end_tag in line:
            return (begin_idx, i)
    return None


def replace_begin_end_block(content: str, block_id: str, new_block_content: str) -> str | None:
    """Replace the content between (and including) BEGIN/END anchors.

    new_block_content should include the BEGIN and END tag lines.
    Returns content unchanged (with a warning-flaggable None return) if not found.
    """
    bounds = find_begin_end_block(content, block_id)
    if bounds is None:
        return None  # Caller should add to warnings

    lines = content.splitlines(keepends=True)
    begin_idx, end_idx = bounds

    new_lines_raw = new_block_content.splitlines(keepends=True)
    # Ensure trailing newline on new block
    if new_lines_raw and not new_lines_raw[-1].endswith("\n"):
        new_lines_raw[-1] += "\n"

    result_lines = lines[:begin_idx] + new_lines_raw + lines[end_idx + 1 :]
    return "".join(result_lines)


def build_plan_summary_block(
    plan_id: str,
    title: str,
    status: str,
    trust: str,
    next_action: str | None,
    plan_progress: tuple[int, int],
    description: str = "",
    detail_path: str | None = None,
) -> str:
    """Build a BEGIN/END block for the plans SUMMARY."""
    done, total = plan_progress
    status_str = status
    next_str = next_action or "(all complete)"
    heading_title = title.strip() if title.strip() else plan_id
    lines = [
        f"<!-- BEGIN: {plan_id} -->",
        f"### {heading_title} · status: {status_str} · trust: {trust}",
        f"Detail: {detail_path or f'memory/working/projects/{plan_id}.md'}",
    ]
    if description:
        lines.append(f"Scope: {description}")
    lines += [
        f"Progress: {done}/{total} complete",
        f"Next: {next_str}",
        f"<!-- END: {plan_id} -->",
    ]
    return "\n".join(lines) + "\n"


def append_plan_to_summary(summary_content: str, block: str) -> str:
    """Append a new plan block to the plans SUMMARY (for new plans)."""
    # Append before the final "## Completed plans" section if it exists,
    # otherwise at end
    completed_marker = "## Completed plans"
    if completed_marker in summary_content:
        idx = summary_content.index(completed_marker)
        return summary_content[:idx] + block + "\n---\n\n" + summary_content[idx:]
    return summary_content.rstrip() + "\n\n---\n\n" + block


# ---------------------------------------------------------------------------
# memory/knowledge/SUMMARY.md — section anchor manipulation
# ---------------------------------------------------------------------------


def find_section_bounds(content: str, section_id: str) -> tuple[int, int] | None:
    """Find (anchor_line_idx, exclusive_end_line_idx) for a section anchor.

    The anchor line is `<!-- section: {section_id} -->`.
    Section ends at the next `<!-- section:` anchor, `---`, or EOF.

    Returns None if anchor not found.
    """
    lines = content.splitlines()
    anchor_tag = f"<!-- section: {section_id} -->"
    anchor_line = None
    for i, line in enumerate(lines):
        if anchor_tag in line:
            anchor_line = i
            break
    if anchor_line is None:
        return None

    end_line = len(lines)
    for i in range(anchor_line + 1, len(lines)):
        line = lines[i]
        if "<!-- section:" in line or line.strip() == "---":
            end_line = i
            break
    return (anchor_line, end_line)


def insert_entry_in_section(
    content: str,
    section_id: str,
    new_entry: str,
) -> str | None:
    """Insert a bullet entry into a knowledge SUMMARY section.

    Inserts before the blank line / next section boundary.
    Returns None if section not found.
    """
    bounds = find_section_bounds(content, section_id)
    if bounds is None:
        return None

    lines = content.splitlines(keepends=True)
    _, end_line = bounds

    # Insert just before the section end, after the last bullet
    # Find last non-empty line within the section
    insert_at = end_line
    for i in range(end_line - 1, bounds[0], -1):
        if lines[i].strip():
            insert_at = i + 1
            break

    entry_line = new_entry if new_entry.endswith("\n") else new_entry + "\n"
    lines.insert(insert_at, entry_line)
    return "".join(lines)


def remove_entry_from_section(
    content: str,
    section_id: str,
    filename: str,
) -> str | None:
    """Remove a bullet entry matching filename from a knowledge SUMMARY section.

    Matches any line within the section that contains the filename.
    Returns None if section not found. Returns content unchanged if entry not found.
    """
    bounds = find_section_bounds(content, section_id)
    if bounds is None:
        return None

    lines = content.splitlines(keepends=True)
    anchor_line, end_line = bounds

    new_lines = []
    for i, line in enumerate(lines):
        if anchor_line < i < end_line and filename in line:
            continue  # Remove this line
        new_lines.append(line)
    return "".join(new_lines)


def infer_section_id_from_path(rel_path: str) -> str:
    """Infer the SUMMARY.md section anchor from a knowledge file's path.

    memory/knowledge/_unverified/django/celery-canvas.md → "django"
    memory/knowledge/react/tanstack-query.md             → "react"
    memory/knowledge/philosophy/history/foo.md           → "philosophy"
    """
    parts = Path(rel_path).parts
    # Find the first folder after "memory/knowledge/" or "memory/knowledge/_unverified/"
    try:
        k_idx = parts.index("knowledge")
    except ValueError:
        return parts[0] if parts else "unknown"
    subject_idx = k_idx + 1
    if subject_idx < len(parts) and parts[subject_idx] == "_unverified":
        subject_idx += 1
    if subject_idx < len(parts):
        return parts[subject_idx]
    return "unknown"


def infer_subject_from_path(rel_path: str) -> str:
    """Same as infer_section_id_from_path — used in filenames/log messages."""
    return infer_section_id_from_path(rel_path)
