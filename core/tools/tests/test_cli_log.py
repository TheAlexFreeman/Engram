from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]


def _load_cmd_log() -> ModuleType:
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    return importlib.import_module("engram_mcp.agent_memory_mcp.cli.cmd_log")


cmd_log = _load_cmd_log()


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _args(
    *,
    json_output: bool = False,
    namespace: str | None = None,
    since: str | None = None,
    limit: int = 20,
):
    return type(
        "Args",
        (),
        {
            "json": json_output,
            "namespace": namespace,
            "since": since,
            "limit": limit,
        },
    )()


def _seed_log_repo(tmp_path: Path) -> tuple[Path, Path]:
    repo_root = tmp_path / "repo"
    content_root = repo_root / "core"

    _write(
        content_root / "memory" / "knowledge" / "ACCESS.jsonl",
        "\n".join(
            [
                json.dumps(
                    {
                        "file": "memory/knowledge/react/hooks.md",
                        "date": "2026-04-01",
                        "session_id": "memory/activity/2026/04/01/chat-001",
                        "task": "read",
                        "mode": "read",
                        "helpfulness": 0.8,
                        "note": "Loaded hooks note.",
                    }
                ),
                json.dumps(
                    {
                        "file": "memory/knowledge/react/context.md",
                        "date": "2026-04-03",
                        "session_id": "memory/activity/2026/04/03/chat-001",
                        "task": "compare",
                        "mode": "read",
                        "helpfulness": 0.7,
                        "note": "Compared context guidance.",
                    }
                ),
            ]
        )
        + "\n",
    )
    _write(
        content_root / "memory" / "skills" / "ACCESS.jsonl",
        json.dumps(
            {
                "file": "memory/skills/testing.md",
                "date": "2026-04-02",
                "session_id": "memory/activity/2026/04/02/chat-001",
                "task": "read",
                "mode": "read",
                "helpfulness": 0.9,
                "note": "Checked testing workflow.",
            }
        )
        + "\n",
    )
    return repo_root, content_root


def test_log_filters_by_namespace(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo_root, content_root = _seed_log_repo(tmp_path)

    exit_code = cmd_log.run_log(
        _args(namespace="knowledge"),
        repo_root=repo_root,
        content_root=content_root,
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "memory/knowledge/react/context.md" in output
    assert "memory/skills/testing.md" not in output


def test_log_filters_by_since_date(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo_root, content_root = _seed_log_repo(tmp_path)

    exit_code = cmd_log.run_log(
        _args(since="2026-04-02"),
        repo_root=repo_root,
        content_root=content_root,
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "2026-04-03" in output
    assert "2026-04-01" not in output


def test_log_handles_empty_results(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo_root = tmp_path / "repo"
    content_root = repo_root / "core"

    exit_code = cmd_log.run_log(
        _args(namespace="knowledge"),
        repo_root=repo_root,
        content_root=content_root,
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "No ACCESS entries found." in output


def test_log_json_output_is_structured(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo_root, content_root = _seed_log_repo(tmp_path)

    exit_code = cmd_log.run_log(
        _args(json_output=True, namespace="knowledge"),
        repo_root=repo_root,
        content_root=content_root,
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["count"] == 2
    assert payload["results"][0]["namespace"] == "knowledge"
