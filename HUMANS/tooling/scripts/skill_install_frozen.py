from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.tools.agent_memory_mcp.errors import ValidationError  # noqa: E402
from core.tools.agent_memory_mcp.skill_gitignore import resolve_skill_deployment_mode  # noqa: E402
from core.tools.agent_memory_mcp.skill_hash import compute_content_hash  # noqa: E402
from core.tools.agent_memory_mcp.skill_resolver import (  # noqa: E402
    SkillResolutionError,
    SkillResolver,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify that all enabled skills can be resolved in frozen mode."
    )
    parser.add_argument(
        "--repo-root",
        default=str(REPO_ROOT),
        help="Path to the target Engram repository root. Defaults to this checkout.",
    )
    return parser.parse_args(argv)


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    return data if isinstance(data, dict) else {}


def _materialize_gitignored_skill(
    repo_root: Path,
    resolver: SkillResolver,
    *,
    slug: str,
    entry: dict[str, Any],
    lock_entry: dict[str, Any] | None,
) -> dict[str, Any]:
    source = entry.get("source")
    if not isinstance(source, str) or not source.strip():
        raise ValidationError("enabled manifest entries must define non-empty source strings")

    if source == "local":
        raise ValidationError(
            "gitignored skills with source=local cannot be restored on a fresh clone; "
            "set deployment_mode=checked or publish the skill from a path:/git: source"
        )

    requested_ref = entry.get("ref") if isinstance(entry.get("ref"), str) else None
    if requested_ref is None and isinstance(lock_entry, dict):
        locked_requested_ref = lock_entry.get("requested_ref")
        if isinstance(locked_requested_ref, str) and locked_requested_ref:
            requested_ref = locked_requested_ref
        else:
            locked_resolved_ref = lock_entry.get("resolved_ref")
            if isinstance(locked_resolved_ref, str) and locked_resolved_ref:
                requested_ref = locked_resolved_ref

    resolved = resolver.resolve(
        source,
        slug=slug,
        ref=requested_ref,
        lock_entry=lock_entry if isinstance(lock_entry, dict) else None,
        frozen=False,
    )
    verification = resolved.lock_verification
    if verification is not None and not verification.usable:
        raise SkillResolutionError(
            source,
            "resolved content did not match the locked deployment state",
            [
                "Refresh SKILLS.lock with a non-frozen sync or install.",
                "Check that the source, ref, and content hash still match the manifest.",
            ],
        )

    target_dir = repo_root / "core" / "memory" / "skills" / slug
    target_dir.parent.mkdir(parents=True, exist_ok=True)
    if target_dir.exists():
        raise ValidationError(f"refusing to overwrite existing skill directory: {target_dir}")

    shutil.copytree(
        resolved.skill_dir,
        target_dir,
        dirs_exist_ok=False,
        ignore=shutil.ignore_patterns(".git", ".svn", ".hg"),
    )

    installed_hash = compute_content_hash(target_dir)
    if (
        verification is not None
        and verification.expected_hash
        and installed_hash != verification.expected_hash
    ):
        raise SkillResolutionError(
            source,
            "materialized skill hash did not match the lock entry after copy",
            [
                "Remove the partially installed directory and rerun the installer.",
                "Refresh SKILLS.lock if the source has legitimately changed.",
            ],
        )

    return {
        "slug": slug,
        "source": resolved.normalized_source,
        "requested_ref": resolved.requested_ref,
        "resolved_ref": resolved.resolved_ref,
        "content_hash": installed_hash,
        "resolution_mode": resolved.resolution_mode,
        "materialized_path": str(target_dir),
    }


