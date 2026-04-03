"""Shared maintenance preview helpers for Engram terminal commands."""

from __future__ import annotations

import re
from pathlib import Path, PurePosixPath
from typing import Any

from ..errors import ValidationError
from ..tools.read_tools._helpers import (
    _load_access_entries,
    _parse_aggregation_trigger,
    _parse_review_queue_entries,
    _parse_trust_thresholds,
    _scan_unverified_content,
)
from ..tools.semantic.session_tools import (
    _archive_target_for_access_file,
    _build_phase1_clusters,
    _filter_aggregation_entries,
    _normalize_aggregation_folders,
)
from .formatting import format_snippet, namespace_prefixes, read_markdown

_ALLOWED_AGGREGATION_FOLDERS = (
    "memory/users",
    "memory/knowledge",
    "memory/knowledge/_unverified",
    "memory/skills",
    "memory/working/projects",
    "memory/activity",
)
_NEAR_TRIGGER_WINDOW = 3
_REVIEW_DECISIONS = ("approve", "reject", "defer")
_PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}
_TYPE_ORDER = {"review_queue": 0, "stale_unverified": 1, "aggregation": 2}


def review_decisions() -> tuple[str, ...]:
    return _REVIEW_DECISIONS


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "item"


def _extract_preview(body: str, *, max_words: int) -> str:
    if max_words <= 0:
        return ""
    words = body.split()
    if not words:
        return ""
    preview = " ".join(words[:max_words])
    if len(words) > max_words:
        preview += " ..."
    return format_snippet(preview, limit=220)


def resolve_aggregation_folders(namespace: str | None) -> list[str] | None:
    if namespace is None:
        return None

    prefixes = namespace_prefixes(namespace)
    if not prefixes:
        raise ValidationError("namespace must be a non-empty namespace or repo-relative path")

    resolved: list[str] = []
    allowed_by_specificity = sorted(_ALLOWED_AGGREGATION_FOLDERS, key=len, reverse=True)
    for prefix in prefixes:
        normalized_prefix = prefix.replace("\\", "/").rstrip("/")
        match = next(
            (
                allowed
                for allowed in allowed_by_specificity
                if normalized_prefix == allowed or normalized_prefix.startswith(f"{allowed}/")
            ),
            None,
        )
        if match is not None and match not in resolved:
            resolved.append(match)

    if not resolved:
        raise ValidationError(
            f"namespace does not map to a supported aggregation folder: {namespace}"
        )

    return _normalize_aggregation_folders(resolved)


def build_aggregation_trigger_report(
    content_root: Path,
    *,
    folders: list[str] | None = None,
) -> dict[str, Any]:
    selected_folders = _normalize_aggregation_folders(folders) if folders is not None else None
    trigger = _parse_aggregation_trigger(content_root)
    _, access_counts = _load_access_entries(content_root)

    reports: list[dict[str, Any]] = []
    above_trigger: list[str] = []
    near_trigger: list[str] = []
    for item in access_counts:
        folder = str(item["folder"]).rstrip("/")
        if selected_folders is not None and folder not in selected_folders:
            continue

        entry_count = int(item["entries"])
        remaining = max(trigger - entry_count, 0)
        if entry_count >= trigger:
            status = "above"
            above_trigger.append(str(item["access_file"]))
        elif remaining <= _NEAR_TRIGGER_WINDOW:
            status = "near"
            near_trigger.append(str(item["access_file"]))
        else:
            status = "below"

        reports.append(
            {
                **item,
                "folder": folder,
                "trigger": trigger,
                "remaining_to_trigger": remaining,
                "status": status,
            }
        )

    reports.sort(key=lambda item: (str(item["folder"]), str(item["access_file"])))
    return {
        "aggregation_trigger": trigger,
        "near_trigger_window": _NEAR_TRIGGER_WINDOW,
        "reports": reports,
        "above_trigger": sorted(above_trigger),
        "near_trigger": sorted(near_trigger),
    }


