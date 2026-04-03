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


cmd_promote = _load_module("engram_mcp.agent_memory_mcp.cli.cmd_promote")
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


def _seed_promote_repo(tmp_path: Path) -> tuple[Path, Path]:
    repo_root = tmp_path / "repo"
    content_root = repo_root / "core"
    _write(
        content_root / "memory" / "knowledge" / "_unverified" / "django" / "note.md",
        "---\ncreated: 2026-03-20\nsource: test\ntrust: low\n---\n\n# Note\n",
    )
    _write(
        content_root / "memory" / "knowledge" / "_unverified" / "SUMMARY.md",
        "# Unverified Knowledge\n\n"
        "<!-- section: django -->\n"
        "### Django\n"
        "- **[note.md](memory/knowledge/_unverified/django/note.md)** — Note\n\n"
        "---\n",
    )
    _write(
        content_root / "memory" / "knowledge" / "SUMMARY.md",
        "# Knowledge\n\n<!-- section: django -->\n### Django\n\n---\n",
    )
    _init_git_repo(repo_root)
    return repo_root, content_root


def _args(
    source_path: str,
    *,
    json_output: bool = False,
    trust: str = "high",
    target_path: str | None = None,
    summary_entry: str | None = None,
    version_token: str | None = None,
    preview: bool = False,
):
    return type(
        "Args",
        (),
        {
            "source_path": source_path,
            "json": json_output,
            "trust": trust,
            "target_path": target_path,
            "summary_entry": summary_entry,
            "version_token": version_token,
            "preview": preview,
        },
    )()


def test_promote_preview_keeps_source_file_and_returns_governed_payload(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo_root, content_root = _seed_promote_repo(tmp_path)

    exit_code = cmd_promote.run_promote(
        _args(
            "memory/knowledge/_unverified/django/note.md",
            json_output=True,
            trust="medium",
            summary_entry="- **[note.md](memory/knowledge/django/note.md)** — Note",
            preview=True,
        ),
        repo_root=repo_root,
        content_root=content_root,
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["preview"]["mode"] == "preview"
    assert payload["new_state"]["new_path"] == "memory/knowledge/django/note.md"
    assert (content_root / "memory" / "knowledge" / "_unverified" / "django" / "note.md").exists()
    assert not (content_root / "memory" / "knowledge" / "django" / "note.md").exists()


def test_promote_apply_moves_file_and_updates_frontmatter(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo_root, content_root = _seed_promote_repo(tmp_path)

    exit_code = cmd_promote.run_promote(
        _args(
            "memory/knowledge/_unverified/django/note.md",
            json_output=True,
            trust="medium",
            summary_entry="- **[note.md](memory/knowledge/django/note.md)** — Note",
        ),
        repo_root=repo_root,
        content_root=content_root,
    )
    payload = json.loads(capsys.readouterr().out)
    promoted_text = (content_root / "memory" / "knowledge" / "django" / "note.md").read_text(
        encoding="utf-8"
    )

    assert exit_code == 0
    assert payload["new_state"]["new_path"] == "memory/knowledge/django/note.md"
    assert payload["new_state"]["trust"] == "medium"
    assert payload["commit_sha"]
    assert not (
        content_root / "memory" / "knowledge" / "_unverified" / "django" / "note.md"
    ).exists()
    assert "trust: medium" in promoted_text
    assert "last_verified:" in promoted_text


def test_promote_rejects_invalid_target_in_json_mode(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo_root, content_root = _seed_promote_repo(tmp_path)

    exit_code = cmd_promote.run_promote(
        _args(
            "memory/knowledge/_unverified/django/note.md",
            json_output=True,
            target_path="memory/users/profile.md",
            preview=True,
        ),
        repo_root=repo_root,
        content_root=content_root,
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 2
    assert payload["valid"] is False
    assert payload["errors"]


def test_promote_command_is_registered_in_main_parser() -> None:
    parser = cli_main.build_parser()
    args = parser.parse_args(
        ["promote", "memory/knowledge/_unverified/django/note.md", "--preview", "--json"]
    )

    assert args.command == "promote"
    assert args.preview is True
    assert args.json is True
    assert args.handler is cmd_promote.run_promote
