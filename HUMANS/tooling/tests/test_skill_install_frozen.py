from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import yaml  # type: ignore[import-untyped]

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.tools.agent_memory_mcp.skill_hash import compute_content_hash  # noqa: E402, I001


SCRIPT_PATH = REPO_ROOT / "HUMANS" / "tooling" / "scripts" / "skill_install_frozen.py"


def _init_git_repo(repo_root: Path) -> None:
    subprocess.run(
        ["git", "init", str(repo_root)],
        capture_output=True,
        text=True,
        check=True,
    )


def _write_yaml(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def _write_skill(repo_root: Path, slug: str, skill_text: str | None = None) -> str:
    skill_dir = repo_root / "core" / "memory" / "skills" / slug
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_text = skill_text or (
        "---\n"
        f"title: {slug}\n"
        "summary: Frozen install test skill\n"
        "trust: medium\n"
        "---\n\n"
        "Test body.\n"
    )
    (skill_dir / "SKILL.md").write_text(skill_text, encoding="utf-8")
    return compute_content_hash(skill_dir)


def _init_git_source_repo(root: Path, files: dict[str, str]) -> str:
    root.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True, text=True)
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    for rel_path, content in files.items():
        target = root / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=root, check=True, capture_output=True, text=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial remote skill"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _run_script(repo_root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--repo-root", str(repo_root)],
        capture_output=True,
        text=True,
        check=False,
    )


def _remove_tree(path: Path) -> None:
    def _onerror(_func: object, failed_path: str, _exc_info: object) -> None:
        os.chmod(failed_path, 0o700)
        os.unlink(failed_path)

    shutil.rmtree(path, onerror=_onerror)


def test_skill_install_frozen_verifies_enabled_skills(tmp_path: Path) -> None:
    slug = "frozen-local"
    _init_git_repo(tmp_path)
    content_hash = _write_skill(tmp_path, slug)
    _write_yaml(
        tmp_path / "core" / "memory" / "skills" / "SKILLS.yaml",
        {
            "version": 1,
            "skills": {
                slug: {
                    "enabled": True,
                    "source": "local",
                }
            },
        },
    )
    _write_yaml(
        tmp_path / "core" / "memory" / "skills" / "SKILLS.lock",
        {
            "version": 1,
            "entries": {
                slug: {
                    "source": "local",
                    "resolved_path": f"core/memory/skills/{slug}/",
                    "content_hash": content_hash,
                }
            },
        },
    )

    result = _run_script(tmp_path)

    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["status"] == "ok"
    assert report["verified_count"] == 1
    assert report["installed_count"] == 0
    assert report["failure_count"] == 0
    assert report["verified"][0]["slug"] == slug
    assert report["verified"][0]["source"] == "local"


def test_skill_install_frozen_reports_missing_manifest(tmp_path: Path) -> None:
    _init_git_repo(tmp_path)

    result = _run_script(tmp_path)

    assert result.returncode == 1
    report = json.loads(result.stdout)
    assert report["status"] == "error"
    assert report["error"] == "Skill manifest not found: core/memory/skills/SKILLS.yaml"
    assert report["verified"] == []
    assert report["installed"] == []
    assert report["failed"] == []


def test_skill_install_frozen_reports_missing_lockfile(tmp_path: Path) -> None:
    slug = "frozen-local"
    _init_git_repo(tmp_path)
    _write_skill(tmp_path, slug)
    _write_yaml(
        tmp_path / "core" / "memory" / "skills" / "SKILLS.yaml",
        {
            "version": 1,
            "skills": {
                slug: {
                    "enabled": True,
                    "source": "local",
                }
            },
        },
    )

    result = _run_script(tmp_path)

    assert result.returncode == 1
    report = json.loads(result.stdout)
    assert report["status"] == "error"
    assert report["error"] == "Skill lockfile not found: core/memory/skills/SKILLS.lock"
    assert report["verified"] == []
    assert report["installed"] == []
    assert report["failed"] == []


