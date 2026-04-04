"""Implementation of the ``engram init`` subcommand.

Initializes an Engram memory worktree inside an existing host git repository.
This is the pure-Python equivalent of ``HUMANS/setup/init-worktree.sh``.
"""

from __future__ import annotations

import argparse
import json
import re
import shlex
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_PLATFORMS = ("codex", "claude-code", "cursor", "chatgpt", "generic")
VALID_PROFILES = (
    "software-developer",
    "researcher",
    "project-manager",
    "designer",
    "educator",
    "student",
    "writer",
)

_TODAY = date.today().isoformat()


# ---------------------------------------------------------------------------
# Seed repo location
# ---------------------------------------------------------------------------


def _seed_repo_root() -> Path:
    """Locate the Engram seed repository root from the installed package.

    The package layout maps ``engram_mcp → core/tools`` so this file lives at
    ``core/tools/agent_memory_mcp/cli/cmd_init.py`` — four parents up reaches
    the repository root.
    """
    return Path(__file__).resolve().parents[4]


def _seed_manifest(seed_root: Path) -> Path:
    return seed_root / "HUMANS" / "setup" / "init-worktree-paths.txt"


def _templates_root(seed_root: Path) -> Path:
    return seed_root / "HUMANS" / "setup" / "templates"


# ---------------------------------------------------------------------------
# CLI registration
# ---------------------------------------------------------------------------


def register_init(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
    *,
    parents: list[argparse.ArgumentParser] | None = None,
) -> argparse.ArgumentParser:
    parser = subparsers.add_parser(
        "init",
        help="Initialize an Engram memory worktree inside the current host repository.",
        parents=parents or [],
    )
    parser.add_argument(
        "--platform",
        choices=VALID_PLATFORMS,
        default="cursor",
        help="AI platform for MCP config generation (default: cursor).",
    )
    parser.add_argument(
        "--profile",
        choices=VALID_PROFILES,
        default="software-developer",
        help="Starter profile template (default: software-developer).",
    )
    parser.add_argument(
        "--worktree-path",
        default=".engram",
        help="Worktree path relative to the host repo root (default: .engram).",
    )
    parser.add_argument(
        "--branch-name",
        default=None,
        help="Orphan branch name (default: worktree--<host-repo-name>).",
    )
    parser.add_argument(
        "--user-name",
        default="",
        help="Optional user name for template-backed starter summaries.",
    )
    parser.add_argument(
        "--user-context",
        default="",
        help="Optional AI-use context for template-backed starter summaries.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned git commands without executing them.",
    )
    parser.set_defaults(handler=run_init)
    return parser


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------


def _git(
    *args: str, cwd: Path | None = None, check: bool = True
) -> subprocess.CompletedProcess[str]:
    cmd = ["git", *args]
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=check)


def _print_cmd(*args: str) -> None:
    print("+ " + " ".join(shlex.quote(a) for a in args))


def _run_git(dry_run: bool, *args: str, cwd: Path | None = None) -> None:
    cmd = ["git", *args]
    _print_cmd(*cmd)
    if not dry_run:
        subprocess.run(cmd, cwd=cwd, check=True)


# ---------------------------------------------------------------------------
# File-writing helpers
# ---------------------------------------------------------------------------


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _write_text(path: Path, content: str) -> None:
    _ensure_parent(path)
    path.write_text(content, encoding="utf-8")


def _write_empty(path: Path) -> None:
    _ensure_parent(path)
    path.write_text("", encoding="utf-8")


def _copy_seed_path(source_root: Path, dest_root: Path, relative: str) -> None:
    src = source_root / relative
    dst = dest_root / relative
    _ensure_parent(dst)
    if src.is_dir():
        shutil.copytree(src, dst, dirs_exist_ok=True)
    else:
        shutil.copy2(src, dst)


# ---------------------------------------------------------------------------
# Template rendering
# ---------------------------------------------------------------------------


def _render_template(text: str, variables: dict[str, str]) -> str:
    for key, value in variables.items():
        text = text.replace("{{" + key + "}}", value)
    # Also replace YYYY-MM-DD date placeholders used in profile templates
    text = text.replace("YYYY-MM-DD", _TODAY)
    return text


