from __future__ import annotations

import posixpath
import re
import statistics
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from posixpath import relpath as posix_relpath
from typing import Any, cast

from ..frontmatter_utils import read_with_frontmatter

_GOVERNED_REFERENCE_ROOTS = (
    "memory/users",
    "memory/knowledge",
    "memory/working",
    "memory/skills",
    "governance",
)
_SCOPE_ALIAS_MAP = {
    "knowledge": ("memory/knowledge", "knowledge"),
    "plans": ("memory/working/projects", "plans"),
    "identity": ("memory/users", "identity"),
    "skills": ("memory/skills", "skills"),
}
_EXCLUDED_FILENAMES = frozenset({"NAMES.md", "SUMMARY.md"})
_URL_PREFIXES = ("http://", "https://", "mailto:", "memory://", "file://", "vscode://")
_MARKDOWN_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)\n]+)\)")
_BODY_PATH_RE = re.compile(
    r"(?P<path>(?:\.\..?/|memory/users/|memory/knowledge/|memory/working/|memory/skills/|governance/)[^\s)\]>'\"+]+)"
)
_HEADING_RE = re.compile(r"^#{1,6}\s+(?P<text>.+?)\s*$", re.MULTILINE)
_STRUCTURE_HEURISTICS = frozenset(
    {"orphan_topics", "deep_nesting", "naming_inconsistency", "summary_drift"}
)


def _normalize_for_match(value: str) -> str:
    normalized = value.strip().replace("\\", "/").rstrip("/").lower()
    return normalized.replace("_", "-")


def _is_external_target(target: str) -> bool:
    lowered = target.strip().lower()
    return lowered.startswith(_URL_PREFIXES) or lowered.startswith("#")


def _is_external_or_anchor_target(target: str) -> bool:
    lowered = target.strip().lower()
    return lowered.startswith(_URL_PREFIXES) or lowered.startswith("#")


def _strip_markdown_target(target: str) -> str:
    cleaned = target.strip()
    if cleaned.startswith("<") and ">" in cleaned:
        cleaned = cleaned[1 : cleaned.index(">")]
    if " " in cleaned and not cleaned.startswith(("./", "../")):
        cleaned = cleaned.split(" ", 1)[0]
    cleaned = cleaned.split("#", 1)[0].split("?", 1)[0].strip()
    return cleaned.replace("\\", "/")


def _split_target_and_anchor(target: str) -> tuple[str, str | None]:
    cleaned = target.strip()
    if cleaned.startswith("<") and ">" in cleaned:
        cleaned = cleaned[1 : cleaned.index(">")]
    if " " in cleaned and not cleaned.startswith(("./", "../")):
        cleaned = cleaned.split(" ", 1)[0]
    path_part, anchor = cleaned, None
    if "#" in cleaned:
        path_part, anchor = cleaned.split("#", 1)
    return path_part.replace("\\", "/").strip(), (anchor.strip() or None) if anchor else None


def _resolve_legacy_relative_target(from_path: str, cleaned: str, root: Path) -> Path | None:
    legacy_prefixes = {
        "../knowledge/": "memory/knowledge/",
        "../users/": "memory/users/",
        "../skills/": "memory/skills/",
    }
    if not from_path.startswith("memory/working/projects/"):
        return None
    for legacy_prefix, current_prefix in legacy_prefixes.items():
        if cleaned.startswith(legacy_prefix):
            return (root / f"{current_prefix}{cleaned[len(legacy_prefix) :]}").resolve()
    return None


def _resolve_ref_posix(from_path: str, cleaned: str) -> str | None:
    """Resolve a cleaned target relative to from_path using pure POSIX logic.

    Returns a normalized repo-relative posix path, or None if the result
    escapes the repository root.
    """
    if cleaned.startswith(("./", "../")):
        from_dir = posixpath.dirname(from_path)
        result = posixpath.normpath(posixpath.join(from_dir, cleaned))
    elif any(cleaned.startswith(f"{prefix}/") for prefix in _GOVERNED_REFERENCE_ROOTS):
        result = posixpath.normpath(cleaned)
    else:
        from_dir = posixpath.dirname(from_path)
        result = posixpath.normpath(posixpath.join(from_dir, cleaned))
    if result.startswith("..") or result.startswith("/"):
        return None
    return result


def _resolve_reference(from_path: str, target: str, root: Path) -> str | None:
    cleaned = _strip_markdown_target(target)
    if not cleaned or _is_external_target(cleaned):
        return None
    if cleaned.startswith("/"):
        cleaned = cleaned.lstrip("/")

    if cleaned.startswith(("./", "../")):
        resolved = _resolve_legacy_relative_target(from_path, cleaned, root)
        if resolved is not None:
            try:
                return resolved.relative_to(root).as_posix()
            except ValueError:
                return None

    return _resolve_ref_posix(from_path, cleaned)


def _resolve_target_path(
    from_path: str, target: str, root: Path
) -> tuple[str | None, str | None, str | None]:
    raw_path, anchor = _split_target_and_anchor(target)
    if not raw_path and anchor:
        return from_path, anchor, None
    if not raw_path:
        return None, anchor, "empty target"
    if _is_external_or_anchor_target(target):
        return None, anchor, None
    cleaned = raw_path.lstrip("/") if raw_path.startswith("/") else raw_path

    if cleaned.startswith(("./", "../")):
        resolved = _resolve_legacy_relative_target(from_path, cleaned, root)
        if resolved is not None:
            try:
                rel_path = resolved.relative_to(root).as_posix()
            except ValueError:
                return None, anchor, "target escapes repository root"
            return rel_path, anchor, None

    rel_path = _resolve_ref_posix(from_path, cleaned)
    if rel_path is None:
        return None, anchor, "target escapes repository root"
    return rel_path, anchor, None


def resolve_link_diagnostics(root: Path, from_path: str, target: str) -> dict[str, Any]:
    """Return structured resolution diagnostics for one markdown target."""
    stripped = target.strip()
    raw_path, anchor = _split_target_and_anchor(target)
    lowered = stripped.lower()
    is_fragment_only = lowered.startswith("#")
    is_external = lowered.startswith(_URL_PREFIXES) and not is_fragment_only
    normalized_target = raw_path.lstrip("/") if raw_path.startswith("/") else raw_path

    payload: dict[str, Any] = {
        "source_path": from_path,
        "raw_target": target,
        "normalized_target": normalized_target,
        "anchor": anchor,
        "resolved_path": None,
        "exists": None,
        "is_external": is_external,
        "is_fragment_only": is_fragment_only,
        "reason": None,
    }

    if is_external:
        payload["reason"] = "external target"
        return payload

    resolved_path, resolved_anchor, error = _resolve_target_path(from_path, target, root)
    payload["resolved_path"] = resolved_path
    payload["anchor"] = resolved_anchor

    if error is not None:
        payload["exists"] = False
        payload["reason"] = error
        return payload

    if resolved_path is None:
        payload["exists"] = False
        payload["reason"] = "unresolved target"
        return payload

    target_path = root / resolved_path
    if not target_path.exists():
        payload["exists"] = False
        payload["reason"] = "target not found"
        return payload

    payload["exists"] = True
    if resolved_anchor:
        try:
            anchors = _extract_heading_anchors(target_path.read_text(encoding="utf-8"))
        except OSError:
            anchors = set()
        if resolved_anchor not in anchors:
            payload["reason"] = f"anchor not found: #{resolved_anchor}"
            return payload

    return payload


def _looks_like_path(value: str) -> bool:
    cleaned = value.strip().replace("\\", "/")
    if not cleaned or _is_external_target(cleaned):
        return False
    return (
        cleaned.endswith(".md")
        or cleaned.startswith(("./", "../"))
        or any(cleaned.startswith(f"{prefix}/") for prefix in _GOVERNED_REFERENCE_ROOTS)
    )


