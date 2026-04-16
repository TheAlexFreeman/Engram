#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from types import ModuleType
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import frontmatter as fmlib  # type: ignore[import-untyped]  # noqa: E402
import yaml  # type: ignore[import-untyped]  # noqa: E402

from core.tools.agent_memory_mcp.errors import ValidationError  # noqa: E402
from core.tools.agent_memory_mcp.frontmatter_policy import (  # noqa: E402
    ALLOWED_SOURCE_VALUES,
    ALLOWED_TRUST_VALUES,
    REQUIRED_FRONTMATTER_KEYS,
)
from core.tools.agent_memory_mcp.skill_trigger import validate_skill_trigger  # noqa: E402

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python < 3.11 fallback
    import tomli

    TOML_MODULE: ModuleType = tomli
else:
    TOML_MODULE = tomllib


CONTENT_DIRS = (
    "core/memory/users",
    "core/memory/knowledge",
    "core/memory/skills",
    "core/memory/working/projects",
)
ACCESS_DIRS = (
    "core/memory/users",
    "core/memory/knowledge",
    "core/memory/skills",
    "core/memory/working/projects",
    "core/memory/activity",
)
ACCESS_COVERAGE_DIRS = ("core/memory/skills", "core/memory/users", "core/memory/activity")
IGNORED_DIR_NAMES = {".git", ".claude", "__pycache__", ".pytest_cache"}
PLACEHOLDER_SNIPPETS = (
    "_Nothing here yet.",
    "_No pending items._",
    "_No current notes._",
)
DEFAULT_ACCESS_COVERAGE_WINDOW_DAYS = 30
ACCESS_COVERAGE_WINDOW_ENV_VAR = "MEMORY_VALIDATE_COVERAGE_WINDOW_DAYS"

ALLOWED_PLAN_STATUS_VALUES = {"active", "paused", "complete"}
CANONICAL_ORIGIN_SESSION_RE = re.compile(
    r"^(?:core/)?memory/activity/\d{4}/\d{2}/\d{2}/chat-\d{3}$"
)
LEGACY_ORIGIN_SESSION_RE = re.compile(r"^chat-\d{3}$")
SPECIAL_ORIGIN_SESSION_VALUES = {"setup", "manual", "unknown"}

REQUIRED_ACCESS_FIELDS = {"file", "date", "task", "helpfulness", "note"}
OPTIONAL_ACCESS_FIELDS = {"session_id", "category", "mode", "task_id", "estimator"}

EXPECTED_QUICK_REFERENCE_PARAMETERS = (
    "Low-trust retirement threshold",
    "Medium-trust flagging threshold",
    "Staleness trigger (no access)",
    "Aggregation trigger",
    "Identity churn alarm",
    "Knowledge flooding alarm",
    "Task similarity method",
    "Cluster co-retrieval threshold",
)

BOOTSTRAP_MANIFEST_PATH = Path("agent-bootstrap.toml")
EXPECTED_BOOTSTRAP_MODES = (
    "first_run",
    "returning",
    "full_bootstrap",
    "periodic_review",
    "automation",
)
EXPECTED_BOOTSTRAP_COST_VALUES = {"light", "medium", "heavy"}
EXPECTED_BOOTSTRAP_TOKEN_BUDGETS = {
    "first_run": 20000,
    "returning": 7000,
    "full_bootstrap": 25000,
    "periodic_review": 25000,
    "automation": 7000,
}
EXPECTED_BOOTSTRAP_PREFER_SUMMARIES = {
    "first_run": False,
    "returning": True,
    "full_bootstrap": True,
    "periodic_review": True,
    "automation": True,
}
EXPECTED_RETURNING_STEP_PATHS = (
    "core/INIT.md",
    "core/memory/HOME.md",
    "core/memory/users/SUMMARY.md",
    "core/memory/activity/SUMMARY.md",
    "core/memory/working/USER.md",
    "core/memory/working/CURRENT.md",
)
EXPECTED_FIRST_RUN_STEP_PATHS = (
    "README.md",
    "core/INIT.md",
    "core/governance/first-run.md",
)
EXPECTED_FULL_BOOTSTRAP_STEP_PATHS = (
    "README.md",
    "core/INIT.md",
    "core/memory/HOME.md",
    "core/memory/users/SUMMARY.md",
    "core/memory/activity/SUMMARY.md",
    "core/memory/working/USER.md",
    "core/memory/working/CURRENT.md",
    "CHANGELOG.md",
    "core/governance/curation-policy.md",
    "core/governance/update-guidelines.md",
)
EXPECTED_PERIODIC_REVIEW_STEP_PATHS = EXPECTED_FULL_BOOTSTRAP_STEP_PATHS + (
    "core/governance/system-maturity.md",
    "core/governance/belief-diff-log.md",
    "core/governance/review-queue.md",
    "core/governance/session-checklists.md",
    "core/governance/security-signals.md",
)
DEPLOYED_WORKTREE_FULL_BOOTSTRAP_STEP_PATHS = tuple(
    path for path in EXPECTED_FULL_BOOTSTRAP_STEP_PATHS if path != "CHANGELOG.md"
)
DEPLOYED_WORKTREE_PERIODIC_REVIEW_STEP_PATHS = tuple(
    path for path in EXPECTED_PERIODIC_REVIEW_STEP_PATHS if path != "CHANGELOG.md"
)
EXPECTED_AUTOMATION_STEP_PATHS = (
    "core/INIT.md",
    "core/memory/HOME.md",
    "core/memory/working/USER.md",
    "core/memory/working/CURRENT.md",
    "core/memory/working/projects/SUMMARY.md",
)
EXPECTED_MODE_STEP_PATHS = {
    "first_run": EXPECTED_FIRST_RUN_STEP_PATHS,
    "returning": EXPECTED_RETURNING_STEP_PATHS,
    "full_bootstrap": EXPECTED_FULL_BOOTSTRAP_STEP_PATHS,
    "periodic_review": EXPECTED_PERIODIC_REVIEW_STEP_PATHS,
    "automation": EXPECTED_AUTOMATION_STEP_PATHS,
}
DEPLOYED_WORKTREE_MODE_STEP_PATHS = {
    "first_run": EXPECTED_FIRST_RUN_STEP_PATHS,
    "returning": EXPECTED_RETURNING_STEP_PATHS,
    "full_bootstrap": DEPLOYED_WORKTREE_FULL_BOOTSTRAP_STEP_PATHS,
    "periodic_review": DEPLOYED_WORKTREE_PERIODIC_REVIEW_STEP_PATHS,
    "automation": EXPECTED_AUTOMATION_STEP_PATHS,
}
EXPECTED_BOOTSTRAP_ON_DEMAND = (
    "core/memory/working/projects/SUMMARY.md",
    "core/memory/knowledge/SUMMARY.md",
    "core/memory/skills/SUMMARY.md",
)
EXPECTED_BOOTSTRAP_MAINTENANCE_PROBES = (
    "core/governance/review-queue.md:load_only_when_non_placeholder",
    "ACCESS.jsonl:count_non_empty_lines",
)
EXPECTED_OPTIONAL_STEP_SKIP_RULES = {
    "core/memory/HOME.md": "placeholder_or_empty",
    "core/memory/working/projects/SUMMARY.md": "placeholder_or_empty",
    "core/memory/activity/SUMMARY.md": "placeholder_or_empty",
    "core/memory/working/USER.md": "placeholder_or_empty",
    "core/memory/working/CURRENT.md": "placeholder_or_empty",
}
COMPACT_RETURNING_BUDGET = EXPECTED_BOOTSTRAP_TOKEN_BUDGETS["returning"]
COMPACT_RETURNING_TARGETS = {
    "core/INIT.md": 2600,
    "core/memory/HOME.md": 500,
    "core/memory/users/SUMMARY.md": 450,
    "core/memory/activity/SUMMARY.md": 750,
    "core/memory/working/USER.md": 400,
    "core/memory/working/CURRENT.md": 650,
}
COMPACT_RETURNING_HEADROOM = 1000
TASK_READINESS_MANIFEST_PATH = Path("HUMANS/tooling/agent-task-readiness.toml")
EXPECTED_TASK_READINESS_PROFILES = (
    "workspace_general",
    "pull_request",
    "publish_branch",
    "terminal_plan_authoring",
    "python_validation",
    "python_dependency_install",
    "node_validation",
    "node_dependency_install",
)
EXPECTED_TASK_READINESS_PROFILE_ORDER = (
    "pull_request",
    "publish_branch",
    "terminal_plan_authoring",
    "python_dependency_install",
    "node_dependency_install",
    "python_validation",
    "node_validation",
)
EXPECTED_TASK_READINESS_CHECKS = (
    "git_cli",
    "git_remote",
    "git_push_dry_run",
    "gh_auth",
    "remote_network",
    "python_runtime",
    "python_validation_stack",
    "python_package_manager",
    "python_package_network",
    "node_runtime",
    "node_validation_stack",
    "node_package_manager",
    "node_package_network",
)
REQUIRED_TASK_READINESS_PROFILE_KEYS = (
    "title",
    "description",
    "keywords",
    "checks",
    "final_gate_checks",
    "fallback_message",
    "blocked_reason",
    "success_message",
)
REQUIRED_TASK_READINESS_CHECK_KEYS = (
    "title",
    "category",
    "failure_modes",
    "retry_action",
    "fallback_paths",
)
EXPECTED_TASK_READINESS_STATUS_LABELS = (
    "ready",
    "attention",
    "blocked",
    "manifest_only",
)
ALLOWED_TASK_READINESS_CATEGORIES = {"github", "connectivity", "runtime", "tooling"}
ALLOWED_TASK_READINESS_FAILURE_MODES = {
    "missing",
    "missing_remote",
    "auth",
    "config",
    "connectivity",
    "runtime",
    "policy",
    "repo_state",
    "unknown",
}