def build_aggregate_preview(content_root: Path, *, namespace: str | None = None) -> dict[str, Any]:
    selected_folders = resolve_aggregation_folders(namespace)
    aggregation_report = build_aggregation_trigger_report(content_root, folders=selected_folders)
    all_entries, _ = _load_access_entries(content_root)
    filtered_entries = _filter_aggregation_entries(all_entries, selected_folders)
    clusters, session_group_count, legacy_fallback_entries = _build_phase1_clusters(
        filtered_entries,
        threshold=3,
    )

    entries_by_access_file: dict[str, list[dict[str, Any]]] = {}
    for entry in filtered_entries:
        access_file = str(entry.get("_access_file") or "").strip()
        if access_file:
            entries_by_access_file.setdefault(access_file, []).append(entry)

    entries_by_folder: dict[str, list[dict[str, Any]]] = {}
    for entry in filtered_entries:
        folder = PurePosixPath(str(entry["file"])).parent.as_posix()
        entries_by_folder.setdefault(folder, []).append(entry)

    summary_targets = [
        f"{folder}/SUMMARY.md"
        for folder, folder_entries in sorted(entries_by_folder.items())
        if folder_entries and (content_root / folder / "SUMMARY.md").exists()
    ]
    hot_access_targets = sorted(entries_by_access_file)
    archive_targets = sorted(
        {
            _archive_target_for_access_file(access_file, entries)
            for access_file, entries in entries_by_access_file.items()
            if entries
        }
    )

    return {
        "mode": "dry_run",
        "namespace": namespace,
        "aggregation_trigger": aggregation_report["aggregation_trigger"],
        "near_trigger_window": aggregation_report["near_trigger_window"],
        "reports": aggregation_report["reports"],
        "above_trigger": aggregation_report["above_trigger"],
        "near_trigger": aggregation_report["near_trigger"],
        "folders": selected_folders or sorted(entries_by_folder),
        "entries_processed": len(filtered_entries),
        "session_groups_processed": session_group_count,
        "legacy_fallback_entries": legacy_fallback_entries,
        "summary_update_targets": summary_targets,
        "summary_materialization_targets": summary_targets,
        "hot_access_targets": hot_access_targets,
        "hot_access_reset_targets": hot_access_targets,
        "archive_targets": archive_targets,
        "clusters": clusters,
    }


def _sort_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates.sort(
        key=lambda item: (
            _PRIORITY_ORDER.get(str(item.get("priority") or "medium"), 9),
            _TYPE_ORDER.get(str(item.get("candidate_type") or "aggregation"), 9),
            str(item.get("title") or item.get("id") or ""),
        )
    )
    for index, candidate in enumerate(candidates, start=1):
        candidate["number"] = index
    return candidates