def _first_line_number(text: str, needle: str) -> int | None:
    for index, line in enumerate(text.splitlines(), start=1):
        if needle in line:
            return index
    return None


def _iter_frontmatter_refs(value: Any, key_path: str = "") -> list[tuple[str, str]]:
    matches: list[tuple[str, str]] = []
    if isinstance(value, dict):
        for key, nested in value.items():
            next_key = f"{key_path}.{key}" if key_path else str(key)
            matches.extend(_iter_frontmatter_refs(nested, next_key))
        return matches
    if isinstance(value, list):
        for idx, nested in enumerate(value):
            next_key = f"{key_path}[{idx}]"
            matches.extend(_iter_frontmatter_refs(nested, next_key))
        return matches
    if isinstance(value, str) and _looks_like_path(value):
        matches.append((key_path, value))
    return matches


def _iter_governed_markdown_files(root: Path) -> list[str]:
    files: list[str] = []
    for folder in _GOVERNED_REFERENCE_ROOTS:
        folder_path = root / folder
        if not folder_path.is_dir():
            continue
        for md_file in sorted(folder_path.rglob("*.md")):
            if md_file.name in _EXCLUDED_FILENAMES:
                continue
            try:
                files.append(md_file.relative_to(root).as_posix())
            except ValueError:
                continue

    humans_root = root / "HUMANS"
    if not humans_root.is_dir():
        humans_root = root.parent / "HUMANS"
    if humans_root.is_dir():
        for md_file in sorted(humans_root.rglob("*.md")):
            if md_file.name in _EXCLUDED_FILENAMES:
                continue
            try:
                rel_path = md_file.relative_to(humans_root).as_posix()
            except ValueError:
                continue
            files.append(f"HUMANS/{rel_path}" if rel_path not in {"", "."} else "HUMANS")
    return files


def _iter_governed_markdown_files_in_scope(root: Path, scope: str = "") -> list[str]:
    normalized_scope = scope.strip().replace("\\", "/").strip("/")
    if not normalized_scope:
        return _iter_governed_markdown_files(root)

    scope_path = _resolve_scope_path(root, normalized_scope)
    if not scope_path.exists():
        return []
    if scope_path.is_file():
        if scope_path.suffix.lower() != ".md":
            return []
        if scope_path.name in _EXCLUDED_FILENAMES:
            return []
        return [scope_path.relative_to(root).as_posix()]

    files: list[str] = []
    for md_file in sorted(scope_path.rglob("*.md")):
        if md_file.name in _EXCLUDED_FILENAMES:
            continue
        try:
            files.append(md_file.relative_to(root).as_posix())
        except ValueError:
            continue
    return files


def _matches_query(query: str, raw_value: str, resolved_value: str | None = None) -> bool:
    normalized_query = _normalize_for_match(query)
    candidates = [raw_value]
    if resolved_value:
        candidates.append(resolved_value)
    for candidate in candidates:
        if normalized_query in _normalize_for_match(candidate):
            return True
    return False


def find_references(root: Path, query: str, include_body: bool = False) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    for rel_path in _iter_governed_markdown_files(root):
        abs_path = root / rel_path
        try:
            content = abs_path.read_text(encoding="utf-8")
            frontmatter, body = read_with_frontmatter(abs_path)
        except OSError:
            continue

        for link_match in _MARKDOWN_LINK_RE.finditer(body):
            raw_target = link_match.group(2)
            resolved = _resolve_reference(rel_path, raw_target, root)
            if not _matches_query(query, raw_target, resolved):
                continue
            matches.append(
                {
                    "from_path": rel_path,
                    "ref_type": "markdown_link",
                    "ref_key": None,
                    "ref_value": raw_target,
                    "resolved_path": resolved,
                    "line": body[: link_match.start()].count("\n") + 1,
                    "snippet": link_match.group(0),
                }
            )

        for key_path, raw_value in _iter_frontmatter_refs(frontmatter):
            resolved = _resolve_reference(rel_path, raw_value, root)
            if not _matches_query(query, raw_value, resolved):
                continue
            matches.append(
                {
                    "from_path": rel_path,
                    "ref_type": "frontmatter_path",
                    "ref_key": key_path,
                    "ref_value": raw_value,
                    "resolved_path": resolved,
                    "line": _first_line_number(content, raw_value),
                    "snippet": raw_value,
                }
            )

        if include_body:
            for line_number, line in enumerate(body.splitlines(), start=1):
                for body_match in _BODY_PATH_RE.finditer(line):
                    raw_value = body_match.group("path")
                    resolved = _resolve_reference(rel_path, raw_value, root)
                    if not _matches_query(query, raw_value, resolved):
                        continue
                    matches.append(
                        {
                            "from_path": rel_path,
                            "ref_type": "body_path",
                            "ref_key": None,
                            "ref_value": raw_value,
                            "resolved_path": resolved,
                            "line": line_number,
                            "snippet": line.strip(),
                        }
                    )

    matches.sort(
        key=lambda item: (
            str(item["from_path"]),
            str(item["ref_type"]),
            int(item["line"] or 0),
            str(item["ref_value"]),
        )
    )
    return matches


def _slugify_heading(text: str) -> str:
    lowered = text.strip().lower()
    lowered = re.sub(r"[^a-z0-9\s-]", "", lowered)
    return re.sub(r"\s+", "-", lowered).strip("-")


def _extract_heading_anchors(markdown_text: str) -> set[str]:
    anchors: set[str] = set()
    for match in _HEADING_RE.finditer(markdown_text):
        anchor = _slugify_heading(match.group("text"))
        if anchor:
            anchors.add(anchor)
    return anchors


def _iter_validation_targets(root: Path, scope: str = "") -> list[dict[str, Any]]:
    targets: list[dict[str, Any]] = []
    for rel_path in _iter_governed_markdown_files_in_scope(root, scope):
        abs_path = root / rel_path
        try:
            content = abs_path.read_text(encoding="utf-8")
            frontmatter, body = read_with_frontmatter(abs_path)
        except OSError:
            continue

        for link_match in _MARKDOWN_LINK_RE.finditer(body):
            raw_target = link_match.group(2)
            resolved_path, anchor, error = _resolve_target_path(rel_path, raw_target, root)
            targets.append(
                {
                    "from_path": rel_path,
                    "ref_type": "markdown_link",
                    "target": raw_target,
                    "resolved_path": resolved_path,
                    "anchor": anchor,
                    "line": body[: link_match.start()].count("\n") + 1,
                    "snippet": link_match.group(0),
                    "error": error,
                }
            )

        for key_path, raw_value in _iter_frontmatter_refs(frontmatter):
            resolved_path, anchor, error = _resolve_target_path(rel_path, raw_value, root)
            targets.append(
                {
                    "from_path": rel_path,
                    "ref_type": "frontmatter_path",
                    "ref_key": key_path,
                    "target": raw_value,
                    "resolved_path": resolved_path,
                    "anchor": anchor,
                    "line": _first_line_number(content, raw_value),
                    "snippet": raw_value,
                    "error": error,
                }
            )

    targets.sort(
        key=lambda item: (
            str(item["from_path"]),
            str(item["ref_type"]),
            int(item["line"] or 0),
            str(item["target"]),
        )
    )
    return targets


