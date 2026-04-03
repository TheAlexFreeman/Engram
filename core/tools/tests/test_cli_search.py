from __future__ import annotations

import importlib
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]


def _load_cmd_search() -> ModuleType:
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    return importlib.import_module("engram_mcp.agent_memory_mcp.cli.cmd_search")


cmd_search = _load_cmd_search()


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _seed_search_repo(tmp_path: Path) -> tuple[Path, Path]:
    repo_root = tmp_path / "repo"
    content_root = repo_root / "core"
    _write(
        content_root / "memory" / "knowledge" / "alpha.md",
        "---\ntrust: high\ncreated: 2026-04-01\norigin_session: manual\nsource: manual\n---\n\n"
        "Alpha topic discusses consciousness and memory retrieval.\n",
    )
    _write(
        content_root / "memory" / "skills" / "beta.md",
        "---\ntrust: medium\ncreated: 2026-04-01\norigin_session: manual\nsource: manual\n---\n\n"
        "Beta topic explains testing workflows.\n",
    )
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
    return repo_root, content_root


def _args(
    query: list[str],
    *,
    json_output: bool = False,
    scope: str | None = None,
    limit: int = 10,
    keyword: bool = False,
    case_sensitive: bool = False,
):
    return type(
        "Args",
        (),
        {
            "query": query,
            "json": json_output,
            "scope": scope,
            "limit": limit,
            "keyword": keyword,
            "case_sensitive": case_sensitive,
        },
    )()


def test_keyword_search_finds_known_content(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo_root, content_root = _seed_search_repo(tmp_path)

    exit_code = cmd_search.run_search(
        _args(["consciousness"], keyword=True),
        repo_root=repo_root,
        content_root=content_root,
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Mode: keyword" in output
    assert "alpha.md" in output


def test_scope_limits_results(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo_root, content_root = _seed_search_repo(tmp_path)

    exit_code = cmd_search.run_search(
        _args(["topic"], keyword=True, scope="memory/skills"),
        repo_root=repo_root,
        content_root=content_root,
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "beta.md" in output
    assert "alpha.md" not in output


def test_json_output_is_valid(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo_root, content_root = _seed_search_repo(tmp_path)

    exit_code = cmd_search.run_search(
        _args(["testing"], json_output=True, keyword=True),
        repo_root=repo_root,
        content_root=content_root,
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["mode"] == "keyword"
    assert payload["results"][0]["path"] == "memory/skills/beta.md"


def test_fallback_prints_mode_banner(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_root, content_root = _seed_search_repo(tmp_path)
    monkeypatch.setattr(cmd_search, "_semantic_available", lambda: False)

    exit_code = cmd_search.run_search(
        _args(["consciousness"]),
        repo_root=repo_root,
        content_root=content_root,
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Mode: keyword (sentence-transformers unavailable)" in output


def test_limit_caps_results(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo_root, content_root = _seed_search_repo(tmp_path)
    _write(
        content_root / "memory" / "knowledge" / "gamma.md",
        "---\ntrust: low\ncreated: 2026-04-01\norigin_session: manual\nsource: manual\n---\n\n"
        "Gamma topic also discusses memory retrieval.\n",
    )

    exit_code = cmd_search.run_search(
        _args(["memory"], keyword=True, limit=1),
        repo_root=repo_root,
        content_root=content_root,
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert output.count("memory/") == 1


def test_semantic_mode_uses_index(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo_root, content_root = _seed_search_repo(tmp_path)
    monkeypatch.setattr(cmd_search, "_semantic_available", lambda: True)

    def _fake_semantic_search(*_args: object, **_kwargs: object) -> list[object]:
        return [
            cmd_search.SearchResult(
                path="memory/knowledge/alpha.md",
                trust="high",
                snippet="Alpha topic discusses consciousness and memory retrieval.",
                score=0.91,
            )
        ]

    monkeypatch.setattr(
        cmd_search,
        "_semantic_search",
        _fake_semantic_search,
    )

    exit_code = cmd_search.run_search(
        _args(["consciousness"]),
        repo_root=repo_root,
        content_root=content_root,
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Mode: semantic" in output
    assert "0.910" in output