def _render_template_file(
    template_path: Path,
    dest_path: Path,
    variables: dict[str, str],
) -> None:
    _ensure_parent(dest_path)
    content = template_path.read_text(encoding="utf-8")
    dest_path.write_text(_render_template(content, variables), encoding="utf-8")


# ---------------------------------------------------------------------------
# Content generators (ported from init-worktree.sh)
# ---------------------------------------------------------------------------


def _write_memory_stubs(wt: Path) -> None:
    """Create the core/memory directory scaffold with empty marker files."""
    for d in (
        "core/memory/activity",
        "core/memory/users",
        "core/memory/knowledge/_unverified",
        "core/memory/working/projects/OUT",
        "core/memory/working/notes",
    ):
        (wt / d).mkdir(parents=True, exist_ok=True)

    for f in (
        "core/memory/activity/ACCESS.jsonl",
        "core/memory/users/ACCESS.jsonl",
        "core/memory/knowledge/ACCESS.jsonl",
        "core/memory/knowledge/_unverified/ACCESS.jsonl",
        "core/memory/working/projects/ACCESS.jsonl",
    ):
        _write_empty(wt / f)

    _write_text(
        wt / "core/memory/activity/SUMMARY.md",
        "# Activity Summary\n\n_Nothing here yet._\n",
    )
    _write_text(
        wt / "core/memory/knowledge/SUMMARY.md",
        "# Knowledge Summary\n\n"
        "No codebase knowledge has been captured yet.\n\n"
        "Add compact architecture notes here as the memory worktree learns the host project.\n",
    )
    _write_text(
        wt / "core/memory/knowledge/_unverified/SUMMARY.md",
        "# Unverified Knowledge Summary\n\n"
        "Use this area for external research and unverified notes until they are reviewed.\n",
    )
    _write_text(
        wt / "core/memory/working/projects/SUMMARY.md",
        f"---\ntype: projects-navigator\ngenerated: {_TODAY} 12:00\nproject_count: 0\n---\n\n"
        "# Projects\n\n_No active or ongoing projects._\n",
    )
    _write_text(
        wt / "core/memory/working/projects/OUT/SUMMARY.md",
        "# Project Outbox\n\n_No shipped artifacts yet._\n",
    )
    _write_text(
        wt / "core/memory/working/CURRENT.md",
        "# Agent working notes\n\n"
        "Provisional, agent-authored. Not formal memory.\n\n"
        "See `core/governance/scratchpad-guidelines.md` for the full write protocol.\n\n"
        "---\n\n"
        "## Active threads\n\n"
        "- **Codebase survey** — Active project. Begin with the entry-point-mapping phase "
        "after onboarding completes. See "
        "`core/memory/working/projects/codebase-survey/plans/survey-plan.yaml`.\n\n"
        "## Immediate next actions\n\n"
        "- Complete onboarding (first session), then begin entry-point-mapping phase of the "
        "codebase survey (second session).\n\n"
        "## Open questions\n\n_None_\n\n"
        "## Drill-down refs\n\n"
        "- `core/memory/working/projects/SUMMARY.md` for the project navigator.\n"
        "- `core/memory/working/projects/codebase-survey/plans/survey-plan.yaml` for the "
        "survey plan.\n",
    )
    _write_text(
        wt / "core/memory/working/USER.md",
        "# User Scratchpad\n\n"
        "User-authored constraints and reminders for this codebase belong here.\n",
    )


def _write_identity_summary(wt: Path, *, user_name: str = "", user_context: str = "") -> None:
    lines = [
        "# Identity Summary\n",
        "Template-based profile — pending onboarding confirmation.\n",
        "A starter profile has been installed from a template. During the first",
        "session, the onboarding skill will walk through the template traits and",
        "confirm, adjust, or remove them.\n",
        "See [profile.md](profile.md) for the current profile.\n",
    ]
    if user_name:
        lines.append(f"**User:** {user_name}\n")
    if user_context:
        lines.append(f"**Uses AI for:** {user_context}\n")
    _write_text(wt / "core/memory/users/SUMMARY.md", "\n".join(lines))