def validate_links(root: Path, scope: str = "") -> dict[str, Any]:
    targets = _iter_validation_targets(root, scope)
    heading_cache: dict[str, set[str]] = {}
    broken: list[dict[str, Any]] = []
    ok_count = 0

    for item in targets:
        if item["error"] is not None:
            broken.append(
                {
                    "from_path": item["from_path"],
                    "ref_type": item["ref_type"],
                    "target": item["target"],
                    "resolved_path": item["resolved_path"],
                    "reason": item["error"],
                    "line": item["line"],
                }
            )
            continue

        resolved_path = item["resolved_path"]
        anchor = item.get("anchor")
        if resolved_path is None:
            continue

        target_path = root / resolved_path
        if not target_path.exists():
            broken.append(
                {
                    "from_path": item["from_path"],
                    "ref_type": item["ref_type"],
                    "target": item["target"],
                    "resolved_path": resolved_path,
                    "reason": "target not found",
                    "line": item["line"],
                }
            )
            continue

        if anchor:
            if resolved_path not in heading_cache:
                try:
                    heading_cache[resolved_path] = _extract_heading_anchors(
                        target_path.read_text(encoding="utf-8")
                    )
                except OSError:
                    heading_cache[resolved_path] = set()
            if anchor not in heading_cache[resolved_path]:
                broken.append(
                    {
                        "from_path": item["from_path"],
                        "ref_type": item["ref_type"],
                        "target": item["target"],
                        "resolved_path": resolved_path,
                        "reason": f"anchor not found: #{anchor}",
                        "line": item["line"],
                    }
                )
                continue

        ok_count += 1

    result: dict[str, Any] = {
        "scope": scope.strip().replace("\\", "/") or ".",
        "checked": len(targets),
        "ok_count": ok_count,
        "broken": broken[:200],
    }
    if len(broken) > 200:
        result["truncated"] = True
        result["total_broken"] = len(broken)
    return result


def _normalize_repo_path(path: str) -> str:
    return path.strip().replace("\\", "/").strip("/")


def _resolve_scope_path(root: Path, scope: str) -> Path:
    normalized_scope = _normalize_repo_path(scope)
    if not normalized_scope:
        return root

    scope_path = root / normalized_scope
    if scope_path.exists():
        return scope_path

    parts = Path(normalized_scope).parts
    if not parts:
        return scope_path

    alias_prefixes = _SCOPE_ALIAS_MAP.get(parts[0], (parts[0],))
    if alias_prefixes != (parts[0],):
        remainder = parts[1:]
        for prefix in alias_prefixes:
            candidate = root / Path(prefix).joinpath(*remainder)
            if candidate.exists():
                return candidate
        primary = alias_prefixes[0]
        return root / Path(primary).joinpath(*remainder)

    return scope_path


def _path_is_within(path: str, prefix: str) -> bool:
    return path == prefix or path.startswith(f"{prefix}/")


def _replace_path_prefix(path: str, source: str, dest: str) -> str:
    if path == source:
        return dest
    return f"{dest}/{path[len(source) + 1 :]}"


def _source_descendants(root: Path, source: str) -> list[str]:
    source_path = root / source
    if source_path.is_file():
        return [source]

    descendants: list[str] = []
    for child in sorted(source_path.rglob("*")):
        if not child.is_file():
            continue
        try:
            descendants.append(child.relative_to(root).as_posix())
        except ValueError:
            continue
    return descendants


def _is_repo_absolute_target(target: str) -> bool:
    cleaned, _ = _split_target_and_anchor(target)
    cleaned = cleaned.lstrip("/")
    return any(cleaned.startswith(f"{prefix}/") for prefix in _GOVERNED_REFERENCE_ROOTS)


def _rewrite_reference_target(from_path: str, target: str, new_resolved_path: str) -> str:
    raw_path, anchor = _split_target_and_anchor(target)
    if not raw_path:
        return target

    if target.strip().startswith("/"):
        rewritten = f"/{new_resolved_path}"
    elif _is_repo_absolute_target(target):
        rewritten = new_resolved_path
    else:
        from_parent = Path(from_path).parent.as_posix()
        rewritten = posix_relpath(new_resolved_path, start=from_parent or ".")
    if anchor:
        rewritten = f"{rewritten}#{anchor}"
    return rewritten


def _summary_targets_for_reorganization(source: str, dest: str) -> list[str]:
    targets: set[str] = set()
    for candidate in (source, dest):
        parts = Path(candidate).parts
        if len(parts) < 2 or parts[0] != "memory" or parts[1] != "knowledge":
            continue
        targets.add("memory/knowledge/SUMMARY.md")
        parent = Path(candidate).parent.as_posix()
        if parent and parent != "." and parent != "memory/knowledge":
            targets.add(f"{parent}/SUMMARY.md")
    return sorted(targets)


def plan_reorganization(root: Path, source: str, dest: str) -> dict[str, Any]:
    normalized_source = _normalize_repo_path(source)
    normalized_dest = _normalize_repo_path(dest)
    files_to_move = _source_descendants(root, normalized_source)
    future_paths = {
        path: _replace_path_prefix(path, normalized_source, normalized_dest)
        for path in files_to_move
    }
    file_moves = [
        {
            "source": path,
            "dest": future_paths[path],
        }
        for path in files_to_move
    ]

    refs_by_file: dict[str, dict[str, Any]] = {}

    def add_ref_update(
        *,
        current_path: str,
        display_path: str,
        ref_type: str,
        old_value: str,
        new_value: str,
        line: int | None,
        resolved_old: str | None,
        resolved_new: str | None,
        ref_key: str | None = None,
        applies_in_execution: bool,
    ) -> None:
        if old_value == new_value:
            return
        bucket = refs_by_file.setdefault(
            display_path,
            {
                "path": display_path,
                "current_path": current_path,
                "refs": [],
            },
        )
        bucket["refs"].append(
            {
                "type": ref_type,
                "old": old_value,
                "new": new_value,
                "line": line,
                "ref_key": ref_key,
                "resolved_old": resolved_old,
                "resolved_new": resolved_new,
                "applies_in_execution": applies_in_execution,
            }
        )

    source_refs = find_references(root, normalized_source, include_body=True)
    for match in source_refs:
        current_from_path = str(match["from_path"])
        if current_from_path in future_paths:
            continue
        resolved_path = match.get("resolved_path")
        if not isinstance(resolved_path, str) or not _path_is_within(
            resolved_path, normalized_source
        ):
            continue
        new_resolved_path = _replace_path_prefix(resolved_path, normalized_source, normalized_dest)
        add_ref_update(
            current_path=current_from_path,
            display_path=current_from_path,
            ref_type=str(match["ref_type"]),
            old_value=str(match["ref_value"]),
            new_value=_rewrite_reference_target(
                current_from_path,
                str(match["ref_value"]),
                new_resolved_path,
            ),
            line=cast(int | None, match.get("line")),
            resolved_old=resolved_path,
            resolved_new=new_resolved_path,
            ref_key=cast(str | None, match.get("ref_key")),
            applies_in_execution=str(match["ref_type"]) != "body_path",
        )

    for item in _iter_validation_targets(root, normalized_source):
        current_from_path = str(item["from_path"])
        future_from_path = future_paths.get(current_from_path, current_from_path)
        resolved_path = cast(str | None, item.get("resolved_path"))
        future_resolved_path = (
            _replace_path_prefix(resolved_path, normalized_source, normalized_dest)
            if isinstance(resolved_path, str) and _path_is_within(resolved_path, normalized_source)
            else resolved_path
        )
        add_ref_update(
            current_path=current_from_path,
            display_path=future_from_path,
            ref_type=str(item["ref_type"]),
            old_value=str(item["target"]),
            new_value=_rewrite_reference_target(
                future_from_path,
                str(item["target"]),
                future_resolved_path or current_from_path,
            ),
            line=cast(int | None, item.get("line")),
            resolved_old=resolved_path,
            resolved_new=future_resolved_path,
            ref_key=cast(str | None, item.get("ref_key")),
            applies_in_execution=True,
        )

    # SUMMARY.md files are excluded from general reference scanning, but a
    # reorganization must still rewrite any links inside them that point into
    # the moved subtree.  Scan only the SUMMARY files that this reorganization
    # touches (those returned by _summary_targets_for_reorganization) so the
    # update stays targeted.
    for summary_path in _summary_targets_for_reorganization(normalized_source, normalized_dest):
        abs_summary = root / summary_path
        if not abs_summary.exists() or summary_path in future_paths:
            continue
        try:
            _, body = read_with_frontmatter(abs_summary)
        except OSError:
            continue
        for link_match in _MARKDOWN_LINK_RE.finditer(body):
            raw_target = link_match.group(2)
            resolved = _resolve_reference(summary_path, raw_target, root)
            if not isinstance(resolved, str) or not _path_is_within(resolved, normalized_source):
                continue
            new_resolved_path = _replace_path_prefix(resolved, normalized_source, normalized_dest)
            add_ref_update(
                current_path=summary_path,
                display_path=summary_path,
                ref_type="markdown_link",
                old_value=raw_target,
                new_value=_rewrite_reference_target(
                    summary_path,
                    raw_target,
                    new_resolved_path,
                ),
                line=body[: link_match.start()].count("\n") + 1,
                resolved_old=resolved,
                resolved_new=new_resolved_path,
                applies_in_execution=True,
            )

    files_with_references = [
        {
            **payload,
            "refs": sorted(
                cast(list[dict[str, Any]], payload["refs"]),
                key=lambda item: (
                    str(item["type"]),
                    int(item["line"] or 0),
                    str(item["old"]),
                ),
            ),
        }
        for _, payload in sorted(refs_by_file.items())
    ]

    warnings: list[str] = []
    dest_path = root / normalized_dest
    if dest_path.exists() and normalized_dest != normalized_source:
        warnings.append(f"Destination already exists: {normalized_dest}")
    for move in file_moves:
        if move["source"] == move["dest"]:
            continue
        if (root / move["dest"]).exists():
            warnings.append(f"Destination conflict: {move['dest']}")

    return {
        "source": normalized_source,
        "dest": normalized_dest,
        "files_to_move": files_to_move,
        "file_moves": file_moves,
        "files_with_references": files_with_references,
        "reference_updates": sum(len(item["refs"]) for item in files_with_references),
        "summary_updates": _summary_targets_for_reorganization(
            normalized_source,
            normalized_dest,
        ),
        "warnings": sorted(set(warnings)),
    }


