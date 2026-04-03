"""Implementation of the ``engram diff`` command."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from ..errors import ValidationError
from .formatting import format_snippet, namespace_prefixes, parse_iso_date, visible_namespace

_STATUS_LABELS = {
    "A": "added",
    "C": "copied",
    "D": "deleted",
    "M": "modified",
    "R": "renamed",
    "T": "type-changed",
}

_STATUS_ORDER = ("added", "modified", "deleted", "renamed", "copied", "type-changed")


def register_diff(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
    *,
    parents: list[argparse.ArgumentParser] | None = None,
) -> argparse.ArgumentParser:
    parser = subparsers.add_parser(
        "diff",
        help="Inspect memory-history changes with namespace and date filters.",
        parents=parents or [],
    )
    parser.add_argument(
        "--namespace",
        help="Restrict results to a namespace or repo-relative memory prefix such as knowledge or memory/skills.",
    )
    parser.add_argument(
        "--since",
        help="Only include commits on or after YYYY-MM-DD.",
    )
    parser.add_argument(
        "--until",
        help="Only include commits on or before YYYY-MM-DD.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum number of commits to inspect.",
    )
    parser.set_defaults(handler=run_diff)
    return parser


def _content_prefix(repo_root: Path, content_root: Path) -> str:
    try:
        return content_root.relative_to(repo_root).as_posix().strip("/")
    except ValueError:
        return ""


def _to_git_path(content_rel: str, *, content_prefix: str) -> str:
    normalized = content_rel.replace("\\", "/").strip("/")
    if not normalized:
        return content_prefix
    if content_prefix:
        return f"{content_prefix}/{normalized}"
    return normalized


def _from_git_path(git_rel: str, *, content_prefix: str) -> str:
    normalized = git_rel.replace("\\", "/").strip("/")
    if content_prefix:
        prefix = f"{content_prefix}/"
        if normalized.startswith(prefix):
            return normalized[len(prefix) :]
    return normalized


def _namespace_label(path: str) -> str:
    normalized = path.replace("\\", "/").lstrip("/")
    if normalized in ("memory/working/USER.md", "memory/working/CURRENT.md"):
        return "scratchpad"
    if normalized.startswith("memory/working/notes/"):
        return "scratchpad"
    return visible_namespace(normalized)


def _run_git(repo_root: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git", *args],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
        check=False,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip() or result.stdout.strip() or "git command failed"
        raise RuntimeError(stderr)
    return result


def _list_commits(
    repo_root: Path,
    *,
    git_paths: list[str],
    limit: int,
    since: str | None,
    until: str | None,
) -> list[dict[str, Any]]:
    record_sep = "\x1e"
    field_sep = "\x1f"
    cmd = [
        "log",
        "--date=short",
        f"--format={record_sep}%H{field_sep}%ad{field_sep}%s{field_sep}%P",
    ]
    if not since and not until:
        cmd.append(f"-{limit}")
    cmd += ["--", *git_paths]
    raw = _run_git(repo_root, cmd).stdout

    commits: list[dict[str, Any]] = []
    since_date = parse_iso_date(since) if since else None
    until_date = parse_iso_date(until) if until else None
    for block in raw.split(record_sep):
        block = block.rstrip("\r\n")
        if not block:
            continue
        parts = block.split(field_sep)
        if len(parts) < 4:
            continue
        sha, commit_date, message, parents_raw = parts[:4]
        parsed_date = parse_iso_date(commit_date.strip())
        if since_date is not None and (parsed_date is None or parsed_date < since_date):
            continue
        if until_date is not None and (parsed_date is None or parsed_date > until_date):
            continue
        commits.append(
            {
                "sha": sha.strip(),
                "short_sha": sha.strip()[:7],
                "date": commit_date.strip(),
                "message": message.strip(),
                "parents": [parent for parent in parents_raw.split() if parent],
            }
        )
        if since_date is not None or until_date is not None:
            if len(commits) >= limit:
                break
    return commits[:limit]


def _read_blob(repo_root: Path, revision: str, git_path: str) -> str | None:
    result = subprocess.run(
        ["git", "show", f"{revision}:{git_path}"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
        check=False,
    )
    if result.returncode != 0:
        return None
    return result.stdout


def _split_frontmatter(text: str | None) -> dict[str, str]:
    if not text:
        return {}
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}

    metadata: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        metadata[key.strip()] = value.strip().strip('"').strip("'")
    return metadata


def _annotations_for_change(
    *,
    status: str,
    previous_path: str | None,
    frontmatter_changed: bool,
    trust_before: str | None,
    trust_after: str | None,
) -> list[str]:
    annotations: list[str] = []
    if status == "added":
        annotations.append("new file")
    elif status == "deleted":
        annotations.append("deleted")
    elif status == "renamed" and previous_path:
        annotations.append(f"renamed from {previous_path}")
    elif status == "copied" and previous_path:
        annotations.append(f"copied from {previous_path}")

    if frontmatter_changed:
        annotations.append("frontmatter changed")

    if trust_before != trust_after:
        if trust_before and trust_after:
            annotations.append(f"trust: {trust_before} -> {trust_after}")
        elif trust_after:
            annotations.append(f"trust: {trust_after}")
        elif trust_before:
            annotations.append(f"trust was {trust_before}")
    return annotations


def _collect_commit_files(
    repo_root: Path,
    *,
    sha: str,
    parent: str | None,
    git_paths: list[str],
    content_prefix: str,
) -> list[dict[str, Any]]:
    result = _run_git(
        repo_root,
        ["show", "--format=", "--name-status", "--find-renames", "--root", sha, "--", *git_paths],
    )

    files: list[dict[str, Any]] = []
    for raw_line in result.stdout.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        parts = line.split("\t")
        status_token = parts[0]
        status_code = status_token[:1]
        status = _STATUS_LABELS.get(status_code, "modified")

        previous_git_path: str | None = None
        current_git_path: str | None = None
        if status_code in {"R", "C"}:
            if len(parts) < 3:
                continue
            previous_git_path = parts[1]
            current_git_path = parts[2]
        else:
            if len(parts) < 2:
                continue
            current_git_path = parts[1]

        current_path = _from_git_path(current_git_path or "", content_prefix=content_prefix)
        previous_path = (
            _from_git_path(previous_git_path, content_prefix=content_prefix)
            if previous_git_path is not None
            else None
        )
        display_path = current_path or previous_path or ""

        before_git_path = previous_git_path or current_git_path or ""
        after_git_path = current_git_path or previous_git_path or ""
        before_text = None
        after_text = None
        if parent is not None and status != "added":
            before_text = _read_blob(repo_root, parent, before_git_path)
        if status != "deleted":
            after_text = _read_blob(repo_root, sha, after_git_path)

        before_frontmatter = _split_frontmatter(before_text)
        after_frontmatter = _split_frontmatter(after_text)
        frontmatter_changed = before_frontmatter != after_frontmatter and bool(
            before_frontmatter or after_frontmatter
        )
        trust_before = before_frontmatter.get("trust") or None
        trust_after = after_frontmatter.get("trust") or None

        files.append(
            {
                "path": display_path,
                "previous_path": previous_path,
                "status": status,
                "namespace": _namespace_label(display_path),
                "frontmatter_changed": frontmatter_changed,
                "trust_before": trust_before,
                "trust_after": trust_after,
                "is_new_file": status == "added",
                "annotations": _annotations_for_change(
                    status=status,
                    previous_path=previous_path,
                    frontmatter_changed=frontmatter_changed,
                    trust_before=trust_before,
                    trust_after=trust_after,
                ),
            }
        )
    return files


def _aggregate_namespaces(commits: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    summary: dict[str, dict[str, int]] = {}
    for commit in commits:
        for changed_file in commit.get("files", []):
            namespace = str(changed_file.get("namespace") or "unknown")
            status = str(changed_file.get("status") or "modified")
            bucket = summary.setdefault(namespace, {name: 0 for name in _STATUS_ORDER})
            if status not in bucket:
                bucket[status] = 0
            bucket[status] += 1
    return summary


def _filter_summary(payload: dict[str, Any]) -> str:
    filters: list[str] = []
    if payload.get("namespace"):
        filters.append(f"namespace={payload['namespace']}")
    if payload.get("since"):
        filters.append(f"since={payload['since']}")
    if payload.get("until"):
        filters.append(f"until={payload['until']}")

    header = "Diff query"
    if filters:
        header += f" ({', '.join(filters)})"
    return header


def _render_human(payload: dict[str, Any]) -> str:
    header = _filter_summary(payload)
    commits = payload.get("commits") or []
    if not commits:
        return header + "\n\nNo matching commits found."

    lines = [header, ""]
    lines.append(f"Matched commits: {int(payload.get('count') or 0)}")
    lines.append(f"Files changed: {int(payload.get('files_changed') or 0)}")

    by_namespace = payload.get("by_namespace") or {}
    if isinstance(by_namespace, dict) and by_namespace:
        lines.append("By namespace:")
        for namespace in sorted(by_namespace):
            counts = by_namespace[namespace]
            if not isinstance(counts, dict):
                continue
            parts = [
                f"{name}={counts[name]}" for name in _STATUS_ORDER if int(counts.get(name, 0)) > 0
            ]
            lines.append(f"  {namespace}: {', '.join(parts)}")

    lines.append("")
    for index, commit in enumerate(commits, start=1):
        if not isinstance(commit, dict):
            continue
        lines.append(
            f"{index}. {commit.get('date') or 'unknown-date'} {commit.get('short_sha') or 'unknown'} "
            f"{format_snippet(str(commit.get('message') or ''), limit=120)}"
        )
        for changed_file in commit.get("files", []):
            if not isinstance(changed_file, dict):
                continue
            lines.append(
                f"   - {changed_file.get('path')} [{changed_file.get('status')}/{changed_file.get('namespace')}]"
            )
            annotations = changed_file.get("annotations") or []
            if annotations:
                lines.append(f"     {'; '.join(str(item) for item in annotations)}")

    return "\n".join(lines)


def _build_payload(
    args: argparse.Namespace, *, repo_root: Path, content_root: Path
) -> dict[str, Any]:
    if args.since and parse_iso_date(args.since) is None:
        raise ValidationError("since must be in YYYY-MM-DD format")
    if args.until and parse_iso_date(args.until) is None:
        raise ValidationError("until must be in YYYY-MM-DD format")
    if args.since and args.until:
        since_date = parse_iso_date(args.since)
        until_date = parse_iso_date(args.until)
        if since_date is not None and until_date is not None and since_date > until_date:
            raise ValidationError("since must be on or before until")

    limit = max(int(getattr(args, "limit", 10) or 10), 1)
    prefixes = list(namespace_prefixes(getattr(args, "namespace", None)) or ("memory",))
    content_prefix = _content_prefix(repo_root, content_root)
    git_paths = [_to_git_path(prefix, content_prefix=content_prefix) for prefix in prefixes]

    commits = _list_commits(
        repo_root,
        git_paths=git_paths,
        limit=limit,
        since=getattr(args, "since", None),
        until=getattr(args, "until", None),
    )

    detailed_commits: list[dict[str, Any]] = []
    total_files = 0
    for commit in commits:
        parent = commit["parents"][0] if commit.get("parents") else None
        files = _collect_commit_files(
            repo_root,
            sha=str(commit["sha"]),
            parent=parent,
            git_paths=git_paths,
            content_prefix=content_prefix,
        )
        if not files:
            continue
        total_files += len(files)
        detailed_commits.append({**commit, "files": files})

    payload = {
        "namespace": getattr(args, "namespace", None),
        "since": getattr(args, "since", None),
        "until": getattr(args, "until", None),
        "limit": limit,
        "count": len(detailed_commits),
        "files_changed": total_files,
        "path_prefixes": prefixes,
        "commits": detailed_commits,
    }
    payload["by_namespace"] = _aggregate_namespaces(detailed_commits)
    return payload


def run_diff(args: argparse.Namespace, *, repo_root: Path, content_root: Path) -> int:
    try:
        payload = _build_payload(args, repo_root=repo_root, content_root=content_root)
    except ValidationError as exc:
        errors = [str(exc)]
        if args.json:
            print(json.dumps({"valid": False, "errors": errors}, indent=2))
        else:
            print("Diff query failed:\n- " + "\n- ".join(errors), file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(payload, indent=2, default=str))
    else:
        print(_render_human(payload))
    return 0
