"""
GitRepo — thin subprocess wrapper around the git CLI.

All paths accepted as arguments should be repo-relative strings.
Absolute paths are constructed internally by joining with self.root.

Design notes:
- Uses subprocess.run (synchronous) — git operations are fast local I/O and
  this is a single-client local MCP, so blocking the event loop briefly is fine.
- Author identity: if git config is missing, we set a fallback automatically
  so Tier 1 tool commits never fail with "Author identity unknown".
- All errors are normalized to StagingError with the git stderr attached.
"""

from __future__ import annotations

import errno
import json
import logging
import os
import subprocess
import tempfile
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path

from .errors import StagingError

_FALLBACK_AUTHOR_NAME = "Claude"
_FALLBACK_AUTHOR_EMAIL = "agent@agent-memory"
_WRITE_LOCK_NAME = "agent-memory-write.lock"
_WRITE_LOCK_TIMEOUT_SECONDS = 5.0
_WRITE_LOCK_POLL_INTERVAL_SECONDS = 0.05
_HEAD_LOCK_NAME = "HEAD.lock"
_INDEX_LOCK_NAME = "index.lock"
_STALE_HEAD_LOCK_MAX_AGE_SECONDS = 30.0
_TRANSIENT_MARKERS = (
    "index.lock",
    "head.lock",
    "could not lock",
    "unable to create",
    "another git process",
    "resource temporarily unavailable",
)

_log = logging.getLogger("engram.git_repo")


def _is_transient_failure(error: StagingError) -> bool:
    """Return True if the error looks like a lock contention or I/O transient."""
    stderr = (error.stderr or str(error)).lower()
    return any(marker in stderr for marker in _TRANSIENT_MARKERS)


def _preserve_input_root_spelling(candidate_root: Path, reported_root: Path) -> Path:
    """Prefer the caller's path spelling when it points into the same repo root.

    On Windows, `git rev-parse --show-toplevel` can return an 8.3 short path
    such as `C:/Users/RUNNER~1/...`, which causes equality checks against the
    original long path to fail even though both point to the same directory.
    """
    resolved_reported_root = reported_root.resolve()
    try:
        for ancestor in (candidate_root, *candidate_root.parents):
            if ancestor.samefile(resolved_reported_root):
                return ancestor
    except OSError:
        pass
    return resolved_reported_root


@dataclass(frozen=True)
class GitPublicationResult:
    sha: str
    parent_sha: str
    published_at: str
    operation: str
    mode: str
    degraded: bool = False
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "parent_sha": self.parent_sha,
            "published_at": self.published_at,
            "operation": self.operation,
            "mode": self.mode,
            "degraded": self.degraded,
            "writer_lock": "exclusive-repo-common-dir",
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True)
class GitFastForwardResult:
    status: str
    target_ref: str
    source_ref: str
    target_sha: str | None
    source_sha: str | None
    applied_sha: str | None = None
    reason: str | None = None
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "operation": "fast-forward",
            "status": self.status,
            "target_ref": self.target_ref,
            "source_ref": self.source_ref,
            "target_sha": self.target_sha,
            "source_sha": self.source_sha,
            "applied_sha": self.applied_sha,
            "warnings": list(self.warnings),
        }
        if self.reason is not None:
            payload["reason"] = self.reason
        return payload