def preview_reorganization(root: Path, source: str, dest: str) -> dict[str, Any]:
    return plan_reorganization(root, source, dest)


def _folder_content_files(folder: Path) -> list[Path]:
    return [
        path
        for path in sorted(folder.rglob("*.md"))
        if path.is_file() and path.name != "SUMMARY.md"
    ]


def _summary_mentions_path(summary_text: str, rel_path: str) -> bool:
    normalized = rel_path.replace("\\", "/")
    name = Path(normalized).name
    stem = Path(normalized).stem
    folder_name = Path(normalized).parts[-2] if len(Path(normalized).parts) >= 2 else stem
    candidates = {
        normalized,
        name,
        stem,
        folder_name,
        f"({name})",
        f"({normalized})",
        f"({folder_name}/SUMMARY.md)",
        f"({folder_name}/",
    }
    return any(candidate in summary_text for candidate in candidates)


def _iter_governed_directories_in_scope(root: Path, scope: str = "") -> list[str]:
    normalized_scope = _normalize_repo_path(scope)
    if normalized_scope:
        scope_path = _resolve_scope_path(root, normalized_scope)
        if not scope_path.exists() or not scope_path.is_dir():
            return []
        return [
            path.relative_to(root).as_posix()
            for path in sorted(scope_path.rglob("*"))
            if path.is_dir()
        ]

    directories: list[str] = []
    for folder in _GOVERNED_REFERENCE_ROOTS:
        folder_path = root / folder
        if not folder_path.is_dir():
            continue
        directories.append(folder)
        directories.extend(
            path.relative_to(root).as_posix()
            for path in sorted(folder_path.rglob("*"))
            if path.is_dir()
        )
    return directories


def _orphan_topic_suggestions(root: Path, scope: str) -> list[dict[str, Any]]:
    suggestions: list[dict[str, Any]] = []
    for rel_dir in _iter_governed_directories_in_scope(root, scope):
        if not rel_dir.startswith("memory/knowledge/"):
            continue
        abs_dir = root / rel_dir
        content_files = _folder_content_files(abs_dir)
        if not content_files or len(content_files) > 2:
            continue
        parent_summary = abs_dir.parent / "SUMMARY.md"
        if not parent_summary.exists():
            continue
        parent_summary_rel = parent_summary.relative_to(root).as_posix()
        summary_text = parent_summary.read_text(encoding="utf-8")
        if _summary_mentions_path(summary_text, rel_dir):
            continue
        suggestions.append(
            {
                "heuristic": "orphan_topics",
                "suggestion": f"Consider merging or summarizing {rel_dir}.",
                "rationale": f"{rel_dir} has {len(content_files)} content file(s) and is not referenced from {parent_summary_rel}.",
                "confidence": "medium",
                "affected_paths": [rel_dir, parent_summary_rel],
            }
        )
    return suggestions


def _deep_nesting_suggestions(root: Path, scope: str) -> list[dict[str, Any]]:
    suggestions: list[dict[str, Any]] = []
    seen_paths: set[str] = set()
    for rel_path in _iter_governed_markdown_files_in_scope(root, scope):
        if rel_path.endswith("SUMMARY.md"):
            continue
        parts = Path(rel_path).parts
        if len(parts) < 6:
            continue
        parent = Path(rel_path).parent.as_posix()
        if parent in seen_paths:
            continue
        seen_paths.add(parent)
        suggestions.append(
            {
                "heuristic": "deep_nesting",
                "suggestion": f"Consider an intermediate summary or flattening under {parent}.",
                "rationale": f"{rel_path} sits {len(parts) - 2} levels below its top-level root, which may make retrieval and maintenance harder.",
                "confidence": "low",
                "affected_paths": [parent],
            }
        )
    return suggestions


def _naming_inconsistency_suggestions(root: Path, scope: str) -> list[dict[str, Any]]:
    suggestions: list[dict[str, Any]] = []
    seen_pairs: set[tuple[str, str]] = set()
    directories = set(_iter_governed_directories_in_scope(root, scope))
    for rel_dir in sorted(directories):
        dir_path = Path(rel_dir)
        folder_name = dir_path.name
        if "-" not in folder_name:
            continue
        parent = dir_path.parent.as_posix()
        left, right = folder_name.split("-", 1)
        alternate = Path(parent) / left / right if parent != "." else Path(left) / right
        alternate_rel = alternate.as_posix()
        if alternate_rel not in directories:
            continue
        ordered_pair = sorted((rel_dir, alternate_rel))
        pair = (ordered_pair[0], ordered_pair[1])
        if pair in seen_pairs:
            continue
        seen_pairs.add(pair)
        suggestions.append(
            {
                "heuristic": "naming_inconsistency",
                "suggestion": f"Align {rel_dir} and {alternate_rel} to one naming pattern.",
                "rationale": f"Both the hyphenated folder {rel_dir} and the nested folder {alternate_rel} exist, which splits related material across two path conventions.",
                "confidence": "high",
                "affected_paths": [rel_dir, alternate_rel],
            }
        )
    return suggestions


