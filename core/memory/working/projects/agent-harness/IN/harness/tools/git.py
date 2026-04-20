from __future__ import annotations

import shutil
import subprocess
from typing import Any

from .fs import WorkspaceScope

_MAX_OUTPUT_CHARS = 80_000
_TIMEOUT = 60

_FORBIDDEN_ARG_TOKENS = frozenset(
    {"--force", "-f", "--force-with-lease", "--force-with-lease=", "--hard"}
)

_ALLOWED_SUBCOMMANDS = frozenset(
    {
        "status",
        "diff",
        "log",
        "show",
        "blame",
        "ls-files",
        "branch",
        "tag",
        "add",
        "rm",
        "mv",
        "checkout",
        "switch",
        "restore",
        "commit",
    }
)


def _format_output(returncode: int, stdout: str, stderr: str) -> str:
    parts = [f"exit code: {returncode}", ""]
    if stdout:
        parts.append(stdout)
    if stderr:
        if stdout:
            parts.append("")
        parts.append("--- stderr ---")
        parts.append(stderr)
    text = "\n".join(parts).rstrip() + "\n"
    if len(text) > _MAX_OUTPUT_CHARS:
        text = (
            text[:_MAX_OUTPUT_CHARS]
            + f"\n\n[output truncated to {_MAX_OUTPUT_CHARS} characters]\n"
        )
    return text


def _run_git(scope: WorkspaceScope, argv: list[str], *, cwd: str = ".") -> str:
    git = shutil.which("git")
    if git is None:
        raise FileNotFoundError("git is not on PATH")
    work = scope.resolve(cwd)
    if not work.is_dir():
        raise NotADirectoryError(f"cwd is not a directory: {cwd!r}")
    try:
        completed = subprocess.run(
            [git, *argv],
            cwd=work,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=_TIMEOUT,
            check=False,
        )
    except subprocess.TimeoutExpired as e:
        raise TimeoutError(
            f"git {' '.join(argv[:2])} timed out after {_TIMEOUT}s"
        ) from e
    return _format_output(
        completed.returncode, completed.stdout or "", completed.stderr or ""
    )


def _optional_str(args: dict, key: str) -> str | None:
    val = args.get(key)
    if val is None:
        return None
    if not isinstance(val, str):
        raise ValueError(f"{key} must be a string")
    val = val.strip()
    return val or None


def _bool(args: dict, key: str, default: bool = False) -> bool:
    val = args.get(key, default)
    if isinstance(val, bool):
        return val
    raise ValueError(f"{key} must be a boolean")


def _validate_rev_range(rev: str) -> str:
    for bad in (" ", "\t", ";", "|", "&", "`", "$("):
        if bad in rev:
            raise ValueError(f"rev_range contains forbidden token {bad!r}")
    return rev


class GitStatus:
    name = "git_status"
    description = (
        "Show git working-tree status using `git status --short --branch`. "
        "Optional `path` scopes the listing to a subdirectory (relative to the workspace)."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Optional workspace-relative subpath to scope status to.",
            },
        },
    }

    def __init__(self, scope: WorkspaceScope):
        self.scope = scope

    def run(self, args: dict) -> str:
        argv = ["status", "--short", "--branch"]
        path = _optional_str(args, "path")
        if path is not None:
            self.scope.resolve(path)
            argv.extend(["--", path])
        return _run_git(self.scope, argv)


class GitDiff:
    name = "git_diff"
    description = (
        "Show a git diff. Defaults to the unstaged working-tree diff. "
        "Set `staged=true` for the index diff (`--cached`), pass `rev_range` "
        "(e.g. 'HEAD~3..HEAD') to diff between revisions, and `path` to limit to a file or dir. "
        "Use `stat=true` to get a summary (`--stat`) instead of the full patch when output is large."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "staged": {
                "type": "boolean",
                "description": "Diff the index against HEAD (adds --cached). Default false.",
            },
            "path": {
                "type": "string",
                "description": "Optional workspace-relative path to limit the diff.",
            },
            "rev_range": {
                "type": "string",
                "description": "Optional revision or range, e.g. 'HEAD~1', 'main..HEAD'.",
            },
            "stat": {
                "type": "boolean",
                "description": "If true, show --stat summary instead of full patch. Default false.",
            },
        },
    }

    def __init__(self, scope: WorkspaceScope):
        self.scope = scope

    def run(self, args: dict) -> str:
        argv = ["diff"]
        if _bool(args, "staged"):
            argv.append("--cached")
        if _bool(args, "stat"):
            argv.append("--stat")
        rev = _optional_str(args, "rev_range")
        if rev is not None:
            argv.append(_validate_rev_range(rev))
        path = _optional_str(args, "path")
        if path is not None:
            self.scope.resolve(path)
            argv.extend(["--", path])
        out = _run_git(self.scope, argv)
        if "[output truncated" in out:
            out += (
                "hint: output was truncated; narrow with `path` or set `stat=true` "
                "for a summary.\n"
            )
        return out


