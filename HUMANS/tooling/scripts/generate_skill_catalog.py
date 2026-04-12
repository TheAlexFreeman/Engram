#!/usr/bin/env python3
"""Generate the skill catalog (SKILL_TREE.md) from SKILL.md frontmatter.

Scans core/memory/skills/*/SKILL.md, extracts name + description from YAML
frontmatter, and writes a compact catalog file for progressive-disclosure
tier 1 loading (~50-100 tokens per skill).

The module API (``regenerate_skill_tree_markdown``, ``write_skill_tree``,
``regenerate_skills_summary_markdown``) is shared with the agent-memory MCP
``memory_skill_sync`` tool; the CLI remains a thin wrapper.

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

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.tools.agent_memory_mcp.skill_trigger import summarize_skill_trigger  # noqa: E402

try:
    import yaml  # PyYAML
except ImportError:
    yaml = None  # type: ignore[assignment]

# Directories under core/memory/skills/ that are not standalone installable skills
# for manifest/catalog alignment (matches generate_skill_manifest.py).
SKIP_SKILL_DIR_NAMES = frozenset({"tool-registry", "eval-scenarios", "_external", "_archive"})

CURRENT_SKILLS_MARKER = "## Current skills"
SCENARIO_SUITES_MARKER = "## Scenario suites"


def default_skills_dir(repo_root: Path) -> Path:
    """Return ``core/memory/skills`` under the repository root."""
    return (repo_root / "core" / "memory" / "skills").resolve()


def skill_tree_output_path(repo_root: Path) -> Path:
    """Default path for SKILL_TREE.md."""
    return default_skills_dir(repo_root) / "SKILL_TREE.md"


def skills_summary_path(repo_root: Path) -> Path:
    """Path to skills SUMMARY.md."""
    return default_skills_dir(repo_root) / "SUMMARY.md"


def should_skip_skill_dir(dir_name: str) -> bool:
    """True if this child of skills/ is not an active catalog skill directory."""
    return dir_name.startswith("_") or dir_name in SKIP_SKILL_DIR_NAMES


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


def discover_skills(skills_dir: Path, *, log_missing_frontmatter: bool = True) -> list[dict]:
    """Find all SKILL.md files and extract catalog entries."""
    entries = []
    for skill_md in sorted(skills_dir.glob("*/SKILL.md")):
        dir_name = skill_md.parent.name
        if should_skip_skill_dir(dir_name):
            continue

        fm = parse_frontmatter(skill_md)
        if fm is None:
            if log_missing_frontmatter:
                print(f"  warning: no frontmatter in {skill_md}", file=sys.stderr)
            continue

        name = fm.get("name", dir_name)
        description = fm.get("description", "(no description)")
        trust = fm.get("trust", "unknown")
        compatibility = fm.get("compatibility", "")
        trigger_summary = summarize_skill_trigger(fm.get("trigger"))

        entries.append(
            {
                "name": name,
                "description": description,
                "trust": trust,
                "compatibility": compatibility,
                "trigger_summary": trigger_summary,
                "path": skill_md.relative_to(skills_dir).as_posix(),
            }
        )
    return entries


def iter_disk_skill_slugs(skills_dir: Path) -> list[str]:
    """Slugs with a SKILL.md under skills/, excluding tool-registry and similar."""
    slugs: list[str] = []
    if not skills_dir.is_dir():
        return slugs
    for child in sorted(skills_dir.iterdir()):
        if not child.is_dir() or should_skip_skill_dir(child.name):
            continue
        if (child / "SKILL.md").is_file():
            slugs.append(child.name)
    return slugs


def generate_catalog(entries: list[dict]) -> str:
    """Generate the SKILL_TREE.md content."""
    lines = [
        "# Skill Catalog",
        "",
        f"_Auto-generated on {date.today()} by `generate_skill_catalog.py`. Do not edit manually._",
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
        if entry.get("trigger_summary"):
            lines.append(f"**Trigger:** {entry['trigger_summary']}")
        lines.append("")
        lines.append(desc)
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(
        f"**{len(entries)} skills** indexed. "
        "Run `python HUMANS/tooling/scripts/generate_skill_catalog.py` to regenerate."
    )
    lines.append("")
    return "\n".join(lines)


def regenerate_skill_tree_markdown(
    repo_root: Path,
    *,
    log_missing_frontmatter: bool = True,
) -> str:
    """Build SKILL_TREE.md body from on-disk skills (library entry point for MCP)."""
    skills_dir = default_skills_dir(repo_root)
    entries = discover_skills(skills_dir, log_missing_frontmatter=log_missing_frontmatter)
    return generate_catalog(entries)


def write_skill_tree(
    repo_root: Path,
    *,
    output: Path | None = None,
    log_missing_frontmatter: bool = True,
) -> Path:
    """Write SKILL_TREE.md; returns the path written."""
    content = regenerate_skill_tree_markdown(
        repo_root, log_missing_frontmatter=log_missing_frontmatter
    )
    out = output or skill_tree_output_path(repo_root)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(content, encoding="utf-8")
    return out


def _collapse_description(text: object) -> str:
    if not isinstance(text, str):
        text = str(text)
    return " ".join(text.split()).strip()


def build_manifest_aligned_skill_bullets(repo_root: Path) -> list[str]:
    """Build ``## Current skills`` bullet lines from SKILLS.yaml + existing directories."""
    if yaml is None:
        raise RuntimeError("PyYAML is required to rebuild SUMMARY.md from the manifest")

    manifest_path = default_skills_dir(repo_root) / "SKILLS.yaml"
    skills_dir = default_skills_dir(repo_root)
    if not manifest_path.is_file():
        return []

    manifest_data = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    skills_block = manifest_data.get("skills", {})
    if not isinstance(skills_block, dict):
        return []

    bullets: list[str] = []
    for slug in sorted(skills_block.keys()):
        entry = skills_block[slug]
        if not isinstance(entry, dict):
            continue
        if entry.get("enabled", True) is False:
            continue
        skill_dir = skills_dir / slug
        if not (skill_dir / "SKILL.md").is_file():
            continue

        desc = _collapse_description(entry.get("description") or "")
        if not desc:
            fm = parse_frontmatter(skill_dir / "SKILL.md")
            raw = (fm or {}).get("description", slug)
            desc = _collapse_description(raw)
        bullets.append(f"- **[{slug}/]({slug}/SKILL.md)** — {desc}")

    return bullets