def test_skill_install_frozen_reports_non_mapping_manifest_entry(tmp_path: Path) -> None:
    slug = "broken-skill"
    _init_git_repo(tmp_path)
    _write_yaml(
        tmp_path / "core" / "memory" / "skills" / "SKILLS.yaml",
        {
            "version": 1,
            "skills": {
                slug: "local",
            },
        },
    )
    _write_yaml(
        tmp_path / "core" / "memory" / "skills" / "SKILLS.lock",
        {
            "version": 1,
            "entries": {},
        },
    )

    result = _run_script(tmp_path)

    assert result.returncode == 1
    report = json.loads(result.stdout)
    assert report["status"] == "failed"
    assert report["verified_count"] == 0
    assert report["installed_count"] == 0
    assert report["failure_count"] == 1
    assert report["failed"][0]["slug"] == slug
    assert report["failed"][0]["reason"] == "manifest entry must be a mapping"


def test_skill_install_frozen_reports_missing_source_for_enabled_skill(tmp_path: Path) -> None:
    slug = "missing-source"
    _init_git_repo(tmp_path)
    _write_yaml(
        tmp_path / "core" / "memory" / "skills" / "SKILLS.yaml",
        {
            "version": 1,
            "skills": {
                slug: {
                    "enabled": True,
                }
            },
        },
    )
    _write_yaml(
        tmp_path / "core" / "memory" / "skills" / "SKILLS.lock",
        {
            "version": 1,
            "entries": {},
        },
    )

    result = _run_script(tmp_path)

    assert result.returncode == 1
    report = json.loads(result.stdout)
    assert report["status"] == "failed"
    assert report["verified_count"] == 0
    assert report["installed_count"] == 0
    assert report["failure_count"] == 1
    assert report["failed"][0]["slug"] == slug
    assert report["failed"][0]["source"] is None
    assert (
        report["failed"][0]["reason"]
        == "enabled manifest entries must define non-empty source strings"
    )


def test_skill_install_frozen_reports_invalid_source_format(tmp_path: Path) -> None:
    slug = "invalid-source"
    _init_git_repo(tmp_path)
    _write_yaml(
        tmp_path / "core" / "memory" / "skills" / "SKILLS.yaml",
        {
            "version": 1,
            "skills": {
                slug: {
                    "enabled": True,
                    "source": "bogus:example",
                }
            },
        },
    )
    _write_yaml(
        tmp_path / "core" / "memory" / "skills" / "SKILLS.lock",
        {
            "version": 1,
            "entries": {},
        },
    )

    result = _run_script(tmp_path)

    assert result.returncode == 1
    report = json.loads(result.stdout)
    assert report["status"] == "failed"
    assert report["verified_count"] == 0
    assert report["installed_count"] == 0
    assert report["failure_count"] == 1
    assert report["failed"][0]["slug"] == slug
    assert report["failed"][0]["source"] == "bogus:example"
    assert (
        report["failed"][0]["reason"]
        == "source format invalid. Must match one of: local, github:owner/repo, git:url, path:./relative or path:../relative"
    )


def test_skill_install_frozen_reports_non_git_repo_startup_error(tmp_path: Path) -> None:
    slug = "frozen-local"
    _write_skill(tmp_path, slug)
    _write_yaml(
        tmp_path / "core" / "memory" / "skills" / "SKILLS.yaml",
        {
            "version": 1,
            "skills": {
                slug: {
                    "enabled": True,
                    "source": "local",
                }
            },
        },
    )
    _write_yaml(
        tmp_path / "core" / "memory" / "skills" / "SKILLS.lock",
        {
            "version": 1,
            "entries": {
                slug: {
                    "source": "local",
                    "resolved_path": f"core/memory/skills/{slug}/",
                    "content_hash": compute_content_hash(
                        tmp_path / "core" / "memory" / "skills" / slug
                    ),
                }
            },
        },
    )

    result = _run_script(tmp_path)

    assert result.returncode == 1
    report = json.loads(result.stdout)
    assert report["status"] == "error"
    assert report["verified"] == []
    assert report["installed"] == []
    assert report["error"] == report["failed"][0]["reason"]
    assert "not a git repository" in report["error"]


