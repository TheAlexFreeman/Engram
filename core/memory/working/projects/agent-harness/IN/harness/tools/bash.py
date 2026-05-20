from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from .fs import WorkspaceScope

_DEFAULT_TIMEOUT = 120
_MAX_TIMEOUT = 600
_MAX_OUTPUT_CHARS = 80_000


def _resolve_bash_executable() -> str:
    """Pick a bash binary. Windows: Git for Windows before PATH (avoids broken WSL shims)."""
    override = os.environ.get("HARNESS_BASH", "").strip()
    if override:
        p = Path(override)
        if p.is_file():
            return str(p)
        raise FileNotFoundError(
            f"HARNESS_BASH is set to {override!r} but that file does not exist."
        )

    if sys.platform == "win32":
        seen: set[str] = set()
        candidates: list[Path] = []
        for env_key, tail in (
            ("ProgramFiles", Path("Git") / "bin" / "bash.exe"),
            ("ProgramFiles(x86)", Path("Git") / "bin" / "bash.exe"),
            ("LOCALAPPDATA", Path("Programs") / "Git" / "bin" / "bash.exe"),
        ):
            root = os.environ.get(env_key)
            if root:
                candidates.append(Path(root) / tail)
        # Some installs only ship usr\bin; try after standard bin paths.
        for env_key in ("ProgramFiles", "ProgramFiles(x86)"):
            root = os.environ.get(env_key)
            if root:
                candidates.append(Path(root) / "Git" / "usr" / "bin" / "bash.exe")

        for c in candidates:
            try:
                key = str(c.resolve())
            except OSError:
                key = str(c)
            if key in seen:
                continue
            seen.add(key)
            if c.is_file():
                return str(c)

    found = shutil.which("bash")
    if found:
        return found

    raise FileNotFoundError(
        "No bash executable found. On Windows install Git for Windows, or set HARNESS_BASH to the "
        r"full path of bash.exe (e.g. C:\Program Files\Git\bin\bash.exe)."
    )


class Bash:
    name = "bash"
    description = (
        "Run a shell command with bash (`bash -lc`). "
        "On Windows, Git for Windows bash is preferred over PATH so a broken WSL `bash` shim is not used; "
        "set HARNESS_BASH to force a specific bash.exe. "
        "Working directory defaults to the workspace root; optional `cwd` is a path relative to the workspace. "
        "Returns exit code plus stdout and stderr (combined, truncated if very long). "
        "Prefer dedicated file tools for reading and editing when they suffice."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "Shell command/script to run as a single string.",
            },
            "cwd": {
                "type": "string",
                "description": "Working directory relative to workspace. Defaults to '.'.",
            },
            "timeout_sec": {
                "type": "integer",
                "description": f"Seconds before the command is killed. Default {_DEFAULT_TIMEOUT}, max {_MAX_TIMEOUT}.",
            },
        },
        "required": ["command"],
    }

    def __init__(self, scope: WorkspaceScope):
        self.scope = scope

    def run(self, args: dict) -> str:
        command = (args.get("command") or "").strip()
        if not command:
            raise ValueError("command must be non-empty")

        cwd = self.scope.resolve(args.get("cwd", "."))
        if not cwd.is_dir():
            raise NotADirectoryError(f"cwd is not a directory: {args.get('cwd', '.')!r}")

        raw_timeout = args.get("timeout_sec", _DEFAULT_TIMEOUT)
        try:
            timeout = int(raw_timeout)
        except (TypeError, ValueError) as e:
            raise ValueError("timeout_sec must be an integer") from e
        timeout = max(1, min(timeout, _MAX_TIMEOUT))

        bash_exe = _resolve_bash_executable()
        try:
            completed = subprocess.run(
                [bash_exe, "-lc", command],
                cwd=cwd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                check=False,
            )
        except FileNotFoundError as e:
            raise FileNotFoundError(
                "bash executable disappeared or is not runnable. "
                "Install Git for Windows or set HARNESS_BASH to a valid bash.exe path."
            ) from e

        out = completed.stdout or ""
        err = completed.stderr or ""
        parts = [f"exit code: {completed.returncode}", ""]
        if out:
            parts.append(out)
        if err:
            if out:
                parts.append("")
            parts.append("--- stderr ---")
            parts.append(err)
        text = "\n".join(parts).rstrip() + "\n"

        if len(text) > _MAX_OUTPUT_CHARS:
            text = text[: _MAX_OUTPUT_CHARS] + f"\n\n[output truncated to {_MAX_OUTPUT_CHARS} characters]\n"

        return text