RUNTIME_GUIDANCE_FILES = (
    Path("README.md"),
    Path("HUMANS/docs/QUICKSTART.md"),
    Path("core/INIT.md"),
    Path("core/governance/curation-policy.md"),
    Path("core/governance/content-boundaries.md"),
    Path("core/governance/security-signals.md"),
    Path("core/governance/update-guidelines.md"),
    Path("core/governance/session-checklists.md"),
)
PROMPT_COPY_FILES = (
    Path("HUMANS/setup/setup.sh"),
    Path("HUMANS/views/setup.html"),
    Path("HUMANS/docs/QUICKSTART.md"),
)
SETUP_GUIDANCE_FILES = (
    Path("HUMANS/setup/setup.sh"),
    Path("HUMANS/docs/QUICKSTART.md"),
)
ONBOARDING_EXPORT_TEMPLATE_PATH = Path("HUMANS/tooling/onboard-export-template.md")
ONBOARDING_EXPORT_REQUIRED_PHRASE = "bash HUMANS/tooling/scripts/onboard-export.sh <file>"
ONBOARDING_EXPORT_FORBIDDEN_PATTERNS = (r"bash scripts/onboard-export\.sh(?: <file>)?",)
ADAPTER_FILES = (Path("AGENTS.md"), Path("CLAUDE.md"), Path(".cursorrules"))
ROOT_SETUP_TARGETS = {
    Path("setup.sh"): "HUMANS/setup/setup.sh",
    Path("setup.html"): "HUMANS/views/setup.html",
}
CANONICAL_SETUP_FILES = (Path("HUMANS/setup/setup.sh"), Path("HUMANS/views/setup.html"))
CAPABILITIES_MANIFEST_PATH = Path("HUMANS/tooling/agent-memory-capabilities.toml")
EXPECTED_MCP_RUNTIME_DIR = Path("core/tools")
EXPECTED_MCP_ENTRYPOINT = Path("core/tools/memory_mcp.py")
LEGACY_MCP_RUNTIME_DIR = Path("tools")
LEGACY_MCP_ENTRYPOINT = Path("HUMANS/tooling/scripts/memory_mcp.py")
LEGACY_MCP_RUNTIME_DIR_V2 = Path("engram_mcp")
LEGACY_MCP_ENTRYPOINT_V2 = Path("engram_mcp/memory_mcp.py")

PROMPT_START_LINE = "Start with `README.md` for the architecture and startup contract, then use `core/INIT.md` for live routing and context-loading rules."
PROMPT_ROUTE_LINE = "Use `core/memory/HOME.md` as the session entry point for normal sessions after `core/INIT.md` routes you there."
PROMPT_MCP_LINE = "If local agent-memory MCP tools are available, prefer them for memory reads, search, and governed writes; fall back to direct file access only when the MCP surface is unavailable or lacks the needed operation."
LIVE_CONFIG_LINE = "core/INIT.md is the live runtime config; do not use hardcoded thresholds."
ADAPTER_ROUTING_PHRASE = "Start with `README.md` for the architectural contract, then continue to `core/INIT.md` for live routing and thresholds"
ADAPTER_MCP_PHRASE = "When local agent-memory MCP tools are available, prefer them for memory reads, search, and governed writes"
README_START_PHRASE = "Start new sessions from this `README.md` unless a platform or tool opens a more specific surface for you."
README_ARCHITECTURE_PHRASE = (
    "continue to `core/INIT.md` for live routing, active thresholds, and maintenance triggers"
)
MCP_PREFERENCE_PHRASE = "When local agent-memory MCP tools are available, prefer them for memory reads, search, and governed writes; fall back to direct file access only when the MCP surface is unavailable or lacks the needed operation."
QUICK_REFERENCE_ROUTER_PHRASE = "Use this file as the live operational router once you reach it:"
FIRST_RUN_MCP_PHRASE = MCP_PREFERENCE_PHRASE
SESSION_CHECKLISTS_MCP_PHRASE = MCP_PREFERENCE_PHRASE
SKILLS_SUMMARY_MCP_PHRASE = "When local agent-memory MCP tools are available, prefer them for memory reads, search, and governed writes while executing these skills; fall back to direct file access only when the MCP surface is unavailable or lacks the needed operation."
ONBOARDING_SKILL_MCP_PHRASE = "When local agent-memory MCP tools are available, prefer them for memory reads, search, and governed writes during onboarding; fall back to direct file access only when the MCP surface is unavailable or lacks the needed operation."
SESSION_START_SKILL_MCP_PHRASE = "When local agent-memory MCP tools are available, prefer them for memory reads and search during session start; fall back to direct file access only when the MCP surface is unavailable or lacks the needed operation."
SESSION_SYNC_SKILL_MCP_PHRASE = "When local agent-memory MCP tools are available, prefer them for memory reads and writes during checkpointing; fall back to direct file access only when the MCP surface is unavailable or lacks the needed operation."
SESSION_WRAPUP_SKILL_MCP_PHRASE = "When local agent-memory MCP tools are available, prefer them for memory reads, search, and governed writes during wrap-up; fall back to direct file access only when the MCP surface is unavailable or lacks the needed operation."
SESSION_CHECKLISTS_ON_DEMAND_PHRASE = "Load on demand"
SETUP_GUIDANCE_REQUIRED_PATTERNS = (r"live routing (?:in|from)\s+`?core/INIT\.md`?",)
SETUP_GUIDANCE_FORBIDDEN_PATTERNS = (r"follow the bootstrap sequence",)
SESSION_START_SKILL_PATH = Path("core/memory/skills/session-start/SKILL.md")
SESSION_START_REQUIRED_PHRASES = (
    "compact returning manifest in `core/INIT.md`",
    "`core/memory/HOME.md` as the session entry point",
    "Load `core/governance/session-checklists.md` only when you want more detail",
    "If `core/governance/review-queue.md` still contains only its placeholder, skip it.",
    "Load it only when there are real pending items or the user asks about them.",
)
SESSION_START_FORBIDDEN_PATTERNS = (
    r"after README\.md has been read",
    r"^- Read `core/governance/review-queue\.md`\.",
    r"compact checklist in `core/governance/session-checklists\.md` is sufficient",
)
SESSION_WRAPUP_SKILL_PATH = Path("core/memory/skills/session-wrapup/SKILL.md")
SESSION_WRAPUP_REQUIRED_PHRASES = (
    "Load `core/governance/session-checklists.md` only when you want",
    "session-end runbook",
)
SESSION_WRAPUP_FORBIDDEN_PATTERNS = (
    r"compact checklist in `core/governance/session-checklists\.md` is sufficient",
)
SKILLS_SUMMARY_PATH = Path("core/memory/skills/SUMMARY.md")
ONBOARDING_SKILL_PATH = Path("core/memory/skills/onboarding/SKILL.md")
SESSION_SYNC_SKILL_PATH = Path("core/memory/skills/session-sync/SKILL.md")

FORBIDDEN_RUNTIME_PATTERNS = (
    r"Check the current maturity stage in `core/governance/system-maturity\.md`",
    r"see `core/governance/system-maturity\.md` for the stage-appropriate value",
    r"use those values from `core/governance/system-maturity\.md`",
    r"Thresholds are stage-specific; see `core/governance/system-maturity\.md`",
    r"The active thresholds are always determined by the system's current maturity stage as assessed in `core/governance/system-maturity\.md`",
    r"The session boundary is proxied by the `date` field",
    r"groups entries by date, identifies file sets co-occurring",
    r"Use core/governance/first-run\.md for blank-slate onboarding, core/governance/session-checklists\.md for returning sessions",
    r"This file is loaded every session",
    r"follow the bootstrap sequence and rules in README\.md",
    r"This file is your entry point\. Read it fully before doing anything else\.",
    r"Normal day-to-day use via `core/governance/session-checklists\.md`",
    r"Use `core/governance/session-checklists\.md` § \"Session start\"",
    r"compact returning-session checklist",
    r"~2,000–5,000",
)


@dataclass
class ValidationResult:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def error(self, message: str) -> None:
        self.errors.append(message)

    def warn(self, message: str) -> None:
        self.warnings.append(message)


def repo_root_from_argv(argv: list[str]) -> Path:
    if len(argv) > 1:
        return Path(argv[1]).resolve()
    return Path(__file__).resolve().parents[3]