def _summary_drift_suggestions(root: Path, scope: str) -> list[dict[str, Any]]:
    suggestions: list[dict[str, Any]] = []
    scope_dirs = _iter_governed_directories_in_scope(root, scope)
    summary_dirs = [rel_dir for rel_dir in scope_dirs if (root / rel_dir / "SUMMARY.md").exists()]
    for rel_dir in sorted(summary_dirs):
        abs_dir = root / rel_dir
        summary_path = abs_dir / "SUMMARY.md"
        summary_rel = summary_path.relative_to(root).as_posix()
        summary_text = summary_path.read_text(encoding="utf-8")
        missing_entries: list[str] = []
        for child in sorted(abs_dir.iterdir()):
            if child.name == "SUMMARY.md":
                continue
            if child.is_file() and child.suffix.lower() == ".md":
                child_rel = child.relative_to(root).as_posix()
                if not _summary_mentions_path(summary_text, child_rel):
                    missing_entries.append(child_rel)
            elif child.is_dir():
                child_summary = child / "SUMMARY.md"
                if child_summary.exists() or _folder_content_files(child):
                    child_rel = child.relative_to(root).as_posix()
                    if not _summary_mentions_path(summary_text, child_rel):
                        missing_entries.append(child_rel)
        if not missing_entries:
            continue
        suggestions.append(
            {
                "heuristic": "summary_drift",
                "suggestion": f"Update {summary_rel} to cover {len(missing_entries)} missing path(s).",
                "rationale": f"{summary_rel} does not mention: {', '.join(missing_entries[:4])}{' ...' if len(missing_entries) > 4 else ''}.",
                "confidence": "high",
                "affected_paths": [summary_rel, *missing_entries[:8]],
            }
        )
    return suggestions


def suggest_structure(
    root: Path,
    scope: str = "",
    heuristics: list[str] | None = None,
) -> dict[str, Any]:
    requested = list(heuristics or sorted(_STRUCTURE_HEURISTICS))
    invalid = [item for item in requested if item not in _STRUCTURE_HEURISTICS]
    if invalid:
        raise ValueError(f"Unsupported heuristics: {', '.join(sorted(invalid))}")

    suggestions: list[dict[str, Any]] = []
    for heuristic in requested:
        if heuristic == "orphan_topics":
            suggestions.extend(_orphan_topic_suggestions(root, scope))
        elif heuristic == "deep_nesting":
            suggestions.extend(_deep_nesting_suggestions(root, scope))
        elif heuristic == "naming_inconsistency":
            suggestions.extend(_naming_inconsistency_suggestions(root, scope))
        elif heuristic == "summary_drift":
            suggestions.extend(_summary_drift_suggestions(root, scope))

    suggestions.sort(
        key=lambda item: (
            str(item["heuristic"]),
            str(cast(list[str], item["affected_paths"])[0]),
            str(item["suggestion"]),
        )
    )
    return {
        "scope": _normalize_repo_path(scope) or ".",
        "heuristics": requested,
        "suggestions": suggestions,
        "total": len(suggestions),
    }


# ------------------------------------------------------------------
# Connectivity graph & unlinked-file surfacing
# ------------------------------------------------------------------

_CATEGORY_PRIORITY = {"isolated": 0, "sink": 1, "source": 2, "low_connectivity": 3}
_VALID_CATEGORIES = frozenset(_CATEGORY_PRIORITY)

_STEM_STOP_WORDS = frozenset(
    {
        "the",
        "and",
        "for",
        "with",
        "from",
        "that",
        "this",
        "into",
        "over",
        "synthesis",
        "overview",
        "summary",
    }
)


@dataclass
class ConnectivityGraph:
    """Lightweight directed graph of cross-references between governed files."""

    files: list[str]
    outgoing: dict[str, set[str]] = field(default_factory=dict)
    incoming: dict[str, set[str]] = field(default_factory=dict)
    scope: str = ""


def _extract_outgoing_refs(rel_path: str, root: Path) -> set[str]:
    """Return resolved canonical paths of all outgoing refs from a file."""
    abs_path = root / rel_path
    try:
        frontmatter, body = read_with_frontmatter(abs_path)
    except OSError:
        return set()

    targets: set[str] = set()

    for link_match in _MARKDOWN_LINK_RE.finditer(body):
        raw_target = link_match.group(2)
        resolved = _resolve_reference(rel_path, raw_target, root)
        if resolved is not None:
            targets.add(resolved)

    for _key_path, raw_value in _iter_frontmatter_refs(frontmatter):
        # Handle comma-separated values (e.g. related: a.md, b.md)
        parts = [p.strip() for p in raw_value.split(",")]
        for part in parts:
            if not part:
                continue
            resolved = _resolve_reference(rel_path, part, root)
            if resolved is not None:
                targets.add(resolved)

    targets.discard(rel_path)
    return targets


def build_connectivity_graph(root: Path, scope: str = "") -> ConnectivityGraph:
    """Build an in-degree/out-degree connectivity graph for governed markdown."""
    all_files = _iter_governed_markdown_files_in_scope(root, scope)
    all_files_set = set(all_files)

    outgoing: dict[str, set[str]] = {}
    incoming: dict[str, set[str]] = {f: set() for f in all_files}

    for rel_path in all_files:
        refs = _extract_outgoing_refs(rel_path, root)
        # Only count edges to files within scope
        scoped_refs = refs & all_files_set
        outgoing[rel_path] = scoped_refs
        for target in scoped_refs:
            incoming.setdefault(target, set()).add(rel_path)

    return ConnectivityGraph(
        files=all_files,
        outgoing=outgoing,
        incoming=incoming,
        scope=_normalize_repo_path(scope) or ".",
    )


def _classify_file(in_deg: int, out_deg: int, threshold: int) -> str | None:
    """Return category string or None if the file is well-connected."""
    if in_deg == 0 and out_deg == 0:
        return "isolated"
    if in_deg > 0 and out_deg == 0:
        return "sink"
    if in_deg == 0 and out_deg > 0:
        return "source"
    if (in_deg + out_deg) <= threshold:
        return "low_connectivity"
    return None


def _file_age_days(frontmatter: dict[str, Any]) -> int | None:
    """Return days since last_verified or created, or None."""
    for key in ("last_verified", "created"):
        value = frontmatter.get(key)
        if value is None:
            continue
        if isinstance(value, date) and not isinstance(value, datetime):
            return (date.today() - value).days
        if isinstance(value, datetime):
            return (datetime.now() - value).days
        if isinstance(value, str):
            for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S"):
                try:
                    parsed = datetime.strptime(value, fmt)
                    return (datetime.now() - parsed).days
                except ValueError:
                    continue
    return None


def _extract_candidate_context(rel_path: str, root: Path) -> dict[str, Any]:
    """Extract lightweight context for a candidate file."""
    abs_path = root / rel_path
    try:
        frontmatter, body = read_with_frontmatter(abs_path)
    except OSError:
        return {"extract": "", "headings": [], "existing_related": []}

    # First 3 non-blank body lines
    lines = [ln.strip() for ln in body.splitlines() if ln.strip()]
    extract = "\n".join(lines[:3])

    # H1/H2 headings
    headings: list[str] = []
    for match in _HEADING_RE.finditer(body):
        full = match.group(0).strip()
        if full.startswith("# ") or full.startswith("## "):
            headings.append(full)
            if len(headings) >= 6:
                break

    # Existing related: frontmatter
    related_raw = frontmatter.get("related", [])
    if isinstance(related_raw, str):
        existing_related = [r.strip() for r in related_raw.split(",") if r.strip()]
    elif isinstance(related_raw, list):
        existing_related = [str(r).strip() for r in related_raw if str(r).strip()]
    else:
        existing_related = []

    return {
        "extract": extract[:500],
        "headings": headings,
        "title": headings[0][2:].strip() if headings and headings[0].startswith("# ") else "",
        "existing_related": existing_related,
        "trust": str(frontmatter.get("trust", "")),
        "age_days": _file_age_days(frontmatter),
    }


