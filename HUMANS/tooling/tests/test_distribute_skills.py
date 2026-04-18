from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import yaml  # type: ignore[import-untyped]

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "HUMANS" / "tooling" / "scripts" / "distribute_skills.py"


def _write_yaml(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def _write_skill(repo_root: Path, slug: str) -> None:
    skill_dir = repo_root / "core" / "memory" / "skills" / slug
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "name: Script Skill\n"
        "description: Exercise the distribution CLI.\n"
        "compatibility:\n"
        "  - cursor\n"
        "  - codex\n"
        "trust: medium\n"
        "---\n\n"
        "## Usage\n\n"
        "Run the CLI.\n",
        encoding="utf-8",
    )


def _run_script(repo_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--repo-root", str(repo_root), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def test_distribute_skills_script_reports_dry_run_preview(tmp_path: Path) -> None:
    slug = "script-skill"
    _write_skill(tmp_path, slug)
    _write_yaml(
        tmp_path / "core" / "memory" / "skills" / "SKILLS.yaml",
        {
            "schema_version": 1,
            "defaults": {"targets": ["engram", "cursor"]},
            "skills": {slug: {"source": "local", "enabled": True}},
        },
    )

    result = _run_script(tmp_path)

    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["status"] == "ok"
    assert report["dry_run"] is True
    assert report["planned_count"] == 1
    assert not (tmp_path / ".cursor" / "skills" / f"{slug}.md").exists()


def test_distribute_skills_script_applies_outputs(tmp_path: Path) -> None:
    slug = "apply-skill"
    _write_skill(tmp_path, slug)
    _write_yaml(
        tmp_path / "core" / "memory" / "skills" / "SKILLS.yaml",
        {
            "schema_version": 1,
            "defaults": {"targets": ["claude", "codex"]},
            "skills": {slug: {"source": "local", "enabled": True}},
        },
    )

    result = _run_script(tmp_path, "--apply", "--force-copy")

    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["status"] == "ok"
    assert report["distributed_count"] == 2
    assert (tmp_path / ".claude" / "skills" / slug / "SKILL.md").is_file()
    assert (tmp_path / ".codex" / "skills" / slug / "metadata.json").is_file()