def _ensure_codebase_context(
    profile_path: Path,
    *,
    project_name: str,
    host_root: str,
    worktree_path: str,
) -> None:
    text = profile_path.read_text(encoding="utf-8")
    context_block = (
        f"\n## Codebase context\n\n"
        f"- **project_name:** {project_name}\n"
        f"- **tech_stack:** _[To be filled during onboarding or the first survey session]_\n"
        f"- **repo_url:** _[Optional - remote URL or canonical repo reference]_\n"
        f"- **codebase_root:** {host_root}\n"
        f"- **host_repo_root:** {host_root}\n"
        f"- **memory_worktree_path:** {worktree_path}\n"
    )

    if "<!-- CODEBASE_CONTEXT_START -->" in text:
        # Replace content between markers using string operations to avoid
        # regex replacement escaping issues with Windows backslash paths.
        start_marker = "<!-- CODEBASE_CONTEXT_START -->"
        end_marker = "<!-- CODEBASE_CONTEXT_END -->"
        start_idx = text.index(start_marker)
        end_idx = text.index(end_marker)
        inner = (
            f"\n- **project_name:** {project_name}\n"
            f"- **tech_stack:** _[To be filled during onboarding or the first survey session]_\n"
            f"- **repo_url:** _[Optional - remote URL or canonical repo reference]_\n"
            f"- **codebase_root:** {host_root}\n"
            f"- **host_repo_root:** {host_root}\n"
            f"- **memory_worktree_path:** {worktree_path}\n"
        )
        text = text[: start_idx + len(start_marker)] + inner + text[end_idx:]
        profile_path.write_text(text, encoding="utf-8")
    else:
        with profile_path.open("a", encoding="utf-8") as f:
            f.write(context_block)


def _install_profile(
    wt: Path,
    *,
    seed_root: Path,
    profile: str,
    project_name: str,
    host_root: str,
    worktree_path: str,
    user_name: str,
    user_context: str,
) -> None:
    dest = wt / "core/memory/users/profile.md"
    _ensure_parent(dest)

    if profile:
        template = _templates_root(seed_root) / "profiles" / f"{profile}.md"
        if not template.exists():
            raise FileNotFoundError(f"Profile template not found: {template}")
        content = template.read_text(encoding="utf-8").replace("YYYY-MM-DD", _TODAY)
        dest.write_text(content, encoding="utf-8")
        _write_identity_summary(wt, user_name=user_name, user_context=user_context)
    else:
        _write_text(
            dest,
            f"---\nsource: template\norigin_session: setup\ncreated: {_TODAY}\n"
            "trust: medium\n---\n\n# User Profile\n\n"
            "Worktree-backed memory store. Confirm or replace these defaults during onboarding.\n",
        )
        _write_text(
            wt / "core/memory/users/SUMMARY.md",
            "# Identity Summary\n\nNo confirmed identity summary yet.\n\n"
            "Start onboarding from [profile.md](profile.md) in the memory worktree.\n",
        )

    _ensure_codebase_context(
        dest,
        project_name=project_name,
        host_root=host_root,
        worktree_path=worktree_path,
    )


def _write_worktree_hygiene_files(wt: Path) -> None:
    _write_text(
        wt / ".ignore",
        "# Hide memory-content folders from host-repo search tools by default.\n"
        "# When working inside the memory worktree directly, use rg --no-ignore (or the\n"
        "# equivalent in your editor) if you need to search these folders intentionally.\n"
        "core/memory/activity/\n"
        "core/memory/users/\n"
        "core/memory/knowledge/\n"
        "core/governance/\n"
        "core/memory/working/projects/\n"
        "core/memory/working/notes/\n"
        "core/memory/skills/\n",
    )
    _write_text(
        wt / ".editorconfig",
        "root = true\n\n"
        "[*]\ncharset = utf-8\nend_of_line = lf\n"
        "insert_final_newline = true\ntrim_trailing_whitespace = false\n\n"
        "[*.md]\nindent_style = space\nindent_size = 2\n\n"
        "[*.jsonl]\nindent_style = space\nindent_size = 2\n",
    )