def _tokenize_stem(filename: str) -> set[str]:
    """Split a filename stem into keyword tokens."""
    stem = Path(filename).stem
    tokens = set(re.split(r"[-_.]", stem.lower()))
    return tokens - _STEM_STOP_WORDS - {""}


def _score_link_pair(
    source: str,
    target: str,
    graph: ConnectivityGraph,
    root: Path,
    *,
    _source_context: dict[str, Any] | None = None,
    _target_context: dict[str, Any] | None = None,
) -> tuple[float, list[str]]:
    """Score the relevance of a link from *source* → *target*.

    Uses the same heuristic signals as :func:`_suggest_link_candidates`.
    Returns ``(score, reasons)`` — higher score means a stronger link.

    Optional *_source_context* and *_target_context* can be supplied to
    avoid redundant file reads when iterating over many pairs.
    """
    path_tokens = _tokenize_stem(source)
    source_parts = Path(source).parts
    source_domain = source_parts[2] if len(source_parts) > 2 else ""
    source_subdir = Path(source).parent.as_posix()
    src_ctx = (
        _source_context if _source_context is not None else _extract_candidate_context(source, root)
    )
    source_body_lower = str(src_ctx.get("extract", "")).lower()
    source_title_lower = str(src_ctx.get("title", "")).lower()
    source_headings_lower = " ".join(
        heading.lower().lstrip("# ").strip() for heading in src_ctx.get("headings", [])
    )
    my_referrers = graph.incoming.get(source, set())
    my_targets = graph.outgoing.get(source, set())

    cand_parts = Path(target).parts
    cand_tokens = _tokenize_stem(target)
    cand_subdir = Path(target).parent.as_posix()
    cand_domain = cand_parts[2] if len(cand_parts) > 2 else ""
    tgt_ctx = (
        _target_context if _target_context is not None else _extract_candidate_context(target, root)
    )
    candidate_title = str(tgt_ctx.get("title", "")).lower()
    candidate_phrase = re.sub(r"[-_.]+", " ", Path(target).stem).strip().lower()

    score = 0.0
    reasons: list[str] = []

    # Filename stem overlap
    overlap = path_tokens & cand_tokens
    if len(overlap) >= 2:
        score += len(overlap) * 2.0
        reasons.append(f"shared stems: {', '.join(sorted(overlap))}")
    elif len(overlap) == 1 and len(path_tokens) <= 3:
        score += 1.0
        reasons.append(f"shared stem: {next(iter(overlap))}")

    # Same subdirectory / same domain
    if cand_subdir == source_subdir:
        score += 3.0
        reasons.append("same directory")
    elif cand_domain == source_domain and source_domain:
        score += 1.0
        reasons.append("same domain")

    # Shared incoming references (co-citation)
    cand_referrers = graph.incoming.get(target, set())
    shared_referrers = my_referrers & cand_referrers
    if shared_referrers:
        score += min(len(shared_referrers), 3) * 1.5
        reasons.append(f"{len(shared_referrers)} shared referrer(s)")

    # Shared outgoing links
    shared_targets = my_targets & graph.outgoing.get(target, set())
    if shared_targets:
        score += min(len(shared_targets), 3) * 1.25
        reasons.append(f"{len(shared_targets)} shared outgoing link(s)")

    # Candidate name appears in source body
    if candidate_phrase and len(candidate_phrase) >= 5 and candidate_phrase in source_body_lower:
        score += 2.5
        reasons.append("body mentions candidate stem")

    # Candidate title appears in source headings/body
    if candidate_title and len(candidate_title) >= 5:
        if candidate_title in source_headings_lower:
            score += 3.0
            reasons.append("heading mentions candidate title")
        elif candidate_title in source_body_lower or candidate_title in source_title_lower:
            score += 2.0
            reasons.append("body mentions candidate title")

    return score, reasons


def _suggest_link_candidates(
    rel_path: str,
    graph: ConnectivityGraph,
    root: Path,
    max_suggestions: int = 5,
) -> list[dict[str, Any]]:
    """Find potential cross-reference targets using structural heuristics."""
    source_context = _extract_candidate_context(rel_path, root)
    context_cache: dict[str, dict[str, Any]] = {}
    scored: list[tuple[float, str, str]] = []

    for candidate in graph.files:
        if candidate == rel_path:
            continue
        candidate_context = context_cache.setdefault(
            candidate, _extract_candidate_context(candidate, root)
        )
        score, reasons = _score_link_pair(
            rel_path,
            candidate,
            graph,
            root,
            _source_context=source_context,
            _target_context=candidate_context,
        )
        if score > 0 and reasons:
            scored.append((score, candidate, "; ".join(reasons)))

    scored.sort(key=lambda item: (-item[0], item[1]))
    return [
        {
            "target": target,
            "reason": reason,
            "reasons": [part.strip() for part in reason.split(";") if part.strip()],
            "score": round(score, 2),
        }
        for score, target, reason in scored[:max_suggestions]
    ]


def score_existing_links(
    rel_path: str,
    graph: ConnectivityGraph,
    root: Path,
    min_score: float = 0.0,
) -> list[dict[str, Any]]:
    """Score each current outgoing link from *rel_path*.

    Uses the same heuristic signals as :func:`_suggest_link_candidates` but
    applied to links that already exist rather than candidates.

    Returns a list sorted ascending by score so that the weakest links appear
    first.  Each entry contains ``{target, score, reasons, alert}`` where
    ``alert=True`` when ``score < min_score``.
    """
    existing_links = graph.outgoing.get(rel_path, set())
    source_context = _extract_candidate_context(rel_path, root)
    results: list[dict[str, Any]] = []
    for target in sorted(existing_links):
        target_context = _extract_candidate_context(target, root)
        score, reasons = _score_link_pair(
            rel_path,
            target,
            graph,
            root,
            _source_context=source_context,
            _target_context=target_context,
        )
        results.append(
            {
                "target": target,
                "score": round(score, 2),
                "reasons": reasons,
                "alert": score < min_score,
            }
        )
    results.sort(key=lambda x: x["score"])
    return results


def suggest_links_for_file(
    root: Path,
    rel_path: str,
    max_suggestions: int = 10,
    domain_mode: str = "all",
    min_score: float = 0.0,
) -> dict[str, Any]:
    """Return scored cross-reference suggestions for one governed markdown file."""
    graph = build_connectivity_graph(root)
    if rel_path not in graph.files:
        raise ValueError(f"File is outside the governed markdown surface: {rel_path}")

    normalized_domain_mode = domain_mode.strip().lower() or "all"
    if normalized_domain_mode not in {"all", "same", "cross"}:
        raise ValueError("domain_mode must be one of: all, same, cross")
    minimum_score = max(0.0, float(min_score))

    source_parts = Path(rel_path).parts
    source_domain = source_parts[2] if len(source_parts) > 2 else ""

    suggestions = _suggest_link_candidates(
        rel_path,
        graph,
        root,
        max_suggestions=max(max_suggestions * 2, max_suggestions),
    )
    existing_links = graph.outgoing.get(rel_path, set())
    filtered: list[dict[str, Any]] = []
    for suggestion in suggestions:
        target = str(suggestion["target"])
        if target in existing_links:
            continue
        target_parts = Path(target).parts
        target_domain = target_parts[2] if len(target_parts) > 2 else ""
        is_same_domain = bool(source_domain and target_domain and source_domain == target_domain)
        if normalized_domain_mode == "same" and not is_same_domain:
            continue
        if normalized_domain_mode == "cross" and is_same_domain:
            continue
        if float(suggestion.get("score", 0.0)) < minimum_score:
            continue
        filtered.append(
            {
                **suggestion,
                "already_linked": False,
                "source_domain": source_domain,
                "target_domain": target_domain,
                "is_same_domain": is_same_domain,
            }
        )
        if len(filtered) >= max_suggestions:
            break

    return {
        "path": rel_path,
        "domain_mode": normalized_domain_mode,
        "min_score": round(minimum_score, 2),
        "source_domain": source_domain,
        "in_degree": len(graph.incoming.get(rel_path, set())),
        "out_degree": len(graph.outgoing.get(rel_path, set())),
        "current_links": sorted(existing_links),
        "suggestions": filtered,
        "total_suggestions": len(filtered),
        "candidate_pool_size": len(graph.files) - 1,
    }


