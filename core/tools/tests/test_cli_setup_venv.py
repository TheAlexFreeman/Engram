from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]


def _load_cmd() -> ModuleType:
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    return importlib.import_module("engram_mcp.agent_memory_mcp.cli.cmd_setup_venv")


cmd_setup_venv = _load_cmd()
cli_main = importlib.import_module("engram_mcp.agent_memory_mcp.cli.main")


def _args(*, recreate: bool = False, dry_run: bool = False):
    return type("Args", (), {"recreate": recreate, "dry_run": dry_run})()


def test_setup_venv_parser_registered() -> None:
    parser = cli_main.build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["setup-venv", "--help"])


def test_setup_venv_dry_run_calls_expected_commands(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    fake_root = tmp_path / "repo"
    fake_root.mkdir()
    (fake_root / "pyproject.toml").write_text(
        (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    recorded: list[tuple[list[str], Path]] = []

    def fake_run(argv: list[str], *, cwd: Path, dry_run: bool) -> int:
        assert dry_run is True
        recorded.append((list(argv), cwd))
        return 0

    monkeypatch.setattr(cmd_setup_venv, "_run", fake_run)

    exit_code = cmd_setup_venv.run_setup_venv(
        _args(dry_run=True), repo_root=fake_root, content_root=fake_root / "core"
    )

    assert exit_code == 0
    assert len(recorded) == 3
    assert recorded[0][0][:3] == [sys.executable, "-m", "venv"]
    assert recorded[0][0][-1] == str(fake_root / ".venv")
    assert recorded[0][1] == fake_root

    venv_py = cmd_setup_venv._venv_python(fake_root)
    assert recorded[1][0] == [str(venv_py), "-m", "pip", "install", "--upgrade", "pip"]
    assert recorded[1][1] == fake_root
    assert recorded[2][0] == [str(venv_py), "-m", "pip", "install", "-e", ".[server]"]
    assert recorded[2][1] == fake_root


def test_setup_venv_missing_pyproject_returns_two(tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    exit_code = cmd_setup_venv.run_setup_venv(_args(), repo_root=empty, content_root=empty / "core")
    assert exit_code == 2
