"""
Tier 2 — Low-level write tools (staged, no auto-commit).

These replace raw Edit/Write/Bash calls for memory writes. All tools:
  - Accept an optional version_token for optimistic locking
  - Stage changes but do NOT commit (call memory_commit when ready)
  - Return MemoryWriteResult JSON
  - Support an optional delete-permission hook for runtimes that need it

Directory restrictions:
  ALL Tier 2 mutation tools (memory_write, memory_edit, memory_delete,
    memory_move, memory_update_frontmatter, memory_update_frontmatter_bulk)
    reject paths under protected directories: memory/users/, governance/,
    memory/activity/, memory/skills/.
  Use Tier 1 semantic tools for governed writes to protected directories.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, cast

from ..path_policy import (
    KNOWN_COMMIT_PREFIXES,
    validate_raw_move_destination,
    validate_raw_mutation_source,
    validate_raw_write_target,
)

_MAX_FRONTMATTER_BULK_UPDATES = 100


def _max_file_bytes() -> int:
    """Return the configured file-size ceiling (default 512 KB).

    Uses ENGRAM_MAX_FILE_SIZE — the same env var as ContentSizeGuard in
    guard_pipeline.py — so a single override controls both checks.
    """
    return int(os.environ.get("ENGRAM_MAX_FILE_SIZE", "512000"))


if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def _tool_annotations(**kwargs: object) -> Any:
    """Return MCP tool annotations with a relaxed runtime-only type surface."""
    return cast(Any, kwargs)


def _drop_tracked_paths(tracked_paths: list[str], *paths: str) -> None:
    blocked = set(paths)
    tracked_paths[:] = [path for path in tracked_paths if path not in blocked]


def _normalize_frontmatter_bulk_entry(
    entry: object, index: int
) -> tuple[str, dict[str, Any], str | None]:
    from ..errors import ValidationError

    if not isinstance(entry, dict):
        raise ValidationError(f"updates[{index}] must be an object")

    path = entry.get("path")
    fields = entry.get("fields")
    version_token = entry.get("version_token")

    if not isinstance(path, str) or not path.strip():
        raise ValidationError(f"updates[{index}].path must be a non-empty string")
    if not isinstance(fields, dict):
        raise ValidationError(f"updates[{index}].fields must be an object")
    if version_token is not None and not isinstance(version_token, str):
        raise ValidationError(f"updates[{index}].version_token must be a string when provided")

    return path, dict(fields), version_token


def _merge_frontmatter_fields(
    current_frontmatter: dict[str, Any],
    updates: dict[str, Any],
    *,
    create_missing_keys: bool,
) -> tuple[dict[str, Any], bool]:
    from ..frontmatter_utils import merge_frontmatter_fields

    return merge_frontmatter_fields(
        current_frontmatter,
        updates,
        create_missing_keys=create_missing_keys,
        auto_last_verified=False,
    )


def register(
    mcp: "FastMCP",
    get_repo,
    get_root,
    grant_delete_permission: Callable[[str], None] | None = None,
) -> dict[str, object]:
    """Register all Tier 2 low-level write tools and return their callables."""

    from ..guard_pipeline import require_guarded_write_pass

    def _run_guards(path: str, operation: str, content: str | None = None) -> None:
        """Run the shared guard pipeline; raise ValidationError on block."""
        require_guarded_write_pass(
            path=path,
            operation=operation,
            root=get_root(),
            content=content,
        )

    tracked_paths: list[str] = []

    def track_paths(*paths: str) -> None:
        for path in paths:
            if path not in tracked_paths:
                tracked_paths.append(path)

    # ------------------------------------------------------------------
    # memory_write
    # ------------------------------------------------------------------
    @mcp.tool(
        name="memory_write",
        annotations=_tool_annotations(
            title="Write Memory File",
            readOnlyHint=False,
            destructiveHint=True,
            idempotentHint=False,
            openWorldHint=False,
        ),
    )
    async def memory_write(
        path: str,
        content: str,
        version_token: str | None = None,
        create_dirs: bool = True,
    ) -> str:
        """Create or overwrite a file and stage it (no auto-commit).

        Call memory_commit when all related writes are staged.

        DIRECTORY RESTRICTIONS: Writes to protected directories (memory/users/,
        governance/, memory/activity/, memory/skills/) are blocked. Use the
        appropriate Tier 1 semantic tool instead (e.g. memory_update_user_trait,
        memory_record_chat_summary). Allowed targets: memory/knowledge/,
        memory/working/, memory/working/notes/.

        Args:
            path:          Repo-relative path (e.g. 'memory/knowledge/_unverified/django/foo.md').
            content:       Full file content to write.
            version_token: If provided, checked against the current file hash before
                           writing. Pass the token returned by memory_read_file to
                           detect concurrent modifications (ConflictError on mismatch).
            create_dirs:   Create parent directories if they don't exist (default: True).

        Returns:
            MemoryWriteResult JSON with new_state.version_token for the written file.
        """
        from ..errors import NotFoundError, ValidationError
        from ..models import MemoryWriteResult

        repo = get_repo()
        path, abs_path = validate_raw_write_target(repo, path)
        _run_guards(path, "write", content=content)

        max_bytes = _max_file_bytes()
        content_bytes = len(content.encode("utf-8"))
        if content_bytes > max_bytes:
            raise ValidationError(
                f"Content is {content_bytes:,} bytes, which exceeds the "
                f"{max_bytes:,}-byte limit (set ENGRAM_MAX_FILE_SIZE to override). "
                "Summarize or split the content before writing."
            )

        if version_token is not None:
            if not abs_path.exists():
                raise NotFoundError(f"Cannot check version_token: {path} does not exist")
            repo.check_version_token(path, version_token)

        if abs_path.exists():
            existing_content = abs_path.read_text(encoding="utf-8")
            if existing_content == content:
                result = MemoryWriteResult(
                    files_changed=[],
                    commit_sha=None,
                    commit_message=None,
                    new_state={"version_token": repo.hash_object(path), "changed": False},
                )
                return result.to_json()

        if create_dirs:
            abs_path.parent.mkdir(parents=True, exist_ok=True)

        abs_path.write_text(content, encoding="utf-8")
        repo.add(path)
        track_paths(path)
        new_token = repo.hash_object(path)

        result = MemoryWriteResult(
            files_changed=[path],
            commit_sha=None,
            commit_message=None,
            new_state={"version_token": new_token, "changed": True},
        )
        return result.to_json()

    # ------------------------------------------------------------------
    # memory_edit
    # ------------------------------------------------------------------
    @mcp.tool(
        name="memory_edit",
        annotations=_tool_annotations(
            title="Edit Memory File (String Replace)",
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=False,
            openWorldHint=False,
        ),
    )
    async def memory_edit(
        path: str,
        old_string: str,
        new_string: str,
        replace_all: bool = False,
        version_token: str | None = None,
    ) -> str:
        """Exact string replacement in a file, then stage (no auto-commit).

        DIRECTORY RESTRICTIONS: Same as memory_write — protected directories
        (memory/users/, governance/, memory/activity/, memory/skills/) are
        blocked for raw edits. Use Tier 1 semantic tools for governed
        modifications to those directories.

        Raises ValidationError if old_string is not found, or is not unique
        when replace_all=False.

        Args:
            path:          Repo-relative path to the file.
            old_string:    Exact string to find and replace.
            new_string:    Replacement text.
            replace_all:   Replace all occurrences (default: False — raises if >1).
            version_token: Optional — checked before writing.

        Returns:
            MemoryWriteResult JSON with new_state.version_token.
        """
        from ..errors import NotFoundError, ValidationError
        from ..models import MemoryWriteResult

        repo = get_repo()
        path, abs_path = validate_raw_write_target(repo, path)

        if not abs_path.exists():
            raise NotFoundError(f"File not found: {path}")

        repo.check_version_token(path, version_token)
        content = abs_path.read_text(encoding="utf-8")

        count = content.count(old_string)
        if count == 0:
            raise ValidationError(
                f"old_string not found in {path}. "
                "Ensure you're matching the exact text including whitespace."
            )
        if count > 1 and not replace_all:
            raise ValidationError(
                f"old_string appears {count} times in {path}. "
                "Use replace_all=True to replace all occurrences, or provide "
                "more surrounding context to make it unique."
            )

        if replace_all:
            new_content = content.replace(old_string, new_string)
        else:
            new_content = content.replace(old_string, new_string, 1)

        _run_guards(path, "write", content=new_content)
        if new_content == content:
            result = MemoryWriteResult(
                files_changed=[],
                commit_sha=None,
                commit_message=None,
                new_state={
                    "version_token": repo.hash_object(path),
                    "replacements": 0,
                    "changed": False,
                },
            )
            return result.to_json()

        abs_path.write_text(new_content, encoding="utf-8")
        repo.add(path)
        track_paths(path)
        new_token = repo.hash_object(path)

        result = MemoryWriteResult(
            files_changed=[path],
            commit_sha=None,
            commit_message=None,
            new_state={
                "version_token": new_token,
                "replacements": count if replace_all else 1,
                "changed": True,
            },
        )
        return result.to_json()

    # ------------------------------------------------------------------
    # memory_delete
    # ------------------------------------------------------------------
    @mcp.tool(
        name="memory_delete",
        annotations=_tool_annotations(
            title="Delete Memory File",
            readOnlyHint=False,
            destructiveHint=True,
            idempotentHint=False,
            openWorldHint=False,
        ),
    )
    async def memory_delete(
        path: str,
        version_token: str | None = None,
    ) -> str:
        """Delete a file and stage the removal (no auto-commit).

        ALLOWED PATHS ONLY: memory/knowledge/, memory/working/, memory/working/notes/.
        Attempts to delete files under memory/users/, governance/, memory/activity/,
        or memory/skills/ raise PermissionError immediately, before any filesystem
        access.

        The deletion is staged via 'git rm'. Call memory_commit to finalise.
        When a delete-permission hook is configured by the runtime, it is
        called automatically for allowed paths before the file is removed.

        Args:
            path:          Repo-relative path to delete. Must be under
                           memory/knowledge/, memory/working/, or
                           memory/working/notes/.
            version_token: Optional — checked before deletion.

        Returns:
            MemoryWriteResult JSON.
        """
        from ..errors import MemoryPermissionError, NotFoundError, StagingError
        from ..models import MemoryWriteResult

        repo = get_repo()
        path, abs_path = validate_raw_mutation_source(
            repo,
            path,
            operation="delete",
        )

        if not abs_path.exists():
            raise NotFoundError(f"File not found: {path}")

        repo.check_version_token(path, version_token)

        if grant_delete_permission is not None:
            try:
                grant_delete_permission(path)
            except Exception as e:
                raise MemoryPermissionError(
                    f"Delete permission hook rejected '{path}': {e}",
                    path=path,
                ) from e

        try:
            repo.rm(path)
            track_paths(path)
        except MemoryPermissionError:
            raise
        except (StagingError, OSError) as e:
            raise StagingError(
                f"Could not delete {path}: {e}.",
                stderr=getattr(e, "stderr", str(e)),
            ) from e

        result = MemoryWriteResult(
            files_changed=[path],
            commit_sha=None,
            commit_message=None,
            new_state={"deleted": path},
        )
        return result.to_json()

    # ------------------------------------------------------------------
    # memory_move
    # ------------------------------------------------------------------
    @mcp.tool(
        name="memory_move",
        annotations=_tool_annotations(
            title="Move/Rename Memory File",
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=False,
            openWorldHint=False,
        ),
    )
    async def memory_move(
        source: str,
        dest: str,
        version_token: str | None = None,
        create_dirs: bool = True,
    ) -> str:
        """Rename or move a file, preserving git history (git mv).

        SOURCE PATH RESTRICTIONS: Same as memory_delete — source paths in
        memory/users/, governance/, memory/activity/, or memory/skills/ are
        blocked. Destination paths in protected directories are also blocked;
        use Tier 1 semantic tools for governed writes into those folders.

        The move is staged. Call memory_commit to finalise.

        Args:
            source:        Repo-relative source path.
            dest:          Repo-relative destination path.
            version_token: Optional — checked against source before moving.
            create_dirs:   Create destination parent dirs if needed (default: True).

        Returns:
            MemoryWriteResult JSON with new_state.new_version_token.
        """
        from ..errors import NotFoundError
        from ..models import MemoryWriteResult

        repo = get_repo()
        source, abs_source = validate_raw_mutation_source(
            repo,
            source,
            operation="move from",
        )
        dest, abs_dest = validate_raw_move_destination(repo, dest, field_name="dest")

        if not abs_source.exists():
            raise NotFoundError(f"Source file not found: {source}")

        repo.check_version_token(source, version_token)

        if create_dirs:
            abs_dest.parent.mkdir(parents=True, exist_ok=True)

        repo.mv(source, dest)
        track_paths(source, dest)
        new_token = repo.hash_object(dest)

        result = MemoryWriteResult(
            files_changed=[source, dest],
            commit_sha=None,
            commit_message=None,
            new_state={"new_path": dest, "new_version_token": new_token},
        )
        return result.to_json()

    # ------------------------------------------------------------------
    # memory_update_frontmatter
    # ------------------------------------------------------------------
    @mcp.tool(
        name="memory_update_frontmatter",
        annotations=_tool_annotations(
            title="Update File Frontmatter",
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=False,
            openWorldHint=False,
        ),
    )
    async def memory_update_frontmatter(
        path: str,
        updates: str,
        version_token: str | None = None,
    ) -> str:
        """Merge key-value pairs into a file's YAML frontmatter (no auto-commit).

        DIRECTORY RESTRICTIONS: Same as memory_write — protected directories
        (memory/users/, governance/, memory/activity/, memory/skills/) are
        blocked for raw frontmatter updates. Use Tier 1 semantic tools for
        governed modifications.

        Does not touch the file body. Always sets last_verified to today's date
        only when 'last_verified' is explicitly included in updates.

        Pass null as a value to remove a frontmatter key.

        Args:
            path:          Repo-relative file path.
            updates:       JSON object of frontmatter key-value pairs to set.
                           Use null values to remove keys.
                           Example: '{"status": "complete", "next_action": null}'
            version_token: Optional — checked before writing.

        Use memory_tool_schema for the machine-readable contract.

        Returns:
            MemoryWriteResult JSON with new_state containing the full updated frontmatter.
        """
        from ..errors import NotFoundError, ValidationError
        from ..frontmatter_utils import (
            merge_frontmatter_fields,
            read_with_frontmatter,
            render_with_frontmatter,
            write_with_frontmatter,
        )
        from ..models import MemoryWriteResult

        repo = get_repo()
        path, abs_path = validate_raw_write_target(repo, path)

        if not abs_path.exists():
            raise NotFoundError(f"File not found: {path}")

        try:
            updates_dict = json.loads(updates)
        except json.JSONDecodeError as e:
            raise ValidationError(f"Invalid JSON for updates: {e}")

        if not isinstance(updates_dict, dict):
            raise ValidationError("updates must be a JSON object")

        repo.check_version_token(path, version_token)

        try:
            current_fm, body = read_with_frontmatter(abs_path)
        except Exception as exc:
            raise ValidationError(f"Could not parse frontmatter in {path}: {exc}") from exc

        updated_fm, changed = merge_frontmatter_fields(
            current_fm,
            updates_dict,
            auto_last_verified=False,
        )
        rendered = render_with_frontmatter(updated_fm, body)
        _run_guards(path, "write", content=rendered)
        if changed:
            write_with_frontmatter(abs_path, updated_fm, body)
            repo.add(path)
            track_paths(path)

        result = MemoryWriteResult(
            files_changed=[path] if changed else [],
            commit_sha=None,
            commit_message=None,
            new_state={
                "frontmatter": json.loads(json.dumps(updated_fm, default=str)),
                "changed": changed,
            },
        )
        return result.to_json()

    # ------------------------------------------------------------------
    # memory_update_frontmatter_bulk
    # ------------------------------------------------------------------
    @mcp.tool(
        name="memory_update_frontmatter_bulk",
        annotations=_tool_annotations(
            title="Update Frontmatter In Batch",
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=False,
            openWorldHint=False,
        ),
    )
    async def memory_update_frontmatter_bulk(
        updates: list[dict[str, object]],
        create_missing_keys: bool = True,
    ) -> str:
        """Apply frontmatter updates to multiple files as a single staged transaction.

        DIRECTORY RESTRICTIONS: Same as memory_write — protected directories
        (memory/users/, governance/, memory/activity/, memory/skills/) are
        blocked for raw frontmatter updates. Use Tier 1 semantic tools for
        governed modifications.

        Every update object must contain:
        - `path`: repo-relative file path
        - `fields`: object of frontmatter key/value pairs to set

        Optional per-entry field:
        - `version_token`: optimistic-lock token previously returned by
          memory_read_file for that file

        The batch validates every entry before staging anything. If a later
        write or `git add` fails, all touched paths are restored to HEAD and
        the staged transaction is discarded.

        Args:
            updates: List of update objects.
            create_missing_keys: Add keys that do not already exist in a file's
                                 frontmatter (default: True).

        Returns:
            MemoryWriteResult JSON with per-batch counts and transaction state.
        """
        from ..errors import NotFoundError, ValidationError
        from ..frontmatter_utils import (
            read_with_frontmatter,
            render_with_frontmatter,
            write_with_frontmatter,
        )
        from ..models import MemoryWriteResult

        repo = get_repo()

        if not isinstance(updates, list) or not updates:
            raise ValidationError("updates must be a non-empty list of update objects")
        if len(updates) > _MAX_FRONTMATTER_BULK_UPDATES:
            raise ValidationError(
                f"updates may contain at most {_MAX_FRONTMATTER_BULK_UPDATES} files per batch"
            )

        prepared_entries: list[dict[str, Any]] = []
        validation_errors: list[str] = []
        seen_paths: set[str] = set()

        for index, entry in enumerate(updates):
            try:
                raw_path, fields, version_token = _normalize_frontmatter_bulk_entry(entry, index)
                path, abs_path = validate_raw_write_target(repo, raw_path)

                if path in seen_paths:
                    raise ValidationError(f"duplicate path in batch: {path}")
                seen_paths.add(path)

                if not abs_path.exists():
                    raise NotFoundError(f"File not found: {path}")
                if repo.has_staged_changes(path) or repo.has_unstaged_changes(path):
                    raise ValidationError(f"Path already has staged or unstaged changes: {path}")

                repo.check_version_token(path, version_token)
                try:
                    current_frontmatter, body = read_with_frontmatter(abs_path)
                except Exception as exc:
                    raise ValidationError(f"Could not parse frontmatter in {path}: {exc}") from exc
                merged_frontmatter, changed = _merge_frontmatter_fields(
                    current_frontmatter,
                    fields,
                    create_missing_keys=create_missing_keys,
                )
                if changed:
                    rendered = render_with_frontmatter(merged_frontmatter, body)
                    _run_guards(path, "write", content=rendered)
                prepared_entries.append(
                    {
                        "path": path,
                        "abs_path": abs_path,
                        "body": body,
                        "frontmatter": merged_frontmatter,
                        "changed": changed,
                    }
                )
            except Exception as exc:
                label = (
                    entry.get("path")
                    if isinstance(entry, dict) and isinstance(entry.get("path"), str)
                    else f"updates[{index}]"
                )
                validation_errors.append(f"{label}: {exc}")

        if validation_errors:
            joined = "\n".join(f"- {message}" for message in validation_errors)
            raise ValidationError(f"Bulk frontmatter update validation failed:\n{joined}")

        files_changed: list[str] = []
        mutated_paths: list[str] = []
        skipped_count = 0

        try:
            for entry in prepared_entries:
                if not entry["changed"]:
                    skipped_count += 1
                    continue

                path = cast(str, entry["path"])
                abs_path = cast(Any, entry["abs_path"])
                body = cast(str, entry["body"])
                frontmatter = cast(dict[str, Any], entry["frontmatter"])

                write_with_frontmatter(abs_path, frontmatter, body)
                mutated_paths.append(path)
                repo.add(path)
                files_changed.append(path)
        except Exception:
            if mutated_paths:
                repo.restore_paths(*mutated_paths)
                _drop_tracked_paths(tracked_paths, *mutated_paths)
            raise

        track_paths(*files_changed)

        result = MemoryWriteResult(
            files_changed=files_changed,
            commit_sha=None,
            commit_message=None,
            new_state={
                "updated_count": len(files_changed),
                "skipped_count": skipped_count,
                "transaction_state": "staged",
            },
        )
        return result.to_json()

    # ------------------------------------------------------------------
    # memory_commit
    # ------------------------------------------------------------------
    @mcp.tool(
        name="memory_commit",
        annotations=_tool_annotations(
            title="Commit Staged Memory Changes",
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=False,
            openWorldHint=False,
        ),
    )
    async def memory_commit(
        message: str,
        allow_empty: bool = False,
    ) -> str:
        """Commit all staged changes to the memory repository.

        Should follow the memory commit convention:
          [{category}] {Verb} {description ≤60 chars}

        Known categories: [knowledge] [project] [user] [chat] [curation]
                          [working] [system]

        Warns (does not error) on unrecognised prefix — the warning appears
        in new_state.warnings so the agent can decide whether to revise.

        Args:
            message:     Commit message following the convention above.
            allow_empty: Allow committing with nothing staged (default: False).

        Returns:
            MemoryWriteResult JSON with commit_sha and any prefix warnings.
        """
        from ..errors import StagingError
        from ..models import MemoryWriteResult

        repo = get_repo()
        warnings = []
        pending_paths = list(tracked_paths)
        staged_pending_paths = repo.staged_paths(*pending_paths) if pending_paths else []
        tracked_paths[:] = staged_pending_paths

        if staged_pending_paths:
            if repo.has_unstaged_changes(*staged_pending_paths):
                raise StagingError(
                    "Tracked Tier 2 paths have unstaged working-tree changes. "
                    "Stage or revert those edits before calling memory_commit."
                )
        elif pending_paths:
            if not repo.has_staged_changes(*pending_paths):
                raise StagingError(
                    "No Tier 2 staged changes remain for the tracked paths. "
                    "Stage new Tier 2 changes before calling memory_commit."
                )
        elif repo.nothing_staged():
            if not allow_empty:
                raise StagingError(
                    "Nothing staged to commit. Use memory_write/memory_edit/memory_delete "
                    "first, then call memory_commit."
                )
        else:
            raise StagingError(
                "No Tier 2 changes are pending commit. memory_commit will not commit "
                "unrelated pre-staged changes."
            )

        # Validate prefix (warn, don't error)
        import re

        prefix_match = re.match(r"^\[([^\]]+)\]", message)
        if not prefix_match:
            warnings.append(
                f"Commit message '{message[:50]}...' does not start with a "
                f"recognised [category] prefix. Known prefixes: "
                f"{sorted(KNOWN_COMMIT_PREFIXES)}"
            )
        else:
            full_prefix = f"[{prefix_match.group(1)}]"
            if full_prefix not in KNOWN_COMMIT_PREFIXES:
                warnings.append(
                    f"Unrecognised commit prefix '{full_prefix}'. "
                    f"Known prefixes: {sorted(KNOWN_COMMIT_PREFIXES)}. "
                    "Proceeding anyway."
                )

        if staged_pending_paths:
            commit_result = repo.commit(message, paths=staged_pending_paths)
            tracked_paths.clear()
            files_changed = staged_pending_paths
        else:
            commit_result = repo.commit(message, allow_empty=allow_empty)
            files_changed = []

        result = MemoryWriteResult.from_commit(
            files_changed=files_changed,
            commit_result=commit_result,
            commit_message=message,
            new_state={},
            warnings=warnings,
        )
        return result.to_json()

    return {
        "memory_write": memory_write,
        "memory_edit": memory_edit,
        "memory_delete": memory_delete,
        "memory_move": memory_move,
        "memory_update_frontmatter": memory_update_frontmatter,
        "memory_update_frontmatter_bulk": memory_update_frontmatter_bulk,
        "memory_commit": memory_commit,
    }