def summarize_cross_domain_links(
    root: Path,
    scope: str = "memory/knowledge",
    source_domain: str = "",
    target_domain: str = "",
    min_edge_count: int = 1,
) -> dict[str, Any]:
    """Return cross-domain directional and symmetric link summaries."""
    from .graph_analysis import analyze_graph, build_knowledge_graph

    graph = build_connectivity_graph(root, scope)
    knowledge_files = [path for path in graph.files if path.startswith("memory/knowledge/")]
    knowledge_set = set(knowledge_files)
    normalized_source = source_domain.strip()
    normalized_target = target_domain.strip()
    min_edges = max(1, int(min_edge_count))

    directional_counts: dict[tuple[str, str], int] = {}
    domain_file_counts: dict[str, int] = {}
    within_domain_edge_total = 0

    def _domain(path: str) -> str:
        parts = Path(path).parts
        return parts[2] if len(parts) > 2 else ""

    for rel_path in knowledge_files:
        domain = _domain(rel_path)
        if domain:
            domain_file_counts[domain] = domain_file_counts.get(domain, 0) + 1

    for source in knowledge_files:
        source_domain = _domain(source)
        for target in graph.outgoing.get(source, set()):
            if target not in knowledge_set:
                continue
            target_domain = _domain(target)
            if not source_domain or not target_domain:
                continue
            if source_domain == target_domain:
                within_domain_edge_total += 1
                continue
            directional_counts[(source_domain, target_domain)] = (
                directional_counts.get((source_domain, target_domain), 0) + 1
            )

    filtered_directional_counts = {
        (left, right): count
        for (left, right), count in directional_counts.items()
        if count >= min_edges
        and (not normalized_source or left == normalized_source)
        and (not normalized_target or right == normalized_target)
    }
    symmetric_counts: dict[tuple[str, str], int] = {}
    per_domain: dict[str, dict[str, Any]] = {}
    domain_target_counts: dict[str, dict[str, int]] = {}
    visible_domains: set[str] = set()
    for (left, right), count in filtered_directional_counts.items():
        key = tuple(sorted((left, right)))
        symmetric_counts[key] = symmetric_counts.get(key, 0) + count
        visible_domains.update((left, right))
        source_bucket = per_domain.setdefault(
            left,
            {
                "domain": left,
                "files": domain_file_counts.get(left, 0),
                "incoming_cross": 0,
                "outgoing_cross": 0,
            },
        )
        target_bucket = per_domain.setdefault(
            right,
            {
                "domain": right,
                "files": domain_file_counts.get(right, 0),
                "incoming_cross": 0,
                "outgoing_cross": 0,
            },
        )
        source_bucket["outgoing_cross"] += count
        target_bucket["incoming_cross"] += count
        targets_for_domain = domain_target_counts.setdefault(left, {})
        targets_for_domain[right] = targets_for_domain.get(right, 0) + count

    if (
        normalized_source
        and normalized_source not in per_domain
        and normalized_source in domain_file_counts
    ):
        per_domain[normalized_source] = {
            "domain": normalized_source,
            "files": domain_file_counts.get(normalized_source, 0),
            "incoming_cross": 0,
            "outgoing_cross": 0,
        }
        visible_domains.add(normalized_source)
    if (
        normalized_target
        and normalized_target not in per_domain
        and normalized_target in domain_file_counts
    ):
        per_domain[normalized_target] = {
            "domain": normalized_target,
            "files": domain_file_counts.get(normalized_target, 0),
            "incoming_cross": 0,
            "outgoing_cross": 0,
        }
        visible_domains.add(normalized_target)

    knowledge_graph = build_knowledge_graph(root, scope=scope)
    metrics = analyze_graph(knowledge_graph["nodes"], knowledge_graph["edges"])
    cross_domain_edge_total = sum(filtered_directional_counts.values())

    domains_payload = []
    for domain_name, bucket in sorted(per_domain.items(), key=lambda item: item[0]):
        top_targets = [
            {"target_domain": target_domain, "edge_count": count}
            for target_domain, count in sorted(
                domain_target_counts.get(domain_name, {}).items(),
                key=lambda item: (-item[1], item[0]),
            )[:5]
        ]
        domains_payload.append(
            {
                **bucket,
                "cross_degree": bucket["incoming_cross"] + bucket["outgoing_cross"],
                "top_targets": top_targets,
            }
        )

    matrix = [
        {
            "source_domain": source_domain,
            "targets": {
                target_domain: count
                for target_domain, count in sorted(targets.items(), key=lambda item: item[0])
            },
        }
        for source_domain, targets in sorted(domain_target_counts.items(), key=lambda item: item[0])
        if targets
    ]

    return {
        "scope": _normalize_repo_path(scope) or "memory/knowledge",
        "source_domain_filter": normalized_source,
        "target_domain_filter": normalized_target,
        "min_edge_count": min_edges,
        "domain_count": len(visible_domains) if visible_domains else len(per_domain),
        "domains": domains_payload,
        "cross_domain_edge_total": cross_domain_edge_total,
        "within_domain_edge_total": within_domain_edge_total,
        "cross_domain_edge_ratio": round(
            cross_domain_edge_total / (cross_domain_edge_total + within_domain_edge_total),
            4,
        )
        if (cross_domain_edge_total + within_domain_edge_total) > 0
        else 0.0,
        "matrix": matrix,
        "directional_pairs": [
            {
                "source_domain": source_domain,
                "target_domain": target_domain,
                "edge_count": count,
            }
            for (source_domain, target_domain), count in sorted(
                filtered_directional_counts.items(), key=lambda item: (-item[1], item[0])
            )
        ],
        "symmetric_pairs": [
            {
                "domains": [left, right],
                "edge_count": count,
            }
            for (left, right), count in sorted(
                symmetric_counts.items(), key=lambda item: (-item[1], item[0])
            )
        ],
        "bridge_files": metrics.get("bridges", []),
        "graph_metrics": {
            "nodes": metrics.get("nodes"),
            "edges": metrics.get("edges"),
            "avg_degree": metrics.get("avg_degree"),
            "sigma": metrics.get("sigma"),
        },
    }


def summarize_connectivity_graph(graph: ConnectivityGraph) -> dict[str, Any]:
    """Return compact stats for a directed connectivity graph."""
    files = graph.files
    edge_count = sum(len(targets) for targets in graph.outgoing.values())
    total_degree = [
        len(graph.outgoing.get(rel_path, set())) + len(graph.incoming.get(rel_path, set()))
        for rel_path in files
    ]
    node_count = len(files)
    isolated_count = sum(1 for degree in total_degree if degree == 0)
    sink_count = sum(
        1
        for rel_path in files
        if graph.incoming.get(rel_path, set()) and not graph.outgoing.get(rel_path, set())
    )
    source_count = sum(
        1
        for rel_path in files
        if graph.outgoing.get(rel_path, set()) and not graph.incoming.get(rel_path, set())
    )
    return {
        "nodes": node_count,
        "edges": edge_count,
        "isolated_count": isolated_count,
        "sink_count": sink_count,
        "source_count": source_count,
        "mean_total_degree": round(sum(total_degree) / node_count, 2) if node_count else 0.0,
    }


