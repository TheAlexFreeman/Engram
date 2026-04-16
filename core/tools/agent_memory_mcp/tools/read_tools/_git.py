"""Read tools — git submodule."""

from __future__ import annotations

import re
import subprocess
from datetime import date
from typing import TYPE_CHECKING, Any, cast

from ...identity_paths import is_working_scratchpad_path
from ...response_envelope import dump_tool_result

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

    from ...session_state import SessionState


def register_git(
    mcp: "FastMCP",
    get_repo,
    get_root,
    H,
    *,
    session_state: "SessionState | None" = None,
) -> dict[str, object]:
    """Register git read tools and return their callables."""
    _build_access_summary_for_file = H._build_access_summary_for_file
    _build_knowledge_freshness_report = H._build_knowledge_freshness_report
    _build_lineage_summary = H._build_lineage_summary
    _commit_metadata = H._commit_metadata
    _effective_date = H._effective_date
    _extract_provenance_fields = H._extract_provenance_fields
    _get_git_repo_for_log = H._get_git_repo_for_log
    _git_file_history = H._git_file_history
    _load_access_entries = H._load_access_entries
    _normalize_user_id = H.normalize_user_id
    _normalize_git_log_path_filter = H._normalize_git_log_path_filter
    _parse_iso_date = H._parse_iso_date
    _recognized_commit_prefix = H._recognized_commit_prefix
    _requires_provenance_pause = H._requires_provenance_pause
    _resolve_default_base_branch = H._resolve_default_base_branch
    _resolve_requested_knowledge_paths = H._resolve_requested_knowledge_paths
    _tool_annotations = H._tool_annotations
    _visible_top_level_category = H._visible_top_level_category

    def _dump_payload(payload: Any, *, default: Any | None = None) -> str:
        if session_state is not None:
            session_state.record_tool_call()
        return dump_tool_result(payload, session_state, indent=2, default=default)

    # ------------------------------------------------------------------
    @mcp.tool(
        name="memory_diff_branch",
        annotations=_tool_annotations(
            title="Branch Divergence",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def memory_diff_branch(base: str = "core") -> str:
        """Compare the current branch against a base branch.

        Returns structured divergence data for merge planning, including recent
        commits and file-change counts grouped by top-level category.
        """
        root = get_root()
        resolved_base = _resolve_default_base_branch(root, base)

        def _git(args: list[str], *, check: bool = False) -> subprocess.CompletedProcess[str]:
            return subprocess.run(
                ["git", *args],
                cwd=str(root),
                capture_output=True,
                text=True,
                stdin=subprocess.DEVNULL,
                check=check,
            )

        current_branch_result = _git(["symbolic-ref", "--quiet", "--short", "HEAD"])
        current_branch = (
            current_branch_result.stdout.strip()
            if current_branch_result.returncode == 0
            else "HEAD"
        )

        def _resolve_base_ref() -> str | None:
            local_result = _git(["rev-parse", "--verify", resolved_base])
            if local_result.returncode == 0:
                return resolved_base
            remote_result = _git(["rev-parse", "--verify", f"origin/{resolved_base}"])
            if remote_result.returncode == 0:
                return f"origin/{resolved_base}"

            fetch_result = _git(["fetch", "origin", resolved_base])
            if fetch_result.returncode != 0:
                return None

            local_retry = _git(["rev-parse", "--verify", resolved_base])
            if local_retry.returncode == 0:
                return resolved_base
            remote_retry = _git(["rev-parse", "--verify", f"origin/{resolved_base}"])
            if remote_retry.returncode == 0:
                return f"origin/{resolved_base}"
            return None

        base_ref = _resolve_base_ref()
        if base_ref is None:
            return _dump_payload(
                {
                    "error": (
                        f"Base branch '{resolved_base}' is not available locally and could not be fetched from origin."
                    ),
                    "base_branch": resolved_base,
                    "current_branch": current_branch,
                }
            )

        ahead_result = _git(["rev-list", "--count", f"{base_ref}..HEAD"], check=True)
        name_status_result = _git(["diff", "--name-status", f"{base_ref}...HEAD"], check=True)
        shortstat_result = _git(["diff", "--shortstat", f"{base_ref}...HEAD"], check=True)
        log_result = _git(
            [
                "log",
                f"{base_ref}..HEAD",
                "--date=short",
                "--format=%H%x09%ad%x09%s",
                "-n",
                "10",
            ],
            check=True,
        )

        category_order = [
            "knowledge",
            "plans",
            "identity",
            "meta",
            "tools",
            "skills",
            "chats",
            "scratchpad",
            "other",
        ]
        by_category = {
            category: {"added": 0, "modified": 0, "deleted": 0} for category in category_order
        }

        files_changed = 0
        for raw_line in name_status_result.stdout.splitlines():
            parts = raw_line.split("\t")
            if len(parts) < 2:
                continue
            status = parts[0]
            rel_path = parts[-1]
            visible_path = rel_path
            if root.name and rel_path.startswith(f"{root.name}/"):
                visible_path = rel_path[len(root.name) + 1 :]

            if visible_path.startswith(("memory/knowledge/", "knowledge/")):
                category = "knowledge"
            elif visible_path.startswith(("memory/working/projects/", "plans/")):
                category = "plans"
            elif visible_path.startswith(("memory/users/", "identity/")):
                category = "identity"
            elif visible_path.startswith(("memory/skills/", "skills/")):
                category = "skills"
            elif visible_path.startswith("memory/activity/"):
                category = "chats"
            elif is_working_scratchpad_path(visible_path):
                category = "scratchpad"
            elif visible_path.startswith(("governance/", "meta/", "HUMANS/")):
                category = "meta"
            elif visible_path.startswith(("tools/", "core/tools/")):
                category = "tools"
            else:
                category = "other"
            if status.startswith("A"):
                bucket = "added"
            elif status.startswith("D"):
                bucket = "deleted"
            else:
                bucket = "modified"
            by_category[category][bucket] += 1
            files_changed += 1

        insertions = 0
        deletions = 0
        shortstat_text = shortstat_result.stdout.strip()
        files_match = re.search(r"(\d+) files? changed", shortstat_text)
        insertions_match = re.search(r"(\d+) insertions?\(\+\)", shortstat_text)
        deletions_match = re.search(r"(\d+) deletions?\(-\)", shortstat_text)
        if files_match:
            files_changed = int(files_match.group(1))
        if insertions_match:
            insertions = int(insertions_match.group(1))
        if deletions_match:
            deletions = int(deletions_match.group(1))

        recent_commits: list[dict[str, Any]] = []
        for raw_line in log_result.stdout.splitlines():
            sha, commit_date, message = (raw_line.split("\t", 2) + ["", "", ""])[:3]
            if not sha:
                continue
            recent_commits.append(
                {
                    "sha": sha[:7],
                    "message": message,
                    "date": commit_date,
                }
            )

        payload = {
            "base_branch": resolved_base,
            "resolved_base_ref": base_ref,
            "current_branch": current_branch,
            "commits_ahead": int(ahead_result.stdout.strip() or "0"),
            "files_changed": files_changed,
            "insertions": insertions,
            "deletions": deletions,
            "by_category": by_category,
            "recent_commits": recent_commits,
        }
        return _dump_payload(payload)

    # ------------------------------------------------------------------
    # memory_git_log

    # ------------------------------------------------------------------
    @mcp.tool(
        name="memory_git_log",
        annotations=_tool_annotations(
            title="Git Log for Memory Repo",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def memory_git_log(
        n: int = 10,
        since: str | None = None,
        path_filter: str | None = None,
        use_host_repo: bool = False,
    ) -> str:
        """Return recent commit history for the memory repository.

        Useful at session start to see what changed since the last session.

        Args:
            n: Number of commits to return (default: 10, max: 50).
            since: Optional ISO date filter (YYYY-MM-DD). Only commits after this date are returned.
            path_filter: Optional repo-relative path or git pathspec to restrict the log.
            use_host_repo: When true, read from host_repo_root in agent-bootstrap.toml.

        Returns:
            JSON list of commits, each with sha, message, date, files_changed, truncated.
        """
        from ...errors import ValidationError

        root = get_root()
        repo = _get_git_repo_for_log(root, get_repo(), use_host_repo=use_host_repo)
        n = min(n, 50)
        if since is not None and _parse_iso_date(since) is None:
            raise ValidationError("since must be a valid ISO date string (YYYY-MM-DD)")

        normalized_path_filter = None
        if path_filter is not None:
            normalized_path_filter = _normalize_git_log_path_filter(path_filter)

        commits = repo.log(n, since=since, path_filter=normalized_path_filter)
        truncated = False
        if since is not None and len(commits) == n and n > 0:
            total_commits = repo.commit_count_since(
                since,
                paths=[normalized_path_filter] if normalized_path_filter else None,
            )
            truncated = total_commits > len(commits)

        for commit in commits:
            commit["truncated"] = truncated
        return _dump_payload(commits)

    # ------------------------------------------------------------------
    # memory_git_health

    # ------------------------------------------------------------------
    @mcp.tool(
        name="memory_git_health",
        annotations=_tool_annotations(
            title="Git Health Diagnostic",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def memory_git_health() -> str:
        """Run git health diagnostics: lock files, repo integrity, filesystem.

        Returns a structured report with lock file status, repo validity,
        HEAD state, index state, filesystem writability, and any warnings.
        Safe to call at any time.
        """
        repo = get_repo()
        report = repo.health_check()
        return _dump_payload(report)

    # ------------------------------------------------------------------
    # memory_check_knowledge_freshness

    # ------------------------------------------------------------------
    @mcp.tool(
        name="memory_check_knowledge_freshness",
        annotations=_tool_annotations(
            title="Check Knowledge Freshness",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def memory_check_knowledge_freshness(paths: str) -> str:
        """Check knowledge-file freshness against the configured host repository.

        Args:
            paths: Comma-separated or newline-separated knowledge file paths.

        Returns:
            JSON with one freshness report per requested knowledge file.
        """
        root = get_root()
        repo = get_repo()
        requested_paths = _resolve_requested_knowledge_paths(root, paths)
        reports = [
            _build_knowledge_freshness_report(root, repo, rel_path, abs_path)
            for rel_path, abs_path in requested_paths
        ]
        if session_state is not None:
            for rel_path, _ in requested_paths:
                session_state.record_read(rel_path)
        payload = {
            "checked_at": str(date.today()),
            "files_checked": len(reports),
            "reports": reports,
        }
        return _dump_payload(payload)

    # ------------------------------------------------------------------
    # memory_session_health_check

    # ------------------------------------------------------------------
    @mcp.tool(
        name="memory_get_file_provenance",
        annotations=_tool_annotations(
            title="File Provenance",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def memory_get_file_provenance(
        path: str,
        history_limit: int = 10,
        user_id: str = "",
    ) -> str:
        """Return provenance, ACCESS history, and git history for one file."""
        from ...errors import NotFoundError
        from ...frontmatter_utils import read_with_frontmatter

        root = get_root()
        repo = get_repo()
        resolved_user_id = _normalize_user_id(user_id)
        abs_path = repo.abs_path(path)
        if not abs_path.exists() or not abs_path.is_file():
            raise NotFoundError(f"File not found: {path}")

        frontmatter, _ = read_with_frontmatter(abs_path)
        version_token = repo.hash_object(path)
        access_entries, _ = _load_access_entries(root)
        access_summary = _build_access_summary_for_file(
            access_entries,
            path,
            user_id=resolved_user_id,
        )
        commit_history = _git_file_history(repo, path, limit=history_limit)
        latest_commit = commit_history[0] if commit_history else None
        first_tracked_date = repo.first_tracked_author_date(path)
        effective_date = _effective_date(frontmatter)
        provenance_fields = _extract_provenance_fields(frontmatter)
        lineage_summary = _build_lineage_summary(path, provenance_fields)

        payload = {
            "path": path,
            "version_token": version_token,
            "tracked": first_tracked_date is not None,
            "first_tracked_date": str(first_tracked_date)
            if first_tracked_date is not None
            else None,
            "effective_date": str(effective_date) if effective_date is not None else None,
            "frontmatter": frontmatter or None,
            "provenance_fields": provenance_fields,
            "lineage_summary": lineage_summary,
            "requires_provenance_pause": _requires_provenance_pause(path, frontmatter),
            "access_filter_user_id": resolved_user_id,
            "access_summary": access_summary,
            "latest_commit": latest_commit,
            "commit_history": commit_history,
        }
        if session_state is not None:
            session_state.record_read(path)
        return _dump_payload(payload, default=str)

    # ------------------------------------------------------------------
    # memory_inspect_commit

    # ------------------------------------------------------------------
    @mcp.tool(
        name="memory_inspect_commit",
        annotations=_tool_annotations(
            title="Inspect Commit",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def memory_inspect_commit(sha: str) -> str:
        """Return structured metadata for a commit plus basic scope analysis."""
        repo = get_repo()
        commit = repo.inspect_commit(sha)
        metadata = _commit_metadata(repo, str(commit["sha"]))
        files_changed = [str(path) for path in cast(list[object], commit["files_changed"])]
        top_levels = sorted({_visible_top_level_category(path) for path in files_changed if path})
        message = str(commit["message"])

        payload = {
            **commit,
            **metadata,
            "requested_sha": sha,
            "recognized_prefix": _recognized_commit_prefix(message),
            "file_count": len(files_changed),
            "top_level_paths": top_levels,
            "is_head": str(commit["sha"]) == repo.current_head(),
        }
        return _dump_payload(payload)

    # ------------------------------------------------------------------
    # memory_diff

    # ------------------------------------------------------------------
    @mcp.tool(
        name="memory_diff",
        annotations=_tool_annotations(
            title="Working Tree Diff Status",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def memory_diff() -> str:
        """Show working tree status — staged, unstaged, and untracked files.

        Call before memory_commit to verify what will be included in the commit.

        Returns:
            JSON with keys staged, unstaged, untracked (each a list of paths).
        """
        repo = get_repo()
        status = repo.diff_status()
        return _dump_payload(status)

    # ------------------------------------------------------------------
    # memory_audit_trust

    return {
        "memory_diff_branch": memory_diff_branch,
        "memory_git_log": memory_git_log,
        "memory_git_health": memory_git_health,
        "memory_check_knowledge_freshness": memory_check_knowledge_freshness,
        "memory_get_file_provenance": memory_get_file_provenance,
        "memory_inspect_commit": memory_inspect_commit,
        "memory_diff": memory_diff,
    }