def build_review_payload(
    content_root: Path,
    *,
    max_extract_words: int = 40,
    include_near: bool = True,
) -> dict[str, Any]:
    if max_extract_words < 0:
        raise ValidationError("max_extract_words must be >= 0")

    low_threshold, _ = _parse_trust_thresholds(content_root)
    queue_entries = _parse_review_queue_entries(content_root)
    pending_queue = [
        entry
        for entry in queue_entries
        if entry.get("status", "pending") == "pending"
        or (entry.get("type") == "security" and entry.get("status", "pending") == "investigated")
    ]

    candidates: list[dict[str, Any]] = []
    for entry in pending_queue:
        entry_type = str(entry.get("type") or "proposed")
        summary = format_snippet(str(entry.get("description") or "Queued governance review item."))
        candidate_id = f"review-queue:{entry.get('date', 'unknown')}:{_slugify(str(entry.get('title') or 'item'))}"
        candidates.append(
            {
                "id": candidate_id,
                "candidate_type": "review_queue",
                "priority": "high",
                "title": str(entry.get("title") or "Review queue item"),
                "summary": summary,
                "action_hint": "Resolve, supersede, or defer the queued proposal.",
                "details": {
                    "date": entry.get("date"),
                    "type": entry_type,
                    "status": entry.get("status", "pending"),
                    "description": entry.get("description"),
                    "rule_affected": entry.get("rule_affected"),
                },
            }
        )

    unverified = _scan_unverified_content(content_root, low_threshold)
    for item in unverified["overdue"]:
        rel_path = str(item["path"])
        abs_path = content_root / rel_path
        _, body = read_markdown(abs_path)
        age_days = item.get("age_days")
        source = item.get("source") or "unknown"
        summary = f"Low-trust note is {age_days} days old and sourced from {source}."
        candidates.append(
            {
                "id": f"unverified:{rel_path}",
                "candidate_type": "stale_unverified",
                "priority": "high",
                "title": rel_path,
                "summary": summary,
                "action_hint": "Review for promotion, archival, or rejection.",
                "details": {
                    **item,
                    "extract": _extract_preview(body, max_words=max_extract_words),
                },
            }
        )

    aggregation_report = build_aggregation_trigger_report(content_root)
    for report in aggregation_report["reports"]:
        status = str(report["status"])
        if status == "below":
            continue
        if status == "near" and not include_near:
            continue
        priority = "high" if status == "above" else "medium"
        entries = int(report["entries"])
        trigger = int(report["trigger"])
        remaining = int(report["remaining_to_trigger"])
        if status == "above":
            summary = f"{entries} entries in {report['access_file']} exceed trigger {trigger}."
        else:
            summary = f"{entries} entries in {report['access_file']} are {remaining} away from trigger {trigger}."
        candidates.append(
            {
                "id": f"aggregation:{report['folder']}",
                "candidate_type": "aggregation",
                "priority": priority,
                "title": str(report["folder"]),
                "summary": summary,
                "action_hint": "Preview or run ACCESS aggregation for this folder.",
                "details": dict(report),
            }
        )

    _sort_candidates(candidates)
    return {
        "max_extract_words": max_extract_words,
        "include_near": include_near,
        "decision_options": list(_REVIEW_DECISIONS),
        "count": len(candidates),
        "counts": {
            "review_queue": len(pending_queue),
            "stale_unverified": len(unverified["overdue"]),
            "aggregation": len(
                [
                    candidate
                    for candidate in candidates
                    if candidate["candidate_type"] == "aggregation"
                ]
            ),
        },
        "candidates": candidates,
    }


def apply_review_decisions(
    payload: dict[str, Any],
    decision_specs: list[str] | None,
) -> dict[str, Any]:
    updated_candidates = [dict(candidate) for candidate in payload.get("candidates", [])]
    result = {**payload, "candidates": updated_candidates}
    if not decision_specs:
        result["decisions"] = []
        result["resolved_count"] = 0
        result["unresolved_count"] = int(result.get("count") or 0)
        return result

    by_number = {str(candidate["number"]): candidate for candidate in updated_candidates}
    by_id = {str(candidate["id"]): candidate for candidate in updated_candidates}
    applied: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for raw_spec in decision_specs:
        target, separator, raw_decision = raw_spec.partition("=")
        if separator != "=":
            raise ValidationError(
                "decision entries must use <candidate-number|candidate-id>=approve|reject|defer"
            )
        decision = raw_decision.strip().lower()
        if decision not in _REVIEW_DECISIONS:
            raise ValidationError(
                f"Unsupported review decision: {raw_decision.strip() or raw_decision}"
            )
        candidate = by_number.get(target.strip()) or by_id.get(target.strip())
        if candidate is None:
            raise ValidationError(f"Unknown review candidate: {target.strip()}")
        candidate_id = str(candidate["id"])
        if candidate_id in seen_ids:
            raise ValidationError(f"Duplicate review decision for {candidate_id}")
        seen_ids.add(candidate_id)
        candidate["decision"] = decision
        applied.append(
            {
                "number": candidate["number"],
                "id": candidate_id,
                "decision": decision,
                "candidate_type": candidate["candidate_type"],
            }
        )

    result["decisions"] = applied
    result["resolved_count"] = len(applied)
    result["unresolved_count"] = int(result.get("count") or 0) - len(applied)
    return result