def diff_connectivity_graphs(
    current: ConnectivityGraph, previous: ConnectivityGraph
) -> dict[str, Any]:
    """Return a structured diff between two directed connectivity graphs."""

    def _domain(path: str) -> str:
        parts = Path(path).parts
        return parts[2] if len(parts) > 2 else ""

    def _degree_category(graph: ConnectivityGraph, rel_path: str) -> str | None:
        return _classify_file(
            len(graph.incoming.get(rel_path, set())),
            len(graph.outgoing.get(rel_path, set())),
            threshold=2,
        )

    current_edges = {
        (source, target) for source, targets in current.outgoing.items() for target in targets
    }
    previous_edges = {
        (source, target) for source, targets in previous.outgoing.items() for target in targets
    }

    added_edges = sorted(current_edges - previous_edges)
    removed_edges = sorted(previous_edges - current_edges)
    changed_files = sorted({path for edge in (added_edges + removed_edges) for path in edge})

    added_domain_pairs: dict[tuple[str, str], int] = {}
    removed_domain_pairs: dict[tuple[str, str], int] = {}
    for source, target in added_edges:
        pair = (_domain(source), _domain(target))
        added_domain_pairs[pair] = added_domain_pairs.get(pair, 0) + 1
    for source, target in removed_edges:
        pair = (_domain(source), _domain(target))
        removed_domain_pairs[pair] = removed_domain_pairs.get(pair, 0) + 1

    impacted_files_detail = []
    changed_category_counts: dict[str, int] = {}
    for rel_path in changed_files:
        previous_category = _degree_category(previous, rel_path)
        current_category = _degree_category(current, rel_path)
        transition = f"{previous_category or 'connected'}->{current_category or 'connected'}"
        changed_category_counts[transition] = changed_category_counts.get(transition, 0) + 1
        impacted_files_detail.append(
            {
                "path": rel_path,
                "domain": _domain(rel_path),
                "previous_category": previous_category or "connected",
                "current_category": current_category or "connected",
            }
        )

    current_stats = summarize_connectivity_graph(current)
    previous_stats = summarize_connectivity_graph(previous)

    return {
        "current_stats": current_stats,
        "previous_stats": previous_stats,
        "graph_stats_delta": {
            key: round(float(current_stats[key]) - float(previous_stats.get(key, 0)), 2)
            for key in current_stats
        },
        "added_edges": [{"source": source, "target": target} for source, target in added_edges],
        "removed_edges": [{"source": source, "target": target} for source, target in removed_edges],
        "impacted_files": changed_files,
        "impacted_files_detail": impacted_files_detail,
        "added_domain_pairs": [
            {
                "source_domain": source_domain,
                "target_domain": target_domain,
                "edge_count": count,
            }
            for (source_domain, target_domain), count in sorted(
                added_domain_pairs.items(), key=lambda item: (-item[1], item[0])
            )
        ],
        "removed_domain_pairs": [
            {
                "source_domain": source_domain,
                "target_domain": target_domain,
                "edge_count": count,
            }
            for (source_domain, target_domain), count in sorted(
                removed_domain_pairs.items(), key=lambda item: (-item[1], item[0])
            )
        ],
        "changed_category_counts": dict(sorted(changed_category_counts.items())),
    }


def _domain_peers(rel_path: str, root: Path, max_peers: int = 8) -> list[str]:
    """Return sibling .md files in the same directory."""
    parent = (root / rel_path).parent
    if not parent.is_dir():
        return []
    return [
        f.name
        for f in sorted(parent.iterdir())
        if f.is_file()
        and f.suffix.lower() == ".md"
        and f.name != Path(rel_path).name
        and f.name != "SUMMARY.md"
    ][:max_peers]


def find_unlinked_files(
    root: Path,
    scope: str = "",
    threshold: int = 2,
    category_filter: str = "",
    max_results: int = 25,
    include_suggestions: bool = True,
) -> dict[str, Any]:
    """Build connectivity graph and surface files with low cross-reference connectivity.

    After review, the agent can add ``related:`` entries via
    ``memory_update_frontmatter_bulk`` to increase cross-reference coverage.

    Args:
        root: Repository root path.
        scope: Repo-relative scope to scan (default: all governed files).
        threshold: Max total degree to count as ``low_connectivity``.
        category_filter: Restrict to a single bucket (isolated/sink/source/low_connectivity).
        max_results: Maximum candidates to return.
        include_suggestions: Whether to compute link suggestions per candidate.

    Returns:
        Dict with graph_stats, candidates list, and budget metadata.
    """
    graph = build_connectivity_graph(root, scope)

    # Compute per-file degrees and classify
    candidates: list[dict[str, Any]] = []
    bucket_counts = {"isolated": 0, "sink": 0, "source": 0, "low_connectivity": 0}
    degrees: list[int] = []

    for rel_path in graph.files:
        in_deg = len(graph.incoming.get(rel_path, set()))
        out_deg = len(graph.outgoing.get(rel_path, set()))
        total = in_deg + out_deg
        degrees.append(total)

        category = _classify_file(in_deg, out_deg, threshold)
        if category is None:
            continue
        bucket_counts[category] += 1

        if category_filter and category != category_filter:
            continue

        parts = Path(rel_path).parts
        ctx = _extract_candidate_context(rel_path, root)
        candidates.append(
            {
                "path": rel_path,
                "category": category,
                "in_degree": in_deg,
                "out_degree": out_deg,
                "total_degree": total,
                "domain": parts[2] if len(parts) > 2 else "",
                "subdirectory": Path(rel_path).parent.as_posix(),
                "age_days": ctx["age_days"],
                "trust": ctx["trust"],
                "extract": ctx["extract"],
                "headings": ctx["headings"],
                "existing_related": ctx["existing_related"],
                "domain_peers": _domain_peers(rel_path, root),
            }
        )

    # Sort: isolated first, then by age (oldest first), then path
    candidates.sort(
        key=lambda c: (
            _CATEGORY_PRIORITY.get(c["category"], 99),
            -(c["age_days"] or 0),
            c["path"],
        )
    )

    total_candidates = len(candidates)
    candidates = candidates[:max_results]

    # Suggestions are computed only for the returned candidates
    if include_suggestions:
        for c in candidates:
            c["suggested_links"] = _suggest_link_candidates(c["path"], graph, root)

    total_edges = sum(len(refs) for refs in graph.outgoing.values())
    graph_stats: dict[str, Any] = {
        "total_files": len(graph.files),
        "total_edges": total_edges,
        "mean_degree": round(statistics.mean(degrees), 1) if degrees else 0,
        "median_degree": round(statistics.median(degrees), 1) if degrees else 0,
        "isolated_count": bucket_counts["isolated"],
        "sink_count": bucket_counts["sink"],
        "source_count": bucket_counts["source"],
        "low_connectivity_count": bucket_counts["low_connectivity"],
    }

    result: dict[str, Any] = {
        "scope": graph.scope,
        "graph_stats": graph_stats,
        "candidates": candidates,
        "budget": {
            "returned": len(candidates),
            "total": total_candidates,
            "truncated": total_candidates > max_results,
        },
    }
    return result
