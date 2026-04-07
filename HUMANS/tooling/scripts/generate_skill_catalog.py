#!/usr/bin/env python3
"""Generate the skill catalog (SKILL_TREE.md) from SKILL.md frontmatter.

Scans core/memory/skills/*/SKILL.md, extracts name + description from YAML
frontmatter, and writes a compact catalog file for progressive-disclosure
tier 1 loading (~50-100 tokens per skill).

Usage:
    python generate_skill_catalog.py [--repo-root PATH] [--output PATH]

Defaults:
    --repo-root  .  (current directory, expects core/memory/skills/ beneath it)
    --output     core/memory/skills/SKILL_TREE.md
"""

from __future__ import annotations

import argparse
import sys
import textwrap
from datetime import date
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
    """Find all SKILL.md files and extract catalog entries."""
    entries = []
    for skill_md in sorted(skills_dir.glob("*/SKILL.md")):
        # Skip _archive and _external directories
        dir_name = skill_md.parent.name
        if dir_name.startswith("_"):
            continue

        fm = parse_frontmatter(skill_md)
        if fm is None:
            print(f"  warning: no frontmatter in {skill_md}", file=sys.stderr)
            continue

        name = fm.get("name", dir_name)
        description = fm.get("description", "(no description)")
        trust = fm.get("trust", "unknown")
        compatibility = fm.get("compatibility", "")

        entries.append({
            "name": name,
            "description": description,
            "trust": trust,
            "compatibility": compatibility,
            "path": str(skill_md.relative_to(skills_dir)),
        })
    return entries


def generate_catalog(entries: list[dict]) -> str:
    """Generate the SKILL_TREE.md content."""
    lines = [
        "# Skill Catalog",
        "",
        f"_Auto-generated on {date.today()} by `generate_skill_catalog.py`. "
        "Do not edit manually._",
        "",
        "This file is the **tier-1 progressive disclosure surface** — loaded at "
        "session start to route skill activation. Each entry is ~50–100 tokens. "
        "Full skill instructions are in each directory's `SKILL.md`.",
        "",
    ]

    if not entries:
        lines.append("_No skills found._")
        return "\n".join(lines)

    for entry in entries:
        desc = entry["description"]
        # Wrap long descriptions for readability
        if len(desc) > 120:
            desc = textwrap.fill(desc, width=100, subsequent_indent="  ")
        lines.append(f"## {entry['name']}")
        lines.append("")
        lines.append(f"**Path:** `{entry['path']}`")
        if entry["trust"] != "unknown":
            lines.append(f"**Trust:** {entry['trust']}")
        if entry["compatibility"]:
            lines.append(f"**Requires:** {entry['compatibility']}")
        lines.append("")
        lines.append(desc)
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(f"**{len(entries)} skills** indexed. "
                 "Run `python HUMANS/tooling/scripts/generate_skill_catalog.py` to regenerate.")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate skill catalog")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path("."),
        help="Repository root (default: current directory)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output path (default: core/memory/skills/SKILL_TREE.md)",
    )
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    skills_dir = repo_root / "core" / "memory" / "skills"
    output = args.output or (skills_dir / "SKILL_TREE.md")

    if not skills_dir.is_dir():
        print(f"error: skills directory not found: {skills_dir}", file=sys.stderr)
        sys.exit(1)

    print(f"Scanning {skills_dir} ...")
    entries = discover_skills(skills_dir)
    print(f"Found {len(entries)} skills")

    catalog = generate_catalog(entries)
    output.write_text(catalog, encoding="utf-8")
    print(f"Wrote {output}")


if __name__ == "__main__":
    main()
