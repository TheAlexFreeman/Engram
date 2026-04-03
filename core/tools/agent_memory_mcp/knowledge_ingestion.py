"""Shared knowledge-ingestion helpers used by semantic tools and the CLI."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .frontmatter_utils import (
    infer_section_id_from_path,
    insert_entry_in_section,
    render_with_frontmatter,
    today_str,
    write_with_frontmatter,
)
from .path_policy import require_under_prefix, resolve_repo_path, validate_session_id
from .preview_contract import build_governed_preview, preview_target

_H1_RE = re.compile(r"^#\s+(.+)$", re.MULTILINE)
_SLUG_RE = re.compile(r"[^a-z0-9\s-]+")


@dataclass(slots=True)
class PreparedKnowledgeAdd:
    path: str
    abs_path: Path
    frontmatter: dict[str, Any]
    body: str
    draft: str
    filename: str
    summary_entry: str
    section_id: str
    summary_path: str
    abs_summary_path: Path
    updated_summary_content: str | None
    warnings: list[str]
    commit_message: str
    source: str
    session_id: str

    @property
    def summary_will_update(self) -> bool:
        return self.updated_summary_content is not None


def _truncate_preview(text: str, *, limit: int = 4000) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def slugify_filename_stem(text: str) -> str:
    lowered = text.strip().lower()
    lowered = _SLUG_RE.sub("", lowered)
    lowered = re.sub(r"\s+", "-", lowered)
    lowered = re.sub(r"-+", "-", lowered)
    slug = lowered.strip("-")
    if not slug:
        raise ValidationError(f"Could not derive a filename slug from {text!r}")
    return slug


def summary_entry_from_content(content: str, path: str) -> str:
    heading_match = _H1_RE.search(content)
    if heading_match is not None:
        heading = heading_match.group(1).strip()
        if heading:
            return heading
    return Path(path).stem


def prepare_knowledge_add(
    repo,
    root: Path,
    *,
    path: str,
    content: str,
    source: str,
    session_id: str,
    trust: str = "low",
    summary_entry: str | None = None,
    expires: str | None = None,
) -> PreparedKnowledgeAdd:
    validate_session_id(session_id)

    normalized_path, abs_path = resolve_repo_path(repo, path)
    require_under_prefix(normalized_path, "memory/knowledge/_unverified")

    if trust != "low":
        raise ValidationError("trust must be 'low' for new unverified knowledge")

    max_bytes = int(os.environ.get("ENGRAM_MAX_FILE_SIZE", "512000"))
    content_bytes = len(content.encode("utf-8"))
    if content_bytes > max_bytes:
        raise ValidationError(
            f"Content is {content_bytes:,} bytes, which exceeds the "
            f"{max_bytes:,}-byte limit (set ENGRAM_MAX_FILE_SIZE to override). "
            "Summarize or split the content before writing."
        )
    if abs_path.exists():
        raise ValidationError(
            f"File already exists: {normalized_path}. Use memory_write to overwrite."
        )

    frontmatter: dict[str, Any] = {
        "source": source,
        "created": today_str(),
        "trust": "low",
        "origin_session": session_id,
    }
    if expires:
        try:
            datetime.strptime(expires, "%Y-%m-%d")
        except ValueError as exc:
            raise ValidationError(
                f"expires must be ISO date (YYYY-MM-DD), got {expires!r}"
            ) from exc
        frontmatter["expires"] = expires

    effective_summary_entry = summary_entry or summary_entry_from_content(content, normalized_path)
    filename = Path(normalized_path).name
    section_id = infer_section_id_from_path(normalized_path)
    summary_path = "memory/knowledge/_unverified/SUMMARY.md"
    abs_summary_path = root / summary_path
    warnings: list[str] = []
    updated_summary_content: str | None = None
    if abs_summary_path.exists():
        summary_content = abs_summary_path.read_text(encoding="utf-8")
        entry = f"- **[{filename}]({normalized_path})** — {effective_summary_entry}"
        updated_summary_content = insert_entry_in_section(summary_content, section_id, entry)
        if updated_summary_content is None:
            warnings.append(
                f"Section '<!-- section: {section_id} -->' not found in "
                f"{summary_path}. Entry not added — add manually."
            )

    return PreparedKnowledgeAdd(
        path=normalized_path,
        abs_path=abs_path,
        frontmatter=frontmatter,
        body=content,
        draft=render_with_frontmatter(frontmatter, content),
        filename=filename,
        summary_entry=effective_summary_entry,
        section_id=section_id,
        summary_path=summary_path,
        abs_summary_path=abs_summary_path,
        updated_summary_content=updated_summary_content,
        warnings=warnings,
        commit_message=f"[knowledge] Add {filename}",
        source=source,
        session_id=session_id,
    )


def apply_prepared_knowledge_add(repo, prepared: PreparedKnowledgeAdd) -> list[str]:
    prepared.abs_path.parent.mkdir(parents=True, exist_ok=True)
    write_with_frontmatter(prepared.abs_path, prepared.frontmatter, prepared.body)
    repo.add(prepared.path)

    files_changed = [prepared.path]
    if prepared.updated_summary_content is not None:
        prepared.abs_summary_path.write_text(prepared.updated_summary_content, encoding="utf-8")
        repo.add(prepared.summary_path)
        files_changed.append(prepared.summary_path)
    return files_changed


def knowledge_add_new_state(
    prepared: PreparedKnowledgeAdd,
    *,
    version_token: str | None = None,
    access_jsonl: str | None = None,
) -> dict[str, Any]:
    new_state: dict[str, Any] = {
        "path": prepared.path,
        "source": prepared.source,
        "trust": "low",
        "session_id": prepared.session_id,
        "summary_updated": prepared.summary_will_update,
    }
    if version_token is not None:
        new_state["version_token"] = version_token
    if access_jsonl is not None:
        new_state["access_jsonl"] = access_jsonl
    return new_state


def build_knowledge_add_preview(
    prepared: PreparedKnowledgeAdd,
    *,
    mode: str = "preview",
    access_jsonl: str | None = None,
    access_log_exists: bool = False,
    include_access_log: bool = False,
) -> dict[str, Any]:
    target_files = [
        preview_target(
            prepared.path,
            "create",
            details="Create a new unverified knowledge file with generated provenance frontmatter.",
        )
    ]
    if prepared.summary_will_update:
        target_files.append(
            preview_target(
                prepared.summary_path,
                "update",
                details="Insert the new file into the matching unverified SUMMARY section.",
            )
        )
    if include_access_log and access_jsonl is not None:
        target_files.append(
            preview_target(
                access_jsonl,
                "update" if access_log_exists else "create",
                details="Append a CLI-ingestion ACCESS entry for the created file.",
            )
        )

    preview = build_governed_preview(
        mode=mode,
        change_class="automatic",
        summary=f"Add {prepared.filename} to memory/knowledge/_unverified.",
        reasoning=(
            "New CLI-ingested knowledge is treated as unverified external content, so it "
            "receives generated provenance and low trust before later review/promotion."
        ),
        target_files=target_files,
        invariant_effects=[
            "Writes the new file only under memory/knowledge/_unverified/.",
            "Generates source, created, trust: low, and origin_session frontmatter.",
            "Uses the first H1 heading or filename stem as the default SUMMARY entry.",
        ]
        + (
            [
                "Appends a create-mode ACCESS entry so CLI ingestion shows up in memory activity.",
            ]
            if include_access_log and access_jsonl is not None
            else []
        ),
        commit_message=prepared.commit_message,
        resulting_state=knowledge_add_new_state(prepared, access_jsonl=access_jsonl),
        warnings=prepared.warnings,
    )
    preview["content_preview"] = _truncate_preview(prepared.draft)
    return preview


__all__ = [
    "PreparedKnowledgeAdd",
    "apply_prepared_knowledge_add",
    "build_knowledge_add_preview",
    "knowledge_add_new_state",
    "prepare_knowledge_add",
    "slugify_filename_stem",
    "summary_entry_from_content",
]
