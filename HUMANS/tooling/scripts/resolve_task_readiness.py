#!/usr/bin/env python3
"""Resolve the task-readiness manifest against the current workspace/runtime."""

from __future__ import annotations

import argparse
import importlib
import json
import socket
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import ModuleType
from typing import Any, Callable
from urllib.parse import urlparse

try:
    tomllib: ModuleType = importlib.import_module("tomllib")
except ModuleNotFoundError:  # pragma: no cover - Python < 3.11 fallback
    tomllib = importlib.import_module("tomli")


MANIFEST_PATH = Path("HUMANS/tooling/agent-task-readiness.toml")
EXPECTED_PROFILES = (
    "workspace_general",
    "pull_request",
    "publish_branch",
    "terminal_plan_authoring",
    "python_validation",
    "python_dependency_install",
    "node_validation",
    "node_dependency_install",
)
EXPECTED_CHECKS = (
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
REQUIRED_PROFILE_KEYS = (
    "title",
    "description",
    "keywords",
    "checks",
    "final_gate_checks",
    "fallback_message",
    "blocked_reason",
    "success_message",
)
REQUIRED_CHECK_KEYS = (
    "title",
    "category",
    "failure_modes",
    "retry_action",
    "fallback_paths",
)
REQUIRED_STATUS_LABELS = ("ready", "attention", "blocked", "manifest_only")
ALLOWED_CHECK_CATEGORIES = {"github", "connectivity", "runtime", "tooling"}
ALLOWED_FAILURE_MODES = {
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
BLOCKER_PRIORITY = {
    "repo_state": 0,
    "config": 1,
    "auth": 2,
    "policy": 3,
    "connectivity": 4,
    "runtime": 5,
    "missing": 6,
    "missing_remote": 7,
    "unknown": 8,
}
VALIDATION_KEYWORDS = ("validate", "validation", "test", "tests", "lint")
INSTALL_KEYWORDS = ("install", "dependency", "dependencies", "package")
REMOTE_POLICY_PATTERNS = (
    "administratively prohibited",
    "pre-receive hook declined",
    "protected branch hook declined",
    "blocked by policy",
)
REMOTE_CONNECTIVITY_PATTERNS = (
    "could not resolve host",
    "could not resolve hostname",
    "connection timed out",
    "failed to connect",
    "network is unreachable",
    "temporary failure in name resolution",
    "operation timed out",
    "unable to access",
    "proxyconnect tcp",
    "tls handshake timeout",
)
REMOTE_AUTH_PATTERNS = (
    "authentication failed",
    "not logged into any github hosts",
    "permission to",
    "repository not found",
    "could not read username",
    "access denied",
    "denied to",
)
REMOTE_CONFIG_PATTERNS = (
    "no such remote",
    "does not appear to be a git repository",
    "not a git repository",
)
GH_CONFIG_PATTERNS = (
    "permission denied",
    "access is denied",
    "failed to read config",
    "config.yml",
)
GH_AUTH_PATTERNS = (
    "not logged into",
    "authentication failed",
    "try authenticating",
    "run: gh auth login",
)
DEFAULT_TIMEOUT_SEC = 5


class CommandProbeResult:
    def __init__(
        self,
        *,
        command: list[str],
        returncode: int,
        stdout: str = "",
        stderr: str = "",
        missing: bool = False,
        timed_out: bool = False,
    ) -> None:
        self.command = command
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        self.missing = missing
        self.timed_out = timed_out

    @property
    def ok(self) -> bool:
        return self.returncode == 0 and not self.missing and not self.timed_out

    @property
    def combined_output(self) -> str:
        return f"{self.stdout}\n{self.stderr}".strip()


class NetworkProbeResult:
    def __init__(
        self,
        *,
        host: str,
        port: int,
        reachable: bool,
        error: str | None = None,
        classification: str | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self.reachable = reachable
        self.error = error
        self.classification = classification


CommandRunner = Callable[[Path, list[str], int], CommandProbeResult]
NetworkRunner = Callable[[str, int, int], NetworkProbeResult]


def load_manifest(repo_root: Path) -> dict[str, Any]:
    return tomllib.loads((repo_root / MANIFEST_PATH).read_text(encoding="utf-8"))


def _ensure_string(errors: list[str], label: str, value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{MANIFEST_PATH}: {label} must be a non-empty string")
        return ""
    return value


def _ensure_bool(errors: list[str], label: str, value: Any) -> bool:
    if not isinstance(value, bool):
        errors.append(f"{MANIFEST_PATH}: {label} must be a boolean")
        return False
    return value


def _ensure_int(errors: list[str], label: str, value: Any) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        errors.append(f"{MANIFEST_PATH}: {label} must be an integer")
        return 0
    return value


def _ensure_string_list(errors: list[str], label: str, value: Any) -> list[str]:
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item.strip() for item in value
    ):
        errors.append(f"{MANIFEST_PATH}: {label} must be an array of non-empty strings")
        return []
    return value


def validate_manifest(repo_root: Path) -> tuple[dict[str, Any], list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    manifest = load_manifest(repo_root)

    if manifest.get("version") != 1:
        errors.append(f"{MANIFEST_PATH}: version must be 1")
    if manifest.get("kind") != "agent-task-readiness":
        errors.append(f"{MANIFEST_PATH}: kind must be 'agent-task-readiness'")

    resolver_entrypoint = _ensure_string(
        errors, "resolver_entrypoint", manifest.get("resolver_entrypoint")
    )
    if resolver_entrypoint and not (repo_root / resolver_entrypoint).is_file():
        errors.append(
            f"{MANIFEST_PATH}: resolver_entrypoint does not exist at {resolver_entrypoint!r}"
        )
    _ensure_string(errors, "manifest_role", manifest.get("manifest_role"))

    task_detection = manifest.get("task_detection")
    if not isinstance(task_detection, dict):
        errors.append(f"{MANIFEST_PATH}: task_detection must be a TOML table")
        task_detection = {}
    default_profile = _ensure_string(
        errors, "task_detection.default_profile", task_detection.get("default_profile")
    )
    profile_order = _ensure_string_list(
        errors, "task_detection.profile_order", task_detection.get("profile_order")
    )

    cache_policy = manifest.get("cache_policy")
    if not isinstance(cache_policy, dict):
        errors.append(f"{MANIFEST_PATH}: cache_policy must be a TOML table")
        cache_policy = {}
    _ensure_int(errors, "cache_policy.result_ttl_sec", cache_policy.get("result_ttl_sec"))
    _ensure_int(
        errors,
        "cache_policy.retry_failure_ttl_sec",
        cache_policy.get("retry_failure_ttl_sec"),
    )
    _ensure_bool(
        errors,
        "cache_policy.recheck_on_manual_retry",
        cache_policy.get("recheck_on_manual_retry"),
    )
    _ensure_bool(
        errors,
        "cache_policy.recheck_on_final_gate",
        cache_policy.get("recheck_on_final_gate"),
    )
    _ensure_bool(
        errors,
        "cache_policy.agent_refresh_allowed",
        cache_policy.get("agent_refresh_allowed"),
    )

    execution = manifest.get("execution")
    if not isinstance(execution, dict):
        errors.append(f"{MANIFEST_PATH}: execution must be a TOML table")
        execution = {}
    _ensure_bool(
        errors,
        "execution.preflight_before_substantial_work",
        execution.get("preflight_before_substantial_work"),
    )
    _ensure_bool(
        errors,
        "execution.surface_changes_since_initial_check",
        execution.get("surface_changes_since_initial_check"),
    )

    automation_integration = manifest.get("automation_integration")
    if not isinstance(automation_integration, dict):
        errors.append(f"{MANIFEST_PATH}: automation_integration must be a TOML table")
        automation_integration = {}
    _ensure_bool(
        errors,
        "automation_integration.carry_forward_blockers",
        automation_integration.get("carry_forward_blockers"),
    )
    _ensure_bool(
        errors,
        "automation_integration.skip_unchanged_publish_attempts",
        automation_integration.get("skip_unchanged_publish_attempts"),
    )
    _ensure_bool(
        errors,
        "automation_integration.notify_when_restored",
        automation_integration.get("notify_when_restored"),
    )

    ui_feedback = manifest.get("ui_feedback")
    if not isinstance(ui_feedback, dict):
        errors.append(f"{MANIFEST_PATH}: ui_feedback must be a TOML table")
        ui_feedback = {}
    _ensure_string(errors, "ui_feedback.panel_title", ui_feedback.get("panel_title"))
    _ensure_string(
        errors,
        "ui_feedback.manifest_action_label",
        ui_feedback.get("manifest_action_label"),
    )
    _ensure_string(
        errors,
        "ui_feedback.manifest_action_reason",
        ui_feedback.get("manifest_action_reason"),
    )
    _ensure_bool(
        errors,
        "ui_feedback.details_when_blocked_only",
        ui_feedback.get("details_when_blocked_only"),
    )
    _ensure_bool(errors, "ui_feedback.green_summary_only", ui_feedback.get("green_summary_only"))
    status_labels = ui_feedback.get("status_labels")
    if not isinstance(status_labels, dict):
        errors.append(f"{MANIFEST_PATH}: ui_feedback.status_labels must be a TOML table")
        status_labels = {}
    for label_key in REQUIRED_STATUS_LABELS:
        _ensure_string(
            errors,
            f"ui_feedback.status_labels.{label_key}",
            status_labels.get(label_key),
        )

    profiles = manifest.get("profiles")
    if not isinstance(profiles, dict):
        errors.append(f"{MANIFEST_PATH}: profiles must be a TOML table")
        profiles = {}
    checks = manifest.get("checks")
    if not isinstance(checks, dict):
        errors.append(f"{MANIFEST_PATH}: checks must be a TOML table")
        checks = {}

    if tuple(profile_order) != (
        "pull_request",
        "publish_branch",
        "terminal_plan_authoring",
        "python_dependency_install",
        "node_dependency_install",
        "python_validation",
        "node_validation",
    ):
        errors.append(
            f"{MANIFEST_PATH}: task_detection.profile_order must match the expected task-priority sequence"
        )
    if default_profile != "workspace_general":
        errors.append(
            f"{MANIFEST_PATH}: task_detection.default_profile must be 'workspace_general'"
        )

    missing_profiles = [profile for profile in EXPECTED_PROFILES if profile not in profiles]
    if missing_profiles:
        errors.append(f"{MANIFEST_PATH}: missing required profiles: {', '.join(missing_profiles)}")
    missing_checks = [check_id for check_id in EXPECTED_CHECKS if check_id not in checks]
    if missing_checks:
        errors.append(f"{MANIFEST_PATH}: missing required checks: {', '.join(missing_checks)}")

    for profile_name in EXPECTED_PROFILES:
        profile = profiles.get(profile_name)
        if not isinstance(profile, dict):
            errors.append(f"{MANIFEST_PATH}: profiles.{profile_name} must be a TOML table")
            continue
        for key in REQUIRED_PROFILE_KEYS:
            if key in {"keywords", "checks", "final_gate_checks"}:
                _ensure_string_list(errors, f"profiles.{profile_name}.{key}", profile.get(key))
            else:
                _ensure_string(errors, f"profiles.{profile_name}.{key}", profile.get(key))
        profile_checks = _ensure_string_list(
            errors, f"profiles.{profile_name}.checks", profile.get("checks")
        )
        final_gate_checks = _ensure_string_list(
            errors,
            f"profiles.{profile_name}.final_gate_checks",
            profile.get("final_gate_checks"),
        )
        for check_id in profile_checks + final_gate_checks:
            if check_id not in checks:
                errors.append(
                    f"{MANIFEST_PATH}: profiles.{profile_name} references unknown check {check_id!r}"
                )

    for check_id in EXPECTED_CHECKS:
        check_definition = checks.get(check_id)
        if not isinstance(check_definition, dict):
            errors.append(f"{MANIFEST_PATH}: checks.{check_id} must be a TOML table")
            continue
        for key in REQUIRED_CHECK_KEYS:
            if key in {"failure_modes", "fallback_paths"}:
                _ensure_string_list(errors, f"checks.{check_id}.{key}", check_definition.get(key))
            else:
                _ensure_string(errors, f"checks.{check_id}.{key}", check_definition.get(key))
        if check_definition.get("category") not in ALLOWED_CHECK_CATEGORIES:
            errors.append(
                f"{MANIFEST_PATH}: checks.{check_id}.category must be one of {sorted(ALLOWED_CHECK_CATEGORIES)!r}"
            )
        for failure_mode in _ensure_string_list(
            errors, f"checks.{check_id}.failure_modes", check_definition.get("failure_modes")
        ):
            if failure_mode not in ALLOWED_FAILURE_MODES:
                errors.append(
                    f"{MANIFEST_PATH}: checks.{check_id}.failure_modes contains unknown mode {failure_mode!r}"
                )

    unknown_profiles = sorted(set(profiles) - set(EXPECTED_PROFILES))
    if unknown_profiles:
        warnings.append(
            f"{MANIFEST_PATH}: additional profiles declared but not covered by the canonical test matrix: {unknown_profiles!r}"
        )
    unknown_checks = sorted(set(checks) - set(EXPECTED_CHECKS))
    if unknown_checks:
        warnings.append(
            f"{MANIFEST_PATH}: additional checks declared but not covered by the canonical test matrix: {unknown_checks!r}"
        )

    return manifest, errors, warnings


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def isoformat(value: datetime) -> str:
    return value.replace(microsecond=0).isoformat()


def execute_command(
    repo_root: Path,
    command: list[str],
    *,
    timeout_sec: int = DEFAULT_TIMEOUT_SEC,
    command_runner: CommandRunner | None = None,
) -> CommandProbeResult:
    if command_runner is not None:
        return command_runner(repo_root, command, timeout_sec)
    try:
        completed = subprocess.run(
            command,
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            check=False,
        )
    except FileNotFoundError:
        return CommandProbeResult(command=command, returncode=127, missing=True)
    except subprocess.TimeoutExpired:
        return CommandProbeResult(
            command=command,
            returncode=124,
            timed_out=True,
            stderr=f"Timed out after {timeout_sec} seconds.",
        )

    return CommandProbeResult(
        command=command,
        returncode=completed.returncode,
        stdout=completed.stdout.strip(),
        stderr=completed.stderr.strip(),
    )


def execute_network_probe(
    host: str,
    port: int,
    *,
    timeout_sec: int = DEFAULT_TIMEOUT_SEC,
    network_runner: NetworkRunner | None = None,
) -> NetworkProbeResult:
    if network_runner is not None:
        return network_runner(host, port, timeout_sec)
    try:
        with socket.create_connection((host, port), timeout=timeout_sec):
            return NetworkProbeResult(host=host, port=port, reachable=True)
    except socket.gaierror as exc:
        return NetworkProbeResult(
            host=host,
            port=port,
            reachable=False,
            error=str(exc),
            classification="connectivity",
        )
    except TimeoutError as exc:
        return NetworkProbeResult(
            host=host,
            port=port,
            reachable=False,
            error=str(exc),
            classification="connectivity",
        )
    except OSError as exc:
        message = str(exc).lower()
        classification = "policy" if "permission" in message else "connectivity"
        return NetworkProbeResult(
            host=host,
            port=port,
            reachable=False,
            error=str(exc),
            classification=classification,
        )


def parse_remote_host(remote_url: str | None) -> str | None:
    if not remote_url:
        return None
    if remote_url.startswith("git@"):
        host_part = remote_url.split("@", 1)[1]
        return host_part.split(":", 1)[0]
    if remote_url.startswith("ssh://"):
        return urlparse(remote_url).hostname
    if "://" in remote_url:
        return urlparse(remote_url).hostname
    if ":" in remote_url and "@" in remote_url.split(":", 1)[0]:
        host_part = remote_url.split("@", 1)[1]
        return host_part.split(":", 1)[0]
    return None


def detect_python_command(repo_root: Path) -> str:
    for candidate in (
        repo_root / ".venv" / "Scripts" / "python.exe",
        repo_root / ".venv" / "bin" / "python",
    ):
        if candidate.is_file():
            return str(candidate)
    return "python"


def detect_repo_hints(
    repo_root: Path,
    *,
    include_runtime: bool,
    command_runner: CommandRunner | None = None,
) -> dict[str, Any]:
    workflow_path = repo_root / ".github" / "workflows" / "ci.yml"
    workflow_text = workflow_path.read_text(encoding="utf-8") if workflow_path.is_file() else ""

    python_command = detect_python_command(repo_root)
    validation_modules: list[str] = []
    if "pytest" in workflow_text:
        validation_modules.append("pytest")
    if "ruff" in workflow_text:
        validation_modules.append("ruff")

    has_python = bool(validation_modules) or (repo_root / ".venv").exists()
    has_node = any(
        (repo_root / name).exists()
        for name in ("package.json", "package-lock.json", "pnpm-lock.yaml", "yarn.lock")
    )

    remote_url: str | None = None
    current_branch: str | None = None
    if include_runtime:
        remote_result = execute_command(
            repo_root,
            ["git", "remote", "get-url", "origin"],
            command_runner=command_runner,
        )
        if remote_result.ok and remote_result.stdout:
            remote_url = remote_result.stdout.strip()

        branch_result = execute_command(
            repo_root,
            ["git", "branch", "--show-current"],
            command_runner=command_runner,
        )
        if branch_result.ok:
            current_branch = branch_result.stdout.strip() or None

    return {
        "python": has_python,
        "node": has_node,
        "validation_modules": validation_modules,
        "python_command": python_command,
        "remote_url": remote_url,
        "remote_host": parse_remote_host(remote_url),
        "current_branch": current_branch,
        "uses_github_actions": workflow_path.is_file(),
    }


def infer_profile(
    manifest: dict[str, Any],
    repo_hints: dict[str, Any],
    *,
    task_text: str | None = None,
    requested_profile: str | None = None,
) -> tuple[str, str]:
    profiles = manifest.get("profiles")
    if not isinstance(profiles, dict):
        profiles = {}
    task_detection = manifest.get("task_detection")
    if not isinstance(task_detection, dict):
        task_detection = {}
    default_profile = task_detection.get("default_profile", "workspace_general")
    profile_order = [
        profile_name
        for profile_name in task_detection.get("profile_order", [])
        if isinstance(profile_name, str) and profile_name in profiles
    ]

    if requested_profile:
        if requested_profile not in profiles:
            raise ValueError(f"Unknown task profile: {requested_profile}")
        return requested_profile, "explicit"

    normalized_task = (task_text or "").strip().lower()
    if normalized_task:
        if any(keyword in normalized_task for keyword in INSTALL_KEYWORDS):
            if repo_hints["python"] and not repo_hints["node"]:
                return "python_dependency_install", "repo_inferred"
            if repo_hints["node"] and not repo_hints["python"]:
                return "node_dependency_install", "repo_inferred"
        if any(keyword in normalized_task for keyword in VALIDATION_KEYWORDS):
            if repo_hints["python"] and not repo_hints["node"]:
                return "python_validation", "repo_inferred"
            if repo_hints["node"] and not repo_hints["python"]:
                return "node_validation", "repo_inferred"

        for profile_name in profile_order:
            profile = profiles.get(profile_name)
            if not isinstance(profile, dict):
                continue
            keywords = [
                keyword.lower()
                for keyword in profile.get("keywords", [])
                if isinstance(keyword, str)
            ]
            if any(keyword in normalized_task for keyword in keywords):
                return profile_name, "keyword_match"

    if default_profile in profiles:
        return default_profile, "default"
    if "workspace_general" in profiles:
        return "workspace_general", "default"
    if profiles:
        return next(iter(profiles)), "default"
    return "workspace_general", "default"


def classify_remote_failure(message: str) -> str:
    lowered = message.lower()
    if any(pattern in lowered for pattern in REMOTE_POLICY_PATTERNS):
        return "policy"
    if any(pattern in lowered for pattern in REMOTE_AUTH_PATTERNS):
        return "auth"
    if any(pattern in lowered for pattern in REMOTE_CONNECTIVITY_PATTERNS):
        return "connectivity"
    if any(pattern in lowered for pattern in REMOTE_CONFIG_PATTERNS):
        return "config"
    return "unknown"


def make_check_result(
    *,
    check_id: str,
    definition: dict[str, Any],
    status: str,
    summary: str,
    checked_at: datetime,
    cache_policy: dict[str, Any],
    classification: str | None = None,
    command: list[str] | None = None,
    details: str | None = None,
    host: str | None = None,
) -> dict[str, Any]:
    ttl_seconds = (
        cache_policy["retry_failure_ttl_sec"]
        if status == "failed"
        else cache_policy["result_ttl_sec"]
    )
    return {
        "id": check_id,
        "title": definition["title"],
        "category": definition["category"],
        "status": status,
        "classification": classification,
        "summary": summary,
        "checked_at": isoformat(checked_at),
        "expires_at": isoformat(checked_at + timedelta(seconds=ttl_seconds)),
        "retry_action": definition["retry_action"],
        "fallback_paths": list(definition["fallback_paths"]),
        "command": command,
        "details": details,
        "host": host,
    }


def fail_check(
    *,
    check_id: str,
    definition: dict[str, Any],
    summary: str,
    classification: str,
    checked_at: datetime,
    cache_policy: dict[str, Any],
    command: list[str] | None = None,
    details: str | None = None,
    host: str | None = None,
) -> dict[str, Any]:
    return make_check_result(
        check_id=check_id,
        definition=definition,
        status="failed",
        summary=summary,
        classification=classification,
        checked_at=checked_at,
        cache_policy=cache_policy,
        command=command,
        details=details,
        host=host,
    )


def pass_check(
    *,
    check_id: str,
    definition: dict[str, Any],
    summary: str,
    checked_at: datetime,
    cache_policy: dict[str, Any],
    command: list[str] | None = None,
    details: str | None = None,
    host: str | None = None,
) -> dict[str, Any]:
    return make_check_result(
        check_id=check_id,
        definition=definition,
        status="passed",
        summary=summary,
        checked_at=checked_at,
        cache_policy=cache_policy,
        command=command,
        details=details,
        host=host,
    )


def resolve_git_cli(
    repo_root: Path,
    definition: dict[str, Any],
    cache_policy: dict[str, Any],
    checked_at: datetime,
    *,
    command_runner: CommandRunner | None = None,
) -> dict[str, Any]:
    command = ["git", "--version"]
    result = execute_command(repo_root, command, command_runner=command_runner)
    if result.ok:
        return pass_check(
            check_id="git_cli",
            definition=definition,
            summary=result.stdout or "git is available.",
            checked_at=checked_at,
            cache_policy=cache_policy,
            command=command,
        )
    classification = "missing" if result.missing else "runtime"
    summary = "git is unavailable." if result.missing else "git could not be executed."
    return fail_check(
        check_id="git_cli",
        definition=definition,
        summary=summary,
        classification=classification,
        checked_at=checked_at,
        cache_policy=cache_policy,
        command=command,
        details=result.combined_output or None,
    )


def resolve_git_remote(
    repo_root: Path,
    definition: dict[str, Any],
    cache_policy: dict[str, Any],
    checked_at: datetime,
    *,
    repo_hints: dict[str, Any],
    command_runner: CommandRunner | None = None,
) -> dict[str, Any]:
    remote_url = repo_hints.get("remote_url")
    if not remote_url:
        return fail_check(
            check_id="git_remote",
            definition=definition,
            summary="No origin remote is configured for this repo.",
            classification="missing_remote",
            checked_at=checked_at,
            cache_policy=cache_policy,
        )

    command = ["git", "ls-remote", "--exit-code", "origin", "HEAD"]
    result = execute_command(repo_root, command, command_runner=command_runner)
    if result.ok:
        host = repo_hints.get("remote_host") or remote_url
        return pass_check(
            check_id="git_remote",
            definition=definition,
            summary=f"Origin remote is reachable at {host}.",
            checked_at=checked_at,
            cache_policy=cache_policy,
            command=command,
            host=repo_hints.get("remote_host"),
        )

    classification = classify_remote_failure(result.combined_output)
    summary = {
        "auth": "Origin remote is reachable but authentication failed.",
        "connectivity": "Origin remote could not be reached over the network.",
        "policy": "Origin remote access appears to be blocked by policy.",
        "config": "Origin remote is misconfigured or unavailable.",
        "unknown": "Origin remote probe failed for an unknown reason.",
    }[classification]
    return fail_check(
        check_id="git_remote",
        definition=definition,
        summary=summary,
        classification=classification,
        checked_at=checked_at,
        cache_policy=cache_policy,
        command=command,
        details=result.combined_output or None,
        host=repo_hints.get("remote_host"),
    )


def resolve_git_push_dry_run(
    repo_root: Path,
    definition: dict[str, Any],
    cache_policy: dict[str, Any],
    checked_at: datetime,
    *,
    repo_hints: dict[str, Any],
    command_runner: CommandRunner | None = None,
) -> dict[str, Any]:
    if not repo_hints.get("remote_url"):
        return fail_check(
            check_id="git_push_dry_run",
            definition=definition,
            summary="Cannot probe push auth because no origin remote is configured.",
            classification="config",
            checked_at=checked_at,
            cache_policy=cache_policy,
        )

    branch = repo_hints.get("current_branch")
    if not branch:
        return fail_check(
            check_id="git_push_dry_run",
            definition=definition,
            summary="Cannot preflight push from a detached HEAD or unnamed branch state.",
            classification="repo_state",
            checked_at=checked_at,
            cache_policy=cache_policy,
        )

    command = [
        "git",
        "push",
        "--dry-run",
        "--porcelain",
        "origin",
        f"HEAD:refs/heads/{branch}",
    ]
    result = execute_command(repo_root, command, command_runner=command_runner)
    if result.ok:
        return pass_check(
            check_id="git_push_dry_run",
            definition=definition,
            summary=f"Dry-run push succeeded for branch {branch}.",
            checked_at=checked_at,
            cache_policy=cache_policy,
            command=command,
        )

    lowered = result.combined_output.lower()
    if any(pattern in lowered for pattern in REMOTE_POLICY_PATTERNS):
        classification = "policy"
    elif any(pattern in lowered for pattern in REMOTE_AUTH_PATTERNS):
        classification = "auth"
    elif any(pattern in lowered for pattern in REMOTE_CONNECTIVITY_PATTERNS):
        classification = "connectivity"
    elif "detached head" in lowered or "src refspec" in lowered or "non-fast-forward" in lowered:
        classification = "repo_state"
    else:
        classification = "config"

    summary = {
        "auth": "Dry-run push reached the remote but authentication failed.",
        "connectivity": "Dry-run push could not reach the remote over the network.",
        "policy": "Dry-run push was rejected by remote policy.",
        "repo_state": "Dry-run push is blocked by the current repo state.",
        "config": "Dry-run push failed because the remote or push target is misconfigured.",
    }[classification]
    return fail_check(
        check_id="git_push_dry_run",
        definition=definition,
        summary=summary,
        classification=classification,
        checked_at=checked_at,
        cache_policy=cache_policy,
        command=command,
        details=result.combined_output or None,
    )


def resolve_gh_auth(
    repo_root: Path,
    definition: dict[str, Any],
    cache_policy: dict[str, Any],
    checked_at: datetime,
    *,
    command_runner: CommandRunner | None = None,
) -> dict[str, Any]:
    command = ["gh", "auth", "status"]
    result = execute_command(repo_root, command, command_runner=command_runner)
    if result.ok:
        return pass_check(
            check_id="gh_auth",
            definition=definition,
            summary="gh auth is ready.",
            checked_at=checked_at,
            cache_policy=cache_policy,
            command=command,
        )

    lowered = result.combined_output.lower()
    if result.missing:
        classification = "missing"
        summary = "gh is not installed."
    elif any(pattern in lowered for pattern in GH_CONFIG_PATTERNS):
        classification = "config"
        summary = "gh is installed but its config is inaccessible."
    elif any(pattern in lowered for pattern in GH_AUTH_PATTERNS):
        classification = "auth"
        summary = "gh is installed but not authenticated."
    elif any(pattern in lowered for pattern in REMOTE_CONNECTIVITY_PATTERNS):
        classification = "connectivity"
        summary = "gh auth could not verify GitHub because the network probe failed."
    else:
        classification = "policy" if "forbidden" in lowered else "unknown"
        summary = "gh auth failed for an unexpected reason."

    return fail_check(
        check_id="gh_auth",
        definition=definition,
        summary=summary,
        classification=classification,
        checked_at=checked_at,
        cache_policy=cache_policy,
        command=command,
        details=result.combined_output or None,
    )


def resolve_remote_network(
    definition: dict[str, Any],
    cache_policy: dict[str, Any],
    checked_at: datetime,
    *,
    repo_hints: dict[str, Any],
    network_runner: NetworkRunner | None = None,
) -> dict[str, Any]:
    host = repo_hints.get("remote_host") or "github.com"
    probe = execute_network_probe(host, 443, network_runner=network_runner)
    if probe.reachable:
        return pass_check(
            check_id="remote_network",
            definition=definition,
            summary=f"Network probe to {host}:443 succeeded.",
            checked_at=checked_at,
            cache_policy=cache_policy,
            host=host,
        )

    classification = probe.classification or "connectivity"
    summary = (
        f"Network probe to {host}:443 was blocked by policy."
        if classification == "policy"
        else f"Network probe to {host}:443 failed."
    )
    return fail_check(
        check_id="remote_network",
        definition=definition,
        summary=summary,
        classification=classification,
        checked_at=checked_at,
        cache_policy=cache_policy,
        details=probe.error,
        host=host,
    )


def resolve_python_runtime(
    repo_root: Path,
    definition: dict[str, Any],
    cache_policy: dict[str, Any],
    checked_at: datetime,
    *,
    repo_hints: dict[str, Any],
    command_runner: CommandRunner | None = None,
) -> dict[str, Any]:
    command = [repo_hints["python_command"], "--version"]
    result = execute_command(repo_root, command, command_runner=command_runner)
    if result.ok:
        return pass_check(
            check_id="python_runtime",
            definition=definition,
            summary=f"Python runtime is available via {repo_hints['python_command']}.",
            checked_at=checked_at,
            cache_policy=cache_policy,
            command=command,
        )
    classification = "missing" if result.missing else "runtime"
    summary = (
        "Python runtime is unavailable."
        if result.missing
        else f"Python runtime at {repo_hints['python_command']} could not be executed."
    )
    return fail_check(
        check_id="python_runtime",
        definition=definition,
        summary=summary,
        classification=classification,
        checked_at=checked_at,
        cache_policy=cache_policy,
        command=command,
        details=result.combined_output or None,
    )


def resolve_python_validation_stack(
    repo_root: Path,
    definition: dict[str, Any],
    cache_policy: dict[str, Any],
    checked_at: datetime,
    *,
    repo_hints: dict[str, Any],
    command_runner: CommandRunner | None = None,
) -> dict[str, Any]:
    missing_modules: list[str] = []
    details: list[str] = []
    for module_name in repo_hints.get("validation_modules") or ["pytest", "ruff"]:
        command = [repo_hints["python_command"], "-m", module_name, "--version"]
        result = execute_command(repo_root, command, command_runner=command_runner)
        if result.ok:
            details.append(f"{module_name}: ok")
            continue
        missing_modules.append(module_name)
        details.append(result.combined_output or f"{module_name}: unavailable")

    if not missing_modules:
        return pass_check(
            check_id="python_validation_stack",
            definition=definition,
            summary="Python validation tooling is available (pytest, ruff).",
            checked_at=checked_at,
            cache_policy=cache_policy,
            details="; ".join(details),
        )
    return fail_check(
        check_id="python_validation_stack",
        definition=definition,
        summary=f"Python validation tooling is missing: {', '.join(missing_modules)}.",
        classification="missing",
        checked_at=checked_at,
        cache_policy=cache_policy,
        details="; ".join(details),
    )


def resolve_python_package_manager(
    repo_root: Path,
    definition: dict[str, Any],
    cache_policy: dict[str, Any],
    checked_at: datetime,
    *,
    repo_hints: dict[str, Any],
    command_runner: CommandRunner | None = None,
) -> dict[str, Any]:
    candidates = [
        ["uv", "--version"],
        [repo_hints["python_command"], "-m", "pip", "--version"],
    ]
    details: list[str] = []
    for command in candidates:
        result = execute_command(repo_root, command, command_runner=command_runner)
        if result.ok:
            return pass_check(
                check_id="python_package_manager",
                definition=definition,
                summary=f"Python package manager is available via {' '.join(command)}.",
                checked_at=checked_at,
                cache_policy=cache_policy,
                command=command,
            )
        details.append(result.combined_output or f"{' '.join(command)} unavailable")

    return fail_check(
        check_id="python_package_manager",
        definition=definition,
        summary="No supported Python package manager is available (uv or python -m pip).",
        classification="missing",
        checked_at=checked_at,
        cache_policy=cache_policy,
        details="; ".join(details),
    )


def resolve_python_package_network(
    definition: dict[str, Any],
    cache_policy: dict[str, Any],
    checked_at: datetime,
    *,
    network_runner: NetworkRunner | None = None,
) -> dict[str, Any]:
    host = "pypi.org"
    probe = execute_network_probe(host, 443, network_runner=network_runner)
    if probe.reachable:
        return pass_check(
            check_id="python_package_network",
            definition=definition,
            summary=f"Network probe to {host}:443 succeeded.",
            checked_at=checked_at,
            cache_policy=cache_policy,
            host=host,
        )
    return fail_check(
        check_id="python_package_network",
        definition=definition,
        summary=f"Network probe to {host}:443 failed.",
        classification=probe.classification or "connectivity",
        checked_at=checked_at,
        cache_policy=cache_policy,
        details=probe.error,
        host=host,
    )


def resolve_node_runtime(
    repo_root: Path,
    definition: dict[str, Any],
    cache_policy: dict[str, Any],
    checked_at: datetime,
    *,
    command_runner: CommandRunner | None = None,
) -> dict[str, Any]:
    command = ["node", "--version"]
    result = execute_command(repo_root, command, command_runner=command_runner)
    if result.ok:
        return pass_check(
            check_id="node_runtime",
            definition=definition,
            summary="Node runtime is available.",
            checked_at=checked_at,
            cache_policy=cache_policy,
            command=command,
        )
    return fail_check(
        check_id="node_runtime",
        definition=definition,
        summary="Node runtime is unavailable.",
        classification="missing" if result.missing else "runtime",
        checked_at=checked_at,
        cache_policy=cache_policy,
        command=command,
        details=result.combined_output or None,
    )


def resolve_node_manager_check(
    repo_root: Path,
    *,
    check_id: str,
    definition: dict[str, Any],
    cache_policy: dict[str, Any],
    checked_at: datetime,
    command_runner: CommandRunner | None = None,
) -> dict[str, Any]:
    for command in (["npm", "--version"], ["pnpm", "--version"], ["yarn", "--version"]):
        result = execute_command(repo_root, command, command_runner=command_runner)
        if result.ok:
            return pass_check(
                check_id=check_id,
                definition=definition,
                summary=f"Node tooling is available via {' '.join(command)}.",
                checked_at=checked_at,
                cache_policy=cache_policy,
                command=command,
            )
    return fail_check(
        check_id=check_id,
        definition=definition,
        summary="No supported Node package manager is available (npm, pnpm, or yarn).",
        classification="missing",
        checked_at=checked_at,
        cache_policy=cache_policy,
    )


def resolve_node_package_network(
    definition: dict[str, Any],
    cache_policy: dict[str, Any],
    checked_at: datetime,
    *,
    network_runner: NetworkRunner | None = None,
) -> dict[str, Any]:
    host = "registry.npmjs.org"
    probe = execute_network_probe(host, 443, network_runner=network_runner)
    if probe.reachable:
        return pass_check(
            check_id="node_package_network",
            definition=definition,
            summary=f"Network probe to {host}:443 succeeded.",
            checked_at=checked_at,
            cache_policy=cache_policy,
            host=host,
        )
    return fail_check(
        check_id="node_package_network",
        definition=definition,
        summary=f"Network probe to {host}:443 failed.",
        classification=probe.classification or "connectivity",
        checked_at=checked_at,
        cache_policy=cache_policy,
        details=probe.error,
        host=host,
    )


def resolve_check(
    repo_root: Path,
    *,
    check_id: str,
    definition: dict[str, Any],
    cache_policy: dict[str, Any],
    checked_at: datetime,
    repo_hints: dict[str, Any],
    command_runner: CommandRunner | None = None,
    network_runner: NetworkRunner | None = None,
) -> dict[str, Any]:
    if check_id == "git_cli":
        return resolve_git_cli(
            repo_root,
            definition,
            cache_policy,
            checked_at,
            command_runner=command_runner,
        )
    if check_id == "git_remote":
        return resolve_git_remote(
            repo_root,
            definition,
            cache_policy,
            checked_at,
            repo_hints=repo_hints,
            command_runner=command_runner,
        )
    if check_id == "git_push_dry_run":
        return resolve_git_push_dry_run(
            repo_root,
            definition,
            cache_policy,
            checked_at,
            repo_hints=repo_hints,
            command_runner=command_runner,
        )
    if check_id == "gh_auth":
        return resolve_gh_auth(
            repo_root,
            definition,
            cache_policy,
            checked_at,
            command_runner=command_runner,
        )
    if check_id == "remote_network":
        return resolve_remote_network(
            definition,
            cache_policy,
            checked_at,
            repo_hints=repo_hints,
            network_runner=network_runner,
        )
    if check_id == "python_runtime":
        return resolve_python_runtime(
            repo_root,
            definition,
            cache_policy,
            checked_at,
            repo_hints=repo_hints,
            command_runner=command_runner,
        )
    if check_id == "python_validation_stack":
        return resolve_python_validation_stack(
            repo_root,
            definition,
            cache_policy,
            checked_at,
            repo_hints=repo_hints,
            command_runner=command_runner,
        )
    if check_id == "python_package_manager":
        return resolve_python_package_manager(
            repo_root,
            definition,
            cache_policy,
            checked_at,
            repo_hints=repo_hints,
            command_runner=command_runner,
        )
    if check_id == "python_package_network":
        return resolve_python_package_network(
            definition,
            cache_policy,
            checked_at,
            network_runner=network_runner,
        )
    if check_id == "node_runtime":
        return resolve_node_runtime(
            repo_root,
            definition,
            cache_policy,
            checked_at,
            command_runner=command_runner,
        )
    if check_id in {"node_validation_stack", "node_package_manager"}:
        return resolve_node_manager_check(
            repo_root,
            check_id=check_id,
            definition=definition,
            cache_policy=cache_policy,
            checked_at=checked_at,
            command_runner=command_runner,
        )
    if check_id == "node_package_network":
        return resolve_node_package_network(
            definition,
            cache_policy,
            checked_at,
            network_runner=network_runner,
        )
    raise ValueError(f"Unsupported check id: {check_id}")


def sort_blockers(blockers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        blockers,
        key=lambda blocker: (
            BLOCKER_PRIORITY.get(str(blocker.get("classification")), 99),
            str(blocker.get("check_id")),
        ),
    )


def compare_with_previous_blockers(
    blockers: list[dict[str, Any]], previous_blockers: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    indexed_previous = {
        (str(blocker.get("check_id")), str(blocker.get("classification"))): blocker
        for blocker in previous_blockers
    }
    current_keys: set[tuple[str, str]] = set()
    for blocker in blockers:
        key = (str(blocker["check_id"]), str(blocker["classification"]))
        current_keys.add(key)
        if key in indexed_previous:
            blocker["previously_seen"] = True
            blocker["unchanged_since_previous"] = True
        else:
            blocker["previously_seen"] = False
            blocker["unchanged_since_previous"] = False

    resolved_previous = [
        blocker for key, blocker in indexed_previous.items() if key not in current_keys
    ]
    return blockers, resolved_previous


def build_blockers(
    check_results: list[dict[str, Any]], previous_blockers: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    blockers = [
        {
            "check_id": check["id"],
            "title": check["title"],
            "category": check["category"],
            "classification": check["classification"],
            "summary": check["summary"],
            "checked_at": check["checked_at"],
            "retry_action": check["retry_action"],
            "fallback_paths": check["fallback_paths"],
        }
        for check in check_results
        if check["status"] == "failed"
    ]
    blockers, resolved_previous = compare_with_previous_blockers(blockers, previous_blockers)
    return sort_blockers(blockers), resolved_previous


def build_ui_feedback(
    manifest: dict[str, Any],
    *,
    profile_name: str,
    profile_source: str,
    checked_at: datetime,
    check_results: list[dict[str, Any]],
    blockers: list[dict[str, Any]],
    resolved_previous: list[dict[str, Any]],
    include_runtime: bool,
) -> dict[str, Any]:
    ui_feedback = manifest.get("ui_feedback")
    if not isinstance(ui_feedback, dict):
        ui_feedback = {}
    status_labels = ui_feedback.get("status_labels")
    if not isinstance(status_labels, dict):
        status_labels = {}
    profiles = manifest.get("profiles")
    if not isinstance(profiles, dict):
        profiles = {}
    profile = profiles.get(profile_name)
    if not isinstance(profile, dict):
        profile = {}
    status = "manifest_only"
    reason = "Runtime probes were skipped."
    recovery_message = None

    if include_runtime:
        if blockers:
            status = "blocked"
            reason = profile["blocked_reason"]
            if any(blocker["unchanged_since_previous"] for blocker in blockers):
                recovery_message = "A previous blocker is unchanged. Skip repeated publish or install attempts until the environment changes."
        elif resolved_previous:
            status = "attention"
            reason = "A previously blocked environment probe is healthy again."
            recovery_message = "The environment improved since the last blocked run."
        else:
            status = "ready"
            reason = profile["success_message"]

    blocker_summary = blockers[0]["summary"] if blockers else None
    return {
        "title": ui_feedback.get("panel_title", "Task Readiness"),
        "status": status,
        "status_label": status_labels.get(status, status.replace("_", " ").title()),
        "profile": profile_name,
        "profile_title": profile.get("title", profile_name.replace("_", " ").title()),
        "profile_source": profile_source,
        "checked_at": isoformat(checked_at),
        "reason": reason,
        "recovery_message": recovery_message,
        "fallback_message": profile.get(
            "fallback_message",
            "Environment checks were not completed.",
        ),
        "details_default": status != "ready",
        "manifest_action": {
            "label": ui_feedback.get("manifest_action_label", "Open Manifest"),
            "path": MANIFEST_PATH.as_posix(),
            "reason": ui_feedback.get(
                "manifest_action_reason",
                "Repo-declared task-readiness contract.",
            ),
        },
        "check_count": len(check_results),
        "blocker_count": len(blockers),
        "blocker_summary": blocker_summary,
        "checks": [
            {
                "id": check["id"],
                "title": check["title"],
                "status": check["status"],
                "summary": check["summary"],
                "classification": check["classification"],
            }
            for check in check_results
        ],
    }


def resolve_task_readiness(
    repo_root: Path,
    *,
    task_text: str | None = None,
    requested_profile: str | None = None,
    include_runtime: bool = True,
    previous_blockers: list[dict[str, Any]] | None = None,
    command_runner: CommandRunner | None = None,
    network_runner: NetworkRunner | None = None,
) -> dict[str, Any]:
    manifest, errors, warnings = validate_manifest(repo_root)
    previous_blockers = previous_blockers or []
    profiles = manifest.get("profiles")
    if not isinstance(profiles, dict):
        profiles = {}
    checks = manifest.get("checks")
    if not isinstance(checks, dict):
        checks = {}
    cache_policy = manifest.get("cache_policy")
    if not isinstance(cache_policy, dict):
        cache_policy = {}
    execution = manifest.get("execution")
    if not isinstance(execution, dict):
        execution = {}
    automation_integration = manifest.get("automation_integration")
    if not isinstance(automation_integration, dict):
        automation_integration = {}

    repo_hints = detect_repo_hints(
        repo_root,
        include_runtime=include_runtime,
        command_runner=command_runner,
    )

    try:
        profile_name, profile_source = infer_profile(
            manifest,
            repo_hints,
            task_text=task_text,
            requested_profile=requested_profile,
        )
    except ValueError as exc:
        errors.append(str(exc))
        profile_name = manifest.get("task_detection", {}).get(
            "default_profile", "workspace_general"
        )
        profile_source = "fallback_after_error"

    check_results: list[dict[str, Any]] = []
    checked_at = now_utc()
    selected_profile = profiles.get(profile_name)
    if not isinstance(selected_profile, dict):
        selected_profile = {}

    if include_runtime and not errors:
        for check_id in selected_profile.get("checks", []):
            if check_id not in checks:
                continue
            check_results.append(
                resolve_check(
                    repo_root,
                    check_id=check_id,
                    definition=checks[check_id],
                    cache_policy=cache_policy,
                    checked_at=checked_at,
                    repo_hints=repo_hints,
                    command_runner=command_runner,
                    network_runner=network_runner,
                )
            )

    blockers, resolved_previous = build_blockers(check_results, previous_blockers)
    ui_feedback = build_ui_feedback(
        manifest,
        profile_name=profile_name,
        profile_source=profile_source,
        checked_at=checked_at,
        check_results=check_results,
        blockers=blockers,
        resolved_previous=resolved_previous,
        include_runtime=include_runtime and not errors,
    )

    if resolved_previous and automation_integration.get("notify_when_restored"):
        warnings.append("One or more previously carried-forward blockers are no longer active.")

    skip_unchanged_publish_attempts = (
        automation_integration.get("skip_unchanged_publish_attempts")
        and profile_name in {"pull_request", "publish_branch"}
        and any(blocker["unchanged_since_previous"] for blocker in blockers)
    )

    return {
        "manifest_path": str(repo_root / MANIFEST_PATH),
        "profile": profile_name,
        "profile_source": profile_source,
        "task_text": task_text,
        "repo_hints": repo_hints,
        "cache_policy": cache_policy,
        "execution": execution,
        "automation_integration": {
            **automation_integration,
            "skip_unchanged_publish_attempts_now": skip_unchanged_publish_attempts,
        },
        "required_checks": list(selected_profile.get("checks", [])),
        "final_gate_checks": list(selected_profile.get("final_gate_checks", [])),
        "check_results": check_results,
        "blockers": blockers,
        "resolved_previous_blockers": resolved_previous,
        "ui_feedback": ui_feedback,
        "errors": errors,
        "warnings": warnings,
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Resolve the task-readiness manifest against the current workspace/runtime."
    )
    parser.add_argument(
        "repo_root",
        nargs="?",
        default=".",
        help="Path to the repo root.",
    )
    parser.add_argument("--task", help="Task text used for profile inference.")
    parser.add_argument("--profile", help="Explicit task profile override.")
    parser.add_argument(
        "--skip-runtime",
        action="store_true",
        help="Only validate manifest structure and infer the task profile.",
    )
    parser.add_argument(
        "--previous-blockers-json",
        help="JSON array of previous blockers for carry-forward comparison.",
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
    previous_blockers: list[dict[str, Any]] = []
    if args.previous_blockers_json:
        try:
            parsed = json.loads(args.previous_blockers_json)
        except json.JSONDecodeError as exc:
            print(f"Invalid --previous-blockers-json payload: {exc}", file=sys.stderr)
            return 2
        if not isinstance(parsed, list):
            print("--previous-blockers-json must decode to a JSON array.", file=sys.stderr)
            return 2
        previous_blockers = [item for item in parsed if isinstance(item, dict)]

    resolution = resolve_task_readiness(
        repo_root,
        task_text=args.task,
        requested_profile=args.profile,
        include_runtime=not args.skip_runtime,
        previous_blockers=previous_blockers,
    )
    json.dump(resolution, sys.stdout, indent=args.indent)
    sys.stdout.write("\n")
    return 1 if resolution["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
