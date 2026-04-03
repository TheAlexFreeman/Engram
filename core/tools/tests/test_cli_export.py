from __future__ import annotations

import importlib
import json
import subprocess
import sys
import tarfile
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]


def _load_module(module_name: str) -> ModuleType:
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    return importlib.import_module(module_name)


cmd_export = _load_module("engram_mcp.agent_memory_mcp.cli.cmd_export")
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


def _seed_export_repo(tmp_path: Path) -> tuple[Path, Path]:
    repo_root = tmp_path / "repo"
    content_root = repo_root / "core"
    _write(content_root / "INIT.md", "# Init\n")
    _write(
        content_root / "governance" / "review-queue.md",
        "### [2026-04-03] Export fixture\n**Type:** proposed\n**Status:** pending\n",
    )
    _write(
        content_root / "memory" / "knowledge" / "topic.md",
        "---\ntrust: high\nsource: manual\ncreated: 2026-04-03\n---\n\n# Topic\n",
    )
    _init_git_repo(repo_root)
    return repo_root, content_root


def _args(
    *,
    bundle_format: str = "md",
    output: str | None = None,
    json_output: bool = False,
):
    return type(
        "Args",
        (),
        {
            "format": bundle_format,
            "output": output,
            "json": json_output,
        },
    )()


def test_export_json_writes_bundle_file_and_summary_json(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo_root, content_root = _seed_export_repo(tmp_path)
    bundle_path = tmp_path / "bundle.json"

    exit_code = cmd_export.run_export(
        _args(bundle_format="json", output=str(bundle_path), json_output=True),
        repo_root=repo_root,
        content_root=content_root,
    )
    payload = json.loads(capsys.readouterr().out)
    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert payload["format"] == "json"
    assert bundle["kind"] == "engram-portability-bundle"
    assert any(item["path"] == "core/memory/knowledge/topic.md" for item in bundle["files"])


def test_export_markdown_streams_bundle_to_stdout(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo_root, content_root = _seed_export_repo(tmp_path)

    exit_code = cmd_export.run_export(
        _args(bundle_format="md"),
        repo_root=repo_root,
        content_root=content_root,
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert output.startswith("---\nkind: engram-portability-bundle\n")
    assert "## File: core/memory/knowledge/topic.md" in output


def test_export_tar_writes_manifest_and_files(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo_root, content_root = _seed_export_repo(tmp_path)
    bundle_path = tmp_path / "bundle.tar"

    exit_code = cmd_export.run_export(
        _args(bundle_format="tar", output=str(bundle_path), json_output=True),
        repo_root=repo_root,
        content_root=content_root,
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["format"] == "tar"
    with tarfile.open(bundle_path, "r") as archive:
        names = archive.getnames()
    assert "manifest.json" in names
    assert "core/memory/knowledge/topic.md" in names


def test_export_command_is_registered_in_main_parser() -> None:
    parser = cli_main.build_parser()
    args = parser.parse_args(["export", "--format", "json", "--output", "bundle.json"])

    assert args.command == "export"
    assert args.format == "json"
    assert args.output == "bundle.json"
    assert args.handler is cmd_export.run_export
