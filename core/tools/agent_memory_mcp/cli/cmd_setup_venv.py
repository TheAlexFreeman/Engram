"""Create or refresh the repository ``.venv`` for the agent-memory MCP server."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


def _venv_python(repo_root: Path) -> Path:
    if os.name == "nt":
        return repo_root / ".venv" / "Scripts" / "python.exe"
    return repo_root / ".venv" / "bin" / "python"


def _run(
    argv: list[str],
    *,
    cwd: Path,
    dry_run: bool,
) -> int:
    if dry_run:
        print(f"Would run: {' '.join(argv)}  (cwd={cwd})")
        return 0
    proc = subprocess.run(argv, cwd=cwd, check=False)
    return int(proc.returncode)


def register_setup_venv(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
    *,
    parents: list[argparse.ArgumentParser] | None = None,
) -> argparse.ArgumentParser:
    parser = subparsers.add_parser(
        "setup-venv",
        help="Create or refresh .venv with MCP server dependencies (for Cursor / MCP configs).",
        parents=parents or [],
    )
    parser.add_argument(
        "--recreate",
        action="store_true",
        help="Remove an existing .venv and create a new one.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the commands that would run without executing them.",
    )
    parser.set_defaults(handler=run_setup_venv)
    return parser


def run_setup_venv(args: argparse.Namespace, *, repo_root: Path, content_root: Path) -> int:
    del content_root
    pyproject = repo_root / "pyproject.toml"
    if not pyproject.is_file():
        print(
            "Error: pyproject.toml not found; setup-venv must run against an Engram checkout.",
            file=sys.stderr,
        )
        return 2

    venv_dir = repo_root / ".venv"
    dry_run: bool = args.dry_run

    if args.recreate and venv_dir.exists():
        if dry_run:
            print(f"Would remove: {venv_dir}")
        else:
            shutil.rmtree(venv_dir)

    if not venv_dir.is_dir():
        code = _run(
            [sys.executable, "-m", "venv", str(venv_dir)],
            cwd=repo_root,
            dry_run=dry_run,
        )
        if code != 0:
            print("Error: failed to create virtual environment.", file=sys.stderr)
            return code

    venv_py = _venv_python(repo_root)
    if not dry_run and not venv_py.is_file():
        print(f"Error: expected venv interpreter missing: {venv_py}", file=sys.stderr)
        return 2

    for step in (
        [str(venv_py), "-m", "pip", "install", "--upgrade", "pip"],
        [str(venv_py), "-m", "pip", "install", "-e", ".[server]"],
    ):
        code = _run(step, cwd=repo_root, dry_run=dry_run)
        if code != 0:
            print("Error: pip step failed.", file=sys.stderr)
            return code

    if not dry_run:
        print("Engram MCP virtual environment is ready.")
        print(f"  Interpreter: {venv_py}")
        if os.name == "nt":
            print('  Cursor MCP (Windows): use "${workspaceFolder}/.venv/Scripts/python.exe"')
        else:
            print('  Cursor MCP (Unix): use "${workspaceFolder}/.venv/bin/python"')
        print(f"  Server script: {repo_root / 'core' / 'tools' / 'memory_mcp.py'}")
        print("Reload MCP in your editor after the first run.")

    return 0