def build_report(repo_root: Path) -> tuple[dict[str, Any], int]:
    manifest_path = repo_root / "core" / "memory" / "skills" / "SKILLS.yaml"
    lock_path = repo_root / "core" / "memory" / "skills" / "SKILLS.lock"

    if not manifest_path.is_file():
        return (
            {
                "repo_root": str(repo_root),
                "status": "error",
                "error": "Skill manifest not found: core/memory/skills/SKILLS.yaml",
                "installed_count": 0,
                "verified": [],
                "installed": [],
                "failed": [],
            },
            1,
        )
    if not lock_path.is_file():
        return (
            {
                "repo_root": str(repo_root),
                "status": "error",
                "error": "Skill lockfile not found: core/memory/skills/SKILLS.lock",
                "installed_count": 0,
                "verified": [],
                "installed": [],
                "failed": [],
            },
            1,
        )

    manifest = _load_yaml(manifest_path)
    lock_data = _load_yaml(lock_path)
    defaults_raw = manifest.get("defaults") or {}
    manifest_defaults = defaults_raw if isinstance(defaults_raw, dict) else {}
    skills_raw = manifest.get("skills") or {}
    skills = skills_raw if isinstance(skills_raw, dict) else {}
    lock_entries_raw = lock_data.get("entries") or {}
    lock_entries = lock_entries_raw if isinstance(lock_entries_raw, dict) else {}

    try:
        resolver = SkillResolver(repo_root)
    except SkillResolutionError as exc:
        return (
            {
                "repo_root": str(repo_root),
                "status": "error",
                "error": exc.reason,
                "installed_count": 0,
                "verified": [],
                "installed": [],
                "failed": [exc.to_dict()],
            },
            1,
        )
    verified: list[dict[str, Any]] = []
    installed: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []

    for slug, entry in sorted(skills.items()):
        if not isinstance(entry, dict):
            failed.append(
                {
                    "slug": slug,
                    "source": None,
                    "reason": "manifest entry must be a mapping",
                }
            )
            continue
        if entry.get("enabled", True) is False:
            continue

        source = entry.get("source")
        if not isinstance(source, str) or not source.strip():
            failed.append(
                {
                    "slug": slug,
                    "source": source,
                    "reason": "enabled manifest entries must define non-empty source strings",
                }
            )
            continue
        ref = entry.get("ref") if isinstance(entry.get("ref"), str) else None
        lock_entry = lock_entries.get(slug)
        try:
            effective_deployment_mode = resolve_skill_deployment_mode(entry, manifest_defaults)
        except ValidationError as exc:
            failed.append(
                {
                    "slug": slug,
                    "source": source,
                    "reason": str(exc),
                }
            )
            continue
        canonical_skill_dir = repo_root / "core" / "memory" / "skills" / slug

        if effective_deployment_mode == "gitignored" and not canonical_skill_dir.is_dir():
            try:
                installed_entry = _materialize_gitignored_skill(
                    repo_root,
                    resolver,
                    slug=slug,
                    entry=entry,
                    lock_entry=lock_entry if isinstance(lock_entry, dict) else None,
                )
            except SkillResolutionError as exc:
                failure = exc.to_dict()
                failure["slug"] = slug
                failure["effective_deployment_mode"] = effective_deployment_mode
                if isinstance(lock_entry, dict):
                    failure["expected_hash"] = lock_entry.get("content_hash")
                    failure["expected_ref"] = lock_entry.get("resolved_ref")
                    failure["expected_requested_ref"] = lock_entry.get("requested_ref")
                failed.append(failure)
                continue
            except ValidationError as exc:
                failed.append(
                    {
                        "slug": slug,
                        "source": source,
                        "effective_deployment_mode": effective_deployment_mode,
                        "reason": str(exc),
                    }
                )
                continue
            installed.append(installed_entry)

        if (
            effective_deployment_mode == "checked"
            and source == "local"
            and not canonical_skill_dir.is_dir()
        ):
            failed.append(
                {
                    "slug": slug,
                    "source": source,
                    "effective_deployment_mode": effective_deployment_mode,
                    "reason": "checked skill is missing locally; checked skills must be present immediately after clone",
                }
            )
            continue

        try:
            resolved = resolver.resolve(
                source,
                slug=slug,
                ref=ref,
                lock_entry=lock_entry if isinstance(lock_entry, dict) else None,
                frozen=True,
            )
        except SkillResolutionError as exc:
            failure = exc.to_dict()
            failure["slug"] = slug
            if isinstance(lock_entry, dict):
                failure["expected_hash"] = lock_entry.get("content_hash")
                failure["expected_ref"] = lock_entry.get("resolved_ref")
                failure["expected_requested_ref"] = lock_entry.get("requested_ref")
            failed.append(failure)
            continue
        except ValidationError as exc:
            failed.append(
                {
                    "slug": slug,
                    "source": source,
                    "reason": str(exc),
                }
            )
            continue

        verified.append(
            {
                "slug": slug,
                "source": resolved.normalized_source,
                "effective_deployment_mode": effective_deployment_mode,
                "requested_ref": resolved.requested_ref,
                "resolved_ref": resolved.resolved_ref,
                "content_hash": resolved.content_hash,
                "resolution_mode": resolved.resolution_mode,
            }
        )

    report = {
        "repo_root": str(repo_root),
        "status": "ok" if not failed else "failed",
        "verified_count": len(verified),
        "installed_count": len(installed),
        "failure_count": len(failed),
        "verified": verified,
        "installed": installed,
        "failed": failed,
    }
    return report, 0 if not failed else 1


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    repo_root = Path(args.repo_root).resolve()
    report, code = build_report(repo_root)
    print(json.dumps(report, indent=2))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
