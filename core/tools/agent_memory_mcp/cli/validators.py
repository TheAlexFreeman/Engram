"""Structured wrappers around the legacy memory-repo validator script."""

from __future__ import annotations

import importlib.util
import re
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from types import ModuleType


@dataclass(frozen=True, slots=True)
class Finding:
    severity: str
    path: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {
            "severity": self.severity,
            "path": self.path,
            "message": self.message,
        }


def _validator_script_path() -> Path:
    return (
        Path(__file__).resolve().parents[4]
        / "HUMANS"
        / "tooling"
        / "scripts"
        / "validate_memory_repo.py"
    )


@lru_cache(maxsize=1)
def _load_validator_module() -> ModuleType:
    path = _validator_script_path()
    spec = importlib.util.spec_from_file_location("engram_cli_validate_memory_repo", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load validator module from {path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    except ModuleNotFoundError as exc:
        sys.modules.pop(spec.name, None)
        missing = exc.name or "required dependency"
        if missing in {"frontmatter", "yaml"}:
            raise RuntimeError(
                'engram validate requires the core optional dependencies. Install with: pip install -e ".[core]"'
            ) from exc
        raise
    return module


def _normalize_path(root: Path, raw_path: str) -> str:
    try:
        return Path(raw_path).resolve().relative_to(root.resolve()).as_posix()
    except Exception:
        return raw_path.replace("\\", "/")


def _message_to_finding(root: Path, severity: str, raw_message: str) -> Finding:
    prefix, separator, remainder = raw_message.partition(": ")
    if not separator:
        return Finding(severity=severity, path="", message=raw_message)

    line_match = re.match(r"^(?P<path>.+):(?P<line>\d+)$", prefix)
    if line_match is not None:
        rel_path = _normalize_path(root, line_match.group("path"))
        return Finding(
            severity=severity,
            path=f"{rel_path}:{line_match.group('line')}",
            message=remainder,
        )

    return Finding(severity=severity, path=_normalize_path(root, prefix), message=remainder)


def _dedupe(findings: list[Finding]) -> list[Finding]:
    seen: set[tuple[str, str, str]] = set()
    deduped: list[Finding] = []
    for item in findings:
        key = (item.severity, item.path, item.message)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _collect_findings(root: Path, result: object) -> list[Finding]:
    warnings = getattr(result, "warnings", []) or []
    errors = getattr(result, "errors", []) or []
    findings = [
        *[_message_to_finding(root, "warning", str(item)) for item in warnings],
        *[_message_to_finding(root, "error", str(item)) for item in errors],
    ]
    return _dedupe(findings)


def check_frontmatter(root: Path) -> list[Finding]:
    validator = _load_validator_module()
    result = validator.ValidationResult()
    for path in validator.iter_content_files(root):
        validator.validate_frontmatter(path, root, result)
    return _collect_findings(root, result)


def check_access_files(root: Path) -> list[Finding]:
    validator = _load_validator_module()
    result = validator.ValidationResult()
    for path in validator.iter_access_files(root):
        validator.validate_access_file(path, root, result)
    validator.validate_access_coverage(root, result)
    return _collect_findings(root, result)


def check_summaries(root: Path) -> list[Finding]:
    validator = _load_validator_module()
    result = validator.ValidationResult()
    validator.validate_compact_startup_contract(root, result)

    projects_summary = root / "core" / "memory" / "working" / "projects" / "SUMMARY.md"
    if projects_summary.exists():
        text = validator.read_text(projects_summary, result)
        if text is not None:
            validator.validate_projects_summary_shape(projects_summary, text, root, result)

    return _collect_findings(root, result)


def check_orphans(root: Path) -> list[Finding]:
    validator = _load_validator_module()
    result = validator.ValidationResult()
    validator.validate_chat_leaf_sessions(root, result)
    return _collect_findings(root, result)


def check_links(root: Path) -> list[Finding]:
    validator = _load_validator_module()
    result = validator.ValidationResult()
    validator.validate_compact_startup_contract(root, result)
    validator.validate_agent_bootstrap_manifest(root, result)
    if not validator.is_deployed_worktree_repo(root):
        validator.validate_task_readiness_manifest(root, result)
        validator.validate_setup_entrypoints(root, result)
    validator.validate_contract_consistency(root, result)
    return _collect_findings(root, result)


def validate_repo(root: Path) -> list[Finding]:
    validator = _load_validator_module()
    result = validator.validate_repo(root)
    return _collect_findings(root, result)


__all__ = [
    "Finding",
    "check_access_files",
    "check_frontmatter",
    "check_links",
    "check_orphans",
    "check_summaries",
    "validate_repo",
]