def test_skill_install_frozen_fails_on_hash_mismatch(tmp_path: Path) -> None:
    slug = "frozen-local"
    _init_git_repo(tmp_path)
    _write_skill(tmp_path, slug)
    _write_yaml(
        tmp_path / "core" / "memory" / "skills" / "SKILLS.yaml",
        {
            "version": 1,
            "skills": {
                slug: {
                    "enabled": True,
                    "source": "local",
                }
            },
        },
    )
    _write_yaml(
        tmp_path / "core" / "memory" / "skills" / "SKILLS.lock",
        {
            "version": 1,
            "entries": {
                slug: {
                    "source": "local",
                    "resolved_path": f"core/memory/skills/{slug}/",
                    "content_hash": "sha256:deadbeef",
                }
            },
        },
    )

    result = _run_script(tmp_path)

    assert result.returncode == 1
    report = json.loads(result.stdout)
    assert report["status"] == "failed"
    assert report["verified_count"] == 0
    assert report["installed_count"] == 0
    assert report["failure_count"] == 1
    assert report["failed"][0]["slug"] == slug
    assert report["failed"][0]["expected_hash"] == "sha256:deadbeef"
    assert (
        report["failed"][0]["reason"]
        == "frozen mode rejected the resolved skill because the lock verification failed"
    )


def test_skill_install_frozen_verifies_remote_skill_from_locked_copy(tmp_path: Path) -> None:
    slug = "remote-skill"
    _init_git_repo(tmp_path)
    remote_skill_text = (
        "---\n"
        "title: remote-skill\n"
        "summary: Remote frozen skill\n"
        "trust: medium\n"
        "---\n\n"
        "Remote body.\n"
    )
    source_repo = tmp_path / "remote-source"
    resolved_ref = _init_git_source_repo(
        source_repo,
        {f"skills/{slug}/SKILL.md": remote_skill_text},
    )
    source = f"git:{source_repo.as_uri()}"
    content_hash = _write_skill(tmp_path, slug, remote_skill_text)
    _write_yaml(
        tmp_path / "core" / "memory" / "skills" / "SKILLS.yaml",
        {
            "version": 1,
            "skills": {
                slug: {
                    "enabled": True,
                    "source": source,
                }
            },
        },
    )
    _write_yaml(
        tmp_path / "core" / "memory" / "skills" / "SKILLS.lock",
        {
            "version": 1,
            "entries": {
                slug: {
                    "source": source,
                    "resolved_path": f"core/memory/skills/{slug}/",
                    "content_hash": content_hash,
                    "resolved_ref": resolved_ref,
                }
            },
        },
    )
    _remove_tree(source_repo)

    result = _run_script(tmp_path)

    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["status"] == "ok"
    assert report["verified_count"] == 1
    assert report["installed_count"] == 0
    assert report["verified"][0]["slug"] == slug
    assert report["verified"][0]["source"] == source
    assert report["verified"][0]["resolved_ref"] == resolved_ref
    assert report["verified"][0]["resolution_mode"] == "locked"