def run_git_command(cwd: Path, *args: str) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return None


def is_git_repo(path: Path) -> bool:
    completed = run_git_command(path, "rev-parse", "--is-inside-work-tree")
    return (
        completed is not None and completed.returncode == 0 and completed.stdout.strip() == "true"
    )


def is_git_worktree_root(path: Path) -> bool:
    return path.joinpath(".git").is_file() and is_git_repo(path)


def current_git_branch(path: Path) -> str | None:
    completed = run_git_command(path, "symbolic-ref", "--quiet", "--short", "HEAD")
    if completed is None or completed.returncode != 0:
        return None
    branch = completed.stdout.strip()
    return branch or None


def resolve_host_default_branch(path: Path) -> str | None:
    remote_head = run_git_command(path, "symbolic-ref", "--quiet", "refs/remotes/origin/HEAD")
    if remote_head is not None and remote_head.returncode == 0:
        ref = remote_head.stdout.strip()
        if ref.startswith("refs/remotes/"):
            return ref
    return current_git_branch(path)


def validate_worktree_topology(
    root: Path,
    manifest_path: Path,
    host_repo_root: object,
    result: ValidationResult,
) -> None:
    repo_is_worktree = is_git_worktree_root(root)
    if host_repo_root is None:
        if repo_is_worktree:
            result.error(
                f"{manifest_path}: host_repo_root is required when validating a git worktree checkout"
            )
        return

    if not isinstance(host_repo_root, str) or not host_repo_root.strip():
        return

    host_root = Path(host_repo_root).resolve()
    memory_root = root.resolve()

    try:
        host_root.relative_to(memory_root)
        result.error(f"{manifest_path}: host_repo_root must not point inside the memory repo root")
    except ValueError:
        pass

    if not host_root.exists():
        result.error(f"{manifest_path}: host_repo_root does not exist: {host_repo_root!r}")
        return

    if not is_git_repo(host_root):
        result.error(f"{manifest_path}: host_repo_root must point to a git repository")

    if not repo_is_worktree:
        result.error(
            f"{manifest_path}: host_repo_root is set but the memory repo root is not a git worktree checkout"
        )

    if not (repo_is_worktree and is_git_repo(host_root)):
        return

    memory_branch = current_git_branch(root)
    host_default_branch = resolve_host_default_branch(host_root)
    if memory_branch and host_default_branch:
        merge_base = run_git_command(host_root, "merge-base", memory_branch, host_default_branch)
        if merge_base is None:
            result.warn(
                f"{manifest_path}: git executable unavailable while checking shared history between {memory_branch!r} and {host_default_branch!r}"
            )
        elif merge_base.returncode == 0 and merge_base.stdout.strip():
            result.warn(
                f"{manifest_path}: worktree branch {memory_branch!r} shares history with host default branch {host_default_branch!r}; orphan memory branches should not share host history"
            )
        elif merge_base.returncode not in (0, 1):
            stderr = merge_base.stderr.strip()
            suffix = f" ({stderr})" if stderr else ""
            result.warn(
                f"{manifest_path}: could not compare worktree branch {memory_branch!r} against host default branch {host_default_branch!r}{suffix}"
            )

    for relative_path in ADAPTER_FILES:
        host_adapter = host_root / relative_path
        worktree_adapter = root / relative_path
        if not host_adapter.exists() or not worktree_adapter.exists():
            continue
        host_text = read_text(host_adapter, result)
        worktree_text = read_text(worktree_adapter, result)
        if host_text is None or worktree_text is None:
            continue
        if host_text == worktree_text:
            result.warn(
                f"{worktree_adapter}: duplicates host-root adapter file {host_adapter} in worktree mode; host and worktree adapters should differ"
            )


def is_deployed_worktree_repo(root: Path) -> bool:
    manifest_path = root / BOOTSTRAP_MANIFEST_PATH
    if not manifest_path.exists():
        return False

    text = read_text(manifest_path, ValidationResult())
    if text is None:
        return False

    try:
        manifest = TOML_MODULE.loads(text)
    except Exception:
        return False

    host_repo_root = manifest.get("host_repo_root")
    return (
        isinstance(host_repo_root, str)
        and bool(host_repo_root.strip())
        and is_git_worktree_root(root)
    )


def read_text(path: Path, result: ValidationResult) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        result.error(f"{path}: could not decode as UTF-8 ({exc})")
    except OSError as exc:
        result.error(f"{path}: could not read file ({exc})")
    return None


def should_ignore(path: Path) -> bool:
    return any(part in IGNORED_DIR_NAMES for part in path.parts)


def _namespace_for_path(posix_path: str) -> str | None:
    """Return the matching ACCESS_DIRS / ACCESS_COVERAGE_DIRS prefix for a path, or None."""
    all_dirs = set(ACCESS_DIRS) | set(ACCESS_COVERAGE_DIRS)
    best: str | None = None
    for prefix in all_dirs:
        if posix_path == prefix or posix_path.startswith(prefix + "/"):
            if best is None or len(prefix) > len(best):
                best = prefix
    return best


def is_project_plan_path(relative_path: Path) -> bool:
    """Check if path matches core/memory/working/projects/<project>/plans/<file>."""
    parts = relative_path.parts
    return (
        len(parts) >= 7
        and parts[:4] == ("core", "memory", "working", "projects")
        and parts[5] == "plans"
    )


def is_plan_path(relative_path: Path) -> bool:
    return is_project_plan_path(relative_path)


def iter_content_files(root: Path) -> list[Path]:
    paths: list[Path] = []
    for dirname in CONTENT_DIRS:
        base = root / dirname
        if not base.exists():
            continue
        for path in base.rglob("*.md"):
            if should_ignore(path.relative_to(root)):
                continue
            if path.name == "SUMMARY.md":
                continue
            paths.append(path)

    projects_root = root / "core" / "memory" / "working" / "projects"
    if projects_root.exists():
        for pattern in ("*/plans/*.md", "*/plans/*.yaml"):
            for path in projects_root.glob(pattern):
                if should_ignore(path.relative_to(root)):
                    continue
                if path.name == "SUMMARY.md":
                    continue
                paths.append(path)
    return sorted(paths)


def iter_access_files(root: Path) -> list[Path]:
    paths: list[Path] = []
    for dirname in ACCESS_DIRS:
        base = root / dirname
        if not base.exists():
            continue
        for path in base.rglob("ACCESS*.jsonl"):
            if should_ignore(path.relative_to(root)):
                continue
            paths.append(path)
    return sorted(paths)


def iter_coverage_target_files(root: Path, folder: str) -> list[Path]:
    base = root / folder
    if not base.exists():
        return []

    paths: list[Path] = []
    for path in base.rglob("*.md"):
        if should_ignore(path.relative_to(root)):
            continue
        if path.name == "SUMMARY.md":
            continue
        paths.append(path)
    return sorted(paths)


def access_coverage_window_days() -> int:
    raw_value = os.environ.get(ACCESS_COVERAGE_WINDOW_ENV_VAR, "").strip()
    if not raw_value:
        return DEFAULT_ACCESS_COVERAGE_WINDOW_DAYS
    try:
        parsed = int(raw_value)
    except ValueError:
        return DEFAULT_ACCESS_COVERAGE_WINDOW_DAYS
    return parsed if parsed > 0 else DEFAULT_ACCESS_COVERAGE_WINDOW_DAYS


def collect_last_access_dates_by_folder(root: Path) -> dict[str, date]:
    last_seen: dict[str, date] = {}
    for path in iter_access_files(root):
        if path.name == "ACCESS_SCANS.jsonl":
            continue

        text = path.read_text(encoding="utf-8")
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, dict):
                continue

            file_value = payload.get("file")
            date_value = payload.get("date")
            if not isinstance(file_value, str) or not isinstance(date_value, str):
                continue

            normalized_file = normalize_repo_relative_path(file_value)
            if normalized_file is None:
                continue
            try:
                entry_date = date.fromisoformat(date_value)
            except ValueError:
                continue

            folder = _namespace_for_path(normalized_file)
            if folder not in ACCESS_COVERAGE_DIRS:
                continue
            current = last_seen.get(folder)
            if current is None or entry_date > current:
                last_seen[folder] = entry_date
    return last_seen


def validate_access_coverage(root: Path, result: ValidationResult) -> None:
    window_days = access_coverage_window_days()
    today = date.today()
    last_seen = collect_last_access_dates_by_folder(root)

    for folder in ACCESS_COVERAGE_DIRS:
        if not iter_coverage_target_files(root, folder):
            continue

        last_entry_date = last_seen.get(folder)
        if last_entry_date is None:
            result.warn(
                f"CoverageGap: {folder}/ has 0 ACCESS entries in the last {window_days} days (days_since_last_entry=never)"
            )
            continue

        days_since_last_entry = (today - last_entry_date).days
        if days_since_last_entry >= window_days:
            result.warn(
                f"CoverageGap: {folder}/ has 0 ACCESS entries in the last {window_days} days (days_since_last_entry={days_since_last_entry})"
            )


