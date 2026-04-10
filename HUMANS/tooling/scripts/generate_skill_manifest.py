#!/usr/bin/env python3
"""Generate SKILLS.yaml manifest and SKILLS.lock from existing skill directories.

Scans core/memory/skills/*/SKILL.md, extracts metadata from YAML frontmatter,
and generates the skill manifest and lockfile with content hashes.

Usage:
    python generate_skill_manifest.py [--repo-root PATH] [--lock] [--verify] [--frozen] [--dry-run]

Flags:
    --repo-root PATH  Repository root (default: current directory)
    --lock            Only regenerate the lockfile without updating manifest
    --verify          Check freshness of existing lockfile and exit (no write)
    --frozen          CI mode: verify lock + reject unlocked skills (exit 1 on failure)
    --dry-run         Print what would be written without writing files
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import textwrap
from datetime import datetime, timezone
from pathlib import Path

try:
    import yaml  # PyYAML
except ImportError:
    yaml = None  # type: ignore[assignment]


def parse_frontmatter(path: Path) -> dict | None:
    """Extract YAML frontmatter from a Markdown file.

    Returns the parsed dict, or None if no frontmatter found.
    Works with or without PyYAML — falls back to a minimal line parser.
    """
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    if end == -1:
        return None
    raw = text[3:end].strip()

    if yaml is not None:
        return yaml.safe_load(raw)

    # Minimal fallback: parse key: value lines (no nested structures)
    result: dict[str, str] = {}
    current_key = None
    current_value_lines: list[str] = []
    for line in raw.splitlines():
        if line and not line[0].isspace() and ":" in line:
            if current_key is not None:
                result[current_key] = " ".join(current_value_lines).strip()
            key, _, val = line.partition(":")
            current_key = key.strip()
            val = val.strip()
            if val == ">-" or val == ">":
                current_value_lines = []
            else:
                current_value_lines = [val]
        elif current_key is not None:
            current_value_lines.append(line.strip())
    if current_key is not None:
        result[current_key] = " ".join(current_value_lines).strip()
    return result


def discover_skills(skills_dir: Path) -> list[dict]:
    """Find all SKILL.md files and extract manifest entries.

    Skips directories starting with _ and special directories like
    tool-registry and eval-scenarios.
    """
    entries = []
    skip_dirs = {"_archive", "_external", "tool-registry", "eval-scenarios"}

    for skill_md in sorted(skills_dir.glob("*/SKILL.md")):
        dir_name = skill_md.parent.name
        if dir_name.startswith("_") or dir_name in skip_dirs:
            continue

        fm = parse_frontmatter(skill_md)
        if fm is None:
            print(f"  warning: no frontmatter in {skill_md}", file=sys.stderr)
            continue

        name = fm.get("name", dir_name)
        description = fm.get("description", "(no description)")
        trust = fm.get("trust", "unknown")

        entries.append(
            {
                "slug": dir_name,
                "name": name,
                "description": description,
                "trust": trust,
                "source": "local",
            }
        )
    return entries


def compute_content_hash(skill_dir: Path) -> str:
    """Compute SHA-256 content hash for a skill directory.

    Algorithm:
    1. List all files recursively, sorted lexicographically
    2. For each: SHA-256(relative_path + "\0" + file_contents)
    3. Concatenate all per-file hashes, SHA-256 the result
    """
    files = []
    for file_path in sorted(skill_dir.rglob("*")):
        if file_path.is_file():
            files.append(file_path)

    # Compute per-file hashes
    per_file_hashes = []
    for file_path in files:
        rel_path = file_path.relative_to(skill_dir)
        file_contents = file_path.read_bytes()
        path_and_content = str(rel_path).encode("utf-8") + b"\0" + file_contents
        file_hash = hashlib.sha256(path_and_content).digest()
        per_file_hashes.append(file_hash)

    # Concatenate and hash
    concatenated = b"".join(per_file_hashes)
    final_hash = hashlib.sha256(concatenated).hexdigest()
    return f"sha256:{final_hash}"


def get_dir_stats(skill_dir: Path) -> tuple[int, int]:
    """Return (file_count, total_bytes) for a directory."""
    file_count = 0
    total_bytes = 0
    for file_path in skill_dir.rglob("*"):
        if file_path.is_file():
            file_count += 1
            total_bytes += file_path.stat().st_size
    return file_count, total_bytes


def generate_manifest(entries: list[dict], skills_dir: Path) -> str:
    """Generate SKILLS.yaml content."""
    lines = [
        "# Skill Manifest — Engram vault skill dependencies",
        "# See core/governance/skill-manifest-spec.md for the full schema specification.",
        "# Schema version tracks breaking changes to this format.",
        "schema_version: 1",
        "",
        "# Default settings applied to all skills unless overridden per-entry.",
        "defaults:",
        "  deployment_mode: checked        # checked | gitignored",
        "  targets: [engram]               # distribution targets",
        "",
        "# Skill declarations. Each key is the skill slug (kebab-case, matches directory name).",
        "skills:",
        "",
    ]

    # Group skills by trust level for readability
    by_trust: dict[str, list[dict]] = {}
    for entry in entries:
        trust = entry["trust"]
        if trust not in by_trust:
            by_trust[trust] = []
        by_trust[trust].append(entry)

    # Output in trust order: high, medium, low, unknown
    trust_order = ["high", "medium", "low", "unknown"]
    for trust in trust_order:
        if trust not in by_trust:
            continue
        skills = by_trust[trust]
        if trust == by_trust.get(trust_order[0]):
            # First group, add header comment
            lines.append(f"  # --- Skills (trust: {trust}) ---")
        else:
            lines.append("")
            lines.append(f"  # --- Skills (trust: {trust}) ---")
        lines.append("")

        for entry in skills:
            slug = entry["slug"]
            description = entry["description"]
            lines.append(f"  {slug}:")
            lines.append(f"    source: {entry['source']}")
            lines.append(f"    trust: {entry['trust']}")
            lines.append("    description: >-")
            # Indent description lines
            for desc_line in textwrap.wrap(description, width=70):
                lines.append(f"      {desc_line}")
            lines.append("")

    return "\n".join(lines)


def generate_lock(entries: list[dict], skills_dir: Path) -> str:
    """Generate SKILLS.lock content."""
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")

    lines = [
        "# Auto-generated by Engram skill resolver. Do not edit manually.",
        "# Regenerate with: memory_skill_sync or generate_skill_manifest.py --lock",
        "lock_version: 1",
        f'locked_at: "{timestamp}"',
        "",
        "entries:",
        "",
    ]

    for entry in entries:
        slug = entry["slug"]
        skill_dir = skills_dir / slug
        content_hash = compute_content_hash(skill_dir)
        file_count, total_bytes = get_dir_stats(skill_dir)

        lines.append(f"  {slug}:")
        lines.append(f"    source: {entry['source']}")
        lines.append(f"    resolved_path: core/memory/skills/{slug}/")
        lines.append(f'    content_hash: "{content_hash}"')
        lines.append(f'    locked_at: "{timestamp}"')
        lines.append(f"    file_count: {file_count}")
        lines.append(f"    total_bytes: {total_bytes}")
        lines.append("")

    return "\n".join(lines)


def verify_lock(lock_path: Path, skills_dir: Path, frozen: bool = False) -> bool:
    """Verify freshness of existing lockfile.

    Returns True if all hashes match, False otherwise.
    When frozen=True, also rejects skills found on disk but missing from the
    lockfile (CI reproducibility mode per skill-manifest-spec.md).
    """
    if not lock_path.exists():
        print(f"error: lockfile not found: {lock_path}", file=sys.stderr)
        return False

    try:
        if yaml is not None:
            lock_data = yaml.safe_load(lock_path.read_text(encoding="utf-8"))
        else:
            print("error: PyYAML required for --verify/--frozen", file=sys.stderr)
            return False
    except Exception as e:
        print(f"error: failed to parse lockfile: {e}", file=sys.stderr)
        return False

    entries = lock_data.get("entries", {})
    all_fresh = True

    for slug, entry in sorted(entries.items()):
        skill_dir = skills_dir / slug
        if not skill_dir.is_dir():
            print(f"MISSING: {slug} — lock entry exists but directory not found", file=sys.stderr)
            all_fresh = False
            continue

        expected_hash = entry.get("content_hash", "")
        actual_hash = compute_content_hash(skill_dir)

        if expected_hash != actual_hash:
            print(f"STALE: {slug}", file=sys.stderr)
            print(f"  expected: {expected_hash}", file=sys.stderr)
            print(f"  actual:   {actual_hash}", file=sys.stderr)
            all_fresh = False
        else:
            print(f"  OK: {slug}")

    # In frozen mode, check for skills on disk not present in the lockfile
    if frozen:
        for skill_md in sorted(skills_dir.glob("*/SKILL.md")):
            dir_name = skill_md.parent.name
            if dir_name.startswith("_") or dir_name in {"tool-registry", "eval-scenarios"}:
                continue
            if dir_name not in entries:
                print(
                    f"UNLOCKED: {dir_name} — present on disk but not in lockfile", file=sys.stderr
                )
                all_fresh = False

    return all_fresh


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate SKILLS.yaml manifest and SKILLS.lock from skill directories"
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path("."),
        help="Repository root (default: current directory)",
    )
    parser.add_argument(
        "--lock",
        action="store_true",
        help="Only regenerate lockfile (skip manifest)",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify lockfile freshness and exit (no write)",
    )
    parser.add_argument(
        "--frozen",
        action="store_true",
        help="CI mode: verify lock integrity + reject unlocked skills (exit 1 on failure)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be written without writing",
    )
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    skills_dir = repo_root / "core" / "memory" / "skills"
    manifest_path = skills_dir / "SKILLS.yaml"
    lock_path = skills_dir / "SKILLS.lock"

    if not skills_dir.is_dir():
        print(f"error: skills directory not found: {skills_dir}", file=sys.stderr)
        sys.exit(1)

    # --verify / --frozen mode
    if args.verify or args.frozen:
        mode = "frozen" if args.frozen else "verify"
        print(f"Verifying {lock_path} (mode: {mode}) ...")
        if verify_lock(lock_path, skills_dir, frozen=args.frozen):
            print("All locks verified.")
            sys.exit(0)
        else:
            print("Verification FAILED. Run with --lock to refresh.", file=sys.stderr)
            sys.exit(1)

    # Normal discovery
    print(f"Scanning {skills_dir} ...")
    entries = discover_skills(skills_dir)
    print(f"Found {len(entries)} skills: {', '.join(e['slug'] for e in entries)}")

    # Generate manifest (unless --lock specified)
    if not args.lock:
        print("Generating manifest...")
        manifest_content = generate_manifest(entries, skills_dir)
        if args.dry_run:
            print(f"\n--- {manifest_path} ---")
            print(manifest_content)
        else:
            manifest_path.write_text(manifest_content, encoding="utf-8")
            print(f"Wrote {manifest_path}")

    # Generate lock
    print("Generating lockfile...")
    lock_content = generate_lock(entries, skills_dir)
    if args.dry_run:
        print(f"\n--- {lock_path} ---")
        print(lock_content)
    else:
        lock_path.write_text(lock_content, encoding="utf-8")
        print(f"Wrote {lock_path}")

    # Summary
    if not args.dry_run:
        print(f"\nSummary: {len(entries)} skills indexed and locked")


if __name__ == "__main__":
    main()
