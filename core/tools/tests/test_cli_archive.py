from __future__ import annotations

import importlib
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]


def _load_module(module_name: str) -> ModuleType:
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    return importlib.import_module(module_name)


cmd_archive = _load_module("engram_mcp.agent_memory_mcp.cli.cmd_archive")
cli_main = _load_module("engram_mcp.agent_memory_mcp.cli.main")


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _init_git_repo(repo_root: Path) -> None:
    subprocess.run(["git", "init"], cwd=repo_root, check=True, capture_output=True, text=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(["git", "add", "-A"], cwd=repo_root, check=True, capture_output=True, text=True)
    subprocess.run(
        ["git", "commit", "-m", "init"],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )


def _seed_archive_repo(tmp_path: Path) -> tuple[Path, Path]:
    repo_root = tmp_path / "repo"
    content_root = repo_root / "core"
    _write(
        content_root / "memory" / "knowledge" / "django" / "note.md",
        "---\n"
        "created: 2026-03-20\n"
        "source: test\n"
        "trust: high\n"
        "last_verified: 2026-03-20\n"
        "---\n\n"
        "# Note\n",
    )
    _write(
        content_root / "memory" / "knowledge" / "SUMMARY.md",
        "# Knowledge\n\n"
        "<!-- section: django -->\n"
        "### Django\n"
        "- **[note.md](memory/knowledge/django/note.md)** — Note\n\n"
        "---\n",
    )
    _init_git_repo(repo_root)
    return repo_root, content_root


def _args(
    source_path: str,
    *,
    json_output: bool = False,
    reason: str | None = None,
    version_token: str | None = None,
    preview: bool = False,
):
    return type(
        "Args",
        (),
        {
            "source_path": source_path,
            "json": json_output,
            "reason": reason,
            "version_token": version_token,
            "preview": preview,
        },
    )()


def test_archive_preview_keeps_source_file_and_returns_governed_payload(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo_root, content_root = _seed_archive_repo(tmp_path)

    exit_code = cmd_archive.run_archive(
        _args("memory/knowledge/django/note.md", json_output=True, reason="stale", preview=True),
        repo_root=repo_root,
        content_root=content_root,
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["preview"]["mode"] == "preview"
    assert payload["new_state"]["archive_path"] == "memory/knowledge/_archive/django/note.md"
    assert (content_root / "memory" / "knowledge" / "django" / "note.md").exists()
    assert not (content_root / "memory" / "knowledge" / "_archive" / "django" / "note.md").exists()


def test_archive_apply_moves_file_and_marks_it_archived(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo_root, content_root = _seed_archive_repo(tmp_path)

    exit_code = cmd_archive.run_archive(
        _args("memory/knowledge/django/note.md", json_output=True, reason="stale"),
        repo_root=repo_root,
        content_root=content_root,
    )
    payload = json.loads(capsys.readouterr().out)
    archived_text = (
        content_root / "memory" / "knowledge" / "_archive" / "django" / "note.md"
    ).read_text(encoding="utf-8")

    assert exit_code == 0
    assert payload["new_state"]["archive_path"] == "memory/knowledge/_archive/django/note.md"
    assert payload["commit_sha"]
    assert not (content_root / "memory" / "knowledge" / "django" / "note.md").exists()
    assert "status: archived" in archived_text
    assert "last_verified:" in archived_text


def test_archive_rejects_non_knowledge_path_in_json_mode(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo_root, content_root = _seed_archive_repo(tmp_path)

    exit_code = cmd_archive.run_archive(
        _args("memory/users/profile.md", json_output=True, preview=True),
        repo_root=repo_root,
        content_root=content_root,
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 2
    assert payload["valid"] is False
    assert payload["errors"]


def test_archive_command_is_registered_in_main_parser() -> None:
    parser = cli_main.build_parser()
    args = parser.parse_args(["archive", "memory/knowledge/django/note.md", "--preview", "--json"])

    assert args.command == "archive"
    assert args.preview is True
    assert args.json is True
    assert args.handler is cmd_archive.run_archive