def parse_frontmatter(path: Path, text: str, result: ValidationResult) -> dict[str, Any] | None:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None

    end_index = None
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end_index = index
            break
    if end_index is None:
        result.error(f"{path}: frontmatter starts with '---' but has no closing delimiter")
        return None

    try:
        return dict(fmlib.loads(text).metadata)
    except Exception as exc:
        result.error(f"{path}: invalid YAML frontmatter ({exc})")
        return None


def validate_iso_date(value: object, path: Path, field_name: str, result: ValidationResult) -> None:
    if isinstance(value, datetime):
        value = value.date()
    if isinstance(value, date):
        return
    if not isinstance(value, str):
        result.error(f"{path}: {field_name} must be a date or string in YYYY-MM-DD format")
        return
    try:
        date.fromisoformat(value)
    except ValueError:
        result.error(f"{path}: {field_name} must be a valid YYYY-MM-DD date, got {value!r}")


def normalize_repo_relative_path(raw_path: str) -> str | None:
    if not raw_path or raw_path.startswith(("/", "\\")):
        return None
    if Path(raw_path).is_absolute():
        return None

    parts: list[str] = []
    for part in raw_path.replace("\\", "/").split("/"):
        if part in {"", "."}:
            continue
        if part == "..":
            if not parts:
                return None
            parts.pop()
            continue
        parts.append(part)

    normalized = "/".join(parts)
    return normalized or None


def validate_frontmatter(path: Path, root: Path, result: ValidationResult) -> None:
    text = read_text(path, result)
    if text is None:
        return

    relative_path = path.relative_to(root)
    if path.suffix == ".yaml" and is_plan_path(relative_path):
        try:
            payload = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            result.error(f"{path}: invalid YAML plan structure: {exc}")
            return
        if not isinstance(payload, dict):
            result.error(f"{path}: YAML plan must contain a top-level mapping")
            return
        for key in ("id", "project", "created", "origin_session", "status", "purpose", "work"):
            if key not in payload:
                result.error(f"{path}: YAML plan missing required key '{key}'")
        origin_session = payload.get("origin_session")
        if isinstance(origin_session, str):
            if origin_session in SPECIAL_ORIGIN_SESSION_VALUES:
                return
            if CANONICAL_ORIGIN_SESSION_RE.fullmatch(origin_session):
                return
            if LEGACY_ORIGIN_SESSION_RE.fullmatch(origin_session):
                result.warn(
                    f"{path}: legacy origin_session {origin_session!r}; prefer core/memory/activity/YYYY/MM/DD/chat-NNN"
                )
                return
        result.error(
            f"{path}: origin_session must be memory/activity/YYYY/MM/DD/chat-NNN, core/memory/activity/YYYY/MM/DD/chat-NNN, setup, manual, or unknown"
        )
        return

    frontmatter = parse_frontmatter(path, text, result)
    if frontmatter is None:
        result.warn(f"{path}: missing YAML frontmatter")
        return

    missing = [key for key in REQUIRED_FRONTMATTER_KEYS if key not in frontmatter]
    if missing:
        result.error(f"{path}: missing required frontmatter keys: {', '.join(missing)}")
        return

    source = frontmatter["source"]
    if source not in ALLOWED_SOURCE_VALUES:
        result.error(f"{path}: invalid source {source!r}")

    trust = frontmatter["trust"]
    if trust not in ALLOWED_TRUST_VALUES:
        result.error(f"{path}: invalid trust {trust!r}")

    validate_iso_date(frontmatter["created"], path, "created", result)
    if "last_verified" in frontmatter:
        validate_iso_date(frontmatter["last_verified"], path, "last_verified", result)
    if "expires" in frontmatter:
        validate_iso_date(frontmatter["expires"], path, "expires", result)
    if "superseded_by" in frontmatter:
        superseded_by = frontmatter["superseded_by"]
        if not isinstance(superseded_by, str) or not superseded_by.strip():
            result.error(f"{path}: superseded_by must be a non-empty string (repo-relative path)")
        else:
            # Validate the successor path exists in the repo
            successor_path = root / "core" / superseded_by
            if not successor_path.exists():
                result.warn(f"{path}: superseded_by target does not exist: {superseded_by}")
    if "trigger" in frontmatter:
        try:
            validate_skill_trigger(frontmatter["trigger"], context=f"{path}: trigger")
        except ValidationError as exc:
            result.error(str(exc))

    origin_session = frontmatter["origin_session"]
    if origin_session in SPECIAL_ORIGIN_SESSION_VALUES:
        pass
    elif CANONICAL_ORIGIN_SESSION_RE.fullmatch(origin_session):
        pass
    elif LEGACY_ORIGIN_SESSION_RE.fullmatch(origin_session):
        result.warn(
            f"{path}: legacy origin_session {origin_session!r}; prefer core/memory/activity/YYYY/MM/DD/chat-NNN"
        )
    else:
        result.error(
            f"{path}: origin_session must be memory/activity/YYYY/MM/DD/chat-NNN, core/memory/activity/YYYY/MM/DD/chat-NNN, setup, manual, or unknown"
        )
    if is_plan_path(relative_path):
        plan_type = frontmatter.get("type")
        if not plan_type:
            result.error(f"{path}: plan files must define frontmatter key 'type'")
        elif not plan_type.endswith("-plan"):
            result.error(f"{path}: plan type must end with '-plan', got {plan_type!r}")

        status = frontmatter.get("status")
        if not status:
            result.error(f"{path}: plan files must define frontmatter key 'status'")
        elif status not in ALLOWED_PLAN_STATUS_VALUES:
            result.error(
                f"{path}: plan status must be one of {sorted(ALLOWED_PLAN_STATUS_VALUES)!r}, got {status!r}"
            )

        next_action = frontmatter.get("next_action")
        if status == "complete":
            return
        if not next_action:
            result.error(f"{path}: plan files must define non-empty frontmatter key 'next_action'")


def validate_access_file(path: Path, root: Path, result: ValidationResult) -> None:
    text = read_text(path, result)
    if text is None:
        return
    namespace = _namespace_for_path(path.relative_to(root).as_posix())
    is_archive = path.name == "ACCESS.archive.jsonl"

    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            result.error(f"{path}:{line_number}: malformed JSON ({exc.msg})")
            continue

        if not isinstance(payload, dict):
            result.error(f"{path}:{line_number}: ACCESS entry must decode to an object")
            continue

        missing = sorted(REQUIRED_ACCESS_FIELDS - payload.keys())
        if missing:
            result.error(
                f"{path}:{line_number}: missing required ACCESS fields: {', '.join(missing)}"
            )
            continue

        if not isinstance(payload["file"], str):
            result.error(f"{path}:{line_number}: file must be a string")
        else:
            normalized_file = normalize_repo_relative_path(payload["file"])
            if normalized_file is None:
                result.error(
                    f"{path}:{line_number}: file must be a repo-relative path inside the memory repo"
                )
            else:
                file_ns = _namespace_for_path(normalized_file)
                if file_ns is None or file_ns != namespace:
                    result.error(
                        f"{path}:{line_number}: file must stay inside the owning namespace {namespace!r}, got {normalized_file!r}"
                    )
                else:
                    file_parts = normalized_file.split("/")
                    target_path = root.joinpath(*file_parts)
                    if not target_path.exists():
                        message = f"{path}:{line_number}: file references missing target {normalized_file!r}"
                        if is_archive:
                            result.warn(message)
                        else:
                            result.error(message)
        validate_iso_date(payload["date"], path, f"line {line_number} date", result)
        if not isinstance(payload["task"], str):
            result.error(f"{path}:{line_number}: task must be a string")
        if not isinstance(payload["note"], str):
            result.error(f"{path}:{line_number}: note must be a string")

        helpfulness = payload["helpfulness"]
        if not isinstance(helpfulness, (int, float)):
            result.error(f"{path}:{line_number}: helpfulness must be numeric")
        elif not 0.0 <= float(helpfulness) <= 1.0:
            result.error(f"{path}:{line_number}: helpfulness must be between 0.0 and 1.0")

        if "session_id" in payload:
            session_id = payload["session_id"]
            if not isinstance(session_id, str):
                result.error(f"{path}:{line_number}: session_id must be a string when present")
            elif not CANONICAL_ORIGIN_SESSION_RE.fullmatch(session_id):
                result.error(
                    f"{path}:{line_number}: session_id must match core/memory/activity/YYYY/MM/DD/chat-NNN when present, got {session_id!r}"
                )
        if "category" in payload and not isinstance(payload["category"], str):
            result.error(f"{path}:{line_number}: category must be a string when present")
        if "estimator" in payload and not isinstance(payload["estimator"], str):
            result.error(f"{path}:{line_number}: estimator must be a string when present")

        unknown_keys = set(payload) - REQUIRED_ACCESS_FIELDS - OPTIONAL_ACCESS_FIELDS
        if unknown_keys:
            result.warn(
                f"{path}:{line_number}: unknown ACCESS fields present: {', '.join(sorted(unknown_keys))}"
            )