class GitLog:
    name = "git_log"
    description = (
        "Show git commit history. Defaults to a compact graph with decorations "
        "(`--oneline --decorate --graph`). Set `oneline=false` for full author/date bodies. "
        "`max_count` defaults to 20 (max 200); `path` limits to one file or dir."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "max_count": {
                "type": "integer",
                "description": "Max commits to show (default 20, max 200).",
            },
            "path": {
                "type": "string",
                "description": "Optional workspace-relative path to limit history.",
            },
            "oneline": {
                "type": "boolean",
                "description": "Compact one-line output with graph/decoration. Default true.",
            },
        },
    }

    def __init__(self, scope: WorkspaceScope):
        self.scope = scope

    def run(self, args: dict) -> str:
        raw = args.get("max_count", 20)
        try:
            n = int(raw)
        except (TypeError, ValueError) as e:
            raise ValueError("max_count must be an integer") from e
        n = max(1, min(n, 200))

        oneline = _bool(args, "oneline", default=True)
        argv = ["log", f"-n{n}"]
        if oneline:
            argv.extend(["--oneline", "--decorate", "--graph"])
        else:
            argv.extend(["--decorate", "--date=iso"])

        path = _optional_str(args, "path")
        if path is not None:
            self.scope.resolve(path)
            argv.extend(["--", path])
        return _run_git(self.scope, argv)


class GitCommit:
    name = "git_commit"
    description = (
        "Create a git commit. `message` is required and passed via argv (-m). "
        "Set `all=true` to stage tracked changes (`-a`), `allow_empty=true` for "
        "`--allow-empty`, or `amend=true` to amend the last commit (you must still "
        "supply a message). Does not support author overrides, signing, or skipping hooks; "
        "use the `bash` tool for those rare cases."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "message": {
                "type": "string",
                "description": "Commit message (required, non-empty).",
            },
            "all": {
                "type": "boolean",
                "description": "Stage modified/deleted tracked files before committing. Default false.",
            },
            "allow_empty": {
                "type": "boolean",
                "description": "Allow a commit with no staged changes. Default false.",
            },
            "amend": {
                "type": "boolean",
                "description": "Amend the last commit with the supplied message. Default false.",
            },
        },
        "required": ["message"],
    }

    def __init__(self, scope: WorkspaceScope):
        self.scope = scope

    def run(self, args: dict) -> str:
        message = args.get("message")
        if not isinstance(message, str) or not message.strip():
            raise ValueError("message must be a non-empty string")

        argv = ["commit", "-m", message]
        if _bool(args, "all"):
            argv.append("-a")
        if _bool(args, "allow_empty"):
            argv.append("--allow-empty")
        if _bool(args, "amend"):
            argv.append("--amend")
        return _run_git(self.scope, argv)


class Git:
    name = "git"
    description = (
        "Run an allowlisted git subcommand with arbitrary string arguments. "
        "Arguments are passed directly as argv (no shell), so quoting is not needed. "
        "Allowed subcommands: "
        + ", ".join(sorted(_ALLOWED_SUBCOMMANDS))
        + ". Destructive flags (--force, -f, --force-with-lease, --hard) are rejected. "
        "For common flows, prefer git_status / git_diff / git_log / git_commit."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "subcommand": {
                "type": "string",
                "description": "Git subcommand (e.g. 'show', 'branch', 'checkout').",
            },
            "args": {
                "type": "array",
                "description": "Additional arguments, passed verbatim as argv.",
                "items": {"type": "string"},
            },
        },
        "required": ["subcommand"],
    }

    def __init__(self, scope: WorkspaceScope):
        self.scope = scope

    def run(self, args: dict) -> str:
        sub = args.get("subcommand")
        if not isinstance(sub, str) or not sub.strip():
            raise ValueError("subcommand must be a non-empty string")
        sub = sub.strip()
        if sub not in _ALLOWED_SUBCOMMANDS:
            raise ValueError(
                f"subcommand {sub!r} is not allowed. "
                f"Allowed: {', '.join(sorted(_ALLOWED_SUBCOMMANDS))}"
            )

        raw_args: Any = args.get("args", [])
        if raw_args is None:
            raw_args = []
        if not isinstance(raw_args, list):
            raise ValueError("args must be an array of strings")

        argv_extra: list[str] = []
        for i, a in enumerate(raw_args):
            if not isinstance(a, str):
                raise ValueError(f"args[{i}] must be a string")
            if a in _FORBIDDEN_ARG_TOKENS:
                raise ValueError(f"argument {a!r} is not allowed")
            if a.startswith("--force-with-lease="):
                raise ValueError(f"argument {a!r} is not allowed")
            if a.startswith("--exec=") or "$(" in a or "`" in a:
                raise ValueError(f"argument {a!r} contains a forbidden token")
            argv_extra.append(a)

        return _run_git(self.scope, [sub, *argv_extra])