def _write_codebase_starters(
    wt: Path,
    *,
    seed_root: Path,
    variables: dict[str, str],
    project_name: str,
    branch_name: str,
) -> None:
    tpl_root = _templates_root(seed_root)

    # Survey plan
    survey_plan_dest = wt / "core/memory/working/projects/codebase-survey/plans/survey-plan.yaml"
    _render_template_file(
        tpl_root / "codebase-survey-plan.yaml",
        survey_plan_dest,
        variables,
    )

    # Directories
    (wt / "core/memory/working/projects/codebase-survey/IN").mkdir(parents=True, exist_ok=True)
    (wt / "core/memory/working/projects/codebase-survey/plans").mkdir(parents=True, exist_ok=True)

    # Project SUMMARY
    _write_text(
        wt / "core/memory/working/projects/codebase-survey/SUMMARY.md",
        f"---\nsource: template\norigin_session: setup\ncreated: {_TODAY}\ntrust: medium\n"
        f"type: project\nstatus: active\ncognitive_mode: exploration\nopen_questions: 5\n"
        f"active_plans: 1\nlast_activity: {_TODAY}\n"
        f'current_focus: "Capture the architecture, interfaces, operations, and design '
        f'rationale for {project_name}."\n---\n\n'
        "# Project: Codebase Survey\n\n"
        "## Description\n"
        f"Build a durable, codebase-specific map of {project_name} so future sessions can "
        "orient quickly without re-reading the whole host repository.\n\n"
        "## Cognitive mode\n"
        "Exploration mode fits the initial survey: the goal is to discover stable structure, "
        "capture it compactly, and turn low-trust stubs into verified knowledge.\n\n"
        "## Artifact flow\n"
        "- IN/: temporary exploration notes, rough subsystem maps, and open questions that "
        "are not ready for durable promotion\n"
        "- OUT contributions: verified core/memory/knowledge/codebase notes and any reusable "
        "operational guidance derived from the host repo\n\n"
        "## Notes\n"
        "Start from `plans/survey-plan.yaml` and replace the template stubs under "
        "`core/memory/knowledge/codebase/` one by one.\n",
    )

    # Questions
    _write_text(
        wt / "core/memory/working/projects/codebase-survey/questions.md",
        f"---\nsource: template\norigin_session: setup\ncreated: {_TODAY}\ntrust: medium\n"
        "type: questions\nnext_question_id: 6\n---\n\n"
        "# Open Questions\n\n"
        "1. What are the main entry points for this application? `[entry-point-mapping]`\n"
        "2. What build, test, and run commands does this project use? `[operations-and-delivery]`\n"
        "3. What is the primary tech stack (language, framework, database)? `[subsystem-survey]`\n"
        "4. Are there existing architecture docs, ADRs, or CONTRIBUTING guides? `[decisions-and-history]`\n"
        "5. What are the main deployment targets and CI pipelines? `[operations-and-delivery]`\n\n"
        "---\n\n# Resolved Questions\n\n_None yet._\n",
    )

    # Knowledge codebase stubs
    codebase_tpl_dir = tpl_root / "knowledge" / "codebase"
    if codebase_tpl_dir.is_dir():
        for tpl_file in sorted(codebase_tpl_dir.glob("*.md")):
            _render_template_file(
                tpl_file,
                wt / "core/memory/knowledge/codebase" / tpl_file.name,
                variables,
            )

    # Knowledge SUMMARY (overwrites the initial stub from _write_memory_stubs)
    _write_text(
        wt / "core/memory/knowledge/SUMMARY.md",
        f"# Knowledge Summary\n\n"
        f"Starter codebase notes for {project_name} live under "
        "[codebase/SUMMARY.md](codebase/SUMMARY.md).\n\n"
        "Begin with [codebase/architecture.md](codebase/architecture.md), then fill the\n"
        "data model, operations, and design-rationale stubs as the survey plan advances.\n\n"
        "## Included knowledge bases\n\n"
        "- [software-engineering/SUMMARY.md](software-engineering/SUMMARY.md) — "
        "Django, React, DevOps, testing, AI engineering, web fundamentals\n",
    )

    # Projects navigator (overwrites the initial stub)
    _write_text(
        wt / "core/memory/working/projects/SUMMARY.md",
        f"---\ntype: projects-navigator\ngenerated: {_TODAY} 12:00\nproject_count: 1\n---\n\n"
        "# Projects\n\n"
        "| Project | Status | Mode | Open Qs | Focus | Last activity |\n"
        "|---|---|---|---|---|---|\n"
        f"| codebase-survey | active | exploration | 5 | Capture the architecture, interfaces, "
        f"operations, and design rationale for {project_name}. | {_TODAY} |\n",
    )


