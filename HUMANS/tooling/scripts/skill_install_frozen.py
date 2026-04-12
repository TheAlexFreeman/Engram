from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.tools.agent_memory_mcp.errors import ValidationError  # noqa: E402
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


def build_report(repo_root: Path) -> tuple[dict[str, Any], int]:
    manifest_path = repo_root / "core" / "memory" / "skills" / "SKILLS.yaml"
    lock_path = repo_root / "core" / "memory" / "skills" / "SKILLS.lock"

    if not manifest_path.is_file():
        return (
            {
                "repo_root": str(repo_root),
                "status": "error",
                "error": "Skill manifest not found: core/memory/skills/SKILLS.yaml",
                "verified": [],
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
                "verified": [],
                "failed": [],
            },
            1,
        )

    manifest = _load_yaml(manifest_path)
    lock_data = _load_yaml(lock_path)
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
                "verified": [],
                "failed": [exc.to_dict()],
            },
            1,
        )
    verified: list[dict[str, Any]] = []
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
        "failure_count": len(failed),
        "verified": verified,
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