def validate_chat_leaf_sessions(root: Path, result: ValidationResult) -> None:
    chats_root = root / "core" / "memory" / "activity"
    if not chats_root.exists():
        return

    for session_dir in sorted(chats_root.glob("*/*/*/chat-*")):
        # The sidecar feature writes chat-NNN.traces.jsonl files alongside the
        # chat-NNN/ session directories. The glob matches both, so skip anything
        # that isn't actually a session directory or this validator would
        # complain that a JSONL trace file is "missing" its SUMMARY.md.
        if not session_dir.is_dir():
            continue
        summary_path = session_dir / "SUMMARY.md"
        reflection_path = session_dir / "reflection.md"
        session_id = session_dir.relative_to(root).as_posix()

        if not summary_path.exists():
            result.error(f"{summary_path}: missing chat leaf SUMMARY.md")
        else:
            text = read_text(summary_path, result)
            if text is not None:
                frontmatter = parse_frontmatter(summary_path, text, result)
                body = text
                if frontmatter is not None:
                    try:
                        body = fmlib.loads(text).content
                    except Exception:
                        body = text
                    session_value = frontmatter.get("session")
                    if session_value is not None and str(session_value) != session_id:
                        result.error(
                            f"{summary_path}: frontmatter session must match {session_id!r}, got {session_value!r}"
                        )
                    if "date" in frontmatter:
                        validate_iso_date(frontmatter["date"], summary_path, "date", result)

                first_nonempty_line = next(
                    (line.strip() for line in body.splitlines() if line.strip()),
                    "",
                )
                if not first_nonempty_line.startswith("# Chat Summary"):
                    result.error(
                        f"{summary_path}: chat leaf summaries must begin with '# Chat Summary'"
                    )

        if not reflection_path.exists():
            result.warn(f"{reflection_path}: missing session reflection note")


def extract_manifest_row(text: str, session_type: str) -> str | None:
    pattern = re.compile(
        rf"^\| \*\*{re.escape(session_type)}\*\* \| (?P<body>.+?) \|$",
        re.MULTILINE,
    )
    match = pattern.search(text)
    if match is None:
        return None
    return match.group("body")


def estimate_token_count(text: str) -> int:
    stripped = text.strip()
    if not stripped:
        return 0
    return max(1, math.ceil(len(stripped) / 4))