class GitRepo:
    def __init__(self, root: Path, *, content_prefix: str = "") -> None:
        candidate_root = Path(root).resolve()
        if not candidate_root.is_dir():
            raise ValueError(f"Not a git repository: {candidate_root}")

        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=str(candidate_root),
            capture_output=True,
            text=True,
            stdin=subprocess.DEVNULL,
        )
        if result.returncode != 0:
            raise ValueError(f"Not a git repository: {candidate_root}")

        git_dir_result = subprocess.run(
            ["git", "rev-parse", "--absolute-git-dir"],
            cwd=str(candidate_root),
            capture_output=True,
            text=True,
            stdin=subprocess.DEVNULL,
        )
        if git_dir_result.returncode != 0:
            raise ValueError(f"Not a git repository: {candidate_root}")

        git_common_dir_result = subprocess.run(
            ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
            cwd=str(candidate_root),
            capture_output=True,
            text=True,
            stdin=subprocess.DEVNULL,
        )
        if git_common_dir_result.returncode != 0:
            git_common_dir_result = subprocess.run(
                ["git", "rev-parse", "--git-common-dir"],
                cwd=str(candidate_root),
                capture_output=True,
                text=True,
                stdin=subprocess.DEVNULL,
            )
        if git_common_dir_result.returncode != 0:
            raise ValueError(f"Not a git repository: {candidate_root}")

        self.root = _preserve_input_root_spelling(
            candidate_root,
            Path(result.stdout.strip()),
        )
        self.git_dir = Path(git_dir_result.stdout.strip()).resolve()
        git_common_dir_raw = git_common_dir_result.stdout.strip()
        git_common_dir_path = Path(git_common_dir_raw)
        if not git_common_dir_path.is_absolute():
            git_common_dir_path = (self.root / git_common_dir_path).resolve()
        self.git_common_dir = git_common_dir_path
        # Content prefix: when set, all content-relative paths are resolved
        # under root / content_prefix (e.g., root / "core"). For older test
        # fixtures and legacy layouts that do not include that folder, fall
        # back to the repository root so tool-facing paths remain usable.
        normalized_prefix = content_prefix.strip("/")
        prefixed_root = (self.root / normalized_prefix) if normalized_prefix else self.root
        if normalized_prefix and prefixed_root.is_dir():
            self.content_prefix = normalized_prefix
            self.content_root = prefixed_root
        else:
            self.content_prefix = ""
            self.content_root = self.root

    def engram_state_dir(self, *parts: str, create: bool = False) -> Path:
        """Return a path under the repo-common untracked Engram state directory."""
        path = self.git_common_dir / "engram"
        if parts:
            path = path.joinpath(*parts)
        if create:
            path.mkdir(parents=True, exist_ok=True)
        return path

    def session_branch_metadata_path(self, branch_name: str) -> Path:
        """Return the repo-common runtime metadata path for a session branch."""
        normalized_branch = branch_name.strip().strip("/")
        if not normalized_branch:
            raise StagingError("branch_name must be a non-empty git branch name")
        branch_path = self.engram_state_dir("session-branches", *normalized_branch.split("/"))
        return Path(str(branch_path) + ".json")

    def load_session_branch_metadata(self, branch_name: str) -> dict[str, str] | None:
        """Load persisted original-base metadata for a session branch."""
        metadata_path = self.session_branch_metadata_path(branch_name)
        if not metadata_path.is_file():
            return None
        try:
            payload = json.loads(metadata_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise StagingError(
                f"Session branch metadata is unreadable for '{branch_name}': {metadata_path}",
                stderr=str(exc),
            ) from exc
        if not isinstance(payload, dict):
            raise StagingError(
                f"Session branch metadata must be a JSON object for '{branch_name}': {metadata_path}"
            )
        base_branch = payload.get("base_branch")
        base_ref = payload.get("base_ref")
        if not isinstance(base_branch, str) or not base_branch.strip():
            raise StagingError(
                f"Session branch metadata is missing base_branch for '{branch_name}': {metadata_path}"
            )
        if not isinstance(base_ref, str) or not base_ref.strip():
            raise StagingError(
                f"Session branch metadata is missing base_ref for '{branch_name}': {metadata_path}"
            )
        return {
            "base_branch": base_branch.strip(),
            "base_ref": base_ref.strip(),
        }

    def ensure_session_branch_metadata(
        self,
        branch_name: str,
        *,
        base_branch: str,
        base_ref: str,
    ) -> dict[str, str]:
        """Persist original-base metadata for a session branch if it is absent."""
        existing = self.load_session_branch_metadata(branch_name)
        if existing is not None:
            return existing

        normalized_base_branch = base_branch.strip()
        normalized_base_ref = base_ref.strip()
        if not normalized_base_branch:
            raise StagingError("base_branch must be a non-empty git branch name")
        if not normalized_base_ref:
            raise StagingError("base_ref must be a non-empty git ref")

        metadata_path = self.session_branch_metadata_path(branch_name)
        metadata_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "base_branch": normalized_base_branch,
            "base_ref": normalized_base_ref,
        }
        metadata_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        return payload

    # ------------------------------------------------------------------
    # Path translation (content-relative <-> git-relative)
    # ------------------------------------------------------------------

    def _to_git_path(self, content_rel: str) -> str:
        """Convert a content-relative path to a git-relative path."""
        if self.content_prefix:
            return f"{self.content_prefix}/{content_rel}"
        return content_rel

    def _from_git_path(self, git_rel: str) -> str:
        """Convert a git-relative path to a content-relative path.

        Returns the path unchanged if it is not under the content prefix.
        """
        if self.content_prefix:
            prefix = self.content_prefix + "/"
            if git_rel.startswith(prefix):
                return git_rel[len(prefix) :]
        return git_rel

    # ------------------------------------------------------------------
    # Internal runner
    # ------------------------------------------------------------------

    def _run(
        self,
        args: list[str],
        check: bool = True,
        capture: bool = True,
        *,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess:
        result = subprocess.run(
            args,
            cwd=str(cwd or self.root),
            capture_output=capture,
            text=True,
            stdin=subprocess.DEVNULL,
            env=env,
        )
        if check and result.returncode != 0:
            stderr = result.stderr.strip()
            cmd = " ".join(args[:3])
            raise StagingError(
                f"`{cmd}` failed (exit {result.returncode}): {stderr}",
                stderr=stderr,
            )
        return result

    def _resolve_commit_ref(self, ref: str) -> str | None:
        result = self._run(["git", "rev-parse", "--verify", f"{ref}^{{commit}}"], check=False)
        if result.returncode != 0:
            return None
        return result.stdout.strip() or None

    # ------------------------------------------------------------------
    # Author identity
    # ------------------------------------------------------------------

    def ensure_author_identity(self) -> None:
        """Set git user.name / user.email locally if not already configured."""
        name_result = self._run(["git", "config", "--local", "user.name"], check=False)
        if name_result.returncode != 0 or not name_result.stdout.strip():
            self._run(["git", "config", "--local", "user.name", _FALLBACK_AUTHOR_NAME])

        email_result = self._run(["git", "config", "--local", "user.email"], check=False)
        if email_result.returncode != 0 or not email_result.stdout.strip():
            self._run(["git", "config", "--local", "user.email", _FALLBACK_AUTHOR_EMAIL])

    def fast_forward_ref(self, *, target_ref: str, source_ref: str) -> GitFastForwardResult:
        """Advance *target_ref* to *source_ref* when it is a strict fast-forward."""
        with self.write_lock("fast-forward"):
            self._try_cleanup_all_stale_locks()

            target_sha = self._resolve_commit_ref(target_ref)
            if target_sha is None:
                return GitFastForwardResult(
                    status="blocked",
                    target_ref=target_ref,
                    source_ref=source_ref,
                    target_sha=None,
                    source_sha=self._resolve_commit_ref(source_ref),
                    reason=f"Target ref '{target_ref}' does not resolve to a commit.",
                )

            source_sha = self._resolve_commit_ref(source_ref)
            if source_sha is None:
                return GitFastForwardResult(
                    status="blocked",
                    target_ref=target_ref,
                    source_ref=source_ref,
                    target_sha=target_sha,
                    source_sha=None,
                    reason=f"Source ref '{source_ref}' does not resolve to a commit.",
                )

            if target_sha == source_sha:
                return GitFastForwardResult(
                    status="already-up-to-date",
                    target_ref=target_ref,
                    source_ref=source_ref,
                    target_sha=target_sha,
                    source_sha=source_sha,
                    applied_sha=source_sha,
                )

            ancestor_result = self._run(
                ["git", "merge-base", "--is-ancestor", target_sha, source_sha],
                check=False,
            )
            if ancestor_result.returncode == 1:
                return GitFastForwardResult(
                    status="blocked",
                    target_ref=target_ref,
                    source_ref=source_ref,
                    target_sha=target_sha,
                    source_sha=source_sha,
                    reason=(
                        f"Target ref '{target_ref}' has diverged from '{source_ref}' and cannot be fast-forwarded."
                    ),
                )
            if ancestor_result.returncode != 0:
                stderr = ancestor_result.stderr.strip()
                raise StagingError(
                    f"`git merge-base --is-ancestor` failed (exit {ancestor_result.returncode}): {stderr}",
                    stderr=stderr,
                )

            warnings: list[str] = []
            try:
                self._run(["git", "update-ref", target_ref, source_sha, target_sha])
            except StagingError as ref_error:
                if not self._should_fallback_to_plumbing(ref_error):
                    raise
                _log.warning(
                    "update-ref fast-forward failed (%s), writing ref file directly", ref_error
                )
                self._direct_update_ref(target_ref, source_sha, target_sha)
                warnings.append(
                    "Target ref updated via direct file write after update-ref could not acquire the git ref lock."
                )

            return GitFastForwardResult(
                status="fast-forwarded",
                target_ref=target_ref,
                source_ref=source_ref,
                target_sha=target_sha,
                source_sha=source_sha,
                applied_sha=source_sha,
                warnings=warnings,
            )

    # ------------------------------------------------------------------
    # Object hashing (version tokens)
    # ------------------------------------------------------------------

    def hash_object(self, rel_path: str) -> str:
        """Return the git object hash (SHA-1) of the file on disk.

        This is the version token: if it changes, the file was modified.
        """
        abs_path = str(self.content_root / rel_path)
        result = self._run(["git", "hash-object", abs_path])
        return result.stdout.strip()

    def check_version_token(self, rel_path: str, token: str | None) -> None:
        """Raise ConflictError if token is provided and does not match current hash."""
        if token is None:
            return
        # Import here to avoid circular
        from .errors import ConflictError

        current = self.hash_object(rel_path)
        if current != token:
            raise ConflictError(
                f"Version conflict on {rel_path}: file was modified since last read. "
                f"Re-read the file to get the current version_token and retry.",
                current_token=current,
            )

    # ------------------------------------------------------------------
    # Staging
    # ------------------------------------------------------------------

    def add(self, *rel_paths: str) -> None:
        """Stage one or more content-relative files."""
        if not rel_paths:
            return
        self._try_cleanup_stale_index_lock()
        git_paths = [self._to_git_path(p) for p in rel_paths]
        self._run(["git", "add", "-A", "--"] + git_paths)

    def add_git_paths(self, *git_paths: str) -> None:
        """Stage one or more git-relative files."""
        if not git_paths:
            return
        self._try_cleanup_stale_index_lock()
        self._run(["git", "add", "-A", "--"] + list(git_paths))

    def is_tracked(self, rel_path: str) -> bool:
        """Return whether a content-relative path is tracked by git."""
        git_path = self._to_git_path(rel_path)
        return self.is_git_path_tracked(git_path)

    def is_git_path_tracked(self, git_path: str) -> bool:
        """Return whether a git-relative path is tracked by git."""
        result = self._run(["git", "ls-files", "--error-unmatch", "--", git_path], check=False)
        return result.returncode == 0

    def add_all(self) -> None:
        """Stage all changes (git add -A)."""
        self._try_cleanup_stale_index_lock()
        self._run(["git", "add", "-A"])

    def restore_paths(
        self,
        *rel_paths: str,
        staged: bool = True,
        worktree: bool = True,
        source: str = "HEAD",
    ) -> None:
        """Restore one or more paths from *source* into index and/or worktree."""
        if not rel_paths:
            return

        git_paths = [self._to_git_path(p) for p in rel_paths]
        cmd = ["git", "restore", f"--source={source}"]
        if staged:
            cmd.append("--staged")
        if worktree:
            cmd.append("--worktree")
        cmd += ["--", *git_paths]
        self._run(cmd)

    def rm(self, rel_path: str) -> None:
        """Remove file from working tree and stage the deletion."""
        self._run(["git", "rm", "--", self._to_git_path(rel_path)])

    def mv(self, rel_src: str, rel_dst: str) -> None:
        """Rename/move a file and stage the change (preserves history)."""
        # Ensure destination directory exists
        dst_abs = self.content_root / rel_dst
        dst_abs.parent.mkdir(parents=True, exist_ok=True)
        self._run(["git", "mv", "--", self._to_git_path(rel_src), self._to_git_path(rel_dst)])

    # ------------------------------------------------------------------
    # Committing
    # ------------------------------------------------------------------

    def nothing_staged(self) -> bool:
        """True if the staging area is empty (nothing to commit)."""
        result = self._run(["git", "diff", "--cached", "--quiet"], check=False)
        return result.returncode == 0

    def has_staged_changes(self, *rel_paths: str) -> bool:
        """True if the staging area contains changes for the given paths."""
        if not rel_paths:
            return not self.nothing_staged()
        git_paths = [self._to_git_path(p) for p in rel_paths]
        result = self._run(["git", "diff", "--cached", "--quiet", "--", *git_paths], check=False)
        return result.returncode == 1

    def _staged_paths_git(self, *git_paths: str) -> list[str]:
        """Internal: return staged paths as raw git-relative strings."""
        cmd = ["git", "diff", "--cached", "--name-only"]
        if git_paths:
            cmd += ["--", *git_paths]
        result = self._run(cmd, check=False)
        return [line.strip() for line in result.stdout.splitlines() if line.strip()]

    def staged_paths(self, *rel_paths: str) -> list[str]:
        """Return staged paths, optionally filtered to a path subset.

        Accepts and returns content-relative paths.
        """
        git_paths = [self._to_git_path(p) for p in rel_paths] if rel_paths else []
        raw = self._staged_paths_git(*git_paths)
        return [self._from_git_path(p) for p in raw]

    def has_unstaged_changes(self, *rel_paths: str) -> bool:
        """True if the working tree has unstaged changes for the given paths."""
        cmd = ["git", "diff", "--quiet"]
        if rel_paths:
            git_paths = [self._to_git_path(p) for p in rel_paths]
            cmd += ["--", *git_paths]
        result = self._run(cmd, check=False)
        return result.returncode == 1

    def current_branch_ref(self) -> str | None:
        """Return the current HEAD symbolic ref, or None when detached."""
        result = self._run(["git", "symbolic-ref", "--quiet", "HEAD"], check=False)
        if result.returncode != 0:
            return None
        ref = result.stdout.strip()
        return ref or None

    def current_branch_name(self) -> str | None:
        """Return the current branch name, or None when detached."""
        ref = self.current_branch_ref()
        if ref is None:
            return None
        prefix = "refs/heads/"
        if ref.startswith(prefix):
            return ref[len(prefix) :]
        return ref

    def ensure_branch_checked_out(
        self,
        branch_name: str,
        *,
        start_point: str | None = None,
    ) -> tuple[str, bool]:
        """Ensure a local branch exists and is the current checkout.

        Returns ``(branch_ref, created)`` where ``created`` is true only when a
        new local branch had to be created.
        """
        normalized_branch = branch_name.strip()
        if not normalized_branch:
            raise StagingError("branch_name must be a non-empty git branch name")

        self._run(["git", "check-ref-format", "--branch", normalized_branch])
        branch_ref = f"refs/heads/{normalized_branch}"
        current_branch = self.current_branch_name()
        if current_branch == normalized_branch:
            return branch_ref, False

        if self.has_staged_changes() or self.has_unstaged_changes():
            raise StagingError(
                "Cannot switch to a session branch with staged or unstaged tracked changes in the worktree. "
                "Commit, stash, or discard those edits before enabling session branch isolation."
            )

        exists_result = self._run(
            ["git", "show-ref", "--verify", "--quiet", branch_ref], check=False
        )
        if exists_result.returncode == 0:
            self._run(["git", "checkout", "--quiet", normalized_branch])
            return branch_ref, False

        cmd = ["git", "checkout", "--quiet", "-b", normalized_branch]
        if start_point:
            cmd.append(start_point)
        self._run(cmd)
        return branch_ref, True

    def _current_branch_ref(self) -> str:
        ref = self.current_branch_ref()
        if ref is None:
            raise StagingError(
                "The memory repository is in detached HEAD state. Attach HEAD to a branch "
                "before publishing writes."
            )
        return ref

    def _direct_update_ref(self, ref: str, new_sha: str, expected_old: str) -> None:
        """Write a ref file directly, bypassing git update-ref.

        This is a last-resort fallback for environments where git's lock-file
        mechanism is broken (e.g. FUSE/cross-filesystem mounts that refuse
        unlink on stale lock files).

        Safety: callers MUST hold write_lock before invoking this.
        The compare-and-swap check (expected_old) ensures we don't clobber a
        concurrent update, though write_lock already prevents that.
        """
        # ref is like "refs/heads/alex" — resolve to filesystem path
        ref_path = self.git_dir / ref
        if not ref_path.parent.exists():
            ref_path.parent.mkdir(parents=True, exist_ok=True)

        # Compare-and-swap: verify current value matches expected.
        # Refs may be stored as loose files *or* in packed-refs — check both.
        current: str | None = None
        if ref_path.exists():
            current = ref_path.read_text(encoding="utf-8").strip()
        else:
            # Ref not present as a loose file; look it up in packed-refs.
            packed_refs_path = self.git_dir / "packed-refs"
            if packed_refs_path.is_file():
                for line in packed_refs_path.read_text(encoding="utf-8").splitlines():
                    # packed-refs lines: "<sha> <refname>" (comment lines start with #/^)
                    if line.startswith("#") or line.startswith("^"):
                        continue
                    parts = line.split()
                    if len(parts) == 2 and parts[1] == ref:
                        current = parts[0]
                        break

        if current is not None and current != expected_old:
            raise StagingError(
                f"Ref {ref} has changed since read: expected {expected_old}, "
                f"found {current}. Refusing direct update."
            )

        ref_path.write_text(new_sha + "\n", encoding="utf-8")
        _log.info("Direct-wrote ref %s → %s", ref, new_sha[:12])

    def _head_tree(self) -> str:
        result = self._run(["git", "rev-parse", "HEAD^{tree}"])
        return result.stdout.strip()

    def _staged_index_entry(self, rel_path: str) -> tuple[str, str] | None:
        result = self._run(["git", "ls-files", "--stage", "--", rel_path], check=False)
        lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        if not lines:
            return None
        if len(lines) != 1:
            raise StagingError(
                f"Path {rel_path} has multiple staged index entries; resolve conflicts before "
                "publishing writes."
            )

        parts = lines[0].split(None, 3)
        if len(parts) != 4:
            raise StagingError(f"Could not parse staged index entry for {rel_path}")

        mode, object_id, stage, path = parts
        if stage != "0":
            raise StagingError(
                f"Path {path} is in a conflicted staged state; resolve conflicts before publishing."
            )
        return mode, object_id

    def _write_lock_path(self) -> Path:
        return self.engram_state_dir() / _WRITE_LOCK_NAME

    def _head_lock_path(self) -> Path:
        return self.git_dir / _HEAD_LOCK_NAME

    def _is_lock_older_than(self, lock_path: Path, threshold_seconds: float) -> bool:
        try:
            lock_mtime = lock_path.stat().st_mtime
        except OSError:
            return False
        lock_age_seconds = time.time() - lock_mtime
        return lock_age_seconds > threshold_seconds

    def _extract_pid_from_lock(self, lock_path: Path) -> int | None:
        try:
            lock_contents = lock_path.read_text(encoding="utf-8")
        except OSError:
            return None

        for raw_line in lock_contents.splitlines():
            line = raw_line.strip()
            if not line.lower().startswith("pid="):
                continue
            pid_token = line.split("=", 1)[1].strip()
            if not pid_token:
                return None
            try:
                pid = int(pid_token)
            except ValueError:
                return None
            return pid if pid > 0 else None
        return None

    def _is_pid_alive(self, pid: int) -> bool:
        if pid <= 0:
            return False
        try:
            os.kill(pid, 0)
            return True
        except ProcessLookupError:
            return False
        except PermissionError:
            # Process exists but we may not have permission to signal it.
            return True
        except OSError as error:
            if error.errno == errno.ESRCH:
                return False
            if getattr(error, "winerror", None) == 87:
                return False
            # Treat unknown errors as alive to avoid unsafe lock removal.
            return True

    def _try_cleanup_stale_lock(self, lock_path: Path) -> bool:
        """Remove a stale lock file if it's old and its owner PID is dead.

        Git's own HEAD.lock and index.lock are typically empty (0 bytes)
        and contain no PID.  When a lock file is older than the staleness
        threshold and either (a) contains no PID or (b) the PID is dead,
        it is safe to remove.
        """
        if not lock_path.exists():
            return False
        if not self._is_lock_older_than(lock_path, _STALE_HEAD_LOCK_MAX_AGE_SECONDS):
            return False

        pid = self._extract_pid_from_lock(lock_path)
        if pid is not None and self._is_pid_alive(pid):
            return False

        # Lock is old enough and either has no PID (empty/git-native) or
        # its owner process is dead — safe to remove.
        try:
            lock_path.unlink()
        except FileNotFoundError:
            return False
        except OSError as unlink_err:
            # On FUSE / cross-filesystem mounts, unlink may fail with EPERM
            # even when the lock is stale.  Log clearly so operators can
            # diagnose, but don't raise — callers will fall back to plumbing.
            _log.warning(
                "Cannot remove stale lock %s (pid=%s): %s. "
                "This is common on FUSE/cross-filesystem mounts. "
                "The plumbing commit path will attempt a direct ref write.",
                lock_path.name,
                pid,
                unlink_err,
            )
            return False
        _log.warning("Removed stale lock file: %s (pid=%s)", lock_path.name, pid)
        return True

    def _try_cleanup_stale_head_lock(self) -> bool:
        return self._try_cleanup_stale_lock(self._head_lock_path())

    def _try_cleanup_stale_index_lock(self) -> bool:
        index_lock = self.git_dir / _INDEX_LOCK_NAME
        return self._try_cleanup_stale_lock(index_lock)

    def _try_cleanup_all_stale_locks(self) -> bool:
        """Attempt to clean up all known stale lock files. Returns True if any were removed."""
        head = self._try_cleanup_stale_head_lock()
        index = self._try_cleanup_stale_index_lock()
        return head or index

    @contextmanager
    def write_lock(self, purpose: str):
        """Serialize publication so each worktree has a single active writer."""
        lock_path = self._write_lock_path()
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        deadline = time.monotonic() + _WRITE_LOCK_TIMEOUT_SECONDS
        lock_payload = f"pid={os.getpid()}\npurpose={purpose}\nstarted_at={time.time()}\n"

        while True:
            try:
                fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                break
            except FileExistsError:
                if time.monotonic() >= deadline:
                    try:
                        owner = lock_path.read_text(encoding="utf-8").strip()
                    except OSError:
                        owner = ""
                    suffix = f" Active writer: {owner}" if owner else ""
                    raise StagingError(
                        "Another writer is already publishing changes for this worktree. "
                        f"Wait for that write to finish and retry.{suffix}"
                    )
                time.sleep(_WRITE_LOCK_POLL_INTERVAL_SECONDS)

        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(lock_payload)
            yield
        finally:
            try:
                lock_path.unlink()
            except FileNotFoundError:
                pass

    def _should_fallback_to_plumbing(self, error: StagingError) -> bool:
        stderr = (error.stderr or str(error)).lower()
        markers = (
            "index.lock",
            "head.lock",
            "could not lock index",
            "unable to create",
            "another git process",
        )
        return any(marker in stderr for marker in markers)

    def _commit_porcelain(
        self,
        message: str,
        *,
        paths: list[str] | None = None,
        allow_empty: bool = False,
    ) -> GitPublicationResult:
        parent_sha = self.current_head()
        cmd = ["git", "commit", "-m", message]
        preserved_paths: list[str] = []
        if allow_empty:
            cmd.append("--allow-empty")
        if paths:
            deduped_paths = list(dict.fromkeys(paths))
            preserved_paths = [
                path for path in self._staged_paths_git() if path not in set(deduped_paths)
            ]
            cmd += ["--only", "--", *deduped_paths]
        self._run(cmd)
        if preserved_paths:
            self._run(["git", "add", "--", *preserved_paths])
        sha_result = self._run(["git", "rev-parse", "HEAD"])
        return GitPublicationResult(
            sha=sha_result.stdout.strip(),
            parent_sha=parent_sha,
            published_at=datetime.now(timezone.utc).isoformat(),
            operation="commit",
            mode="porcelain",
        )

    def _commit_with_plumbing(
        self,
        message: str,
        *,
        paths: list[str] | None = None,
        allow_empty: bool = False,
    ) -> GitPublicationResult:
        branch_ref = self._current_branch_ref()
        parent_sha = self.current_head()
        parent_tree = self._head_tree()
        selected_paths = list(dict.fromkeys(paths)) if paths else self._staged_paths_git()

        if not selected_paths and not allow_empty:
            raise StagingError("Nothing staged to commit.")

        with tempfile.TemporaryDirectory(prefix="agent-memory-commit-") as tmpdir:
            temp_index = Path(tmpdir) / "index"
            env = {**os.environ, "GIT_INDEX_FILE": str(temp_index)}
            self._run(["git", "read-tree", "HEAD"], env=env)

            for rel_path in selected_paths:
                entry = self._staged_index_entry(rel_path)
                if entry is None:
                    self._run(
                        ["git", "update-index", "--remove", "--force-remove", "--", rel_path],
                        check=False,
                        env=env,
                    )
                    continue

                mode, object_id = entry
                self._run(
                    [
                        "git",
                        "update-index",
                        "--add",
                        "--cacheinfo",
                        mode,
                        object_id,
                        rel_path,
                    ],
                    env=env,
                )

            tree_result = self._run(["git", "write-tree"], env=env)
            tree_sha = tree_result.stdout.strip()

        if tree_sha == parent_tree and not allow_empty:
            raise StagingError("Nothing staged to commit.")

        commit_result = self._run(["git", "commit-tree", tree_sha, "-p", parent_sha, "-m", message])
        commit_sha = commit_result.stdout.strip()

        warnings = [
            "Published via degraded plumbing path after porcelain commit could not lock the git index."
        ]
        try:
            self._run(["git", "update-ref", branch_ref, commit_sha, parent_sha])
        except StagingError as ref_error:
            # update-ref needs HEAD.lock, which may be stuck on FUSE/cross-FS
            # mounts.  Since we already hold write_lock (serialising all
            # writers), it is safe to write the ref file directly.
            if not self._should_fallback_to_plumbing(ref_error):
                raise
            _log.warning("update-ref failed (%s), writing ref file directly", ref_error)
            self._direct_update_ref(branch_ref, commit_sha, parent_sha)
            warnings.append(
                "Ref updated via direct file write after update-ref could not acquire HEAD.lock."
            )
        return GitPublicationResult(
            sha=commit_sha,
            parent_sha=parent_sha,
            published_at=datetime.now(timezone.utc).isoformat(),
            operation="commit",
            mode="plumbing",
            degraded=True,
            warnings=warnings,
        )

    def commit(
        self,
        message: str,
        *,
        paths: list[str] | None = None,
        allow_empty: bool = False,
    ) -> GitPublicationResult:
        """Commit staged changes with lock-aware fallback.

        Tries the porcelain path first.  On a transient lock error, cleans any
        stale HEAD lock and falls back to the plumbing path.  If plumbing also
        fails with a transient error, attempts one final HEAD lock cleanup and,
        only if a stale lock was actually removed, retries plumbing once more.

        *paths* are content-relative; converted to git-relative internally.
        """
        self.ensure_author_identity()
        git_paths = [self._to_git_path(p) for p in paths] if paths else None

        with self.write_lock("commit"):
            # 0. Proactively clean stale git locks before attempting commit.
            self._try_cleanup_all_stale_locks()

            # 1. Try porcelain commit.
            try:
                return self._commit_porcelain(message, paths=git_paths, allow_empty=allow_empty)
            except StagingError as error:
                if not _is_transient_failure(error):
                    raise
                _log.warning("Porcelain commit failed, falling back to plumbing: %s", error)

            # 2. Clean any stale HEAD lock, then try plumbing.
            self._try_cleanup_stale_head_lock()
            try:
                return self._commit_with_plumbing(message, paths=git_paths, allow_empty=allow_empty)
            except StagingError as plumbing_error:
                if not _is_transient_failure(plumbing_error):
                    raise
                _log.warning("Plumbing commit attempt 1 failed: %s", plumbing_error)
                last_plumbing_error = plumbing_error

            # 3. Try one more cleanup. If a stale lock was actually removed,
            #    attempt plumbing one final time; otherwise give up immediately.
            cleaned = self._try_cleanup_stale_head_lock()
            if not cleaned:
                raise last_plumbing_error

            return self._commit_with_plumbing(message, paths=git_paths, allow_empty=allow_empty)

    # ------------------------------------------------------------------
    # Inspection
    # ------------------------------------------------------------------

    def log(
        self,
        n: int = 10,
        *,
        since: str | None = None,
        path_filter: str | None = None,
    ) -> list[dict]:
        """Return the last n commits as structured dicts."""
        # Use a record separator to handle multi-line messages
        sep = "|||COMMIT|||"
        cmd = [
            "git",
            "log",
            f"-{n}",
            f"--pretty=format:{sep}%H%n%s%n%ai%n",
            "--name-only",
        ]
        if since is not None:
            cmd.append(f"--after={since}")
        if path_filter is not None:
            cmd += ["--", self._to_git_path(path_filter)]

        result = self._run(cmd)

        commits = []
        raw = result.stdout.strip()
        for block in raw.split(sep):
            block = block.strip()
            if not block:
                continue
            lines = block.splitlines()
            if len(lines) < 3:
                continue
            sha = lines[0].strip()
            message = lines[1].strip()
            date = lines[2].strip()
            files = [self._from_git_path(line.strip()) for line in lines[3:] if line.strip()]
            commits.append(
                {
                    "sha": sha,
                    "message": message,
                    "date": date,
                    "files_changed": files,
                }
            )
        return commits

    def commit_count_since(self, since: str, *, paths: list[str] | None = None) -> int:
        """Return the number of commits since a date, optionally filtered to paths."""
        cmd = ["git", "rev-list", "--count", f"--since={since}", "HEAD"]
        if paths:
            git_paths = [self._to_git_path(p) for p in paths]
            cmd += ["--", *git_paths]
        result = self._run(cmd)
        return int(result.stdout.strip() or "0")

    def current_head(self) -> str:
        """Return the current HEAD commit SHA."""
        result = self._run(["git", "rev-parse", "HEAD"])
        return result.stdout.strip()

    def inspect_commit(self, sha: str) -> dict[str, object]:
        """Return structured metadata for a commit."""
        resolved = self._run(["git", "rev-parse", "--verify", f"{sha}^{{commit}}"])
        full_sha = resolved.stdout.strip()

        show_result = self._run(["git", "show", "--quiet", "--format=%H%n%s%n%P", full_sha])
        lines = show_result.stdout.splitlines()
        if len(lines) < 3:
            raise StagingError(f"Could not inspect commit metadata for {sha}")

        files_result = self._run(
            ["git", "diff-tree", "--no-commit-id", "--name-only", "--root", "-r", full_sha]
        )
        parents = [parent for parent in lines[2].split() if parent]
        files_changed = [
            self._from_git_path(line.strip())
            for line in files_result.stdout.splitlines()
            if line.strip()
        ]
        return {
            "sha": lines[0].strip(),
            "message": lines[1].strip(),
            "parents": parents,
            "files_changed": files_changed,
        }

    def revert_preview_status(self, sha: str) -> dict[str, object]:
        """Return whether reverting *sha* at HEAD would apply cleanly."""
        with tempfile.TemporaryDirectory(prefix="agent-memory-revert-preview-") as tmpdir:
            worktree_path = Path(tmpdir) / "worktree"

            add_result = subprocess.run(
                ["git", "worktree", "add", "--detach", str(worktree_path), "HEAD"],
                cwd=str(self.root),
                capture_output=True,
                text=True,
                stdin=subprocess.DEVNULL,
            )
            if add_result.returncode != 0:
                stderr = add_result.stderr.strip()
                raise StagingError(
                    f"`git worktree add` failed (exit {add_result.returncode}): {stderr}",
                    stderr=stderr,
                )

            try:
                revert_result = subprocess.run(
                    ["git", "revert", "--no-commit", "--no-edit", sha],
                    cwd=str(worktree_path),
                    capture_output=True,
                    text=True,
                    stdin=subprocess.DEVNULL,
                )
                combined = "\n".join(
                    part.strip()
                    for part in (revert_result.stdout, revert_result.stderr)
                    if part and part.strip()
                ).strip()
                return {
                    "applies_cleanly": revert_result.returncode == 0,
                    "details": combined,
                }
            finally:
                remove_result = subprocess.run(
                    ["git", "worktree", "remove", "--force", str(worktree_path)],
                    cwd=str(self.root),
                    capture_output=True,
                    text=True,
                    stdin=subprocess.DEVNULL,
                )
                if remove_result.returncode != 0:
                    stderr = remove_result.stderr.strip()
                    raise StagingError(
                        f"`git worktree remove` failed (exit {remove_result.returncode}): {stderr}",
                        stderr=stderr,
                    )

    def revert(self, sha: str) -> GitPublicationResult:
        """Create a revert commit for *sha*. Returns the new HEAD commit SHA."""
        self.ensure_author_identity()
        with self.write_lock("revert"):
            parent_sha = self.current_head()
            self._run(["git", "revert", "--no-edit", sha])
            result = self._run(["git", "rev-parse", "HEAD"])
            return GitPublicationResult(
                sha=result.stdout.strip(),
                parent_sha=parent_sha,
                published_at=datetime.now(timezone.utc).isoformat(),
                operation="revert",
                mode="porcelain",
            )

    def grep(
        self,
        pattern: str,
        *,
        glob: str = "*.md",
        case_sensitive: bool = False,
        max_count: int | None = None,
    ) -> list[tuple[str, int, str]]:
        """Run git grep and return (rel_path, line_no, line_text) triples.

        Raises StagingError only on genuine failures. Returns [] when there
        are no matches (git grep exits 1 for "no matches" — that is not an error).

        Args:
            pattern:        POSIX extended regex to match.
            glob:           Path glob passed to git grep via '--' (e.g. '*.md').
            case_sensitive: If False, passes -i to git grep.
            max_count:      If set, pass --max-count to limit matches per file.
        """
        cmd = ["git", "grep", "-n", "-E"]
        if not case_sensitive:
            cmd.append("-i")
        if max_count is not None:
            cmd += [f"--max-count={max_count}"]
        actual_glob = f"{self.content_prefix}/{glob}" if self.content_prefix else glob
        cmd += [pattern, "--", actual_glob]

        result = self._run(cmd, check=False)

        if result.returncode == 0:
            pass  # matches found
        elif result.returncode == 1:
            return []  # no matches — not an error
        else:
            # Real failure (e.g. bad regex, git not available)
            raise StagingError(
                f"git grep failed (exit {result.returncode}): {result.stderr.strip()}",
                stderr=result.stderr.strip(),
            )

        matches: list[tuple[str, int, str]] = []
        for line in result.stdout.splitlines():
            # Format: <path>:<line_no>:<content>
            try:
                path_part, rest = line.split(":", 1)
                line_no_str, text = rest.split(":", 1)
                matches.append((self._from_git_path(path_part), int(line_no_str), text))
            except ValueError:
                continue
        return matches

    def diff_status(self) -> dict[str, list[str]]:
        """Return working tree status: staged, unstaged, untracked file lists."""
        staged_result = self._run(["git", "diff", "--name-only", "--cached"], check=False)
        unstaged_result = self._run(["git", "diff", "--name-only"], check=False)
        untracked_result = self._run(
            ["git", "ls-files", "--others", "--exclude-standard"], check=False
        )

        def _lines(result: subprocess.CompletedProcess) -> list[str]:
            return [line for line in result.stdout.strip().splitlines() if line.strip()]

        return {
            "staged": [self._from_git_path(line) for line in _lines(staged_result)],
            "unstaged": [self._from_git_path(line) for line in _lines(unstaged_result)],
            "untracked": [self._from_git_path(line) for line in _lines(untracked_result)],
        }

    def first_tracked_author_date(self, rel_path: str) -> date | None:
        """Return the first git author date for a tracked path, if available."""
        result = self._run(
            [
                "git",
                "log",
                "--diff-filter=A",
                "--follow",
                "--format=%aI",
                "--reverse",
                "--",
                self._to_git_path(rel_path),
            ],
            check=False,
        )
        if result.returncode not in (0, 1):
            raise StagingError(
                f"git log failed (exit {result.returncode}): {result.stderr.strip()}",
                stderr=result.stderr.strip(),
            )

        first_line = next(
            (line.strip() for line in result.stdout.splitlines() if line.strip()),
            "",
        )
        if not first_line:
            return None

        return date.fromisoformat(first_line[:10])

    # ------------------------------------------------------------------
    # Path utilities
    # ------------------------------------------------------------------

    def abs_path(self, rel_path: str) -> Path:
        """Resolve a content-relative path to an absolute path."""
        p = (self.content_root / rel_path).resolve()
        # Ensure it's within the content root (prevent path traversal)
        try:
            p.relative_to(self.content_root)
        except ValueError:
            from .errors import MemoryPermissionError

            raise MemoryPermissionError(f"Path escapes repository root: {rel_path}", path=rel_path)
        return p

    def rel_path(self, abs_path: Path) -> str:
        """Return content-relative path from an absolute path."""
        return str(abs_path.relative_to(self.content_root))

    def health_check(self) -> dict:
        """Run diagnostic checks and return a structured health report."""
        report: dict = {
            "root": str(self.root),
            "git_dir": str(self.git_dir),
            "git_common_dir": str(self.git_common_dir),
            "locks": {},
            "repo_valid": False,
            "head_valid": False,
            "index_valid": False,
            "fs_writable": False,
            "warnings": [],
        }

        head_lock = self._head_lock_path()
        index_lock = self.git_dir / _INDEX_LOCK_NAME
        write_lock = self._write_lock_path()
        for name, path in [
            ("HEAD.lock", head_lock),
            ("index.lock", index_lock),
            ("write.lock", write_lock),
        ]:
            if path.exists():
                try:
                    age = time.time() - path.stat().st_mtime
                except OSError:
                    age = None
                pid = self._extract_pid_from_lock(path)
                alive = self._is_pid_alive(pid) if pid is not None else None
                report["locks"][name] = {
                    "exists": True,
                    "age_seconds": round(age, 1) if age is not None else None,
                    "pid": pid,
                    "pid_alive": alive,
                }
                if age is not None and age > _STALE_HEAD_LOCK_MAX_AGE_SECONDS and not alive:
                    report["warnings"].append(
                        f"Stale {name} detected (age={age:.0f}s, pid={pid} dead)"
                    )

        try:
            self._run(["git", "rev-parse", "--git-dir"])
            report["repo_valid"] = True
        except StagingError:
            report["warnings"].append("git rev-parse --git-dir failed")

        try:
            self._run(["git", "rev-parse", "HEAD"])
            report["head_valid"] = True
        except StagingError:
            report["warnings"].append("HEAD is not valid (empty repo?)")

        try:
            index_result = self._run(
                ["git", "diff-index", "--quiet", "--cached", "HEAD"], check=False
            )
            if index_result.returncode in (0, 1):
                report["index_valid"] = True
            else:
                report["warnings"].append("Index check failed")
        except StagingError:
            report["warnings"].append("Index check failed")

        test_path = self.root / ".engram-fs-test"
        try:
            test_path.write_text("test", encoding="utf-8")
            test_path.unlink()
            report["fs_writable"] = True
        except OSError as exc:
            report["warnings"].append(f"Filesystem write test failed: {exc}")

        return report