def test_skill_install_frozen_materializes_missing_gitignored_remote_skill(tmp_path: Path) -> None:
    slug = "remote-gitignored"
    _init_git_repo(tmp_path)
    remote_skill_text = (
        "---\n"
        f"name: {slug}\n"
        "description: Remote gitignored skill\n"
        "source: external-research\n"
        "origin_session: manual\n"
        "created: 2026-04-15\n"
        "trust: low\n"
        "---\n\n"
        "Remote body.\n"
    )
    source_repo = tmp_path / "remote-source-gitignored"
    resolved_ref = _init_git_source_repo(
        source_repo,
        {f"skills/{slug}/SKILL.md": remote_skill_text},
    )
    source = f"git:{source_repo.as_uri()}"
    content_hash = compute_content_hash(source_repo / "skills" / slug)
    _write_yaml(
        tmp_path / "core" / "memory" / "skills" / "SKILLS.yaml",
        {
            "schema_version": 1,
            "defaults": {},
            "skills": {
                slug: {
                    "enabled": True,
                    "source": source,
                    "trust": "low",
                    "deployment_mode": "gitignored",
                    "description": "Remote gitignored skill",
                }
            },
        },
    )
    _write_yaml(
        tmp_path / "core" / "memory" / "skills" / "SKILLS.lock",
        {
            "lock_version": 1,
            "entries": {
                slug: {
                    "source": source,
                    "resolved_path": f"core/memory/skills/{slug}/",
                    "content_hash": content_hash,
                    "resolved_ref": resolved_ref,
                }
            },
        },
    )

    result = _run_script(tmp_path)

    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["status"] == "ok"
    assert report["installed_count"] == 1
    assert report["verified_count"] == 1
    assert report["failure_count"] == 0
    assert report["installed"][0]["slug"] == slug
    assert report["installed"][0]["resolution_mode"] == "remote"
    installed_skill = tmp_path / "core" / "memory" / "skills" / slug / "SKILL.md"
    assert installed_skill.is_file()


def test_skill_install_frozen_reports_unrecoverable_gitignored_local_skill(tmp_path: Path) -> None:
    slug = "local-gitignored"
    _init_git_repo(tmp_path)
    _write_yaml(
        tmp_path / "core" / "memory" / "skills" / "SKILLS.yaml",
        {
            "schema_version": 1,
            "defaults": {},
            "skills": {
                slug: {
                    "enabled": True,
                    "source": "local",
                    "trust": "low",
                    "deployment_mode": "gitignored",
                    "description": "Local gitignored skill",
                }
            },
        },
    )
    _write_yaml(
        tmp_path / "core" / "memory" / "skills" / "SKILLS.lock",
        {
            "lock_version": 1,
            "entries": {
                slug: {
                    "source": "local",
                    "resolved_path": f"core/memory/skills/{slug}/",
                    "content_hash": "sha256:deadbeef",
                }
            },
        },
    )

    result = _run_script(tmp_path)

    assert result.returncode == 1
    report = json.loads(result.stdout)
    assert report["status"] == "failed"
    assert report["installed_count"] == 0
    assert report["verified_count"] == 0
    assert report["failure_count"] == 1
    assert report["failed"][0]["slug"] == slug
    assert "cannot be restored on a fresh clone" in report["failed"][0]["reason"]


def test_skill_install_frozen_fails_for_remote_source_without_lock_entry(tmp_path: Path) -> None:
    slug = "remote-skill"
    _init_git_repo(tmp_path)
    source_repo = tmp_path / "remote-source"
    source = f"git:{source_repo.as_uri()}"
    _init_git_source_repo(
        source_repo,
        {
            f"skills/{slug}/SKILL.md": "# Remote Skill\n",
        },
    )
    _write_yaml(
        tmp_path / "core" / "memory" / "skills" / "SKILLS.yaml",
        {
            "version": 1,
            "skills": {
                slug: {
                    "enabled": True,
                    "source": source,
                }
            },
        },
    )
    _write_yaml(
        tmp_path / "core" / "memory" / "skills" / "SKILLS.lock",
        {
            "version": 1,
            "entries": {},
        },
    )

    result = _run_script(tmp_path)

    assert result.returncode == 1
    report = json.loads(result.stdout)
    assert report["status"] == "failed"
    assert report["verified_count"] == 0
    assert report["installed_count"] == 0
    assert report["failure_count"] == 1
    assert report["failed"][0]["slug"] == slug
    assert report["failed"][0]["source"] == source
    assert (
        report["failed"][0]["reason"]
        == "frozen mode requires a fresh lock entry for remote sources"
    )


