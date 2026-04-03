from __future__ import annotations

import importlib
import io
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]


def _load_cmd_add() -> ModuleType:
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    return importlib.import_module("engram_mcp.agent_memory_mcp.cli.cmd_add")


cmd_add = _load_cmd_add()


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


def _seed_add_repo(tmp_path: Path) -> tuple[Path, Path]:
    repo_root = tmp_path / "repo"
    content_root = repo_root / "core"
    _write(
        content_root / "memory" / "knowledge" / "_unverified" / "SUMMARY.md",
        "# Unverified Knowledge\n\n<!-- section: react -->\n### React\n\n---\n",
    )
    _init_git_repo(repo_root)
    return repo_root, content_root


def _args(
    namespace: str,
    *,
    input_path: str | None = None,
    json_output: bool = False,
    name: str | None = None,
    source: str = "external-research",
    session_id: str = "memory/activity/2026/04/03/chat-001",
    summary_entry: str | None = None,
    expires: str | None = None,
    preview: bool = False,
):
    return type(
        "Args",
        (),
        {
            "namespace": namespace,
            "input": input_path,
            "json": json_output,
            "name": name,
            "source": source,
            "session_id": session_id,
            "summary_entry": summary_entry,
            "expires": expires,
            "preview": preview,
        },
    )()


def test_add_file_input_writes_unverified_file_and_access_log(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo_root, content_root = _seed_add_repo(tmp_path)
    source_file = tmp_path / "hooks-note.md"
    source_file.write_text("# Hooks Note\n\nBody\n", encoding="utf-8")

    exit_code = cmd_add.run_add(
        _args("knowledge/react", input_path=str(source_file), json_output=True),
        repo_root=repo_root,
        content_root=content_root,
    )
    payload = json.loads(capsys.readouterr().out)

    target_path = content_root / "memory" / "knowledge" / "_unverified" / "react" / "hooks-note.md"
    access_log = content_root / "memory" / "knowledge" / "_unverified" / "ACCESS.jsonl"
    summary_text = (content_root / "memory" / "knowledge" / "_unverified" / "SUMMARY.md").read_text(
        encoding="utf-8"
    )
    entry = json.loads(access_log.read_text(encoding="utf-8").strip())

    assert exit_code == 0
    assert payload["new_state"]["path"] == "memory/knowledge/_unverified/react/hooks-note.md"
    assert payload["new_state"]["access_jsonl"] == "memory/knowledge/_unverified/ACCESS.jsonl"
    assert target_path.exists()
    assert "trust: low" in target_path.read_text(encoding="utf-8")
    assert entry["file"] == "memory/knowledge/_unverified/react/hooks-note.md"
    assert entry["mode"] == "create"
    assert (
        "**[hooks-note.md](memory/knowledge/_unverified/react/hooks-note.md)** — Hooks Note"
        in summary_text
    )


def test_add_preview_from_stdin_derives_filename_from_heading(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_root, content_root = _seed_add_repo(tmp_path)
    monkeypatch.setattr(sys, "stdin", io.StringIO("# Preview Note\n\nBody\n"))

    exit_code = cmd_add.run_add(
        _args("knowledge/react", json_output=True, preview=True, input_path=None),
        repo_root=repo_root,
        content_root=content_root,
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["new_state"]["path"] == "memory/knowledge/_unverified/react/preview-note.md"
    assert (
        payload["preview"]["target_files"][0]["path"]
        == "memory/knowledge/_unverified/react/preview-note.md"
    )
    assert not (
        content_root / "memory" / "knowledge" / "_unverified" / "react" / "preview-note.md"
    ).exists()
    assert not (content_root / "memory" / "knowledge" / "_unverified" / "ACCESS.jsonl").exists()


def test_add_routes_verified_namespace_requests_into_unverified(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo_root, content_root = _seed_add_repo(tmp_path)
    source_file = tmp_path / "context.md"
    source_file.write_text("# Context\n\nBody\n", encoding="utf-8")

    exit_code = cmd_add.run_add(
        _args("memory/knowledge/react", input_path=str(source_file), json_output=True),
        repo_root=repo_root,
        content_root=content_root,
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["new_state"]["path"] == "memory/knowledge/_unverified/react/context.md"


def test_add_requires_name_when_stdin_lacks_heading(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_root, content_root = _seed_add_repo(tmp_path)
    monkeypatch.setattr(sys, "stdin", io.StringIO("Body only\n"))

    with pytest.raises(ValueError):
        cmd_add.run_add(
            _args("knowledge/react", input_path=None, preview=True),
            repo_root=repo_root,
            content_root=content_root,
        )
