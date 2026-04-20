from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import fnmatch

from .scope import (
    MAX_GREP_BYTES_PER_FILE,
    MAX_GREP_FILES_SCANNED,
    MAX_GREP_MATCHES,
    WorkspaceScope,
)


class GrepWorkspace:
    name = "grep_workspace"
    description = (
        "Search file contents under the workspace with a regular expression (multiline). "
        "Uses ripgrep (rg) when available for speed and .gitignore awareness; otherwise "
        "falls back to a bounded Python scan. Results are capped; paths are workspace-relative."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "pattern": {"type": "string", "description": "Regular expression (Python re syntax)."},
            "path": {
                "type": "string",
                "description": "Directory under workspace to search. Default '.'.",
            },
            "glob": {
                "type": "string",
                "description": "Optional glob filter (e.g. '*.py'). Passed to rg as -g when using rg.",
            },
            "max_matches": {
                "type": "integer",
                "description": f"Maximum matches to report. Default {MAX_GREP_MATCHES}.",
            },
            "context_lines": {
                "type": "integer",
                "description": "Lines of context before/after each match (rg only). Default 0.",
            },
        },
        "required": ["pattern"],
    }

    def __init__(self, scope: WorkspaceScope):
        self.scope = scope

    def run(self, args: dict) -> str:
        pattern = args["pattern"]
        rel_base = args.get("path", ".")
        search_root = self.scope.resolve(rel_base)
        if not search_root.is_dir():
            raise ValueError("path must be a directory")
        max_matches = int(args.get("max_matches") or MAX_GREP_MATCHES)
        max_matches = min(max(max_matches, 1), MAX_GREP_MATCHES)
        context = int(args.get("context_lines") or 0)
        context = max(0, min(context, 5))
        file_glob = args.get("glob")

        rg = shutil.which("rg")
        if rg:
            return self._run_rg(
                rg, pattern, search_root, file_glob, max_matches, context
            )
        return self._run_python(pattern, search_root, max_matches, file_glob)

    def _run_rg(
        self,
        rg: str,
        pattern: str,
        search_root: Path,
        file_glob: str | None,
        max_matches: int,
        context: int,
    ) -> str:
        root_r = self.scope._root_resolved()
        argv = [
            rg,
            "--json",
            "--max-count",
            str(max_matches),
            "-S",
        ]
        if context > 0:
            argv.extend(["-C", str(context)])
        if file_glob:
            argv.extend(["--glob", file_glob])
        argv.extend([pattern, "."])
        try:
            proc = subprocess.run(
                argv,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=120,
                check=False,
                cwd=str(search_root.resolve()),
            )
        except subprocess.TimeoutExpired:
            return "grep_workspace: rg timed out after 120s"
        if proc.returncode not in (0, 1):
            err = (proc.stderr or "").strip()
            return f"grep_workspace: rg failed (exit {proc.returncode}): {err}"

        out_lines: list[str] = []
        for raw in (proc.stdout or "").splitlines():
            if len(out_lines) >= max_matches:
                break
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if msg.get("type") != "match":
                continue
            data = msg.get("data") or {}
            path_obj = data.get("path") or {}
            if isinstance(path_obj, dict):
                fpath = path_obj.get("text")
            else:
                fpath = str(path_obj) if path_obj else None
            if not fpath:
                continue
            abs_path = Path(fpath)
            try:
                ar = abs_path.resolve()
                rel = ar.relative_to(root_r).as_posix()
            except (ValueError, OSError):
                try:
                    rel = Path(fpath).as_posix()
                except OSError:
                    rel = str(fpath)
            line_no = data.get("line_number")
            if not isinstance(line_no, int):
                line_no = 0
            subl = data.get("lines", {}) or {}
            text = (subl.get("text") or "").rstrip("\n").replace("\n", "\\n")
            if len(text) > 240:
                text = text[:240] + "..."
            out_lines.append(f"{rel}:{line_no}:{text}")

        if not out_lines:
            return "(no matches)"
        body = "\n".join(out_lines)
        if len(out_lines) >= max_matches:
            body += f"\n\n[harness: capped at max_matches={max_matches}]"
        return body

    def _run_python(
        self,
        pattern: str,
        search_root: Path,
        max_matches: int,
        file_glob: str | None,
    ) -> str:
        root_r = self.scope._root_resolved()
        try:
            rx = re.compile(pattern, re.MULTILINE)
        except re.error as e:
            raise ValueError(f"invalid regex: {e}") from e

        matches_out: list[str] = []
        files_seen = 0
        for dirpath, dirnames, filenames in os.walk(
            search_root, topdown=True, followlinks=False
        ):
            _prune_hidden(dirnames)
            for name in sorted(filenames):
                if len(matches_out) >= max_matches:
                    break
                fp = Path(dirpath) / name
                files_seen += 1
                if files_seen > MAX_GREP_FILES_SCANNED:
                    suffix = (
                        f"\n\n[harness: scanned file limit {MAX_GREP_FILES_SCANNED}; "
                        "install ripgrep for full-repo search]"
                    )
                    return ("\n".join(matches_out) + suffix) if matches_out else (
                        f"(no matches in first {MAX_GREP_FILES_SCANNED} files)" + suffix
                    )
                try:
                    rel_file = fp.resolve().relative_to(root_r).as_posix()
                except ValueError:
                    continue
                if file_glob and not _python_glob_matches(rel_file, name, file_glob):
                    continue
                if not fp.is_file():
                    continue
                try:
                    data = fp.read_bytes()
                except OSError:
                    continue
                if b"\x00" in data[:8192]:
                    continue
                text = data[:MAX_GREP_BYTES_PER_FILE].decode("utf-8", errors="replace")
                for m in rx.finditer(text):
                    if len(matches_out) >= max_matches:
                        break
                    line_no = text.count("\n", 0, m.start()) + 1
                    snippet = m.group(0).replace("\n", "\\n")
                    if len(snippet) > 200:
                        snippet = snippet[:200] + "..."
                    matches_out.append(f"{rel_file}:{line_no}:{snippet}")
            if len(matches_out) >= max_matches:
                break

        if not matches_out:
            return "(no matches)"
        body = "\n".join(matches_out)
        if len(matches_out) >= max_matches:
            body += f"\n\n[harness: capped at max_matches={max_matches}]"
        return body


def _prune_hidden(dirnames: list[str]) -> None:
    dirnames[:] = [d for d in dirnames if not d.startswith(".")]


def _python_glob_matches(rel_file: str, basename: str, file_glob: str) -> bool:
    """fnmatch on basename when pattern has no path sep; else match on posix rel path."""
    g = file_glob.replace("\\", "/")
    if "/" not in g and "**" not in g:
        return fnmatch.fnmatch(basename, g)
    rel = rel_file.replace("\\", "/")
    return fnmatch.fnmatch(rel, g)
