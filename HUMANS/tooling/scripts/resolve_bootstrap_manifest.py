#!/usr/bin/env python3
"""Resolve a repo bootstrap manifest into a concrete startup trace.

This is a repo-side prototype for the Codex desktop bootstrap-support plan.
It makes the manifest executable enough to test mode selection, preload order,
skip handling, startup warnings, and manual override controls before those
behaviors exist app-side.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Any

import frontmatter as fmlib

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python < 3.11 fallback
    import tomli as tomllib


BOOTSTRAP_MANIFEST = "agent-bootstrap.toml"
PLACEHOLDER_SNIPPETS = (
    "_Nothing here yet.",
    "_No pending items._",
    "_No current notes._",
)
EXPECTED_MODES = (
    "first_run",
    "returning",
    "full_bootstrap",
    "periodic_review",
    "automation",
)
COST_TOKEN_ESTIMATES = {
    "light": 500,
    "medium": 2500,
    "heavy": 7000,
}
MIN_BUDGET_RESERVE = 500
DEFAULT_COST_ESTIMATE = COST_TOKEN_ESTIMATES["medium"]

# Manual override definitions — the three controls surfaced in the startup panel.
# Each override is always present in startup_panel.available_overrides; at most
# one has active=True.
_OVERRIDE_DEFINITIONS: list[dict[str, str]] = [
    {
        "id": "full_bootstrap",
        "label": "Load Full Bootstrap",
        "description": (
            "Load the complete governance stack regardless of the detected session type."
        ),
    },
    {
        "id": "compact_only",
        "label": "Load Compact Startup Only",
        "description": (
            "Force the compact returning-session preload and skip heavier governance files."
        ),
    },
    {
        "id": "skip_manifest",
        "label": "Skip Repo Manifest",
        "description": (
            "Bypass agent-bootstrap.toml for this thread and fall back to"
            " generic startup heuristics (AGENTS.md → README.md)."
        ),
    },
]


@dataclass(frozen=True)
class GitState:
    current_branch: str | None
    detached_head: bool
    worktree_branch_drift: bool
    branch_checked_out_elsewhere: bool


@dataclass(frozen=True)
class StartupWarning:
    code: str
    message: str


@dataclass(frozen=True)
class StartupBudget:
    limit: int
    reserve: int
    estimated_used: int
    estimated_remaining: int
    pressure: bool


@dataclass(frozen=True)
class StartupTraceStep:
    path: str
    role: str
    status: str
    required: bool
    cost: str
    estimated_tokens: int
    budget_after: int
    reason: str | None = None


@dataclass(frozen=True)
class StartupPanelFile:
    path: str
    role: str
    status: str
    reason: str | None
    required: bool


@dataclass(frozen=True)
class StartupPanelAction:
    label: str
    path: str
    reason: str


@dataclass(frozen=True)
class StartupPanelWarning:
    code: str
    title: str
    message: str
    severity: str
    source: str


@dataclass(frozen=True)
class StartupPanelOverride:
    """One of the three manual controls the UI can render as a button."""

    id: str
    label: str
    description: str
    active: bool


@dataclass(frozen=True)
class StartupPanel:
    title: str
    status: str
    mode_label: str
    mode_source: str
    repo_next_step: StartupPanelAction
    files: list[StartupPanelFile]
    warnings: list[StartupPanelWarning]
    loaded_count: int
    skipped_count: int
    missing_count: int
    warning_count: int
    budget_status: str
    active_override: str | None
    available_overrides: list[StartupPanelOverride]


@dataclass(frozen=True)
class StartupResolution:
    router: str
    mode: str
    mode_source: str
    token_budget: int
    prefer_summaries: bool
    on_demand: list[str]
    maintenance_probes: list[str]
    preload_access_mode: str
    budget: StartupBudget
    git_state: GitState
    host_repo_root: str | None
    host_git_state: GitState | None
    warnings: list[StartupWarning]
    trace: list[StartupTraceStep]
    active_override: str | None
    startup_panel: StartupPanel


def normalize_manifest_path(raw_path: str) -> str:
    parts: list[str] = []
    for part in raw_path.replace("\\", "/").split("/"):
        if part in {"", "."}:
            continue
        if part == "..":
            if parts:
                parts.pop()
            continue
        parts.append(part)
    return "/".join(parts)


def read_manifest(repo_root: Path) -> dict[str, Any]:
    manifest_path = repo_root / BOOTSTRAP_MANIFEST
    return tomllib.loads(manifest_path.read_text(encoding="utf-8"))


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def parse_frontmatter_value(path: Path, key: str) -> str | None:
    if not path.exists():
        return None
    text = read_text(path)
    if not text.lstrip().startswith("---"):
        return None
    try:
        metadata = dict(fmlib.loads(text).metadata)
    except Exception:
        return None

    value = metadata.get(key)
    if value is None:
        return None
    return str(value)


def has_chat_history(repo_root: Path) -> bool:
    chats_root = repo_root / "chats"
    if not chats_root.exists():
        return False
    return any(chats_root.glob("*/*/*/chat-*"))


def repo_looks_first_run(repo_root: Path) -> bool:
    profile_source = parse_frontmatter_value(repo_root / "identity" / "profile.md", "source")
    if has_chat_history(repo_root):
        return False
    return profile_source in {None, "template"}


def detect_mode(
    repo_root: Path,
    manifest: dict[str, Any],
    *,
    requested_mode: str = "auto",
    automation: bool = False,
    periodic_review: bool = False,
    fresh_instantiation: bool = False,
    full_bootstrap: bool = False,
) -> tuple[str, str]:
    if requested_mode != "auto":
        return requested_mode, "mode_override"
    if automation:
        return "automation", "automation_flag"
    if periodic_review:
        return "periodic_review", "periodic_review_flag"
    if repo_looks_first_run(repo_root):
        return "first_run", "first_run_heuristic"
    if fresh_instantiation:
        return "full_bootstrap", "fresh_instantiation_flag"
    if full_bootstrap:
        return "full_bootstrap", "full_bootstrap_flag"
    return str(manifest.get("default_mode", "returning")), "default_mode"


def run_git(repo_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )


def parse_worktree_list(output: str) -> list[dict[str, str]]:
    worktrees: list[dict[str, str]] = []
    current: dict[str, str] = {}
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line:
            if current:
                worktrees.append(current)
                current = {}
            continue
        key, _, value = line.partition(" ")
        current[key] = value.strip()
    if current:
        worktrees.append(current)
    return worktrees


def detect_git_state(repo_root: Path, expected_branch: str | None = None) -> GitState:
    top_level = run_git(repo_root, "rev-parse", "--show-toplevel")
    if top_level.returncode != 0:
        return GitState(
            current_branch=None,
            detached_head=False,
            worktree_branch_drift=False,
            branch_checked_out_elsewhere=False,
        )

    branch_result = run_git(repo_root, "branch", "--show-current")
    current_branch = branch_result.stdout.strip() or None

    detached_head = False
    if current_branch is None:
        head_result = run_git(repo_root, "rev-parse", "--abbrev-ref", "HEAD")
        detached_head = head_result.returncode == 0 and head_result.stdout.strip() == "HEAD"

    worktree_branch_drift = False
    if expected_branch:
        if detached_head:
            worktree_branch_drift = True
        elif current_branch and current_branch != expected_branch:
            worktree_branch_drift = True

    target_branch = expected_branch or current_branch
    branch_checked_out_elsewhere = False
    if target_branch:
        worktree_result = run_git(repo_root, "worktree", "list", "--porcelain")
        if worktree_result.returncode == 0:
            current_worktree = top_level.stdout.strip()
            target_ref = f"refs/heads/{target_branch}"
            for worktree in parse_worktree_list(worktree_result.stdout):
                if worktree.get("branch") != target_ref:
                    continue
                if worktree.get("worktree") and worktree["worktree"] != current_worktree:
                    branch_checked_out_elsewhere = True
                    break

    return GitState(
        current_branch=current_branch,
        detached_head=detached_head,
        worktree_branch_drift=worktree_branch_drift,
        branch_checked_out_elsewhere=branch_checked_out_elsewhere,
    )


def resolve_host_repo_root(repo_root: Path, manifest: dict[str, Any]) -> Path | None:
    raw_root = manifest.get("host_repo_root")
    if not isinstance(raw_root, str) or not raw_root.strip():
        return None
    candidate = Path(raw_root)
    if not candidate.is_absolute():
        candidate = (repo_root / candidate).resolve()
    return candidate


def is_placeholder_or_empty(path: Path) -> bool:
    if not path.exists():
        return True
    text = read_text(path).strip()
    if not text:
        return True
    return any(snippet in text for snippet in PLACEHOLDER_SNIPPETS)


def has_active_projects(path: Path) -> bool:
    if not path.exists():
        return False
    text = read_text(path)
    return (
        "| active |" in text
        or "| ongoing |" in text
        or "status: active" in text
        or "status: ongoing" in text
    )


def resolve_skip_reason(path: Path, skip_if: str | None) -> str | None:
    if skip_if == "placeholder_or_empty" and is_placeholder_or_empty(path):
        return skip_if
    if skip_if == "no_active_projects" and not has_active_projects(path):
        return skip_if
    return None


def compute_budget_reserve(token_budget: int) -> int:
    return max(MIN_BUDGET_RESERVE, token_budget // 7)


def is_transcript_path(normalized_path: str) -> bool:
    return PurePosixPath(normalized_path).name.lower() == "transcript.md"


def estimate_tokens_for_step(
    normalized_path: str,
    cost: str,
    *,
    prefer_summaries: bool,
) -> int:
    estimate = COST_TOKEN_ESTIMATES.get(cost, DEFAULT_COST_ESTIMATE)
    if prefer_summaries and is_transcript_path(normalized_path):
        return max(estimate, COST_TOKEN_ESTIMATES["heavy"])
    return estimate


def resolve_trace(
    repo_root: Path,
    steps: list[dict[str, Any]],
    *,
    token_budget: int,
    prefer_summaries: bool,
) -> tuple[list[StartupTraceStep], StartupBudget]:
    trace: list[StartupTraceStep] = []
    seen_paths: set[str] = set()
    reserve = compute_budget_reserve(token_budget)
    estimated_used = 0
    budget_pressure = False

    for step in steps:
        normalized_path = normalize_manifest_path(str(step["path"]))
        role = str(step["role"])
        required = bool(step["required"])
        cost = str(step["cost"])
        estimated_tokens = estimate_tokens_for_step(
            normalized_path,
            cost,
            prefer_summaries=prefer_summaries,
        )
        budget_after = token_budget - estimated_used

        if normalized_path in seen_paths:
            trace.append(
                StartupTraceStep(
                    path=normalized_path,
                    role=role,
                    status="skipped",
                    required=required,
                    cost=cost,
                    estimated_tokens=estimated_tokens,
                    budget_after=budget_after,
                    reason="duplicate_path",
                )
            )
            continue

        seen_paths.add(normalized_path)
        target_path = repo_root / normalized_path
        if not target_path.exists():
            trace.append(
                StartupTraceStep(
                    path=normalized_path,
                    role=role,
                    status="missing",
                    required=required,
                    cost=cost,
                    estimated_tokens=estimated_tokens,
                    budget_after=budget_after,
                )
            )
            continue

        skip_reason = resolve_skip_reason(target_path, step.get("skip_if"))
        if skip_reason is not None:
            trace.append(
                StartupTraceStep(
                    path=normalized_path,
                    role=role,
                    status="skipped",
                    required=required,
                    cost=cost,
                    estimated_tokens=estimated_tokens,
                    budget_after=budget_after,
                    reason=skip_reason,
                )
            )
            continue

        remaining_after_load = token_budget - (estimated_used + estimated_tokens)
        if not required and remaining_after_load < reserve:
            budget_pressure = True
            trace.append(
                StartupTraceStep(
                    path=normalized_path,
                    role=role,
                    status="skipped",
                    required=required,
                    cost=cost,
                    estimated_tokens=estimated_tokens,
                    budget_after=budget_after,
                    reason="budget_pressure",
                )
            )
            continue

        estimated_used += estimated_tokens
        budget_after = token_budget - estimated_used
        if budget_after < reserve:
            budget_pressure = True

        trace.append(
            StartupTraceStep(
                path=normalized_path,
                role=role,
                status="loaded",
                required=required,
                cost=cost,
                estimated_tokens=estimated_tokens,
                budget_after=budget_after,
            )
        )

    return trace, StartupBudget(
        limit=token_budget,
        reserve=reserve,
        estimated_used=estimated_used,
        estimated_remaining=token_budget - estimated_used,
        pressure=budget_pressure,
    )


def resolve_warnings(
    git_state: GitState,
    mode_detection: dict[str, Any],
    *,
    budget: StartupBudget | None = None,
    expected_branch: str | None = None,
) -> list[StartupWarning]:
    warnings: list[StartupWarning] = []

    if mode_detection.get("warn_on_detached_head") and git_state.detached_head:
        warnings.append(
            StartupWarning(
                code="detached_head",
                message="Repo is in detached HEAD state before startup.",
            )
        )

    if mode_detection.get("warn_on_worktree_branch_drift") and git_state.worktree_branch_drift:
        current = git_state.current_branch or "detached HEAD"
        target = expected_branch or "requested branch"
        warnings.append(
            StartupWarning(
                code="worktree_branch_drift",
                message=f"Current worktree is on {current}; expected {target}.",
            )
        )

    if (
        mode_detection.get("warn_on_branch_checked_out_elsewhere")
        and git_state.branch_checked_out_elsewhere
    ):
        target = expected_branch or git_state.current_branch or "requested branch"
        warnings.append(
            StartupWarning(
                code="branch_checked_out_elsewhere",
                message=f"Branch {target} is already checked out in another worktree.",
            )
        )

    if budget is not None and budget.pressure:
        warnings.append(
            StartupWarning(
                code="budget_pressure",
                message=(
                    "Startup preload hit budget pressure; optional higher-cost files were"
                    " skipped to preserve compact context."
                ),
            )
        )

    return warnings


def format_mode_label(mode: str) -> str:
    return mode.replace("_", " ").title()


def panel_status_from_resolution(
    trace: list[StartupTraceStep],
    warnings: list[StartupWarning],
) -> str:
    if warnings:
        return "attention"
    if any(step.status == "missing" and step.required for step in trace):
        return "attention"
    return "ready"


def budget_status_from_budget(budget: StartupBudget) -> str:
    if budget.pressure:
        return "tight"
    return "healthy"


def build_panel_warning(warning: StartupWarning) -> StartupPanelWarning:
    titles = {
        "detached_head": "Detached HEAD",
        "worktree_branch_drift": "Branch Drift",
        "branch_checked_out_elsewhere": "Branch In Another Worktree",
        "budget_pressure": "Budget Pressure",
        "manifest_skipped": "Manifest Bypassed",
    }
    sources = {
        "detached_head": "git",
        "worktree_branch_drift": "git",
        "branch_checked_out_elsewhere": "git",
        "budget_pressure": "budget",
        "manifest_skipped": "user_override",
    }
    return StartupPanelWarning(
        code=warning.code,
        title=titles.get(warning.code, warning.code.replace("_", " ").title()),
        message=warning.message,
        severity="warning",
        source=sources.get(warning.code, "startup"),
    )


def _build_available_overrides(active_override: str | None) -> list[StartupPanelOverride]:
    return [
        StartupPanelOverride(
            id=defn["id"],
            label=defn["label"],
            description=defn["description"],
            active=defn["id"] == active_override,
        )
        for defn in _OVERRIDE_DEFINITIONS
    ]


def build_startup_panel(
    *,
    router: str,
    mode: str,
    mode_source: str,
    trace: list[StartupTraceStep],
    warnings: list[StartupWarning],
    budget: StartupBudget,
    active_override: str | None = None,
) -> StartupPanel:
    return StartupPanel(
        title=f"{format_mode_label(mode)} Startup",
        status=panel_status_from_resolution(trace, warnings),
        mode_label=format_mode_label(mode),
        mode_source=mode_source,
        repo_next_step=StartupPanelAction(
            label="Open Router",
            path=router,
            reason=f"Repo-declared router for {format_mode_label(mode)} mode.",
        ),
        files=[
            StartupPanelFile(
                path=step.path,
                role=step.role,
                status=step.status,
                reason=step.reason,
                required=step.required,
            )
            for step in trace
        ],
        warnings=[build_panel_warning(warning) for warning in warnings],
        loaded_count=sum(1 for step in trace if step.status == "loaded"),
        skipped_count=sum(1 for step in trace if step.status == "skipped"),
        missing_count=sum(1 for step in trace if step.status == "missing"),
        warning_count=len(warnings),
        budget_status=budget_status_from_budget(budget),
        active_override=active_override,
        available_overrides=_build_available_overrides(active_override),
    )


def _resolve_skip_manifest(
    repo_root: Path,
    *,
    expected_branch: str | None = None,
    git_state: GitState | None = None,
) -> StartupResolution:
    """Resolve startup without reading agent-bootstrap.toml.

    Falls back to AGENTS.md → README.md and emits a manifest_skipped warning
    so the UI can surface the bypass clearly.
    """
    active_override = "skip_manifest"
    mode = "first_run" if repo_looks_first_run(repo_root) else "returning"
    mode_source = "user_override_skip_manifest"
    token_budget = 7_000
    prefer_summaries = True
    router = "README.md"

    # Build a minimal fallback step list from the files most likely to exist
    # in a generic repo. Required is False for both so budget pressure can
    # still skip them; missing files are handled by resolve_trace normally.
    fallback_steps: list[dict[str, Any]] = []
    for path_str, role in [
        ("AGENTS.md", "agents-manifest"),
        ("README.md", "readme"),
    ]:
        fallback_steps.append({"path": path_str, "role": role, "required": False, "cost": "medium"})

    trace, budget = resolve_trace(
        repo_root,
        fallback_steps,
        token_budget=token_budget,
        prefer_summaries=prefer_summaries,
    )

    current_git_state = git_state or detect_git_state(repo_root, expected_branch=expected_branch)

    # Always warn that the manifest was bypassed, then append any git/budget warnings.
    warnings: list[StartupWarning] = [
        StartupWarning(
            code="manifest_skipped",
            message=(
                "agent-bootstrap.toml was bypassed by user override;"
                " fallback heuristics used for this thread."
            ),
        )
    ]
    warnings.extend(
        resolve_warnings(
            current_git_state,
            {
                "warn_on_detached_head": True,
                "warn_on_worktree_branch_drift": True,
                "warn_on_branch_checked_out_elsewhere": True,
            },
            budget=budget,
            expected_branch=expected_branch,
        )
    )

    return StartupResolution(
        router=router,
        mode=mode,
        mode_source=mode_source,
        token_budget=token_budget,
        prefer_summaries=prefer_summaries,
        on_demand=[],
        maintenance_probes=[],
        preload_access_mode="startup_trace_only",
        budget=budget,
        git_state=current_git_state,
        host_repo_root=None,
        host_git_state=None,
        warnings=warnings,
        trace=trace,
        active_override=active_override,
        startup_panel=build_startup_panel(
            router=router,
            mode=mode,
            mode_source=mode_source,
            trace=trace,
            warnings=warnings,
            budget=budget,
            active_override=active_override,
        ),
    )


def resolve_startup(
    repo_root: Path,
    *,
    requested_mode: str = "auto",
    automation: bool = False,
    periodic_review: bool = False,
    fresh_instantiation: bool = False,
    full_bootstrap: bool = False,
    expected_branch: str | None = None,
    git_state: GitState | None = None,
    user_override: str | None = None,
) -> StartupResolution:
    """Resolve the startup state for a repo.

    ``user_override`` implements the three manual controls from the startup panel:

    * ``"full_bootstrap"``  — force the full-bootstrap mode regardless of what
      would have been auto-detected.
    * ``"compact_only"``    — force the compact returning-session route,
      skipping heavier governance files even if another mode would normally apply.
    * ``"skip_manifest"``   — bypass ``agent-bootstrap.toml`` entirely; fall back
      to AGENTS.md → README.md and emit a ``manifest_skipped`` warning.
    """
    # --- handle the skip-manifest override before touching the manifest ---
    if user_override == "skip_manifest":
        return _resolve_skip_manifest(
            repo_root,
            expected_branch=expected_branch,
            git_state=git_state,
        )

    # --- translate the other two user overrides into detect_mode inputs ---
    active_override: str | None = user_override
    if user_override == "full_bootstrap":
        full_bootstrap = True
        mode_source = "user_override"
    elif user_override == "compact_only":
        requested_mode = "returning"
        mode_source = "user_override"

    manifest = read_manifest(repo_root)
    if user_override == "full_bootstrap":
        mode = "full_bootstrap"
    elif user_override == "compact_only":
        mode = "returning"
    else:
        mode, mode_source = detect_mode(
            repo_root,
            manifest,
            requested_mode=requested_mode,
            automation=automation,
            periodic_review=periodic_review,
            fresh_instantiation=fresh_instantiation,
            full_bootstrap=full_bootstrap,
        )

    if mode not in EXPECTED_MODES:
        raise ValueError(f"Unsupported mode {mode!r}")

    mode_config = manifest["modes"][mode]
    host_repo_root = resolve_host_repo_root(repo_root, manifest)
    current_git_state = git_state or detect_git_state(repo_root, expected_branch=expected_branch)
    host_git_state = None
    if host_repo_root is not None:
        host_git_state = detect_git_state(host_repo_root)
    trace, budget = resolve_trace(
        repo_root,
        list(mode_config["steps"]),
        token_budget=int(mode_config["token_budget"]),
        prefer_summaries=bool(mode_config["prefer_summaries"]),
    )
    warnings = resolve_warnings(
        current_git_state,
        manifest.get("mode_detection", {}),
        budget=budget,
        expected_branch=expected_branch,
    )
    return StartupResolution(
        router=str(manifest["router"]),
        mode=mode,
        mode_source=mode_source,
        token_budget=int(mode_config["token_budget"]),
        prefer_summaries=bool(mode_config["prefer_summaries"]),
        on_demand=[str(item) for item in mode_config.get("on_demand", [])],
        maintenance_probes=[str(item) for item in mode_config.get("maintenance_probes", [])],
        preload_access_mode="startup_trace_only",
        budget=budget,
        git_state=current_git_state,
        host_repo_root=str(host_repo_root) if host_repo_root is not None else None,
        host_git_state=host_git_state,
        warnings=warnings,
        trace=trace,
        active_override=active_override,
        startup_panel=build_startup_panel(
            router=str(manifest["router"]),
            mode=mode,
            mode_source=mode_source,
            trace=trace,
            warnings=warnings,
            budget=budget,
            active_override=active_override,
        ),
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Resolve agent-bootstrap.toml into a concrete startup trace."
    )
    parser.add_argument(
        "repo_root",
        nargs="?",
        default=".",
        help="Path to the repo root containing agent-bootstrap.toml.",
    )
    parser.add_argument(
        "--mode",
        choices=("auto", *EXPECTED_MODES),
        default="auto",
        help="Force a mode instead of auto-detecting it.",
    )
    parser.add_argument(
        "--automation",
        action="store_true",
        help="Treat the run as a scheduled or recurring automation.",
    )
    parser.add_argument(
        "--periodic-review",
        action="store_true",
        help="Treat the run as a periodic governance review.",
    )
    parser.add_argument(
        "--fresh-instantiation",
        action="store_true",
        help="Treat the run as a fresh thread on a returning repo.",
    )
    parser.add_argument(
        "--full-bootstrap",
        action="store_true",
        help="Force the full-bootstrap route without using --mode.",
    )
    parser.add_argument(
        "--expected-branch",
        help="Expected branch for worktree-drift and branch-elsewhere warnings.",
    )
    parser.add_argument(
        "--override",
        choices=("full_bootstrap", "compact_only", "skip_manifest"),
        default=None,
        help=(
            "Apply a manual user override to the startup mode selection. "
            "Corresponds to the three controls in the startup panel: "
            "'full_bootstrap' loads the complete governance stack, "
            "'compact_only' forces the compact returning-session route, "
            "'skip_manifest' bypasses agent-bootstrap.toml entirely."
        ),
    )
    parser.add_argument(
        "--indent",
        type=int,
        default=2,
        help="JSON indentation level for output.",
    )
    return parser.parse_args(argv[1:])


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv)
    repo_root = Path(args.repo_root).resolve()
    resolution = resolve_startup(
        repo_root,
        requested_mode=args.mode,
        automation=args.automation,
        periodic_review=args.periodic_review,
        fresh_instantiation=args.fresh_instantiation,
        full_bootstrap=args.full_bootstrap,
        expected_branch=args.expected_branch,
        user_override=args.override,
    )
    json.dump(asdict(resolution), sys.stdout, indent=args.indent)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