def _update_bootstrap_file(bootstrap_path: Path, host_root: str) -> None:
    """Inject host_repo_root and strip CHANGELOG.md steps from bootstrap TOML."""
    if not bootstrap_path.exists():
        return

    text = bootstrap_path.read_text(encoding="utf-8")

    # Normalize host root to forward slashes for TOML
    host_root_toml = host_root.replace("\\", "/")

    # Insert host_repo_root after adapter_files line if not already present
    if "host_repo_root = " not in text:
        text = re.sub(
            r"(^adapter_files = .+)$",
            rf'\1\nhost_repo_root = "{host_root_toml}"',
            text,
            count=1,
            flags=re.MULTILINE,
        )

    # Remove [[modes.*.steps]] blocks that reference CHANGELOG.md
    # Match blocks starting with [[modes.XYZ.steps]] up to the next [[ or [section
    def _remove_changelog_steps(text: str) -> str:
        lines = text.splitlines(keepends=True)
        result: list[str] = []
        in_step_block = False
        block: list[str] = []
        drop_block = False

        for line in lines:
            if re.match(r"^\[\[modes\.(full_bootstrap|periodic_review)\.steps\]\]$", line.rstrip()):
                # Flush any pending block
                if in_step_block and not drop_block:
                    result.extend(block)
                in_step_block = True
                block = [line]
                drop_block = False
            elif in_step_block:
                if line.startswith("[[") or (line.startswith("[") and not line.startswith("[[")):
                    # End of step block — flush
                    if not drop_block:
                        result.extend(block)
                    block = []
                    in_step_block = False
                    drop_block = False
                    result.append(line)
                else:
                    block.append(line)
                    if line.strip() == 'path = "CHANGELOG.md"':
                        drop_block = True
            else:
                result.append(line)

        # Flush final block
        if in_step_block and not drop_block:
            result.extend(block)

        return "".join(result)

    text = _remove_changelog_steps(text)
    bootstrap_path.write_text(text, encoding="utf-8")


# ---------------------------------------------------------------------------
# Server launcher detection
# ---------------------------------------------------------------------------


def _detect_engram_mcp(worktree: Path) -> tuple[str, str, str] | None:
    """Try to find engram-mcp in worktree venv or PATH.

    Returns (command, arg, mode) or None.
    """
    candidates = [
        worktree / ".venv/Scripts/engram-mcp.exe",
        worktree / ".venv/Scripts/engram-mcp.cmd",
        worktree / ".venv/Scripts/engram-mcp.bat",
        worktree / ".venv/bin/engram-mcp",
    ]
    for c in candidates:
        if c.exists():
            return (str(c), "", "cli")

    if shutil.which("engram-mcp"):
        return ("engram-mcp", "", "cli")
    return None


def _detect_python(worktree: Path) -> tuple[str, str, str] | None:
    """Try to find Python in worktree venv or PATH.

    Returns (command, arg, mode) or None.
    """
    venv_candidates = [
        worktree / ".venv/Scripts/python.exe",
        worktree / ".venv/bin/python",
    ]
    for c in venv_candidates:
        if c.exists():
            script = str(worktree / "core/tools/memory_mcp.py")
            return (str(c), script, "python")

    for name in ("python3", "python"):
        found = shutil.which(name)
        if found:
            script = str(worktree / "core/tools/memory_mcp.py")
            return (found, script, "python")
    return None


def _resolve_server_launcher(worktree: Path) -> tuple[str, str, str]:
    """Returns (command, arg, mode) for MCP config.

    mode is one of: 'cli', 'python', 'fallback'.
    """
    result = _detect_engram_mcp(worktree)
    if result:
        return result
    result = _detect_python(worktree)
    if result:
        return result
    return ("python", str(worktree / "core/tools/memory_mcp.py"), "fallback")