def splice_current_skills_section(full_text: str, bullet_lines: list[str]) -> str:
    """Replace the ``## Current skills`` section, preserving the rest of SUMMARY.md."""
    start = full_text.find(CURRENT_SKILLS_MARKER)
    end = full_text.find(SCENARIO_SUITES_MARKER)
    if start == -1 or end == -1 or end <= start:
        return full_text

    before = full_text[:start]
    after = full_text[end:]
    body = f"{CURRENT_SKILLS_MARKER}\n\n"
    if bullet_lines:
        body += "\n".join(bullet_lines) + "\n\n"
    else:
        body += "_No manifest-registered skills with on-disk SKILL.md._\n\n"
    return before + body + after


def regenerate_skills_summary_markdown(repo_root: Path) -> str | None:
    """Return full SUMMARY.md with ``## Current skills`` rebuilt; None if file missing or markers absent."""
    summary_path = skills_summary_path(repo_root)
    if not summary_path.is_file():
        return None
    text = summary_path.read_text(encoding="utf-8")
    if CURRENT_SKILLS_MARKER not in text or SCENARIO_SUITES_MARKER not in text:
        return None
    bullets = build_manifest_aligned_skill_bullets(repo_root)
    return splice_current_skills_section(text, bullets)


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
    skills_dir = default_skills_dir(repo_root)
    output = args.output or skill_tree_output_path(repo_root)

    if not skills_dir.is_dir():
        print(f"error: skills directory not found: {skills_dir}", file=sys.stderr)
        sys.exit(1)

    print(f"Scanning {skills_dir} ...")
    entries = discover_skills(skills_dir, log_missing_frontmatter=True)
    print(f"Found {len(entries)} skills")

    written = write_skill_tree(repo_root, output=output, log_missing_frontmatter=True)
    print(f"Wrote {written}")


if __name__ == "__main__":
    main()
