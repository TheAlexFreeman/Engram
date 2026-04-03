from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]


def _load_cmd_recall() -> ModuleType:
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    return importlib.import_module("engram_mcp.agent_memory_mcp.cli.cmd_recall")


cmd_recall = _load_cmd_recall()


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _args(
    target: list[str],
    *,
    json_output: bool = False,
    limit: int = 10,
    keyword: bool = False,
):
    return type(
        "Args",
        (),
        {
            "target": target,
            "json": json_output,
            "limit": limit,
            "keyword": keyword,
        },
    )()


def _seed_recall_repo(tmp_path: Path) -> tuple[Path, Path]:
    repo_root = tmp_path / "repo"
    content_root = repo_root / "core"

    _write(
        content_root / "memory" / "knowledge" / "react" / "SUMMARY.md",
        "---\ntrust: medium\nsource: manual\ncreated: 2026-04-01\n---\n\n"
        "React workspace overview for common patterns and reference files.\n",
    )
    _write(
        content_root / "memory" / "knowledge" / "react" / "hooks.md",
        "---\ntrust: high\nsource: manual\ncreated: 2026-04-01\n"
        "origin_session: manual\n---\n\n"
        "Hooks let components share stateful logic without changing hierarchy.\n",
    )
    _write(
        content_root / "memory" / "knowledge" / "react" / "context.md",
        "---\ntrust: medium\nsource: manual\ncreated: 2026-04-02\n---\n\n"
        "Context helps pass values through trees without prop drilling.\n",
    )
    _write(
        content_root / "memory" / "knowledge" / "ACCESS.jsonl",
        "\n".join(
            [
                json.dumps(
                    {
                        "file": "memory/knowledge/react/hooks.md",
                        "date": "2026-04-01",
                        "task": "read",
                        "helpfulness": 0.8,
                        "note": "Needed the hooks recap.",
                    }
                ),
                json.dumps(
                    {
                        "file": "memory/knowledge/react/hooks.md",
                        "date": "2026-04-02",
                        "task": "read",
                        "helpfulness": 0.9,
                        "note": "Reused the hooks explanation.",
                    }
                ),
                json.dumps(
                    {
                        "file": "memory/knowledge/react/context.md",
                        "date": "2026-04-02",
                        "task": "read",
                        "helpfulness": 0.6,
                        "note": "Checked the context note.",
                    }
                ),
            ]
        )
        + "\n",
    )
    return repo_root, content_root


def test_recall_file_renders_frontmatter_and_access_context(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo_root, content_root = _seed_recall_repo(tmp_path)

    exit_code = cmd_recall.run_recall(
        _args(["memory/knowledge/react/hooks.md"]),
        repo_root=repo_root,
        content_root=content_root,
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Path: memory/knowledge/react/hooks.md" in output
    assert "Trust: high" in output
    assert "Accesses: 2" in output
    assert "Hooks let components share stateful logic" in output


def test_recall_namespace_shows_summary_and_file_listing(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo_root, content_root = _seed_recall_repo(tmp_path)

    exit_code = cmd_recall.run_recall(
        _args(["knowledge/react"]),
        repo_root=repo_root,
        content_root=content_root,
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Namespace: memory/knowledge/react" in output
    assert "React workspace overview" in output
    assert "memory/knowledge/react/hooks.md" in output
    assert "memory/knowledge/react/context.md" in output


def test_recall_query_fallback_loads_best_match(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo_root, content_root = _seed_recall_repo(tmp_path)

    exit_code = cmd_recall.run_recall(
        _args(["share", "stateful", "logic"], keyword=True),
        repo_root=repo_root,
        content_root=content_root,
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Matched by query: share stateful logic" in output
    assert "Path: memory/knowledge/react/hooks.md" in output


def test_recall_json_output_includes_access_summary(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo_root, content_root = _seed_recall_repo(tmp_path)

    exit_code = cmd_recall.run_recall(
        _args(["memory/knowledge/react/hooks.md"], json_output=True),
        repo_root=repo_root,
        content_root=content_root,
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["kind"] == "file"
    assert payload["path"] == "memory/knowledge/react/hooks.md"
    assert payload["access"]["count"] == 2
