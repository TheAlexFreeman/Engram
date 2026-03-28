"""Read tools — inspection submodule."""
from __future__ import annotations

import json
import tempfile
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from ...errors import NotFoundError, ValidationError
from ...frontmatter_utils import read_with_frontmatter

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def register_inspection(mcp: "FastMCP", get_repo, get_root, H) -> dict[str, object]:
    """Register inspection read tools and return their callables."""
    _IGNORED_NAMES = H._IGNORED_NAMES
    _READ_FILE_INLINE_THRESHOLD_BYTES = H._READ_FILE_INLINE_THRESHOLD_BYTES
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
    async def memory_read_file(path: str) -> str:
        """Read a file from the memory repository.

        Returns file metadata, parsed frontmatter, and either inline content for
        files up to 20,000 bytes or a temporary file path for larger payloads.
        Always includes a version_token (git object hash) for optimistic locking.

        Args:
            path: Repo-relative content path (e.g. 'memory/users/profile.md',
                'memory/knowledge/_unverified/django/celery-canvas.md').

        Returns:
            JSON with keys:
              path         (str)       Repo-relative path requested
              size_bytes   (int)       UTF-8 byte size of the file content
              inline       (bool)      True when content is returned inline;
                                       false when content is written to temp_file
              content      (str)       Full file text when inline is true
              temp_file    (str)       Temporary file containing full text when
                                       inline is false
              version_token (str)      Git SHA-1 of the file; pass back to write
                                       tools to detect concurrent modifications
              frontmatter  (dict|null) Parsed YAML frontmatter, or null
        """

        root = get_root()
        repo = get_repo()
        abs_path = _resolve_visible_path(root, path)
        if not abs_path.exists():
            raise NotFoundError(f"File not found: {path}")

        display_path = _display_rel_path(abs_path, root)

        fm_dict, body = read_with_frontmatter(abs_path)
        try:
            abs_path.relative_to(root)
        except ValueError:
            version_token = repo._run(["git", "hash-object", str(abs_path)]).stdout.strip()
        else:
            version_token = repo.hash_object(display_path)
        content = abs_path.read_text(encoding="utf-8")
        size_bytes = len(content.encode("utf-8"))

        result = {
            "path": display_path,
            "size_bytes": size_bytes,
            "inline": size_bytes <= _READ_FILE_INLINE_THRESHOLD_BYTES,
            "version_token": version_token,
            "frontmatter": fm_dict or None,
        }
        if result["inline"]:
            result["content"] = content
        else:
            suffix = abs_path.suffix or ".txt"
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                suffix=suffix,
                prefix="agent-memory-read-",
                delete=False,
            ) as handle:
                handle.write(content)
                temp_path = handle.name
            result["temp_file"] = temp_path
        return json.dumps(result, indent=2, default=str)

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

            return json.dumps(
                {
                    "path": path,
                    "preview_chars": preview_chars,
                    "entries": payload_entries,
                },
                indent=2,
                default=str,
            )

        for entry in entries:
            rel = _display_rel_path(entry, root)
            if entry.is_dir():
                lines.append(f"📁 {rel}/")
            else:
                size = entry.stat().st_size
                lines.append(f"📄 {entry.name}  ({size:,} bytes)  `{rel}`")

        if len(lines) == 1:
            lines.append("_(empty)_")
        return "\n".join(lines)

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
        folder = _resolve_memory_subpath(root, folder_path, "knowledge/_unverified")
        if not folder.exists():
            return json.dumps(
                {
                    "folder_path": folder_path,
                    "max_extract_words": max_extract_words,
                    "include_expired": include_expired,
                    "total_files": 0,
                    "expired_count": 0,
                    "trust_counts": {"low": 0, "medium": 0, "high": 0, "unknown": 0},
                    "groups": {},
                },
                indent=2,
                default=str,
            )
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

        return json.dumps(
            {
                "folder_path": folder_path,
                "max_extract_words": max_extract_words,
                "include_expired": include_expired,
                "total_files": total_files,
                "expired_count": expired_count,
                "trust_counts": trust_counts,
                "groups": grouped,
            },
            indent=2,
            default=str,
        )

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
        return json.dumps(payload, indent=2)

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
        return json.dumps(payload, indent=2, default=str)

    # ------------------------------------------------------------------
    # memory_get_file_provenance

    return {
        "memory_read_file": memory_read_file,
        "memory_list_folder": memory_list_folder,
        "memory_review_unverified": memory_review_unverified,
        "memory_scan_frontmatter_health": memory_scan_frontmatter_health,
        "memory_extract_file": memory_extract_file,
    }
