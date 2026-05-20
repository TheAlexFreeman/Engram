"""Read tools — inspection submodule."""

from __future__ import annotations

import tempfile
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from ...errors import NotFoundError, ValidationError
from ...frontmatter_utils import read_with_frontmatter
from ...response_envelope import dump_tool_result

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

    from ...session_state import SessionState


def register_inspection(
    mcp: "FastMCP",
    get_repo,
    get_root,
    H,
    *,
    session_state: "SessionState | None" = None,
) -> dict[str, object]:
    """Register inspection read tools and return their callables."""
    _IGNORED_NAMES = H._IGNORED_NAMES
    _READ_FILE_INLINE_THRESHOLD_BYTES = H._READ_FILE_INLINE_THRESHOLD_BYTES
    _READ_FILE_DEFAULT_LIMIT_BYTES = H._READ_FILE_DEFAULT_LIMIT_BYTES
    _READ_FILE_MAX_LIMIT_BYTES = H._READ_FILE_MAX_LIMIT_BYTES
    _cross_filesystem_sandbox_detected = H._cross_filesystem_sandbox_detected
    _build_markdown_sections = H._build_markdown_sections
    _display_rel_path = H._display_rel_path
    _effective_date = H._effective_date
    _extract_preview_words = H._extract_preview_words
    _frontmatter_health_report = H._frontmatter_health_report
    _is_humans_path = H._is_humans_path
    _iter_frontmatter_health_files = H._iter_frontmatter_health_files
    _match_requested_sections = H._match_requested_sections
    _parse_trust_thresholds = H._parse_trust_thresholds
    _preview_file_entry = H._preview_file_entry
    _resolve_humans_root = H._resolve_humans_root
    _resolve_memory_subpath = H._resolve_memory_subpath
    _resolve_visible_path = H._resolve_visible_path
    _review_expiry_threshold_days = H._review_expiry_threshold_days
    _split_csv_or_lines = H._split_csv_or_lines
    _tool_annotations = H._tool_annotations

    # ------------------------------------------------------------------
    @mcp.tool(
        name="memory_read_file",
        annotations=_tool_annotations(
            title="Read Memory File",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def memory_read_file(
        path: str,
        offset_bytes: int = 0,
        limit_bytes: int | None = None,
        prefer_temp_file: bool = False,
    ) -> str:
        """Read a file from the memory repository.

        Returns file metadata, parsed frontmatter, and either the full content
        inline (for files within the inline threshold) or a paginated byte slice
        with pagination metadata so agents can request the rest. A temporary-file
        path is returned only when ``prefer_temp_file=True`` and the deployment
        is not cross-filesystem; otherwise the response is always inline.

        Args:
            path: Repo-relative content path (e.g. 'memory/users/profile.md',
                'memory/knowledge/_unverified/django/celery-canvas.md').
            offset_bytes: Byte offset into the file to begin reading. Defaults to
                0 (start of file).
            limit_bytes: Maximum number of bytes to return inline starting at
                ``offset_bytes``. When omitted, defaults to the inline threshold.
                Hard-capped at an upper bound to protect response size. Slicing
                happens on bytes; UTF-8 boundary errors at the edges are
                handled with ``errors="replace"``.
            prefer_temp_file: When True *and* the deployment is same-filesystem
                (``AGENT_MEMORY_CROSS_FILESYSTEM`` is not set), the full file is
                also written to a temp file and its path is returned. Ignored on
                cross-filesystem deployments.

        Returns:
            JSON envelope with keys:
                result.path          (str)       Repo-relative path requested
                result.size_bytes    (int)       Full UTF-8 byte size of the file
                result.total_bytes   (int)       Alias of size_bytes kept for agents
                                                 reasoning about pagination
                result.offset_bytes  (int)       Start of the returned slice
                result.returned_bytes(int)       Number of bytes in the returned slice
                result.inline        (bool)      True when content is returned inline
                                                 (now always True unless prefer_temp_file
                                                 is honored)
                result.has_more      (bool)      True when offset+returned < total
                result.next_call_hint(dict|null) When has_more, suggested next
                                                 ``{offset_bytes, limit_bytes}`` pagination
                                                 arguments. Null otherwise.
                result.content       (str)       File text (full when has_more is False,
                                                 otherwise the slice)
                result.temp_file     (str)       Optional; only present when
                                                 ``prefer_temp_file`` is honored
                result.version_token (str)       Git SHA-1 of the file; pass back to
                                                 write tools to detect concurrent
                                                 modifications
                result.frontmatter   (dict|null) Parsed YAML frontmatter, or null.
                                                 Only populated for full-file reads
                                                 (offset 0, has_more False); paginated
                                                 reads return null to avoid
                                                 misrepresenting a partial slice
                _session             (dict)      Compact session metadata for the call
        """
        if not isinstance(offset_bytes, int) or isinstance(offset_bytes, bool) or offset_bytes < 0:
            raise ValidationError("offset_bytes must be a non-negative integer")
        if limit_bytes is not None:
            if (
                not isinstance(limit_bytes, int)
                or isinstance(limit_bytes, bool)
                or limit_bytes <= 0
            ):
                raise ValidationError("limit_bytes must be a positive integer when provided")
            if limit_bytes > _READ_FILE_MAX_LIMIT_BYTES:
                raise ValidationError(f"limit_bytes must not exceed {_READ_FILE_MAX_LIMIT_BYTES}")
        effective_limit = limit_bytes or _READ_FILE_DEFAULT_LIMIT_BYTES

        root = get_root()
        repo = get_repo()
        abs_path = _resolve_visible_path(root, path)
        if not abs_path.exists():
            raise NotFoundError(f"File not found: {path}")

        display_path = _display_rel_path(abs_path, root)

        try:
            abs_path.relative_to(root)
        except ValueError:
            version_token = repo._run(["git", "hash-object", str(abs_path)]).stdout.strip()
        else:
            version_token = repo.hash_object(display_path)

        raw_bytes = abs_path.read_bytes()
        total_bytes = len(raw_bytes)

        slice_end = min(offset_bytes + effective_limit, total_bytes)
        if offset_bytes > total_bytes:
            offset_bytes = total_bytes
        slice_bytes = raw_bytes[offset_bytes:slice_end]
        returned_bytes = len(slice_bytes)
        has_more = slice_end < total_bytes
        is_full_read = offset_bytes == 0 and not has_more

        # Decode with error tolerance so a slice that lands mid-codepoint does
        # not raise. Full reads always decode cleanly because the file is UTF-8.
        content = slice_bytes.decode("utf-8", errors="replace")

        frontmatter: dict[str, Any] | None = None
        if is_full_read:
            fm_dict, _body = read_with_frontmatter(abs_path)
            frontmatter = fm_dict or None

        result: dict[str, Any] = {
            "path": display_path,
            "size_bytes": total_bytes,
            "total_bytes": total_bytes,
            "offset_bytes": offset_bytes,
            "returned_bytes": returned_bytes,
            "inline": True,
            "has_more": has_more,
            "next_call_hint": (
                {"offset_bytes": slice_end, "limit_bytes": effective_limit} if has_more else None
            ),
            "content": content,
            "version_token": version_token,
            "frontmatter": frontmatter,
        }

        # prefer_temp_file is an escape hatch for same-filesystem callers that
        # want the whole file in one shot even when the inline slice is
        # paginated. Skip when (a) the file already fits inline (no pagination
        # happening), (b) the caller didn't ask, or (c) the deployment flags
        # cross-filesystem — the path wouldn't resolve from the sandbox.
        if (
            prefer_temp_file
            and total_bytes > _READ_FILE_INLINE_THRESHOLD_BYTES
            and not _cross_filesystem_sandbox_detected()
        ):
            suffix = abs_path.suffix or ".txt"
            with tempfile.NamedTemporaryFile(
                mode="wb",
                suffix=suffix,
                prefix="agent-memory-read-",
                delete=False,
            ) as handle:
                handle.write(raw_bytes)
                temp_path = handle.name
            result["temp_file"] = temp_path

        if session_state is not None:
            session_state.record_tool_call()
            session_state.record_read(display_path)
        return dump_tool_result(result, session_state, default=str)

    # ------------------------------------------------------------------
    # memory_list_folder

    # ------------------------------------------------------------------
    @mcp.tool(
        name="memory_list_folder",
        annotations=_tool_annotations(
            title="List Memory Folder",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def memory_list_folder(
        path: str = ".",
        include_hidden: bool = False,
        include_humans: bool = False,
        preview_chars: int = 0,
    ) -> str:
        """List the contents of a folder in the memory repository.

        Args:
            path:           Repo-relative folder path (default: repo root '.').
            include_hidden: Include dot-files/folders (default: False).
            include_humans: Include the human-facing HUMANS/ tree when browsing
                            broad scopes like '.' (default: False).
            preview_chars:  When > 0, return structured JSON including markdown
                            frontmatter and a truncated body preview.

        Returns:
            Markdown-formatted directory listing with file sizes when
            preview_chars == 0; otherwise structured JSON entry metadata.
        """
        root = get_root()
        folder = _resolve_visible_path(root, path)
        if not folder.exists():
            return f"Error: Folder not found: {path}"
        if not folder.is_dir():
            return f"Error: Not a directory: {path}"

        explicit_humans_request = _is_humans_path(folder, root)
        lines = [f"# {path}/\n"]
        try:
            all_entries = list(folder.iterdir())
        except PermissionError:
            return f"Error: Permission denied reading {path}"

        if not explicit_humans_request and include_humans and path in {"", "."}:
            humans_root = _resolve_humans_root(root)
            if humans_root.exists() and humans_root.is_dir():
                all_entries.append(humans_root)

        def _keep(entry: Path) -> bool:
            if entry.name in _IGNORED_NAMES:
                return False
            if not include_hidden and entry.name.startswith("."):
                return False
            if not explicit_humans_request and not include_humans and _is_humans_path(entry, root):
                return False
            return True

        entries = sorted(
            [entry for entry in all_entries if _keep(entry)],
            key=lambda p: (p.is_file(), p.name),
        )

        if preview_chars > 0:
            payload_entries: list[dict[str, Any]] = []
            for entry in entries:
                rel = _display_rel_path(entry, root)
                if entry.is_dir():
                    payload_entries.append(
                        {
                            "name": entry.name,
                            "path": rel,
                            "kind": "directory",
                        }
                    )
                else:
                    payload_entries.append(_preview_file_entry(entry, root, preview_chars))

            result = {
                "path": path,
                "preview_chars": preview_chars,
                "entries": payload_entries,
            }
            if session_state is not None:
                session_state.record_tool_call()
            return dump_tool_result(result, session_state, default=str)

        for entry in entries:
            rel = _display_rel_path(entry, root)
            if entry.is_dir():
                lines.append(f"📁 {rel}/")
            else:
                size = entry.stat().st_size
                lines.append(f"📄 {entry.name}  ({size:,} bytes)  `{rel}`")

        if len(lines) == 1:
            lines.append("_(empty)_")
        if session_state is not None:
            session_state.record_tool_call()
        return "\n".join(lines)

    def _build_review_unverified_payload(
        root: Any,
        folder_path: str,
        max_extract_words: int,
        include_expired: bool,
    ) -> dict[str, Any]:
        """Build the unverified-review payload dict without recording a tool call."""
        folder = _resolve_memory_subpath(root, folder_path, "knowledge/_unverified")
        if not folder.exists():
            return {
                "folder_path": folder_path,
                "max_extract_words": max_extract_words,
                "include_expired": include_expired,
                "total_files": 0,
                "expired_count": 0,
                "trust_counts": {"low": 0, "medium": 0, "high": 0, "unknown": 0},
                "groups": {},
            }
        if not folder.is_dir():
            raise ValidationError(f"Not a directory: {folder_path}")

        low_threshold, medium_threshold = _parse_trust_thresholds(root)
        today = date.today()
        grouped: dict[str, list[dict[str, Any]]] = {}
        trust_counts = {"low": 0, "medium": 0, "high": 0, "unknown": 0}
        total_files = 0
        expired_count = 0

        for md_file in sorted(folder.rglob("*.md")):
            if not md_file.is_file() or md_file.name == "SUMMARY.md":
                continue

            rel_path = md_file.relative_to(root).as_posix()
            group_key = md_file.parent.relative_to(folder).as_posix()
            if group_key == ".":
                group_key = ""

            frontmatter, body = read_with_frontmatter(md_file)
            effective_date = _effective_date(frontmatter)
            days_old = (today - effective_date).days if effective_date is not None else None
            trust_value = frontmatter.get("trust")
            trust = str(trust_value) if trust_value is not None else None
            threshold = _review_expiry_threshold_days(trust, low_threshold, medium_threshold)
            expired = days_old is not None and threshold is not None and days_old > threshold

            if not include_expired and expired:
                continue

            total_files += 1
            if trust in trust_counts:
                trust_counts[cast(str, trust)] += 1
            else:
                trust_counts["unknown"] += 1
            if expired:
                expired_count += 1

            grouped.setdefault(group_key, []).append(
                {
                    "path": rel_path,
                    "created": str(frontmatter.get("created"))
                    if frontmatter.get("created") is not None
                    else None,
                    "source": frontmatter.get("source"),
                    "trust": trust,
                    "days_old": days_old,
                    "expired": expired,
                    "extract": _extract_preview_words(body, max_extract_words),
                }
            )

        return {
            "folder_path": folder_path,
            "max_extract_words": max_extract_words,
            "include_expired": include_expired,
            "total_files": total_files,
            "expired_count": expired_count,
            "trust_counts": trust_counts,
            "groups": grouped,
        }

    @mcp.tool(
        name="memory_review_unverified",
        annotations=_tool_annotations(
            title="Review Unverified Knowledge",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def memory_review_unverified(
        folder_path: str = "memory/knowledge/_unverified",
        max_extract_words: int = 150,
        include_expired: bool = True,
    ) -> str:
        """Return a grouped digest of unverified knowledge files.

        Each file entry includes provenance metadata, age, expiry status, and a
        truncated body extract to support review workflows without per-file reads.
        """

        if max_extract_words < 0:
            raise ValidationError("max_extract_words must be >= 0")

        root = get_root()
        result = _build_review_unverified_payload(
            root, folder_path, max_extract_words, include_expired
        )
        if session_state is not None:
            session_state.record_tool_call()
        return dump_tool_result(result, session_state, default=str)

    # ------------------------------------------------------------------
    # memory_search

    # ------------------------------------------------------------------
    @mcp.tool(
        name="memory_scan_frontmatter_health",
        annotations=_tool_annotations(
            title="Scan Frontmatter Health",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def memory_scan_frontmatter_health(path: str = "memory/knowledge") -> str:
        """Scan markdown frontmatter and headings for cross-reference health issues."""

        root = get_root()
        requested_path = path.strip().replace("\\", "/") or "memory/knowledge"
        scope_path = _resolve_visible_path(root, requested_path)
        try:
            scope_path.relative_to(root)
        except ValueError as exc:
            raise ValidationError("path must stay within the repository root") from exc
        if not scope_path.exists():
            return f"Error: Path not found: {path}"

        reports = [
            _frontmatter_health_report(root, rel_path)
            for rel_path in _iter_frontmatter_health_files(root, requested_path)
        ]
        issue_counts: dict[str, int] = {}
        for report in reports:
            for issue in report["issues"]:
                kind = str(issue["kind"])
                issue_counts[kind] = issue_counts.get(kind, 0) + 1

        payload = {
            "scope": requested_path,
            "files_scanned": len(reports),
            "files_with_issues": sum(1 for report in reports if report["issues"]),
            "issue_counts": dict(sorted(issue_counts.items())),
            "files": [report for report in reports if report["issues"]],
        }
        if session_state is not None:
            session_state.record_tool_call()
        return dump_tool_result(payload, session_state)

    # ------------------------------------------------------------------
    # memory_validate_links

    # ------------------------------------------------------------------
    @mcp.tool(
        name="memory_extract_file",
        annotations=_tool_annotations(
            title="Extract Structured File Content",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def memory_extract_file(
        path: str,
        section_headings: str = "",
        max_sections: int = 5,
        preview_chars: int = 1200,
        include_outline: bool = True,
    ) -> str:
        """Return frontmatter, outline, selected sections, and bounded previews for a file.

        This is the structured alternative to temp-file fallback when a caller
        needs targeted inspection of larger Markdown files.
        """

        if max_sections < 1:
            raise ValidationError("max_sections must be >= 1")
        if preview_chars < 1:
            raise ValidationError("preview_chars must be >= 1")

        repo = get_repo()
        abs_path = repo.abs_path(path)
        if not abs_path.exists() or not abs_path.is_file():
            raise NotFoundError(f"File not found: {path}")

        requested_headings = _split_csv_or_lines(section_headings)
        frontmatter, body = read_with_frontmatter(abs_path)
        content = abs_path.read_text(encoding="utf-8")
        size_bytes = len(content.encode("utf-8"))
        markdown_sections = _build_markdown_sections(body)
        matched_sections = _match_requested_sections(markdown_sections, requested_headings)
        selected_sections = matched_sections[:max_sections]
        outline = [
            {
                "heading": section["heading"],
                "level": section["level"],
                "start_line": section["start_line"],
                "anchor": section["anchor"],
            }
            for section in markdown_sections[:50]
        ]

        payload = {
            "path": path,
            "size_bytes": size_bytes,
            "frontmatter": frontmatter or None,
            "preview": body[:preview_chars],
            "selected_headings": requested_headings or None,
            "outline": outline if include_outline else None,
            "sections": [
                {
                    "heading": section["heading"],
                    "level": section["level"],
                    "start_line": section["start_line"],
                    "end_line": section["end_line"],
                    "anchor": section["anchor"],
                    "content": cast(str, section["content"])[:preview_chars],
                    "truncated": len(cast(str, section["content"])) > preview_chars,
                }
                for section in selected_sections
            ],
            "available_section_count": len(markdown_sections),
            "delivery": {
                "uses_temp_file_fallback": False,
                "preview_chars": preview_chars,
            },
        }
        if session_state is not None:
            session_state.record_tool_call()
            session_state.record_read(path)
        return dump_tool_result(payload, session_state, default=str)

    # ------------------------------------------------------------------
    # memory_get_file_provenance

    return {
        "memory_read_file": memory_read_file,
        "memory_list_folder": memory_list_folder,
        "memory_review_unverified": memory_review_unverified,
        "memory_scan_frontmatter_health": memory_scan_frontmatter_health,
        "memory_extract_file": memory_extract_file,
        "_build_review_unverified_payload": _build_review_unverified_payload,
    }
