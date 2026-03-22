from __future__ import annotations

import re
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


def _resolve_reference(from_path: str, target: str, root: Path) -> str | None:
    cleaned = _strip_markdown_target(target)
    if not cleaned or _is_external_target(cleaned):
        return None
    if cleaned.startswith("/"):
        cleaned = cleaned.lstrip("/")

    base = root / from_path
    if cleaned.startswith(("./", "../")):
        resolved = _resolve_legacy_relative_target(from_path, cleaned, root)
        if resolved is None:
            resolved = (base.parent / cleaned).resolve()
    elif any(cleaned.startswith(f"{prefix}/") for prefix in _GOVERNED_REFERENCE_ROOTS):
        resolved = (root / cleaned).resolve()
    else:
        resolved = (base.parent / cleaned).resolve()

    try:
        return resolved.relative_to(root).as_posix()
    except ValueError:
        return None


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
    base = root / from_path
    if cleaned.startswith(("./", "../")):
        resolved = _resolve_legacy_relative_target(from_path, cleaned, root)
        if resolved is None:
            resolved = (base.parent / cleaned).resolve()
    elif any(cleaned.startswith(f"{prefix}/") for prefix in _GOVERNED_REFERENCE_ROOTS):
        resolved = (root / cleaned).resolve()
    else:
        resolved = (base.parent / cleaned).resolve()

    try:
        rel_path = resolved.relative_to(root).as_posix()
    except ValueError:
        return None, anchor, "target escapes repository root"
    return rel_path, anchor, None


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
            try:
                files.append(md_file.relative_to(root).as_posix())
            except ValueError:
                continue

    humans_root = root / "HUMANS"
    if not humans_root.is_dir():
        humans_root = root.parent / "HUMANS"
    if humans_root.is_dir():
        for md_file in sorted(humans_root.rglob("*.md")):
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
        return [scope_path.relative_to(root).as_posix()]

    files: list[str] = []
    for md_file in sorted(scope_path.rglob("*.md")):
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
