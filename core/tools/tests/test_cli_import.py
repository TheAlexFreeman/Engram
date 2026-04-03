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


cmd_export = _load_module("engram_mcp.agent_memory_mcp.cli.cmd_export")
cmd_import = _load_module("engram_mcp.agent_memory_mcp.cli.cmd_import")
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


def _seed_source_repo(tmp_path: Path) -> tuple[Path, Path]:
    repo_root = tmp_path / "source"
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


def _seed_target_repo(tmp_path: Path, *, conflict: bool = False) -> tuple[Path, Path]:
    repo_root = tmp_path / "target"
    content_root = repo_root / "core"
    _write(content_root / "INIT.md", "# Init\n")
    _write(content_root / "memory" / "knowledge" / "SUMMARY.md", "# Knowledge\n")
    if conflict:
        _write(
            content_root / "memory" / "knowledge" / "topic.md",
            "---\ntrust: low\nsource: manual\ncreated: 2026-04-03\n---\n\n# Different Topic\n",
        )
    _init_git_repo(repo_root)
    return repo_root, content_root


def _export_args(
    *, bundle_format: str = "json", output: str | None = None, json_output: bool = False
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


def _import_args(
    source: str,
    *,
    json_output: bool = False,
    apply: bool = False,
    overwrite: bool = False,
):
    return type(
        "Args",
        (),
        {
            "source": source,
            "json": json_output,
            "apply": apply,
            "overwrite": overwrite,
        },
    )()


def test_import_preview_reports_conflicts_without_writing(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source_repo, source_root = _seed_source_repo(tmp_path)
    target_repo, target_root = _seed_target_repo(tmp_path, conflict=True)
    bundle_path = tmp_path / "bundle.json"

    cmd_export.run_export(
        _export_args(bundle_format="json", output=str(bundle_path)),
        repo_root=source_repo,
        content_root=source_root,
    )
    capsys.readouterr()

    exit_code = cmd_import.run_import(
        _import_args(str(bundle_path), json_output=True),
        repo_root=target_repo,
        content_root=target_root,
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["preview"]["mode"] == "preview"
    assert payload["new_state"]["can_apply"] is False
    assert "core/memory/knowledge/topic.md" in payload["new_state"]["existing_conflicts"]


def test_import_apply_writes_new_files_and_commits(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source_repo, source_root = _seed_source_repo(tmp_path)
    target_repo, target_root = _seed_target_repo(tmp_path, conflict=False)
    bundle_path = tmp_path / "bundle.json"

    cmd_export.run_export(
        _export_args(bundle_format="json", output=str(bundle_path)),
        repo_root=source_repo,
        content_root=source_root,
    )
    capsys.readouterr()

    exit_code = cmd_import.run_import(
        _import_args(str(bundle_path), json_output=True, apply=True),
        repo_root=target_repo,
        content_root=target_root,
    )
    payload = json.loads(capsys.readouterr().out)

    imported_file = target_root / "memory" / "knowledge" / "topic.md"
    assert exit_code == 0
    assert payload["commit_sha"]
    assert "core/memory/knowledge/topic.md" in payload["new_state"]["created_paths"]
    assert imported_file.exists()
    assert "# Topic" in imported_file.read_text(encoding="utf-8")


def test_import_rejects_invalid_bundle_in_json_mode(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    target_repo, target_root = _seed_target_repo(tmp_path, conflict=False)
    bundle_path = tmp_path / "invalid.json"
    bundle_path.write_text("{}\n", encoding="utf-8")

    exit_code = cmd_import.run_import(
        _import_args(str(bundle_path), json_output=True),
        repo_root=target_repo,
        content_root=target_root,
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 2
    assert payload["valid"] is False
    assert payload["errors"]


def test_import_preview_accepts_markdown_bundle_with_nested_fences(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source_repo, source_root = _seed_source_repo(tmp_path)
    target_repo, target_root = _seed_target_repo(tmp_path, conflict=False)
    bundle_path = tmp_path / "bundle.md"

    _write(
        source_root / "memory" / "knowledge" / "rich.md",
        "---\n"
        "trust: high\n"
        "source: manual\n"
        "created: 2026-04-03\n"
        "---\n\n"
        "## File: not a bundle header\n\n"
        "````yaml\n"
        "key: value\n"
        "````\n",
    )

    export_exit = cmd_export.run_export(
        _export_args(bundle_format="md", output=str(bundle_path)),
        repo_root=source_repo,
        content_root=source_root,
    )
    export_output = capsys.readouterr().out

    import_exit = cmd_import.run_import(
        _import_args(str(bundle_path), json_output=True),
        repo_root=target_repo,
        content_root=target_root,
    )
    payload = json.loads(capsys.readouterr().out)
    bundle_text = bundle_path.read_text(encoding="utf-8")

    assert export_exit == 0
    assert "Exported bundle:" in export_output
    assert "`````markdown" in bundle_text

    assert import_exit == 0
    assert payload["preview"]["mode"] == "preview"
    assert payload["new_state"]["format"] == "md"
    assert payload["new_state"]["can_apply"] is True


def test_import_command_is_registered_in_main_parser() -> None:
    parser = cli_main.build_parser()
    args = parser.parse_args(["import", "bundle.json", "--apply", "--overwrite", "--json"])

    assert args.command == "import"
    assert args.apply is True
    assert args.overwrite is True
    assert args.json is True
    assert args.handler is cmd_import.run_import


def test_import_preview_treats_directory_path_collision_as_conflict(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source_repo, source_root = _seed_source_repo(tmp_path)
    target_repo, target_root = _seed_target_repo(tmp_path, conflict=False)
    bundle_path = tmp_path / "bundle.json"

    cmd_export.run_export(
        _export_args(bundle_format="json", output=str(bundle_path)),
        repo_root=source_repo,
        content_root=source_root,
    )
    capsys.readouterr()

    # Place a directory at the path where a bundle file would be written.
    collision_dir = target_root / "memory" / "knowledge" / "topic.md"
    collision_dir.mkdir(parents=True, exist_ok=True)

    exit_code = cmd_import.run_import(
        _import_args(str(bundle_path), json_output=True),
        repo_root=target_repo,
        content_root=target_root,
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["preview"]["mode"] == "preview"
    assert payload["new_state"]["can_apply"] is False
    assert "core/memory/knowledge/topic.md" in payload["new_state"]["existing_conflicts"]