def test_skill_install_frozen_aggregates_failures_and_skips_disabled_entries(
    tmp_path: Path,
) -> None:
    good_slug = "local-skill"
    bad_slug = "remote-skill"
    disabled_slug = "disabled-remote"
    _init_git_repo(tmp_path)
    content_hash = _write_skill(tmp_path, good_slug)
    source_repo = tmp_path / "remote-source"
    source = f"git:{source_repo.as_uri()}"
    _init_git_source_repo(
        source_repo,
        {
            f"skills/{bad_slug}/SKILL.md": "# Remote Skill\n",
            f"skills/{disabled_slug}/SKILL.md": "# Disabled Remote Skill\n",
        },
    )
    _write_yaml(
        tmp_path / "core" / "memory" / "skills" / "SKILLS.yaml",
        {
            "version": 1,
            "skills": {
                good_slug: {
                    "enabled": True,
                    "source": "local",
                },
                bad_slug: {
                    "enabled": True,
                    "source": source,
                },
                disabled_slug: {
                    "enabled": False,
                    "source": source,
                },
            },
        },
    )
    _write_yaml(
        tmp_path / "core" / "memory" / "skills" / "SKILLS.lock",
        {
            "version": 1,
            "entries": {
                good_slug: {
                    "source": "local",
                    "resolved_path": f"core/memory/skills/{good_slug}/",
                    "content_hash": content_hash,
                }
            },
        },
    )

    result = _run_script(tmp_path)

    assert result.returncode == 1
    report = json.loads(result.stdout)
    assert report["status"] == "failed"
    assert report["verified_count"] == 1
    assert report["installed_count"] == 0
    assert report["failure_count"] == 1
    assert [item["slug"] for item in report["verified"]] == [good_slug]
    assert [item["slug"] for item in report["failed"]] == [bad_slug]


def test_skill_install_frozen_fails_when_manifest_ref_differs_from_locked_ref(
    tmp_path: Path,
) -> None:
    slug = "remote-skill"
    requested_ref = "release-2026-04"
    _init_git_repo(tmp_path)
    remote_skill_text = (
        "---\n"
        "title: remote-skill\n"
        "summary: Remote frozen skill\n"
        "trust: medium\n"
        "---\n\n"
        "Remote body.\n"
    )
    source_repo = tmp_path / "remote-source-ref-mismatch"
    resolved_ref = _init_git_source_repo(
        source_repo,
        {f"skills/{slug}/SKILL.md": remote_skill_text},
    )
    source = f"git:{source_repo.as_uri()}"
    content_hash = _write_skill(tmp_path, slug, remote_skill_text)
    _write_yaml(
        tmp_path / "core" / "memory" / "skills" / "SKILLS.yaml",
        {
            "version": 1,
            "skills": {
                slug: {
                    "enabled": True,
                    "source": source,
                    "ref": requested_ref,
                }
            },
        },
    )
    _write_yaml(
        tmp_path / "core" / "memory" / "skills" / "SKILLS.lock",
        {
            "version": 1,
            "entries": {
                slug: {
                    "source": source,
                    "requested_ref": "release-2026-03",
                    "resolved_ref": resolved_ref,
                    "resolved_path": f"core/memory/skills/{slug}/",
                    "content_hash": content_hash,
                }
            },
        },
    )

    result = _run_script(tmp_path)

    assert result.returncode == 1
    report = json.loads(result.stdout)
    assert report["status"] == "failed"
    assert report["verified_count"] == 0
    assert report["installed_count"] == 0
    assert report["failure_count"] == 1
    assert report["failed"][0]["slug"] == slug
    assert report["failed"][0]["expected_ref"] == resolved_ref
    assert report["failed"][0]["expected_requested_ref"] == "release-2026-03"
    assert (
        report["failed"][0]["reason"]
        == "frozen mode requires a fresh lock entry for remote sources"
    )
