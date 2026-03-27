#!/usr/bin/env python3
"""Refresh or verify the setup initial-commit manifest from repo files."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

MANIFEST_PATH = Path("HUMANS/setup/initial-commit-paths.txt")
SCRIPT_PATH = Path("HUMANS/tooling/scripts/generate_initial_commit_manifest.py")
DEFAULT_HEADER = [
    "# Canonical allowlist for the first setup commit.",
    "# Refresh with: python HUMANS/tooling/scripts/generate_initial_commit_manifest.py",
    "# Generated repo-local files such as chatgpt-instructions.txt and system-prompt.txt",
    "# are intentionally excluded so they remain local artifacts.",
]


def _read_header(text: str) -> list[str]:
    header: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#") or (not stripped and header):
            header.append(line.rstrip())
            continue
        if not stripped and not header:
            continue
        break
    return header or DEFAULT_HEADER


def _tracked_paths(repo_root: Path) -> list[str]:
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )
    paths = {line.strip() for line in result.stdout.splitlines() if line.strip()}
    if SCRIPT_PATH.exists():
        paths.add(SCRIPT_PATH.as_posix())
    return sorted(paths)


def render_manifest(repo_root: Path, existing_text: str) -> str:
    header = [line.rstrip() for line in _read_header(existing_text)]
    while header and not header[-1]:
        header.pop()
    body = _tracked_paths(repo_root)
    return "\n".join([*header, "", *body]) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Refresh or verify HUMANS/setup/initial-commit-paths.txt.",
    )
    parser.add_argument("repo_root", nargs="?", default=".", help="Repository root.")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail if the manifest is not up to date.",
    )
    args = parser.parse_args(argv)

    repo_root = Path(args.repo_root).resolve()
    manifest_path = repo_root / MANIFEST_PATH
    existing_text = manifest_path.read_text(encoding="utf-8") if manifest_path.exists() else ""
    rendered = render_manifest(repo_root, existing_text)

    if args.check:
        if existing_text != rendered:
            print(
                f"{MANIFEST_PATH.as_posix()} is stale. "
                "Run: python HUMANS/tooling/scripts/generate_initial_commit_manifest.py",
                file=sys.stderr,
            )
            return 1
        print(f"{MANIFEST_PATH.as_posix()} is up to date.")
        return 0

    manifest_path.write_text(rendered, encoding="utf-8")
    print(f"Wrote {MANIFEST_PATH.as_posix()}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