def _resolve_relative_server_paths(
    worktree_rel: str,
    worktree_abs: Path,
    mode: str,
    command: str,
) -> tuple[str, str]:
    """Compute (rel_command, rel_arg) for config files."""
    if mode == "cli":
        for suffix in (
            ".venv/Scripts/engram-mcp.exe",
            ".venv/Scripts/engram-mcp.cmd",
            ".venv/Scripts/engram-mcp.bat",
            ".venv/bin/engram-mcp",
        ):
            if (worktree_abs / suffix).exists():
                return (f"{worktree_rel}/{suffix}", "")
        return ("engram-mcp", "")
    elif mode == "python":
        for suffix in (".venv/Scripts/python.exe", ".venv/bin/python"):
            if (worktree_abs / suffix).exists():
                return (
                    f"{worktree_rel}/{suffix}",
                    f"{worktree_rel}/core/tools/memory_mcp.py",
                )
        # System python — use bare command name
        basename = Path(command).name
        return (basename, f"{worktree_rel}/core/tools/memory_mcp.py")
    else:
        return ("python", f"{worktree_rel}/core/tools/memory_mcp.py")


# ---------------------------------------------------------------------------
# Host-side config writers
# ---------------------------------------------------------------------------


def _toml_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _write_host_codex_config(
    host_root: Path,
    rel_command: str,
    rel_arg: str,
    worktree_rel: str,
) -> None:
    codex_dir = host_root / ".codex"
    codex_dir.mkdir(exist_ok=True)
    args_value = f'"{_toml_escape(rel_arg)}"' if rel_arg else ""
    _write_text(
        codex_dir / "config.toml",
        f"# Paths are relative to the host repository root.\n"
        f"[mcp_servers.agent_memory]\n"
        f'command = "{_toml_escape(rel_command)}"\n'
        f"args = [{args_value}]\n"
        f'cwd = "{_toml_escape(worktree_rel)}"\n'
        f"startup_timeout_sec = 20\n"
        f"tool_timeout_sec = 120\n"
        f"required = false\n\n"
        f"[mcp_servers.agent_memory.env]\n"
        f'MEMORY_REPO_ROOT = "{_toml_escape(worktree_rel)}"\n'
        f'HOST_REPO_ROOT = "."\n',
    )


def _write_host_mcp_example(
    host_root: Path,
    rel_command: str,
    rel_arg: str,
    worktree_rel: str,
) -> None:
    args_list = [rel_arg] if rel_arg else []
    config = {
        "_comment": (
            "Copy this MCP server entry into your client configuration. "
            "Paths are relative to the host repository root."
        ),
        "agent_memory": {
            "command": rel_command,
            "args": args_list,
            "cwd": worktree_rel,
            "env": {
                "MEMORY_REPO_ROOT": worktree_rel,
                "HOST_REPO_ROOT": ".",
            },
        },
    }
    _write_text(
        host_root / "mcp-config-example.json",
        json.dumps(config, indent=2) + "\n",
    )


def _write_host_adapter_files(
    host_root: Path,
    worktree_display: str,
    branch_name: str,
    config_hint: str,
) -> None:
    qr = f"{worktree_display}/core/INIT.md"

    _write_text(
        host_root / "AGENTS.md",
        f"# Engram\n\n"
        f"This project uses a dedicated Engram worktree.\n\n"
        f"- Memory worktree: {worktree_display}\n"
        f"- Memory branch: {branch_name}\n"
        f"- Session router: {qr}\n"
        f"- MCP config: {config_hint}\n\n"
        f"At the start of every session, route startup through "
        f"`{qr}` instead of assuming the host repo root is the memory store.\n"
        f"Use the host repository for application code operations and the memory worktree for\n"
        f"memory reads, writes, and governance files.\n",
    )
    _write_text(
        host_root / "CLAUDE.md",
        f"# Engram\n\n"
        f"This host repository keeps its persistent memory in a separate worktree.\n\n"
        f"- Memory worktree: {worktree_display}\n"
        f"- Memory branch: {branch_name}\n"
        f"- Session router: {qr}\n"
        f"- MCP config: {config_hint}\n\n"
        f"Start each session from `{qr}`. Use the host repository for product\n"
        f"code work, and use the memory worktree for user profiles, knowledge, projects,\n"
        f"activity, scratchpad, skills, and governance.\n",
    )
    _write_text(
        host_root / ".cursorrules",
        f"This host repository uses a dedicated memory worktree at {worktree_display} on\n"
        f"branch {branch_name}. Start every session from {qr}, use {config_hint}\n"
        f"for MCP wiring, operate on host-repo code from the project root, and keep memory\n"
        f"operations inside the worktree.\n",
    )


