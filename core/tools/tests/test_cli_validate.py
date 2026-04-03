from __future__ import annotations

import importlib
import json
import sys
import tempfile
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]


def _load_cmd_validate() -> ModuleType:
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    return importlib.import_module("engram_mcp.agent_memory_mcp.cli.cmd_validate")


cmd_validate = _load_cmd_validate()
Finding = importlib.import_module("engram_mcp.agent_memory_mcp.cli.validators").Finding
cli_main = importlib.import_module("engram_mcp.agent_memory_mcp.cli.main")


def _args(*, json_output: bool = False):
    return type("Args", (), {"json": json_output})()


def test_validate_clean_repo_returns_zero(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(cmd_validate, "validate_repo", lambda _root: [])

    exit_code = cmd_validate.run_validate(
        _args(), repo_root=REPO_ROOT, content_root=REPO_ROOT / "core"
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Validation passed with no findings." in output


def test_validate_missing_frontmatter_returns_warning(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        cmd_validate,
        "validate_repo",
        lambda _root: [
            Finding(
                severity="warning",
                path="core/memory/knowledge/software-engineering/cli-temp.md",
                message="missing YAML frontmatter",
            )
        ],
    )

    exit_code = cmd_validate.run_validate(
        _args(), repo_root=REPO_ROOT, content_root=REPO_ROOT / "core"
    )
    output = capsys.readouterr().out

    assert exit_code == 1
    assert "cli-temp.md" in output
    assert "missing YAML frontmatter" in output


def test_validate_broken_link_returns_error(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        cmd_validate,
        "validate_repo",
        lambda _root: [
            Finding(
                severity="error",
                path="core/memory/knowledge/software-engineering/cli-link.md",
                message="file references missing target 'memory/knowledge/does-not-exist.md'",
            )
        ],
    )

    exit_code = cmd_validate.run_validate(
        _args(), repo_root=REPO_ROOT, content_root=REPO_ROOT / "core"
    )
    output = capsys.readouterr().out

    assert exit_code == 2
    assert "does-not-exist.md" in output


def test_validate_json_output_is_array(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        cmd_validate,
        "validate_repo",
        lambda _root: [
            Finding(
                severity="warning",
                path="core/memory/knowledge/example.md",
                message="missing YAML frontmatter",
            )
        ],
    )

    exit_code = cmd_validate.run_validate(
        _args(json_output=True),
        repo_root=REPO_ROOT,
        content_root=REPO_ROOT / "core",
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 1
    assert isinstance(payload, list)


def test_resolve_repo_root_raises_for_non_engram_explicit_path() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        non_engram = Path(tmp) / "not-an-engram-repo"
        non_engram.mkdir()

        with pytest.raises(ValueError, match="does not appear to be an Engram repository root"):
            cli_main.resolve_repo_root(explicit_root=str(non_engram))


def test_resolve_repo_root_raises_for_non_engram_env_root() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        non_engram = Path(tmp) / "not-an-engram-repo"
        non_engram.mkdir()

        with pytest.raises(ValueError, match="does not appear to be an Engram repository root"):
            cli_main.resolve_repo_root(env={"MEMORY_REPO_ROOT": str(non_engram)})


def test_resolve_repo_root_accepts_valid_engram_root() -> None:
    result = cli_main.resolve_repo_root(explicit_root=str(REPO_ROOT))
    assert result == REPO_ROOT
