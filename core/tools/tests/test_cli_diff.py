from __future__ import annotations

import importlib
import json
import os
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


cmd_diff = _load_module("engram_mcp.agent_memory_mcp.cli.cmd_diff")
cli_main = _load_module("engram_mcp.agent_memory_mcp.cli.main")


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _git(repo_root: Path, *args: str, env: dict[str, str] | None = None) -> None:
    subprocess.run(
        ["git", *args],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )


def _commit(repo_root: Path, message: str, when: str) -> None:
    env = dict(os.environ)
    env["GIT_AUTHOR_DATE"] = when
    env["GIT_COMMITTER_DATE"] = when
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-m", message, env=env)


def _diff_args(
    *,
    json_output: bool = False,
    namespace: str | None = None,
    since: str | None = None,
    until: str | None = None,
    limit: int = 10,
):
    return type(
        "Args",
        (),
        {
            "json": json_output,
            "namespace": namespace,
            "since": since,
            "until": until,
            "limit": limit,
        },
    )()


def _seed_diff_repo(tmp_path: Path) -> tuple[Path, Path]:
    repo_root = tmp_path / "repo"
    content_root = repo_root / "core"
    repo_root.mkdir(parents=True, exist_ok=True)
    content_root.mkdir(parents=True, exist_ok=True)

    _git(repo_root, "init")
    _git(repo_root, "config", "user.email", "test@test.com")
    _git(repo_root, "config", "user.name", "Test")

    _write(
        content_root / "memory" / "knowledge" / "alpha.md",
        "---\n"
        "trust: low\n"
        "created: 2026-04-01\n"
        "origin_session: manual\n"
        "source: manual\n"
        "---\n\n"
        "Alpha body\n",
    )
    _commit(repo_root, "seed knowledge", "2026-04-01T09:00:00Z")

    _write(
        content_root / "memory" / "knowledge" / "alpha.md",
        "---\n"
        "trust: medium\n"
        "created: 2026-04-01\n"
        "last_verified: 2026-04-03\n"
        "origin_session: manual\n"
        "source: manual\n"
        "---\n\n"
        "Alpha body revised\n",
    )
    _write(
        content_root / "memory" / "knowledge" / "beta.md",
        "---\n"
        "trust: low\n"
        "created: 2026-04-03\n"
        "origin_session: manual\n"
        "source: external-research\n"
        "---\n\n"
        "Beta body\n",
    )
    _commit(repo_root, "update knowledge trust", "2026-04-03T10:00:00Z")

    _write(
        content_root / "memory" / "skills" / "testing.md",
        "---\n"
        "trust: high\n"
        "created: 2026-04-04\n"
        "origin_session: manual\n"
        "source: manual\n"
        "---\n\n"
        "Testing skill\n",
    )
    _commit(repo_root, "add testing skill", "2026-04-04T08:30:00Z")

    return repo_root, content_root


def test_diff_human_output_renders_commit_annotations(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo_root, content_root = _seed_diff_repo(tmp_path)

    exit_code = cmd_diff.run_diff(_diff_args(), repo_root=repo_root, content_root=content_root)
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Diff query" in output
    assert "Matched commits: 3" in output
    assert "memory/knowledge/alpha.md [modified/knowledge]" in output
    assert "frontmatter changed; trust: low -> medium" in output
    assert "memory/knowledge/beta.md [added/knowledge]" in output
    assert "new file; frontmatter changed; trust: low" in output


def test_diff_json_filters_by_namespace_and_date(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo_root, content_root = _seed_diff_repo(tmp_path)

    exit_code = cmd_diff.run_diff(
        _diff_args(json_output=True, namespace="knowledge", since="2026-04-03"),
        repo_root=repo_root,
        content_root=content_root,
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["count"] == 1
    assert payload["files_changed"] == 2
    assert payload["by_namespace"] == {
        "knowledge": {
            "added": 1,
            "modified": 1,
            "deleted": 0,
            "renamed": 0,
            "copied": 0,
            "type-changed": 0,
        }
    }
    assert payload["commits"][0]["short_sha"]
    assert payload["commits"][0]["files"][0]["namespace"] == "knowledge"


def test_diff_supports_until_filter(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo_root, content_root = _seed_diff_repo(tmp_path)

    exit_code = cmd_diff.run_diff(
        _diff_args(json_output=True, until="2026-04-03"),
        repo_root=repo_root,
        content_root=content_root,
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["count"] == 2
    assert {commit["message"] for commit in payload["commits"]} == {
        "seed knowledge",
        "update knowledge trust",
    }


def test_diff_rejects_invalid_since_in_json_mode(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo_root, content_root = _seed_diff_repo(tmp_path)

    exit_code = cmd_diff.run_diff(
        _diff_args(json_output=True, since="2026/04/03"),
        repo_root=repo_root,
        content_root=content_root,
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 2
    assert payload["valid"] is False
    assert payload["errors"] == ["since must be in YYYY-MM-DD format"]


def test_diff_command_is_registered_in_main_parser() -> None:
    parser = cli_main.build_parser()
    args = parser.parse_args(["diff", "--namespace", "knowledge", "--json"])

    assert args.command == "diff"
    assert args.namespace == "knowledge"
    assert args.json is True
    assert args.handler is cmd_diff.run_diff