# ---------------------------------------------------------------------------
# Main handler
# ---------------------------------------------------------------------------


def run_init(args: argparse.Namespace, *, repo_root: Path, content_root: Path) -> int:
    """Execute ``engram init`` — create an Engram memory worktree in the host repo."""
    del repo_root, content_root  # Not used; we resolve the host repo from git

    dry_run: bool = args.dry_run
    platform: str = args.platform
    profile: str = args.profile
    worktree_path: str = args.worktree_path
    user_name: str = args.user_name or ""
    user_context: str = args.user_context or ""

    # --- Locate host repo root ---
    result = _git("rev-parse", "--show-toplevel", check=False)
    if result.returncode != 0:
        print("Error: engram init must be run from inside a git repository.", file=sys.stderr)
        return 2
    host_root = Path(result.stdout.strip()).resolve()

    project_name = host_root.name
    branch_name = args.branch_name or f"worktree--{project_name}"

    # --- Locate seed content ---
    seed_root = _seed_repo_root()
    manifest = _seed_manifest(seed_root)
    if not manifest.exists():
        print(f"Error: seed manifest not found: {manifest}", file=sys.stderr)
        print(
            "Ensure Engram is installed from a complete checkout (pip install -e .).",
            file=sys.stderr,
        )
        return 2

    # --- Resolve paths ---
    if Path(worktree_path).is_absolute():
        worktree_abs = Path(worktree_path).resolve()
    else:
        worktree_abs = (host_root / worktree_path).resolve()

    host_root_str = str(host_root)
    worktree_abs_str = str(worktree_abs)

    # --- Validate preconditions ---
    ref_check = _git("show-ref", "--verify", "--quiet", f"refs/heads/{branch_name}", check=False)
    if ref_check.returncode == 0:
        print(
            f"Error: branch '{branch_name}' already exists in the host repository.", file=sys.stderr
        )
        return 2

    if worktree_abs.exists():
        print(f"Error: worktree path already exists: {worktree_abs}", file=sys.stderr)
        return 2

    # --- Template variables ---
    variables = {
        "PROJECT_NAME": project_name,
        "HOST_REPO_ROOT": host_root_str,
        "MEMORY_WORKTREE_PATH": worktree_abs_str,
        "MEMORY_BRANCH": branch_name,
        "TODAY": _TODAY,
    }

    # --- Dry run ---
    temp_worktree = host_root / ".git" / f"engram-tmp-{branch_name}"

    if dry_run:
        print("=== Dry run: init worktree ===")
        _print_cmd("git", "worktree", "add", "--detach", str(temp_worktree), "HEAD")
        _print_cmd("git", "-C", str(temp_worktree), "checkout", "--orphan", branch_name)
        _print_cmd("git", "-C", str(temp_worktree), "rm", "-rf", "--ignore-unmatch", ".")
        print(f"  [copy seed files from {manifest}]")
        print("  [write memory stubs]")
        print(f"  [install profile: {profile}]")
        print("  [update agent-bootstrap.toml]")
        print("  [write hygiene files]")
        print("  [write codebase starters]")
        _print_cmd("git", "-C", str(temp_worktree), "add", "--all")
        _print_cmd(
            "git",
            "-C",
            str(temp_worktree),
            "commit",
            "--no-verify",
            "-m",
            "[system] Initialize Engram worktree",
            "-m",
            f"Seeded from Engram on {_TODAY}.",
        )
        _print_cmd("git", "worktree", "remove", str(temp_worktree))
        _print_cmd("git", "worktree", "add", str(worktree_abs), branch_name)
        print(f"  [write host adapter files for platform: {platform}]")
        print(
            "[dry-run] Worktree initialization commands printed only; no files or git state changed."
        )
        return 0

    # --- Create orphan branch via temporary worktree ---
    print("=== Engram Worktree Setup ===\n")

    def _cleanup_temp() -> None:
        if temp_worktree.exists():
            try:
                subprocess.run(
                    ["git", "worktree", "remove", "--force", str(temp_worktree)],
                    capture_output=True,
                    check=False,
                )
            except OSError:
                pass

    try:
        _run_git(False, "worktree", "add", "--detach", str(temp_worktree), "HEAD")
        _run_git(False, "-C", str(temp_worktree), "checkout", "--orphan", branch_name)
        _run_git(False, "-C", str(temp_worktree), "rm", "-rf", "--ignore-unmatch", ".")

        # Copy seed files from manifest
        for line in manifest.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            _copy_seed_path(seed_root, temp_worktree, line)

        # Generate content
        _write_memory_stubs(temp_worktree)
        _install_profile(
            temp_worktree,
            seed_root=seed_root,
            profile=profile,
            project_name=project_name,
            host_root=host_root_str,
            worktree_path=worktree_abs_str,
            user_name=user_name,
            user_context=user_context,
        )
        _update_bootstrap_file(temp_worktree / "agent-bootstrap.toml", host_root_str)
        _write_worktree_hygiene_files(temp_worktree)
        _write_codebase_starters(
            temp_worktree,
            seed_root=seed_root,
            variables=variables,
            project_name=project_name,
            branch_name=branch_name,
        )

        # Commit and switch to final worktree
        _run_git(False, "-C", str(temp_worktree), "add", "--all")
        _run_git(
            False,
            "-C",
            str(temp_worktree),
            "commit",
            "--no-verify",
            "-m",
            "[system] Initialize Engram worktree",
            "-m",
            f"Seeded from Engram on {_TODAY}.",
        )
        _run_git(False, "worktree", "remove", str(temp_worktree))
        _run_git(False, "worktree", "add", str(worktree_abs), branch_name)
    except (subprocess.CalledProcessError, OSError) as exc:
        _cleanup_temp()
        print(f"Error during worktree creation: {exc}", file=sys.stderr)
        return 2

    # --- Server launcher detection & host config ---
    command, _arg, mode = _resolve_server_launcher(worktree_abs)
    rel_command, rel_arg = _resolve_relative_server_paths(
        worktree_path, worktree_abs, mode, command
    )

    if platform == "codex":
        if mode != "fallback":
            _write_host_codex_config(host_root, rel_command, rel_arg, worktree_path)
            _write_host_adapter_files(host_root, worktree_path, branch_name, ".codex/config.toml")
            print("[ok] Wrote host Codex MCP config to .codex/config.toml")
        else:
            _write_host_adapter_files(
                host_root, worktree_path, branch_name, "mcp-config-example.json"
            )
            print("[warn] Could not detect a Python interpreter for Codex MCP config")
    else:
        _write_host_mcp_example(host_root, rel_command, rel_arg, worktree_path)
        _write_host_adapter_files(host_root, worktree_path, branch_name, "mcp-config-example.json")
        print("[ok] Wrote host MCP example config to mcp-config-example.json")

    # --- Summary ---
    current_branch_result = _git("symbolic-ref", "--quiet", "--short", "HEAD", check=False)
    current_branch = (
        current_branch_result.stdout.strip() if current_branch_result.returncode == 0 else "HEAD"
    )

    print()
    print("=== Worktree setup complete ===")
    print()
    print(f"Host branch:        {current_branch}")
    print(f"Memory branch:      {branch_name}")
    print(f"Memory worktree:    {worktree_abs}")
    print(f"Host repo root:     {host_root}")
    print()
    print("Next steps:")
    print("  1. Open the host repository in your agent client.")
    if platform == "codex":
        print(
            "  2. Ensure .codex/config.toml is trusted so the MCP server loads from the worktree."
        )
    else:
        print("  2. Copy mcp-config-example.json into your client-specific MCP configuration.")
    print("  3. Start the first codebase-survey or maintenance session against the host repo.")

    return 0
