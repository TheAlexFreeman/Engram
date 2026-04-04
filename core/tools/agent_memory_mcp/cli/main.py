"""Console entry point for the lightweight Engram terminal CLI."""

from __future__ import annotations

import argparse
import os
import re
import sys
from collections.abc import Mapping, Sequence
from importlib import metadata
from pathlib import Path


def _candidate_root(path_like: str | Path) -> Path:
    candidate = Path(path_like).expanduser().resolve()
    if candidate.is_dir():
        return candidate

    existing_parent = candidate
    while not existing_parent.exists() and existing_parent != existing_parent.parent:
        existing_parent = existing_parent.parent
    if existing_parent.is_dir():
        return existing_parent
    raise ValueError(f"Repository root is not a directory: {candidate}")


def _looks_like_repo_root(path: Path) -> bool:
    return (
        (path / "agent-bootstrap.toml").exists()
        or ((path / "core" / "INIT.md").exists() and (path / "pyproject.toml").exists())
        or ((path / "INIT.md").exists() and (path / "pyproject.toml").exists())
    )


def _walk_for_repo_root(start: Path) -> Path | None:
    current = start.resolve()
    for candidate in (current, *current.parents):
        if _looks_like_repo_root(candidate):
            return candidate
    return None


def resolve_repo_root(
    explicit_root: str | None = None,
    env: Mapping[str, str] | None = None,
    cwd: Path | None = None,
) -> Path:
    """Resolve the Engram repository root.

    Resolution order:
    1. Explicit ``--repo-root`` value.
    2. ``MEMORY_REPO_ROOT`` / ``AGENT_MEMORY_ROOT``.
    3. Walk upward from the current working directory.
    4. Fall back to the repository containing this module.
    """

    environment = dict(env or os.environ)

    for candidate in (
        explicit_root,
        environment.get("MEMORY_REPO_ROOT"),
        environment.get("AGENT_MEMORY_ROOT"),
    ):
        if not candidate:
            continue
        resolved = _candidate_root(candidate)
        walked = _walk_for_repo_root(resolved)
        if walked is not None:
            return walked
        raise ValueError(
            f"'{candidate}' does not appear to be an Engram repository root. "
            "Ensure the path contains agent-bootstrap.toml or "
            "core/INIT.md alongside pyproject.toml."
        )

    walked = _walk_for_repo_root(cwd or Path.cwd())
    if walked is not None:
        return walked

    return Path(__file__).resolve().parents[4]


def resolve_content_root(repo_root: Path, env: Mapping[str, str] | None = None) -> Path:
    environment = dict(env or os.environ)
    content_prefix = environment.get("MEMORY_CORE_PREFIX", "core")
    candidate = repo_root / content_prefix
    if (candidate / "memory").exists():
        return candidate
    return repo_root


def _package_version(repo_root: Path) -> str:
    try:
        return metadata.version("agent-memory-mcp")
    except metadata.PackageNotFoundError:
        pyproject = repo_root / "pyproject.toml"
        if pyproject.exists():
            match = re.search(
                r'^version\s*=\s*"(?P<version>[^"]+)"',
                pyproject.read_text(encoding="utf-8"),
                re.MULTILINE,
            )
            if match is not None:
                return match.group("version")
    return "0.1.0"


def _add_common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON output where supported.",
    )
    parser.add_argument(
        "--repo-root",
        help="Engram repository root (default: env vars, cwd walk, then file-relative fallback).",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="engram",
        description="Terminal commands for searching, inspecting, and validating an Engram repo.",
    )
    _add_common_arguments(parser)
    parser.add_argument(
        "--version",
        action="store_true",
        help="Print the installed Engram package version.",
    )

    common_parser = argparse.ArgumentParser(add_help=False)
    _add_common_arguments(common_parser)
    subparsers = parser.add_subparsers(dest="command")

    from .cmd_add import register_add
    from .cmd_aggregate import register_aggregate
    from .cmd_approval import register_approval
    from .cmd_archive import register_archive
    from .cmd_diff import register_diff
    from .cmd_export import register_export
    from .cmd_import import register_import
    from .cmd_init import register_init
    from .cmd_log import register_log
    from .cmd_plan import register_plan
    from .cmd_project import register_project
    from .cmd_promote import register_promote
    from .cmd_recall import register_recall
    from .cmd_review import register_review
    from .cmd_search import register_search
    from .cmd_setup_venv import register_setup_venv
    from .cmd_status import register_status
    from .cmd_trace import register_trace
    from .cmd_validate import register_validate

    register_init(subparsers, parents=[common_parser])
    register_search(subparsers, parents=[common_parser])
    register_status(subparsers, parents=[common_parser])
    register_add(subparsers, parents=[common_parser])
    register_archive(subparsers, parents=[common_parser])
    register_approval(subparsers, parents=[common_parser])
    register_aggregate(subparsers, parents=[common_parser])
    register_diff(subparsers, parents=[common_parser])
    register_export(subparsers, parents=[common_parser])
    register_import(subparsers, parents=[common_parser])
    register_promote(subparsers, parents=[common_parser])
    register_review(subparsers, parents=[common_parser])
    register_recall(subparsers, parents=[common_parser])
    register_log(subparsers, parents=[common_parser])
    register_plan(subparsers, parents=[common_parser])
    register_project(subparsers, parents=[common_parser])
    register_trace(subparsers, parents=[common_parser])
    register_validate(subparsers, parents=[common_parser])
    register_setup_venv(subparsers, parents=[common_parser])
    return parser


# Subcommands that run from a host repo rather than an Engram checkout.
_HOST_REPO_COMMANDS = frozenset({"init"})


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    command = getattr(args, "command", None)

    # 'init' operates on the host repo, not an Engram checkout — skip normal
    # repo-root resolution and pass cwd as a placeholder.
    if command in _HOST_REPO_COMMANDS:
        repo_root = Path.cwd()
        content_root = repo_root
    else:
        repo_root = resolve_repo_root(getattr(args, "repo_root", None))
        content_root = resolve_content_root(repo_root)

    if args.version:
        print(_package_version(repo_root))
        return 0

    if not command:
        parser.print_help()
        return 0

    handler = getattr(args, "handler", None)
    if not callable(handler):
        parser.print_help()
        return 2

    try:
        return int(handler(args, repo_root=repo_root, content_root=content_root))
    except BrokenPipeError:
        return 1
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