def is_placeholder_or_empty_text(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return True
    return any(snippet in stripped for snippet in PLACEHOLDER_SNIPPETS)


def projects_summary_has_active_projects(text: str) -> bool:
    return (
        "| active |" in text
        or "| ongoing |" in text
        or "status: active" in text
        or "status: ongoing" in text
    )


def iter_compact_startup_measurements(
    root: Path, result: ValidationResult
) -> list[tuple[str, int, str]]:
    measurements: list[tuple[str, int, str]] = []

    for rel_path in EXPECTED_RETURNING_STEP_PATHS:
        path = root / rel_path
        if not path.exists():
            continue

        text = read_text(path, result)
        if text is None:
            continue

        if rel_path in {
            "core/memory/activity/SUMMARY.md",
            "core/memory/working/USER.md",
            "core/memory/working/CURRENT.md",
        }:
            if is_placeholder_or_empty_text(text):
                continue

        measurements.append((rel_path, estimate_token_count(text), text))

    return measurements


def find_repo_path_references(text: str, root: Path, prefixes: tuple[str, ...]) -> list[str]:
    references: list[str] = []
    for token in re.findall(r"[A-Za-z0-9_./-]+", text):
        normalized = normalize_repo_relative_path(token)
        if normalized is None:
            continue
        if not normalized.startswith(prefixes):
            continue
        if not (root / normalized).exists():
            continue
        references.append(normalized)
    return references


def validate_projects_summary_shape(
    path: Path, text: str, root: Path, result: ValidationResult
) -> None:
    if not text.lstrip().startswith("---"):
        result.error(f"{path}: projects navigator must begin with YAML frontmatter")
        return

    post = fmlib.loads(text)
    if post.metadata.get("type") != "projects-navigator":
        result.error(f"{path}: frontmatter must set type: projects-navigator")
    if "generated" not in post.metadata:
        result.error(f"{path}: frontmatter must include generated timestamp")
    if "project_count" not in post.metadata:
        result.error(f"{path}: frontmatter must include project_count")

    body = post.content
    if "# Projects" not in body:
        result.error(f"{path}: missing '# Projects' heading")

    required_header = "| Project | Status | Mode | Open Qs | Focus | Last activity |"
    if required_header not in body:
        result.error(f"{path}: missing canonical navigator table header")
        return

    row_pattern = re.compile(
        r"^\| (?P<project>[^|]+) \| (?P<status>active|ongoing|completed|archived) \| (?P<mode>[^|]+) \| (?P<open_qs>\d+) \| (?P<focus>[^|]+) \| (?P<activity>\d{4}-\d{2}-\d{2}) \|$",
        re.MULTILINE,
    )
    rows = list(row_pattern.finditer(body))
    if not rows:
        result.error(f"{path}: navigator must contain at least one project row")
        return

    project_count = post.metadata.get("project_count")
    if isinstance(project_count, int) and project_count != len(rows):
        result.error(
            f"{path}: project_count={project_count} does not match navigator row count {len(rows)}"
        )

    activity_dates = [match.group("activity") for match in rows]
    if activity_dates != sorted(activity_dates, reverse=True):
        result.error(f"{path}: navigator rows must be sorted by last activity descending")


def validate_chats_summary_shape(
    path: Path, text: str, root: Path, result: ValidationResult
) -> None:
    for heading in ("## Live themes", "## Recent continuity", "## Retrieval guide"):
        if heading not in text:
            result.error(f"{path}: missing compact chats heading {heading!r}")

    if "## Drill-down paths" not in text:
        result.error(f"{path}: missing compact chats heading '## Drill-down paths'")

    if re.search(r"^### chat-\d+", text, re.MULTILINE):
        result.error(
            f"{path}: chat-by-chat narrative headings are too detailed for the compact startup path"
        )

    if "Load dated summaries" not in text and "Load dated summaries when" not in text:
        result.error(f"{path}: must include retrieval guidance for dated summaries")

    if not find_repo_path_references(text, root, ("core/memory/activity/",)):
        result.error(
            f"{path}: must include at least one drill-down path into core/memory/activity/"
        )


def validate_scratchpad_current_shape(
    path: Path, text: str, root: Path, result: ValidationResult
) -> None:
    for heading in (
        "## Active threads",
        "## Immediate next actions",
        "## Open questions",
        "## Drill-down refs",
    ):
        if heading not in text:
            result.error(f"{path}: missing compact scratchpad heading {heading!r}")

    if "|---|" in text:
        result.error(
            f"{path}: compact CURRENT.md should not contain large tables; move analysis into a dated scratchpad"
        )

    if not find_repo_path_references(
        text,
        root,
        (
            "core/memory/working/projects/",
            "core/memory/working/notes/",
            "core/memory/knowledge/",
            "core/governance/",
            "core/memory/activity/",
            "core/memory/skills/",
            "core/memory/users/",
        ),
    ):
        result.error(f"{path}: must include at least one drill-down reference into the repo")


def validate_compact_startup_contract(root: Path, result: ValidationResult) -> None:
    measurements = iter_compact_startup_measurements(root, result)
    if not measurements:
        return

    total_tokens = sum(tokens for _, tokens, _ in measurements)
    if total_tokens > COMPACT_RETURNING_BUDGET:
        largest = ", ".join(
            f"{path}={tokens}"
            for path, tokens, _ in sorted(measurements, key=lambda item: item[1], reverse=True)[:3]
        )
        result.error(
            f"compact returning startup uses ~{total_tokens} tokens against the {COMPACT_RETURNING_BUDGET}-token ceiling; largest contributors: {largest}"
        )
    elif total_tokens > COMPACT_RETURNING_BUDGET - COMPACT_RETURNING_HEADROOM:
        result.warn(
            f"compact returning startup uses ~{total_tokens} tokens, leaving less than {COMPACT_RETURNING_HEADROOM} tokens of reserve"
        )

    for rel_path, tokens, text in measurements:
        target = COMPACT_RETURNING_TARGETS.get(rel_path)
        if target is not None and tokens > target:
            result.error(
                f"{root / rel_path}: compact startup file uses ~{tokens} tokens, above target {target}; move detail behind drill-down reads"
            )

        path = root / rel_path
        if rel_path == "core/memory/activity/SUMMARY.md":
            validate_chats_summary_shape(path, text, root, result)
        elif rel_path == "core/memory/working/CURRENT.md":
            validate_scratchpad_current_shape(path, text, root, result)


def validate_agent_bootstrap_manifest(root: Path, result: ValidationResult) -> None:
    path = root / BOOTSTRAP_MANIFEST_PATH
    if not path.exists():
        result.error(f"{path}: missing bootstrap manifest")
        return

    text = read_text(path, result)
    if text is None:
        return

    try:
        manifest = TOML_MODULE.loads(text)
    except TOML_MODULE.TOMLDecodeError as exc:
        result.error(f"{path}: invalid TOML ({exc})")
        return

    version = manifest.get("version")
    if version != 1:
        result.error(f"{path}: version must be 1, got {version!r}")

    router = manifest.get("router")
    if router != "core/INIT.md":
        result.error(f"{path}: router must be 'core/INIT.md', got {router!r}")
    elif not (root / router).exists():
        result.error(f"{path}: router target {router!r} does not exist")

    default_mode = manifest.get("default_mode")
    if default_mode != "returning":
        result.error(f"{path}: default_mode must be 'returning', got {default_mode!r}")

    adapter_files = manifest.get("adapter_files")
    expected_adapter_files = [str(adapter_path) for adapter_path in ADAPTER_FILES]
    if adapter_files != expected_adapter_files:
        result.error(
            f"{path}: adapter_files must be {expected_adapter_files!r}, got {adapter_files!r}"
        )

    host_repo_root = manifest.get("host_repo_root")
    deployed_worktree = (
        isinstance(host_repo_root, str)
        and bool(host_repo_root.strip())
        and is_git_worktree_root(root)
    )
    if host_repo_root is not None:
        if not isinstance(host_repo_root, str) or not host_repo_root.strip():
            result.error(f"{path}: host_repo_root must be a non-empty string when present")
        elif not Path(host_repo_root).is_absolute():
            result.error(f"{path}: host_repo_root must be an absolute path when present")

    mode_detection = manifest.get("mode_detection")
    if not isinstance(mode_detection, dict):
        result.error(f"{path}: mode_detection must be a TOML table")
    else:
        for key in EXPECTED_BOOTSTRAP_MODES:
            value = mode_detection.get(key)
            if not isinstance(value, str) or not value.strip():
                result.error(f"{path}: mode_detection.{key} must be a non-empty string")
        for key in (
            "warn_on_detached_head",
            "warn_on_worktree_branch_drift",
            "warn_on_branch_checked_out_elsewhere",
        ):
            if not isinstance(mode_detection.get(key), bool):
                result.error(f"{path}: mode_detection.{key} must be a boolean")

    modes = manifest.get("modes")
    if not isinstance(modes, dict):
        result.error(f"{path}: modes must be a TOML table")
        return

    missing_modes = [mode for mode in EXPECTED_BOOTSTRAP_MODES if mode not in modes]
    if missing_modes:
        result.error(f"{path}: missing required bootstrap modes: {', '.join(missing_modes)}")

    for mode_name in EXPECTED_BOOTSTRAP_MODES:
        mode = modes.get(mode_name)
        if not isinstance(mode, dict):
            result.error(f"{path}: modes.{mode_name} must be a TOML table")
            continue

        expected_budget = EXPECTED_BOOTSTRAP_TOKEN_BUDGETS[mode_name]
        if mode.get("token_budget") != expected_budget:
            result.error(
                f"{path}: modes.{mode_name}.token_budget must be {expected_budget}, got {mode.get('token_budget')!r}"
            )

        expected_prefer_summaries = EXPECTED_BOOTSTRAP_PREFER_SUMMARIES[mode_name]
        if mode.get("prefer_summaries") is not expected_prefer_summaries:
            result.error(
                f"{path}: modes.{mode_name}.prefer_summaries must be {expected_prefer_summaries!r}"
            )

        if mode_name != "first_run":
            if mode.get("on_demand") != list(EXPECTED_BOOTSTRAP_ON_DEMAND):
                result.error(
                    f"{path}: modes.{mode_name}.on_demand must be {list(EXPECTED_BOOTSTRAP_ON_DEMAND)!r}"
                )
            if mode.get("maintenance_probes") != list(EXPECTED_BOOTSTRAP_MAINTENANCE_PROBES):
                result.error(
                    f"{path}: modes.{mode_name}.maintenance_probes must be {list(EXPECTED_BOOTSTRAP_MAINTENANCE_PROBES)!r}"
                )

        steps = mode.get("steps")
        if not isinstance(steps, list) or not steps:
            result.error(f"{path}: modes.{mode_name}.steps must be a non-empty array")
            continue

        step_paths: list[str] = []
        seen_paths: set[str] = set()
        for index, step in enumerate(steps, start=1):
            if not isinstance(step, dict):
                result.error(f"{path}: modes.{mode_name}.steps[{index}] must be a table")
                continue

            step_path = step.get("path")
            if not isinstance(step_path, str) or not step_path:
                result.error(
                    f"{path}: modes.{mode_name}.steps[{index}].path must be a non-empty string"
                )
                continue
            if step_path in seen_paths:
                result.error(
                    f"{path}: modes.{mode_name} declares duplicate step path {step_path!r}"
                )
            seen_paths.add(step_path)
            step_paths.append(step_path)

            if not (root / step_path).exists():
                result.error(
                    f"{path}: modes.{mode_name}.steps[{index}] references missing path {step_path!r}"
                )

            role = step.get("role")
            if not isinstance(role, str) or not role.strip():
                result.error(
                    f"{path}: modes.{mode_name}.steps[{index}].role must be a non-empty string"
                )

            if not isinstance(step.get("required"), bool):
                result.error(f"{path}: modes.{mode_name}.steps[{index}].required must be a boolean")

            cost = step.get("cost")
            if cost not in EXPECTED_BOOTSTRAP_COST_VALUES:
                result.error(
                    f"{path}: modes.{mode_name}.steps[{index}].cost must be one of {sorted(EXPECTED_BOOTSTRAP_COST_VALUES)!r}, got {cost!r}"
                )

            skip_if = step.get("skip_if")
            if skip_if is not None and not isinstance(skip_if, str):
                result.error(
                    f"{path}: modes.{mode_name}.steps[{index}].skip_if must be a string when present"
                )

            expected_skip_if = EXPECTED_OPTIONAL_STEP_SKIP_RULES.get(step_path)
            if expected_skip_if is not None:
                if step.get("required") is not False:
                    result.error(
                        f"{path}: modes.{mode_name}.steps[{index}] for {step_path!r} must remain optional"
                    )
                if skip_if != expected_skip_if:
                    result.error(
                        f"{path}: modes.{mode_name}.steps[{index}] for {step_path!r} must use skip_if = {expected_skip_if!r}"
                    )

        expected_mode_step_paths = (
            DEPLOYED_WORKTREE_MODE_STEP_PATHS if deployed_worktree else EXPECTED_MODE_STEP_PATHS
        )
        expected_step_paths = list(expected_mode_step_paths[mode_name])
        if step_paths != expected_step_paths:
            result.error(
                f"{path}: modes.{mode_name}.steps must load {expected_step_paths!r}, got {step_paths!r}"
            )

    validate_worktree_topology(root, path, host_repo_root, result)


def validate_task_readiness_manifest(root: Path, result: ValidationResult) -> None:
    path = root / TASK_READINESS_MANIFEST_PATH
    if not path.exists():
        result.error(f"{path}: missing task-readiness manifest")
        return

    text = read_text(path, result)
    if text is None:
        return

    try:
        manifest = TOML_MODULE.loads(text)
    except TOML_MODULE.TOMLDecodeError as exc:
        result.error(f"{path}: invalid TOML ({exc})")
        return

    if manifest.get("version") != 1:
        result.error(f"{path}: version must be 1")
    if manifest.get("kind") != "agent-task-readiness":
        result.error(f"{path}: kind must be 'agent-task-readiness'")
    if not isinstance(manifest.get("manifest_role"), str) or not manifest["manifest_role"].strip():
        result.error(f"{path}: manifest_role must be a non-empty string")

    resolver_entrypoint = manifest.get("resolver_entrypoint")
    if not isinstance(resolver_entrypoint, str) or not resolver_entrypoint.strip():
        result.error(f"{path}: resolver_entrypoint must be a non-empty string")
    elif not (root / resolver_entrypoint).exists():
        result.error(f"{path}: resolver_entrypoint does not exist at {resolver_entrypoint!r}")

    task_detection = manifest.get("task_detection")
    if not isinstance(task_detection, dict):
        result.error(f"{path}: task_detection must be a TOML table")
    else:
        if task_detection.get("default_profile") != "workspace_general":
            result.error(f"{path}: task_detection.default_profile must be 'workspace_general'")
        if task_detection.get("profile_order") != list(EXPECTED_TASK_READINESS_PROFILE_ORDER):
            result.error(
                f"{path}: task_detection.profile_order must be {list(EXPECTED_TASK_READINESS_PROFILE_ORDER)!r}"
            )

    cache_policy = manifest.get("cache_policy")
    if not isinstance(cache_policy, dict):
        result.error(f"{path}: cache_policy must be a TOML table")
    else:
        for key in (
            "result_ttl_sec",
            "retry_failure_ttl_sec",
        ):
            if not isinstance(cache_policy.get(key), int) or isinstance(
                cache_policy.get(key), bool
            ):
                result.error(f"{path}: cache_policy.{key} must be an integer")
        for key in (
            "recheck_on_manual_retry",
            "recheck_on_final_gate",
            "agent_refresh_allowed",
        ):
            if not isinstance(cache_policy.get(key), bool):
                result.error(f"{path}: cache_policy.{key} must be a boolean")

    execution = manifest.get("execution")
    if not isinstance(execution, dict):
        result.error(f"{path}: execution must be a TOML table")
    else:
        for key in (
            "preflight_before_substantial_work",
            "surface_changes_since_initial_check",
        ):
            if not isinstance(execution.get(key), bool):
                result.error(f"{path}: execution.{key} must be a boolean")

    automation_integration = manifest.get("automation_integration")
    if not isinstance(automation_integration, dict):
        result.error(f"{path}: automation_integration must be a TOML table")
    else:
        for key in (
            "carry_forward_blockers",
            "skip_unchanged_publish_attempts",
            "notify_when_restored",
        ):
            if not isinstance(automation_integration.get(key), bool):
                result.error(f"{path}: automation_integration.{key} must be a boolean")

    ui_feedback = manifest.get("ui_feedback")
    if not isinstance(ui_feedback, dict):
        result.error(f"{path}: ui_feedback must be a TOML table")
    else:
        for key in (
            "panel_title",
            "manifest_action_label",
            "manifest_action_reason",
        ):
            if not isinstance(ui_feedback.get(key), str) or not ui_feedback[key].strip():
                result.error(f"{path}: ui_feedback.{key} must be a non-empty string")
        for key in ("details_when_blocked_only", "green_summary_only"):
            if not isinstance(ui_feedback.get(key), bool):
                result.error(f"{path}: ui_feedback.{key} must be a boolean")
        status_labels = ui_feedback.get("status_labels")
        if not isinstance(status_labels, dict):
            result.error(f"{path}: ui_feedback.status_labels must be a TOML table")
        else:
            for key in EXPECTED_TASK_READINESS_STATUS_LABELS:
                if not isinstance(status_labels.get(key), str) or not status_labels[key].strip():
                    result.error(
                        f"{path}: ui_feedback.status_labels.{key} must be a non-empty string"
                    )

    profiles = manifest.get("profiles")
    if not isinstance(profiles, dict):
        result.error(f"{path}: profiles must be a TOML table")
        profiles = {}
    checks = manifest.get("checks")
    if not isinstance(checks, dict):
        result.error(f"{path}: checks must be a TOML table")
        checks = {}

    missing_profiles = [
        profile for profile in EXPECTED_TASK_READINESS_PROFILES if profile not in profiles
    ]
    if missing_profiles:
        result.error(
            f"{path}: missing required task-readiness profiles: {', '.join(missing_profiles)}"
        )

    missing_checks = [
        check_id for check_id in EXPECTED_TASK_READINESS_CHECKS if check_id not in checks
    ]
    if missing_checks:
        result.error(f"{path}: missing required task-readiness checks: {', '.join(missing_checks)}")

    for profile_name in EXPECTED_TASK_READINESS_PROFILES:
        profile = profiles.get(profile_name)
        if not isinstance(profile, dict):
            result.error(f"{path}: profiles.{profile_name} must be a TOML table")
            continue
        for key in REQUIRED_TASK_READINESS_PROFILE_KEYS:
            value = profile.get(key)
            if key in {"keywords", "checks", "final_gate_checks"}:
                if not isinstance(value, list) or not all(
                    isinstance(item, str) and item.strip() for item in value
                ):
                    result.error(
                        f"{path}: profiles.{profile_name}.{key} must be an array of non-empty strings"
                    )
                else:
                    for check_id in value:
                        if key != "keywords" and check_id not in checks:
                            result.error(
                                f"{path}: profiles.{profile_name}.{key} references unknown check {check_id!r}"
                            )
            elif not isinstance(value, str) or not value.strip():
                result.error(f"{path}: profiles.{profile_name}.{key} must be a non-empty string")

    for check_id in EXPECTED_TASK_READINESS_CHECKS:
        check_definition = checks.get(check_id)
        if not isinstance(check_definition, dict):
            result.error(f"{path}: checks.{check_id} must be a TOML table")
            continue
        for key in REQUIRED_TASK_READINESS_CHECK_KEYS:
            value = check_definition.get(key)
            if key in {"failure_modes", "fallback_paths"}:
                if not isinstance(value, list) or not all(
                    isinstance(item, str) and item.strip() for item in value
                ):
                    result.error(
                        f"{path}: checks.{check_id}.{key} must be an array of non-empty strings"
                    )
                elif key == "failure_modes":
                    for item in value:
                        if item not in ALLOWED_TASK_READINESS_FAILURE_MODES:
                            result.error(
                                f"{path}: checks.{check_id}.failure_modes contains unknown mode {item!r}"
                            )
            elif not isinstance(value, str) or not value.strip():
                result.error(f"{path}: checks.{check_id}.{key} must be a non-empty string")
        if check_definition.get("category") not in ALLOWED_TASK_READINESS_CATEGORIES:
            result.error(
                f"{path}: checks.{check_id}.category must be one of {sorted(ALLOWED_TASK_READINESS_CATEGORIES)!r}"
            )


def validate_quick_reference(root: Path, result: ValidationResult) -> None:
    path = root / "core" / "INIT.md"
    text = read_text(path, result)
    if text is None:
        return

    for parameter in EXPECTED_QUICK_REFERENCE_PARAMETERS:
        if parameter not in text:
            result.error(f"{path}: missing active parameter name {parameter!r}")

    required_phrases = (
        "single authoritative source",
        QUICK_REFERENCE_ROUTER_PHRASE,
        "Grouping precedence:",
        "`session_id`",
        "`date`",
        "Exploration defaults apply",
        "metadata-first maintenance probes",
        "Count non-empty lines in `ACCESS.jsonl` files",
        "task-driven drill-down context",
        "Whole-file compact mode",
        "Compact file success criteria",
        "Target budget",
        MCP_PREFERENCE_PHRASE,
    )
    for phrase in required_phrases:
        if phrase not in text:
            result.error(f"{path}: missing required runtime guidance phrase {phrase!r}")

    compact_row = extract_manifest_row(text, "Compact returning")
    if compact_row is None:
        result.error(f"{path}: missing manifest row for 'Compact returning'")
        return

    required_compact_markers = (
        "core/memory/HOME.md",
        "core/memory/users/SUMMARY.md",
        "core/memory/activity/SUMMARY.md",
        "core/memory/working/projects/SUMMARY.md",
        "core/memory/working/USER.md",
        "core/memory/working/CURRENT.md",
        "core/memory/knowledge/SUMMARY.md",
        "core/memory/skills/SUMMARY.md",
    )
    for marker in required_compact_markers:
        if marker not in compact_row:
            result.error(f"{path}: compact manifest is missing {marker!r}")

    forbidden_compact_markers = ("README.md", "session-checklists")
    for marker in forbidden_compact_markers:
        if marker in compact_row:
            result.error(
                f"{path}: compact manifest must not require {marker!r} on returning sessions"
            )


def validate_runtime_guidance(root: Path, result: ValidationResult) -> None:
    for relative_path in RUNTIME_GUIDANCE_FILES:
        path = root / relative_path
        if not path.exists():
            result.error(f"{path}: missing runtime guidance file")
            continue
        text = read_text(path, result)
        if text is None:
            continue
        for pattern in FORBIDDEN_RUNTIME_PATTERNS:
            if re.search(pattern, text):
                result.error(f"{path}: contains forbidden runtime guidance pattern {pattern!r}")


def validate_setup_entrypoints(root: Path, result: ValidationResult) -> None:
    for path, target in ROOT_SETUP_TARGETS.items():
        absolute = root / path
        if not absolute.exists():
            result.error(f"{absolute}: missing repo-root setup entrypoint")
            continue
        text = read_text(absolute, result)
        if text is None:
            continue
        if target not in text:
            result.error(f"{absolute}: expected to reference {target!r}")

    for path in CANONICAL_SETUP_FILES:
        absolute = root / path
        if not absolute.exists():
            result.error(f"{absolute}: missing canonical setup implementation")


def validate_mcp_runtime_layout(root: Path, result: ValidationResult) -> None:
    manifest_path = root / CAPABILITIES_MANIFEST_PATH
    runtime_dir = root / EXPECTED_MCP_RUNTIME_DIR
    entrypoint_path = root / EXPECTED_MCP_ENTRYPOINT
    legacy_runtime_dir = root / LEGACY_MCP_RUNTIME_DIR
    legacy_entrypoint_path = root / LEGACY_MCP_ENTRYPOINT
    legacy_runtime_dir_v2 = root / LEGACY_MCP_RUNTIME_DIR_V2
    legacy_entrypoint_v2 = root / LEGACY_MCP_ENTRYPOINT_V2

    has_mcp_runtime = manifest_path.exists() or runtime_dir.exists() or entrypoint_path.exists()
    if not has_mcp_runtime:
        return

    if not runtime_dir.is_dir():
        result.error(f"{runtime_dir}: missing MCP runtime directory")

    if not entrypoint_path.exists():
        result.error(f"{entrypoint_path}: missing MCP entrypoint script")

    if legacy_runtime_dir.exists():
        result.error(
            f"{legacy_runtime_dir}: legacy tools/ runtime directory must not exist after migration"
        )

    if legacy_entrypoint_path.exists():
        result.error(f"{legacy_entrypoint_path}: stale MCP shim must not exist after migration")

    if legacy_runtime_dir_v2.is_dir():
        result.error(
            f"{legacy_runtime_dir_v2}: legacy engram_mcp/ runtime directory must not exist after core/tools migration"
        )

    if legacy_entrypoint_v2.exists():
        result.error(
            f"{legacy_entrypoint_v2}: stale engram_mcp entrypoint must not exist after core/tools migration"
        )

    if not manifest_path.exists():
        return

    text = read_text(manifest_path, result)
    if text is None:
        return

    try:
        manifest = TOML_MODULE.loads(text)
    except Exception as exc:
        result.error(f"{manifest_path}: invalid TOML ({exc})")
        return

    mcp_entrypoint = manifest.get("mcp_entrypoint")
    expected_entrypoint = EXPECTED_MCP_ENTRYPOINT.as_posix()
    if mcp_entrypoint != expected_entrypoint:
        result.error(
            f"{manifest_path}: mcp_entrypoint must be {expected_entrypoint!r}, got {mcp_entrypoint!r}"
        )


def validate_adapter_routing(root: Path, result: ValidationResult) -> None:
    for relative_path in ADAPTER_FILES:
        path = root / relative_path
        if not path.exists():
            result.error(f"{path}: missing adapter file")
            continue
        text = read_text(path, result)
        if text is None:
            continue
        if "core/INIT.md" not in text:
            result.error(f"{path}: must point agents to core/INIT.md")
        if ADAPTER_ROUTING_PHRASE not in text:
            result.error(f"{path}: missing adapter routing phrase {ADAPTER_ROUTING_PHRASE!r}")
        if ADAPTER_MCP_PHRASE not in text:
            result.error(f"{path}: missing MCP preference phrase {ADAPTER_MCP_PHRASE!r}")


def validate_prompt_copy(root: Path, result: ValidationResult) -> None:
    for relative_path in PROMPT_COPY_FILES:
        path = root / relative_path
        if not path.exists():
            result.error(f"{path}: missing prompt-copy file")
            continue
        text = read_text(path, result)
        if text is None:
            continue
        for phrase in (
            PROMPT_START_LINE,
            PROMPT_ROUTE_LINE,
            PROMPT_MCP_LINE,
            LIVE_CONFIG_LINE,
        ):
            if phrase not in text:
                result.error(f"{path}: missing prompt-copy phrase {phrase!r}")


def validate_setup_guidance(root: Path, result: ValidationResult) -> None:
    for relative_path in SETUP_GUIDANCE_FILES:
        path = root / relative_path
        if not path.exists():
            result.error(f"{path}: missing setup-guidance file")
            continue
        text = read_text(path, result)
        if text is None:
            continue
        for pattern in SETUP_GUIDANCE_REQUIRED_PATTERNS:
            if not re.search(pattern, text):
                result.error(f"{path}: missing setup-guidance pattern {pattern!r}")
        for pattern in SETUP_GUIDANCE_FORBIDDEN_PATTERNS:
            if re.search(pattern, text):
                result.error(f"{path}: contains forbidden setup-guidance pattern {pattern!r}")


def validate_onboarding_export_template(root: Path, result: ValidationResult) -> None:
    path = root / ONBOARDING_EXPORT_TEMPLATE_PATH
    if not path.exists():
        result.error(f"{path}: missing onboarding export template")
        return

    text = read_text(path, result)
    if text is None:
        return

    if ONBOARDING_EXPORT_REQUIRED_PHRASE not in text:
        result.error(
            f"{path}: missing onboarding-export phrase {ONBOARDING_EXPORT_REQUIRED_PHRASE!r}"
        )

    for pattern in ONBOARDING_EXPORT_FORBIDDEN_PATTERNS:
        if re.search(pattern, text):
            result.error(f"{path}: contains forbidden onboarding-export pattern {pattern!r}")


def validate_contract_consistency(root: Path, result: ValidationResult) -> None:
    readme = read_text(root / "README.md", result)
    if readme is not None:
        for phrase in (README_START_PHRASE, README_ARCHITECTURE_PHRASE):
            if phrase not in readme:
                result.error(f"{root / 'README.md'}: missing contract phrase {phrase!r}")

    session_checklists = read_text(root / "core" / "governance" / "session-checklists.md", result)
    if session_checklists is not None:
        if SESSION_CHECKLISTS_ON_DEMAND_PHRASE not in session_checklists:
            result.error(
                f"{root / 'core' / 'governance' / 'session-checklists.md'}: missing on-demand guidance"
            )

    # MCP preference is centralized in core/INIT.md (checked in validate_quick_reference);
    # individual files no longer need their own copy.

    session_start = root / SESSION_START_SKILL_PATH
    if session_start.exists():
        text = read_text(session_start, result)
        if text is not None:
            for phrase in SESSION_START_REQUIRED_PHRASES:
                if phrase not in text:
                    result.error(f"{session_start}: missing startup-skill phrase {phrase!r}")
            for pattern in SESSION_START_FORBIDDEN_PATTERNS:
                if re.search(pattern, text, re.MULTILINE):
                    result.error(
                        f"{session_start}: contains forbidden startup-skill pattern {pattern!r}"
                    )

    session_wrapup = root / SESSION_WRAPUP_SKILL_PATH
    if session_wrapup.exists():
        text = read_text(session_wrapup, result)
        if text is not None:
            for phrase in SESSION_WRAPUP_REQUIRED_PHRASES:
                if phrase not in text:
                    result.error(f"{session_wrapup}: missing wrapup-skill phrase {phrase!r}")
            for pattern in SESSION_WRAPUP_FORBIDDEN_PATTERNS:
                if re.search(pattern, text, re.MULTILINE):
                    result.error(
                        f"{session_wrapup}: contains forbidden wrapup-skill pattern {pattern!r}"
                    )

    read_text(root / SKILLS_SUMMARY_PATH, result)
    read_text(root / ONBOARDING_SKILL_PATH, result)
    read_text(root / SESSION_SYNC_SKILL_PATH, result)


def validate_quarantine(root: Path, result: ValidationResult) -> None:
    unverified = root / "core" / "memory" / "knowledge" / "_unverified"
    if not unverified.exists():
        return

    for path in sorted(unverified.rglob("*.md")):
        if should_ignore(path.relative_to(root)):
            continue
        if path.name == "SUMMARY.md":
            continue
        text = read_text(path, result)
        if text is None:
            continue

        frontmatter = parse_frontmatter(path, text, result)
        if frontmatter is None:
            continue

        trust = frontmatter.get("trust")
        if trust and trust != "low":
            result.error(f"{path}: quarantine file must have trust: low, got {trust!r}")

        source = frontmatter.get("source")
        relative_path = path.relative_to(root).as_posix()
        allow_internal_quarantine_source = (
            relative_path == "core/memory/knowledge/_unverified/brainstorm-pwr-protocol.md"
            or relative_path.startswith("core/memory/knowledge/_unverified/system-notes/")
        )
        if source and source != "external-research" and not allow_internal_quarantine_source:
            result.warn(
                f"{path}: quarantine file expected source: external-research, got {source!r}"
            )

        if "last_verified" in frontmatter:
            result.error(
                f"{path}: quarantine file must omit last_verified until explicitly reviewed and promoted"
            )


def validate_repo(root: Path) -> ValidationResult:
    result = ValidationResult()
    deployed_worktree = is_deployed_worktree_repo(root)

    validate_agent_bootstrap_manifest(root, result)
    if not deployed_worktree:
        validate_task_readiness_manifest(root, result)
    validate_quick_reference(root, result)
    validate_compact_startup_contract(root, result)
    if not deployed_worktree:
        validate_runtime_guidance(root, result)
        validate_setup_entrypoints(root, result)
    validate_mcp_runtime_layout(root, result)
    validate_adapter_routing(root, result)
    if not deployed_worktree:
        validate_prompt_copy(root, result)
        validate_setup_guidance(root, result)
        validate_onboarding_export_template(root, result)
    validate_contract_consistency(root, result)
    validate_quarantine(root, result)
    validate_chat_leaf_sessions(root, result)

    projects_summary = root / "core" / "memory" / "working" / "projects" / "SUMMARY.md"
    if projects_summary.exists():
        text = read_text(projects_summary, result)
        if text is not None:
            validate_projects_summary_shape(projects_summary, text, root, result)

    for path in iter_content_files(root):
        validate_frontmatter(path, root, result)

    for path in iter_access_files(root):
        validate_access_file(path, root, result)

    validate_access_coverage(root, result)

    return result


def main(argv: list[str] | None = None) -> int:
    argv = argv or sys.argv
    root = repo_root_from_argv(argv)
    result = validate_repo(root)

    for warning in result.warnings:
        print(f"WARNING: {warning}")
    for error in result.errors:
        print(f"ERROR: {error}")

    if result.errors:
        print(
            f"Validation failed with {len(result.errors)} error(s) and {len(result.warnings)} warning(s)."
        )
        return 1

    print(f"Validation passed with {len(result.warnings)} warning(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
