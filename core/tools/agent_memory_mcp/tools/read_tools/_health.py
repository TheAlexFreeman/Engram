"""Read tools — health submodule."""

from __future__ import annotations

import re
import subprocess
import sys
from datetime import date
from typing import TYPE_CHECKING, Any, cast

from ...response_envelope import dump_tool_result

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

    from ...session_state import SessionState


def register_health(
    mcp: "FastMCP",
    get_repo,
    get_root,
    H,
    *,
    tools: dict[str, object],
    session_state: "SessionState | None" = None,
) -> dict[str, object]:
    """Register health read tools and return their callables."""
    _build_review_unverified_payload = cast(Any, tools["_build_review_unverified_payload"])

    _NEAR_TRIGGER_WINDOW = H._NEAR_TRIGGER_WINDOW
    _assess_maturity_stage = H._assess_maturity_stage
    _build_capabilities_summary = H._build_capabilities_summary
    _build_knowledge_freshness_report = H._build_knowledge_freshness_report
    _collect_plan_entries = H._collect_plan_entries
    _collect_recent_reflections = H._collect_recent_reflections
    _compute_maturity_signals = H._compute_maturity_signals
    _detect_access_anomalies = H._detect_access_anomalies
    _detect_co_retrieval_clusters = H._detect_co_retrieval_clusters
    _effective_date = H._effective_date
    _filter_access_entries = H._filter_access_entries
    _find_conflict_tags = H._find_conflict_tags
    _get_host_git_repo = H._get_host_git_repo
    _git_changed_files_since = H._git_changed_files_since
    _load_access_entries = H._load_access_entries
    _load_capabilities_manifest = H._load_capabilities_manifest
    _load_content_files = H._load_content_files
    _normalize_user_id = H.normalize_user_id
    _normalize_repo_relative_path = H._normalize_repo_relative_path
    _parse_aggregation_trigger = H._parse_aggregation_trigger
    _parse_current_stage = H._parse_current_stage
    _parse_expires_date = H._parse_expires_date
    _parse_iso_date = H._parse_iso_date
    _parse_last_periodic_review = H._parse_last_periodic_review
    _parse_periodic_review_window = H._parse_periodic_review_window
    _parse_review_queue_entries = H._parse_review_queue_entries
    _parse_trust_thresholds = H._parse_trust_thresholds
    _resolve_category_prefixes = H._resolve_category_prefixes
    _resolve_governance_path = H._resolve_governance_path
    _resolve_humans_root = H._resolve_humans_root
    _resolve_live_router_path = H._resolve_live_router_path
    _route_workflow_hint = H._route_workflow_hint
    _scan_unverified_content = H._scan_unverified_content
    _summarize_access_by_file = H._summarize_access_by_file
    _summarize_access_by_folder = H._summarize_access_by_folder
    _tool_annotations = H._tool_annotations
    _truncate_items = H._truncate_items

    def _dump_payload(payload: Any, *, default: Any | None = None) -> str:
        if session_state is not None:
            session_state.record_tool_call()
        return dump_tool_result(payload, session_state, indent=2, default=default)

    def _build_session_health_payload() -> dict[str, Any]:
        root = get_root()
        trigger = _parse_aggregation_trigger(root)
        review_window_days = _parse_periodic_review_window(root)
        _, access_counts = _load_access_entries(root)
        last_review = _parse_last_periodic_review(root)
        today = date.today()
        days_since_review = (today - last_review).days if last_review is not None else None

        aggregation_due = []
        for item in access_counts:
            entry_count = int(item["entries"])
            if entry_count < trigger:
                continue
            folder = str(item["folder"]).rstrip("/")
            aggregation_due.append(
                {
                    "folder": f"{folder}/",
                    "entries": entry_count,
                    "threshold": trigger,
                    "overdue": True,
                }
            )

        aggregation_due.sort(
            key=lambda item: (-cast(int, item["entries"]), cast(str, item["folder"]))
        )

        review_queue_entries = _parse_review_queue_entries(root)
        pending_review_queue = [
            entry
            for entry in review_queue_entries
            if entry.get("status", "pending") == "pending"
            or (
                entry.get("type") == "security" and entry.get("status", "pending") == "investigated"
            )
        ]

        return {
            "aggregation_due": aggregation_due,
            "aggregation_threshold": trigger,
            "review_queue_pending": len(pending_review_queue),
            "periodic_review_due": last_review is None
            or (days_since_review is not None and days_since_review > review_window_days),
            "days_since_review": days_since_review,
            "last_periodic_review": str(last_review) if last_review is not None else None,
            "checked_at": str(today),
        }

    # ------------------------------------------------------------------
    @mcp.tool(
        name="memory_session_health_check",
        annotations=_tool_annotations(
            title="Session Health Check",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def memory_session_health_check() -> str:
        """Return session-start maintenance status for ACCESS, review queue, and review cadence.

        Reads the active aggregation trigger and last periodic review date from
        the live router file, counts hot ACCESS.jsonl entries, and summarizes
        pending review-queue items.

        Returns:
            JSON envelope with result and _session metadata. result contains
            aggregation_due, aggregation_threshold, review_queue_pending,
            periodic_review_due, days_since_review, last_periodic_review, checked_at.
        """
        return _dump_payload(_build_session_health_payload())

    # ------------------------------------------------------------------
    # memory_check_aggregation_triggers

    # ------------------------------------------------------------------
    @mcp.tool(
        name="memory_check_aggregation_triggers",
        annotations=_tool_annotations(
            title="ACCESS Aggregation Trigger Status",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def memory_check_aggregation_triggers() -> str:
        """Report which hot ACCESS logs are below, near, or above aggregation trigger.

        Uses the active aggregation threshold from the live router file and
        counts valid non-empty entries in each hot ACCESS.jsonl file.

        Returns:
            JSON with trigger metadata, per-log counts, and lists of files that
            are near or above the aggregation threshold.
        """
        root = get_root()
        trigger = _parse_aggregation_trigger(root)
        _, access_counts = _load_access_entries(root)

        report: list[dict[str, Any]] = []
        above_trigger: list[str] = []
        near_trigger: list[str] = []

        for item in access_counts:
            entry_count = int(item["entries"])
            remaining = max(trigger - entry_count, 0)
            if entry_count >= trigger:
                status = "above"
                above_trigger.append(cast(str, item["access_file"]))
            elif remaining <= _NEAR_TRIGGER_WINDOW:
                status = "near"
                near_trigger.append(cast(str, item["access_file"]))
            else:
                status = "below"

            report.append(
                {
                    **item,
                    "trigger": trigger,
                    "remaining_to_trigger": remaining,
                    "status": status,
                }
            )

        payload = {
            "aggregation_trigger": trigger,
            "near_trigger_window": _NEAR_TRIGGER_WINDOW,
            "files_checked": len(report),
            "above_trigger": above_trigger,
            "near_trigger": near_trigger,
            "reports": report,
        }
        return _dump_payload(payload)

    # ------------------------------------------------------------------
    # memory_aggregate_access

    # ------------------------------------------------------------------
    @mcp.tool(
        name="memory_aggregate_access",
        annotations=_tool_annotations(
            title="Aggregate ACCESS Logs",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def memory_aggregate_access(
        folder: str = "",
        file_prefix: str = "",
        start_date: str = "",
        end_date: str = "",
        user_id: str = "",
        min_helpfulness: float | None = None,
        max_helpfulness: float | None = None,
    ) -> str:
        """Aggregate hot ACCESS.jsonl entries into a maintenance report.

        The first cut is read-only. It computes file-level access summaries,
        high-value and low-value candidates, same-session co-retrieval clusters,
        and preview targets for follow-up curation work.

        Returns:
            JSON report with filters, file summaries, clusters, and proposed
            follow-up outputs for summary updates, review queue entries, and
            archive targets.
        """
        root = get_root()
        trigger = _parse_aggregation_trigger(root)
        all_entries, access_counts = _load_access_entries(root)
        resolved_user_id = _normalize_user_id(user_id)
        filtered_entries = _filter_access_entries(
            all_entries,
            folder=folder,
            file_prefix=file_prefix,
            start_date=start_date,
            end_date=end_date,
            user_id=resolved_user_id,
            min_helpfulness=min_helpfulness,
            max_helpfulness=max_helpfulness,
        )
        file_summaries = _summarize_access_by_file(filtered_entries)
        clusters = _detect_co_retrieval_clusters(filtered_entries)

        high_value_files = [
            item
            for item in file_summaries
            if int(item["entry_count"]) >= 5
            and item["mean_helpfulness"] is not None
            and float(item["mean_helpfulness"]) >= 0.7
        ]
        low_value_files = [
            item
            for item in file_summaries
            if int(item["entry_count"]) >= 3
            and item["mean_helpfulness"] is not None
            and float(item["mean_helpfulness"]) <= 0.3
        ]

        archive_targets: list[str] = []
        if resolved_user_id is not None:
            scoped_archive_counts: dict[str, int] = {}
            archive_scope_entries = _filter_access_entries(
                all_entries,
                folder=folder,
                user_id=resolved_user_id,
            )
            for entry in archive_scope_entries:
                access_file = str(entry.get("_access_file", "")).strip()
                if not access_file:
                    continue
                scoped_archive_counts[access_file] = scoped_archive_counts.get(access_file, 0) + 1
            archive_targets = [
                access_file
                for access_file, entry_count in sorted(scoped_archive_counts.items())
                if entry_count >= trigger
            ]
        elif folder:
            normalized_folder = folder.rstrip("/")
            archive_targets = [
                cast(str, item["access_file"])
                for item in access_counts
                if cast(str, item["access_file"]).startswith(f"{normalized_folder}/")
                and int(item["entries"]) >= trigger
            ]
        else:
            archive_targets = [
                cast(str, item["access_file"])
                for item in access_counts
                if int(item["entries"]) >= trigger
            ]

        summary_update_targets = {
            f"{item['folder']}/SUMMARY.md"
            for item in high_value_files + low_value_files
            if isinstance(item.get("folder"), str)
        }
        for cluster in clusters:
            for folder_name in cast(list[str], cluster["folders"]):
                summary_update_targets.add(f"{folder_name}/SUMMARY.md")
        sorted_summary_update_targets = sorted(summary_update_targets)
        review_queue_candidates = [
            {
                "file": item["file"],
                "reason": "Consistently low-value ACCESS pattern",
                "entry_count": item["entry_count"],
                "mean_helpfulness": item["mean_helpfulness"],
            }
            for item in low_value_files
        ]
        task_group_candidates = [
            {
                "files": cluster["files"],
                "folders": cluster["folders"],
                "co_retrieval_count": cluster["co_retrieval_count"],
            }
            for cluster in clusters
            if len(cast(list[str], cluster["folders"])) >= 2
        ]

        payload = {
            "access_scope": "hot_only",
            "filters": {
                "folder": folder or None,
                "file_prefix": file_prefix or None,
                "start_date": start_date or None,
                "end_date": end_date or None,
                "user_id": resolved_user_id,
                "min_helpfulness": min_helpfulness,
                "max_helpfulness": max_helpfulness,
            },
            "aggregation_trigger": trigger,
            "entries_considered": len(filtered_entries),
            "files_considered": len(file_summaries),
            "high_value_files": high_value_files,
            "low_value_files": low_value_files,
            "co_retrieval_clusters": clusters,
            "file_summaries": file_summaries,
            "proposed_outputs": {
                "summary_update_targets": sorted_summary_update_targets,
                "access_archive_targets": archive_targets,
                "review_queue_candidates": review_queue_candidates,
                "task_group_candidates": task_group_candidates,
            },
        }
        return _dump_payload(payload)

    # ------------------------------------------------------------------
    # memory_run_periodic_review

    def _build_periodic_review_payload() -> dict[str, Any]:
        root = get_root()
        repo = get_repo()
        low_threshold, _ = _parse_trust_thresholds(root)
        current_stage = _parse_current_stage(root)
        last_review = _parse_last_periodic_review(root)
        today = date.today()
        review_window_days = _parse_periodic_review_window(root)
        days_since_review = (today - last_review).days if last_review is not None else None

        all_entries, access_counts = _load_access_entries(root)
        file_summaries = _summarize_access_by_file(all_entries)
        low_value_files = [
            item
            for item in file_summaries
            if int(item["entry_count"]) >= 3
            and item["mean_helpfulness"] is not None
            and float(item["mean_helpfulness"]) <= 0.3
        ]
        clusters = _detect_co_retrieval_clusters(all_entries)
        folder_summaries = _summarize_access_by_folder(file_summaries)
        review_queue_entries = _parse_review_queue_entries(root)
        security_entries = [
            entry for entry in review_queue_entries if entry.get("type") == "security"
        ]
        pending_security_entries = [
            entry
            for entry in security_entries
            if entry.get("status", "pending") in {"pending", "investigated"}
        ]
        pending_non_security_entries = [
            entry
            for entry in review_queue_entries
            if entry.get("type") != "security" and entry.get("status", "pending") == "pending"
        ]
        false_positive_security = [
            entry for entry in security_entries if entry.get("status") == "false-positive"
        ]

        unverified = _scan_unverified_content(root, low_threshold)
        conflicts = _find_conflict_tags(root)
        signals = _compute_maturity_signals(root, repo, all_entries)
        maturity = _assess_maturity_stage(signals, current_stage)
        anomaly_candidates = _detect_access_anomalies(root, all_entries, low_threshold)
        reflections = _collect_recent_reflections(root)
        recently_touched_files = _git_changed_files_since(repo, last_review)

        if last_review is None:
            review_due_reason = "No recorded periodic review date."
        elif days_since_review is not None and days_since_review > review_window_days:
            review_due_reason = f"Last periodic review was {days_since_review} days ago, beyond the {review_window_days}-day cadence."
        else:
            review_due_reason = "Periodic review cadence not yet exceeded."

        folder_candidates = {
            "high_access": [item for item in folder_summaries if int(item["entry_count"]) >= 15],
            "low_access": [item for item in folder_summaries if int(item["entry_count"]) <= 2],
        }
        governance_review_queue_count = len(
            [entry for entry in pending_non_security_entries if entry.get("type") == "governance"]
        )
        governance_evaluation = {
            "threshold_effectiveness": {
                "overdue_low_trust_files": len(cast(list[dict[str, Any]], unverified["overdue"])),
                "low_value_files": len(low_value_files),
            },
            "signal_quality": {
                "security_entries_total": len(security_entries),
                "security_false_positive_count": len(false_positive_security),
                "security_false_positive_ratio": (
                    round(len(false_positive_security) / len(security_entries), 3)
                    if security_entries
                    else None
                ),
                "anomaly_candidates": anomaly_candidates,
            },
            "consistency_targets": [
                "README.md",
                _resolve_live_router_path(root).relative_to(root).as_posix(),
                _resolve_governance_path(root, "update-guidelines.md").relative_to(root).as_posix(),
            ],
            "user_friendliness_notes": [
                "Keep protected changes in deferred output rather than applying them silently.",
                "Preserve metadata-first checks before loading expensive governance files.",
            ],
            "context_efficiency_notes": [
                "Compact returning path remains the default routing surface.",
                "Aggregation and periodic review stay read-first until a user approves protected writes.",
            ],
            "missing_coverage_prompt": governance_review_queue_count == 0,
        }

        summary_update_targets = {
            f"{item['folder']}/SUMMARY.md"
            for item in low_value_files
            if isinstance(item.get("folder"), str)
        }
        for cluster in clusters:
            for folder_name in cast(list[str], cluster["folders"]):
                summary_update_targets.add(f"{folder_name}/SUMMARY.md")

        deferred_write_targets = [
            _resolve_governance_path(root, "belief-diff-log.md").relative_to(root).as_posix()
        ]
        if (
            pending_non_security_entries
            or pending_security_entries
            or anomaly_candidates
            or unverified["overdue"]
        ):
            deferred_write_targets.append(
                _resolve_governance_path(root, "review-queue.md").relative_to(root).as_posix()
            )
        if (
            days_since_review is None
            or (days_since_review is not None and days_since_review > review_window_days)
            or maturity["transition_recommended"]
        ):
            deferred_write_targets.append(
                _resolve_live_router_path(root).relative_to(root).as_posix()
            )
        deferred_write_targets.extend(sorted(summary_update_targets))

        new_files_since_review = []
        for rel_path in _load_content_files(root):
            try:
                text = (root / rel_path).read_text(encoding="utf-8")
            except OSError:
                continue
            created_match = re.search(r"^created:\s*(\d{4}-\d{2}-\d{2})$", text, re.MULTILINE)
            if created_match is None or last_review is None:
                continue
            created_date = _parse_iso_date(created_match.group(1))
            if created_date is not None and created_date > last_review:
                new_files_since_review.append(rel_path)

        payload = {
            "review_due": {
                "last_periodic_review": str(last_review) if last_review is not None else None,
                "days_since_review": days_since_review,
                "due": last_review is None
                or (days_since_review is not None and days_since_review > review_window_days),
                "reason": review_due_reason,
            },
            "ordered_checks": {
                "security_flags": {
                    "pending_count": len(pending_security_entries),
                    "pending_entries": pending_security_entries,
                    "generated_candidates": anomaly_candidates,
                },
                "unverified_content": {
                    "total_files": len(cast(list[dict[str, Any]], unverified["files"])),
                    "overdue_count": len(cast(list[dict[str, Any]], unverified["overdue"])),
                    "overdue_files": unverified["overdue"],
                },
                "conflict_resolution": {
                    "count": len(conflicts),
                    "files": conflicts,
                },
                "review_queue": {
                    "pending_non_security_count": len(pending_non_security_entries),
                    "pending_non_security_entries": pending_non_security_entries,
                },
                "unhelpful_memory": {
                    "count": len(low_value_files),
                    "files": low_value_files,
                },
                "maturity_assessment": {
                    **maturity,
                    "signals": signals,
                },
                "governance_evaluation": governance_evaluation,
                "folder_structure": {
                    "folder_summaries": folder_summaries,
                    "candidates": folder_candidates,
                },
                "emergent_categorization": {
                    "cluster_count": len(clusters),
                    "clusters": clusters,
                },
                "session_reflection_themes": {
                    "reflection_count": len(reflections),
                    "recent_reflections": reflections,
                },
            },
            "belief_diff_preview": {
                "new_files_since_review": sorted(new_files_since_review),
                "recently_touched_files": recently_touched_files,
            },
            "aggregation_status": {
                "trigger": _parse_aggregation_trigger(root),
                "logs": access_counts,
            },
            "proposed_outputs": {
                "deferred_write_targets": sorted(set(deferred_write_targets)),
                "summary_update_targets": sorted(summary_update_targets),
                "review_queue_candidates": [
                    {
                        "type": "security",
                        "title": candidate["type"],
                        "file": candidate["file"],
                        "recommended_action": candidate["recommended_action"],
                    }
                    for candidate in anomaly_candidates
                ],
            },
        }
        return payload

    # ------------------------------------------------------------------
    @mcp.tool(
        name="memory_run_periodic_review",
        annotations=_tool_annotations(
            title="Periodic Review Report",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def memory_run_periodic_review() -> str:
        """Run the ordered periodic-review checklist as a read-only report.

        The tool mirrors the checklist in governance/update-guidelines.md and returns
        structured findings plus deferred write targets rather than mutating any
        protected files directly.
        """
        return _dump_payload(_build_periodic_review_payload())

    # ------------------------------------------------------------------
    # memory_session_bootstrap

    # ------------------------------------------------------------------
    @mcp.tool(
        name="memory_session_bootstrap",
        annotations=_tool_annotations(
            title="Session Bootstrap Bundle",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def memory_session_bootstrap(
        max_active_plans: int = 5,
        max_review_items: int = 5,
    ) -> str:
        """Return a compact session-start bundle for the returning-agent path."""
        from ...errors import ValidationError

        if max_active_plans < 1 or max_review_items < 1:
            raise ValidationError("max_active_plans and max_review_items must be >= 1")

        root = get_root()
        manifest, manifest_error = _load_capabilities_manifest(root)
        capabilities_summary = manifest_error or {
            "summary": _build_capabilities_summary(cast(dict[str, Any], manifest))
        }
        session_health = _build_session_health_payload()
        active_plans, active_plan_budget = _truncate_items(
            _collect_plan_entries(root, status="active"),
            max_active_plans,
        )
        review_queue_entries = _parse_review_queue_entries(root)
        pending_review_items = [
            {
                "item_id": entry.get("item_id"),
                "title": entry.get("title"),
                "type": entry.get("type", "unknown"),
                "priority": entry.get("priority", "normal"),
                "file": entry.get("file"),
                "status": entry.get("status", "pending"),
            }
            for entry in review_queue_entries
            if entry.get("status", "pending") == "pending"
        ]
        pending_review_items, review_budget = _truncate_items(
            pending_review_items,
            max_review_items,
        )

        recommended_checks: list[str] = []
        if cast(list[dict[str, Any]], session_health["aggregation_due"]):
            recommended_checks.append(
                "Inspect aggregation pressure with memory_check_aggregation_triggers."
            )
        if bool(session_health["periodic_review_due"]):
            recommended_checks.append(
                "Prepare the protected periodic review workflow with memory_prepare_periodic_review."
            )
        if pending_review_items:
            recommended_checks.append(
                "Review pending queue items before any protected cleanup writes."
            )
        if active_plans:
            lead_project = active_plans[0].get("project_id")
            lead_plan = active_plans[0].get("plan_id")
            recommended_checks.append(
                "Load project resume context with "
                f'memory_context_project(project="{lead_project}") for active plan {lead_plan}.'
            )
        if not recommended_checks:
            recommended_checks.append(
                "No urgent maintenance signals detected; continue the current plan or inspect capabilities."
            )

        payload = {
            "capabilities": capabilities_summary,
            "session_health": session_health,
            "active_plans": active_plans,
            "pending_review_items": pending_review_items,
            "recommended_checks": recommended_checks,
            "response_budget": {
                "active_plans": active_plan_budget,
                "review_items": review_budget,
            },
        }
        return _dump_payload(payload)

    # ------------------------------------------------------------------
    # memory_prepare_unverified_review

    # ------------------------------------------------------------------
    @mcp.tool(
        name="memory_prepare_unverified_review",
        annotations=_tool_annotations(
            title="Prepare Unverified Review",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def memory_prepare_unverified_review(
        folder_path: str = "memory/knowledge/_unverified",
        max_files: int = 12,
        max_extract_words: int = 60,
        paths_only: bool = False,
    ) -> str:
        """Return a compact unverified-review bundle with bounded file extracts."""
        from ...errors import ValidationError

        if max_files < 1 and not paths_only:
            raise ValidationError("max_files must be >= 1")

        review_payload = _build_review_unverified_payload(
            get_root(), folder_path, max_extract_words, True
        )
        candidates: list[dict[str, Any]] = []
        for group_name, entries in cast(
            dict[str, list[dict[str, Any]]], review_payload["groups"]
        ).items():
            for entry in entries:
                candidates.append(
                    {
                        "group": group_name,
                        "path": entry.get("path"),
                        "trust": entry.get("trust"),
                        "days_old": entry.get("days_old"),
                        "expired": entry.get("expired"),
                        "source": entry.get("source"),
                        "extract": entry.get("extract"),
                    }
                )
        candidates.sort(
            key=lambda item: (
                0 if item.get("expired") else 1,
                -(cast(int | None, item.get("days_old")) or -1),
                cast(str, item.get("path") or ""),
            )
        )
        if paths_only:
            all_paths = [cast(str, item["path"]) for item in candidates if item.get("path")]
            payload = {
                "folder_path": folder_path,
                "trust_counts": review_payload["trust_counts"],
                "expired_count": review_payload["expired_count"],
                "paths_only": True,
                "all_paths": all_paths,
                "recommended_operations": {
                    "single_file": "memory_promote_knowledge",
                    "batch": "memory_promote_knowledge_batch",
                    "subtree": "memory_promote_knowledge_subtree",
                },
                "response_budget": {
                    "paths": {
                        "returned": len(all_paths),
                        "total": len(all_paths),
                        "truncated": False,
                    },
                },
            }
            return _dump_payload(payload)
        selected_files, file_budget = _truncate_items(candidates, max_files)
        payload = {
            "folder_path": folder_path,
            "trust_counts": review_payload["trust_counts"],
            "expired_count": review_payload["expired_count"],
            "paths_only": False,
            "selected_files": selected_files,
            "recommended_operations": {
                "single_file": "memory_promote_knowledge",
                "batch": "memory_promote_knowledge_batch",
                "subtree": "memory_promote_knowledge_subtree",
            },
            "response_budget": {
                "files": file_budget,
            },
        }
        return _dump_payload(payload)

    # ------------------------------------------------------------------
    # memory_prepare_promotion_batch

    # ------------------------------------------------------------------
    @mcp.tool(
        name="memory_prepare_promotion_batch",
        annotations=_tool_annotations(
            title="Prepare Knowledge Promotion Batch",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def memory_prepare_promotion_batch(
        folder_path: str = "memory/knowledge/_unverified",
        max_files: int = 12,
    ) -> str:
        """Return compact promotion candidates with default target paths and operation hints."""
        from ...errors import ValidationError

        if max_files < 1:
            raise ValidationError("max_files must be >= 1")

        root = get_root()
        low_threshold, _ = _parse_trust_thresholds(root)
        unverified = _scan_unverified_content(root, low_threshold)
        normalized_folder = _normalize_repo_relative_path(folder_path)
        abs_folder = root / normalized_folder
        path_is_dir = abs_folder.exists() and abs_folder.is_dir()
        has_nested_subdirectories = path_is_dir and any(
            child.is_dir() for child in abs_folder.iterdir() if child.name != "SUMMARY.md"
        )
        candidates = [
            {
                "source_path": item["path"],
                "target_path": cast(str, item["path"]).replace(
                    "memory/knowledge/_unverified/", "memory/knowledge/", 1
                ),
                "trust": item.get("trust"),
                "days_old": item.get("age_days"),
                "source": item.get("source"),
            }
            for item in cast(list[dict[str, Any]], unverified["files"])
            if cast(str, item["path"]).startswith(normalized_folder.rstrip("/") + "/")
            or cast(str, item["path"]) == normalized_folder
        ]
        candidates.sort(
            key=lambda item: (
                -(cast(int | None, item.get("days_old")) or -1),
                cast(str, item["source_path"]),
            )
        )
        selected_candidates, candidate_budget = _truncate_items(candidates, max_files)
        if path_is_dir and has_nested_subdirectories:
            suggested_operation = "memory_promote_knowledge_subtree"
        elif len(candidates) <= 1:
            suggested_operation = "memory_promote_knowledge"
        else:
            suggested_operation = "memory_promote_knowledge_batch"
        suggested_target_folder = (
            normalized_folder.replace("memory/knowledge/_unverified/", "memory/knowledge/", 1)
            if normalized_folder.startswith("memory/knowledge/_unverified/")
            else None
        )
        payload = {
            "folder_path": folder_path,
            "candidate_count": len(candidates),
            "suggested_operation": suggested_operation,
            "suggested_target_folder": suggested_target_folder,
            "folder_shape": {
                "is_directory": path_is_dir,
                "has_nested_subdirectories": has_nested_subdirectories,
            },
            "workflow_hint": _route_workflow_hint(suggested_operation, normalized_folder, root),
            "selected_candidates": selected_candidates,
            "response_budget": {
                "candidates": candidate_budget,
            },
        }
        return _dump_payload(payload)

    # ------------------------------------------------------------------
    # memory_prepare_periodic_review

    # ------------------------------------------------------------------
    @mcp.tool(
        name="memory_prepare_periodic_review",
        annotations=_tool_annotations(
            title="Prepare Periodic Review",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def memory_prepare_periodic_review(
        max_queue_items: int = 8,
        max_deferred_targets: int = 8,
    ) -> str:
        """Return a compact periodic-review preparation bundle with bounded high-signal outputs."""
        from ...errors import ValidationError

        if max_queue_items < 1 or max_deferred_targets < 1:
            raise ValidationError("max_queue_items and max_deferred_targets must be >= 1")

        session_health = _build_session_health_payload()
        review_payload = _build_periodic_review_payload()
        security_candidates, security_budget = _truncate_items(
            cast(
                list[dict[str, Any]],
                review_payload["ordered_checks"]["security_flags"]["generated_candidates"],
            ),
            max_queue_items,
        )
        deferred_targets = [
            {"path": path}
            for path in cast(
                list[str], review_payload["proposed_outputs"]["deferred_write_targets"]
            )
        ]
        deferred_targets, target_budget = _truncate_items(deferred_targets, max_deferred_targets)
        overdue_files = cast(
            list[dict[str, Any]],
            review_payload["ordered_checks"]["unverified_content"]["overdue_files"],
        )
        payload = {
            "review_due": review_payload["review_due"],
            "session_health": session_health,
            "high_signal": {
                "pending_security_count": review_payload["ordered_checks"]["security_flags"][
                    "pending_count"
                ],
                "generated_security_candidates": security_candidates,
                "overdue_unverified_count": review_payload["ordered_checks"]["unverified_content"][
                    "overdue_count"
                ],
                "overdue_unverified_files": overdue_files[:max_queue_items],
                "conflict_count": review_payload["ordered_checks"]["conflict_resolution"]["count"],
            },
            "deferred_write_targets": deferred_targets,
            "recommended_operations": {
                "write": "memory_record_periodic_review",
                "queue_resolution": "memory_resolve_review_item",
            },
            "response_budget": {
                "security_candidates": security_budget,
                "deferred_targets": target_budget,
            },
        }
        return _dump_payload(payload)

    # ------------------------------------------------------------------
    # memory_extract_file

    # ------------------------------------------------------------------
    @mcp.tool(
        name="memory_audit_trust",
        annotations=_tool_annotations(
            title="Trust Decay Audit",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def memory_audit_trust(
        include_categories: str = "",
        warn_pct: float = 0.75,
    ) -> str:
        """Audit trust decay across the memory repository.

                Checks all files with trust frontmatter against the decay thresholds
                from the live router file, and treats files without frontmatter as
                implicit medium-trust when a git-backed effective date is available:
          - low-trust files:    overdue at 120 days, flagged at 90 days, approaching at 75%
          - medium-trust files: overdue at 180 days, flagged at 150 days, approaching at 75%
                    - frontmatterless tracked files: audited as implicit medium-trust
                    - frontmatterless untracked files: reported as unevaluable

        Does not modify any files — pure read operation.

        Args:
            include_categories: Comma-separated list of top-level folders to scan
                                 (e.g. 'knowledge,plans'). Empty = scan all.
            warn_pct: Fraction of the threshold that should surface in the
                      approaching bucket before the 30-day upcoming window.

        Returns:
            JSON with overdue/upcoming/approaching buckets plus unevaluable files,
            checked_at, and files_checked count.
        """
        from ...errors import ValidationError
        from ...frontmatter_utils import read_with_frontmatter

        if warn_pct <= 0 or warn_pct >= 1:
            raise ValidationError("warn_pct must satisfy 0 < warn_pct < 1")

        root = get_root()
        low_threshold, medium_threshold = _parse_trust_thresholds(root)
        low_warn = low_threshold - 30
        medium_warn = medium_threshold - 30

        categories = [c.strip() for c in include_categories.split(",") if c.strip()]
        if not categories:
            categories = ["knowledge", "plans", "identity", "skills"]

        today = date.today()
        overdue_low = []
        overdue_medium = []
        approaching = []
        upcoming_low = []
        upcoming_medium = []
        expired_files = []
        superseded_files = []
        unevaluable = []
        files_checked = 0
        repo = get_repo()
        host_repo = _get_host_git_repo(root, repo)
        untracked_files = set(repo.diff_status()["untracked"])

        for cat in categories:
            for category_prefix in _resolve_category_prefixes(cat):
                cat_path = root / category_prefix
                if not cat_path.is_dir():
                    continue
                for md_file in cat_path.rglob("*.md"):
                    if not md_file.is_file():
                        continue
                    try:
                        fm_dict, _ = read_with_frontmatter(md_file)
                    except Exception:
                        continue

                    rel = md_file.relative_to(root).as_posix()
                    trust = fm_dict.get("trust")
                    implicit_medium = False
                    if trust in ("low", "medium", "high"):
                        pass
                    elif fm_dict:
                        continue
                    else:
                        trust = "medium"
                        implicit_medium = True

                    files_checked += 1

                    # Check explicit supersession
                    superseded_by = fm_dict.get("superseded_by")
                    if superseded_by and isinstance(superseded_by, str):
                        superseded_files.append(
                            {
                                "path": rel,
                                "trust": trust,
                                "superseded_by": superseded_by,
                                "successor_exists": (root / superseded_by).is_file(),
                            }
                        )
                        continue  # Skip decay checks for superseded files

                    # Check explicit expiration
                    expires_date = _parse_expires_date(fm_dict)
                    if expires_date is not None and today > expires_date:
                        expired_files.append(
                            {
                                "path": rel,
                                "trust": trust,
                                "expires": str(expires_date),
                                "days_past_expiry": (today - expires_date).days,
                                "action_required": "archive" if trust == "low" else "review",
                            }
                        )
                        continue  # Explicit expiration takes precedence over decay

                    eff_date = _effective_date(fm_dict)
                    if eff_date is None and implicit_medium:
                        if rel in untracked_files:
                            unevaluable.append(
                                {
                                    "path": rel,
                                    "trust": trust,
                                    "reason": "untracked_without_frontmatter",
                                    "implicit_trust": True,
                                }
                            )
                            continue
                        eff_date = repo.first_tracked_author_date(rel)
                    if eff_date is None:
                        if implicit_medium:
                            unevaluable.append(
                                {
                                    "path": rel,
                                    "trust": trust,
                                    "reason": "missing_effective_date",
                                    "implicit_trust": True,
                                }
                            )
                        continue

                    days = (today - eff_date).days

                    entry = {
                        "path": rel,
                        "trust": trust,
                        "effective_date": str(eff_date),
                        "days_since_verified": days,
                    }
                    if implicit_medium:
                        entry["implicit_trust"] = True

                    freshness_report = None
                    freshness_status = "unknown"
                    if host_repo is not None:
                        freshness_report = _build_knowledge_freshness_report(
                            root, repo, rel, md_file
                        )
                        freshness_status = str(freshness_report["status"])
                        for key in (
                            "current_head",
                            "verified_against_commit",
                            "host_changes_since",
                            "source_files",
                        ):
                            if freshness_report.get(key) is not None:
                                entry[key] = freshness_report[key]
                        entry["freshness_status"] = freshness_status

                    if trust == "low":
                        threshold = low_threshold
                        warn = low_warn
                        approaching_warn = threshold * warn_pct
                        entry["days_until_threshold"] = max(0, threshold - days)
                        if days >= threshold:
                            if freshness_status == "fresh":
                                entry["action_required"] = "review"
                                upcoming_low.append(entry)
                            else:
                                entry["action_required"] = "archive"
                                overdue_low.append(entry)
                        elif days >= warn or freshness_status == "stale":
                            entry["action_required"] = "review"
                            upcoming_low.append(entry)
                        elif days >= approaching_warn:
                            entry["action_required"] = "review"
                            approaching.append(entry)
                    elif trust == "medium":
                        threshold = medium_threshold
                        warn = medium_warn
                        approaching_warn = threshold * warn_pct
                        entry["days_until_threshold"] = max(0, threshold - days)
                        if days >= threshold:
                            if freshness_status == "fresh":
                                entry["action_required"] = "review"
                                upcoming_medium.append(entry)
                            else:
                                entry["action_required"] = "flag"
                                overdue_medium.append(entry)
                        elif days >= warn or freshness_status == "stale":
                            entry["action_required"] = (
                                "reverify" if freshness_status == "stale" else "review"
                            )
                            upcoming_medium.append(entry)
                        elif days >= approaching_warn:
                            entry["action_required"] = "review"
                            approaching.append(entry)
                    else:
                        # High-trust files are tracked for `files_checked` but are
                        # intentionally excluded from low/medium decay buckets.
                        continue

        result = {
            "expired": expired_files,
            "superseded": superseded_files,
            "overdue_low": overdue_low,
            "overdue_medium": overdue_medium,
            "approaching": approaching,
            "upcoming_low": upcoming_low,
            "upcoming_medium": upcoming_medium,
            "unevaluable": unevaluable,
            "checked_at": str(today),
            "files_checked": files_checked,
            "thresholds": {
                "low_days": low_threshold,
                "medium_days": medium_threshold,
                "warn_pct": warn_pct,
            },
        }
        return _dump_payload(result)

    # ------------------------------------------------------------------
    # memory_validate

    # ------------------------------------------------------------------
    @mcp.tool(
        name="memory_validate",
        annotations=_tool_annotations(
            title="Validate Memory Repository",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def memory_validate() -> str:
        """Run the structural validator against the memory repository.

        Checks frontmatter keys, ACCESS.jsonl structure, and governance
        consistency. Returns a validation report.

        Returns:
            Validation report with errors and warnings, or a clean-pass message.
        """
        root = get_root()
        repo = get_repo()
        repo_root = repo.root
        validator_path = (
            _resolve_humans_root(root) / "tooling" / "scripts" / "validate_memory_repo.py"
        )
        if not validator_path.exists():
            return "Validator not found at HUMANS/tooling/scripts/validate_memory_repo.py"
        try:
            result = subprocess.run(
                [sys.executable, str(validator_path), str(repo_root)],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                timeout=30,
                stdin=subprocess.DEVNULL,
            )
            output = result.stdout + result.stderr
            return output.strip() or "Validation complete (no output)."
        except subprocess.TimeoutExpired:
            return "Error: Validator timed out after 30 seconds."
        except Exception as e:
            return f"Error running validator: {e}"

    # ------------------------------------------------------------------
    # memory_get_maturity_signals

    # ------------------------------------------------------------------
    @mcp.tool(
        name="memory_get_maturity_signals",
        annotations=_tool_annotations(
            title="Maturity Signals",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def memory_get_maturity_signals() -> str:
        """Compute all six maturity signals for the periodic review.

        These signals drive the maturity stage assessment in
        governance/system-maturity.md and determine whether to retain the current
        parameter set or transition to the next stage. All values are derived
        from hot ACCESS.jsonl files and content-file frontmatter; archive
        segments and ACCESS_SCANS sidecars are excluded, and no network calls
        are made.

        Returns:
            JSON with the following keys:
              access_scope            (str)   Always "hot_only"; archive
                                              segments and ACCESS_SCANS sidecars
                                              are excluded from these metrics
              total_sessions          (int)   Distinct session_id values across
                                              hot ACCESS.jsonl files
              session_id_coverage_pct (float) % of hot ACCESS entries carrying
                                              canonical session_id values
              access_density          (int)   Total ACCESS.jsonl entries across
                                              hot logs across all folders
              file_coverage_pct       (float) % of content files accessed at
                                              least once (0–100)
              files_accessed          (int)   Count of distinct files in
                                              ACCESS.jsonl entries
              total_content_files     (int)   Total .md files in memory/knowledge,
                                              memory/working/projects,
                                              memory/users, memory/skills
              confirmation_ratio      (float) trust:high files / total content
                                              files (0.0–1.0)
              high_trust_files        (int)   Count of trust:high content files
              identity_stability      (int|null)
                                              Sessions since last change to
                                              memory/users/profile.md; null if the
                                              file has no tracked commit history
              write_sessions         (int)   Distinct session_id values with at
                                              least one non-read ACCESS entry
              access_density_by_task_id (dict) ACCESS entry counts grouped by
                                              task_id bucket; entries without
                                              task_id are grouped under
                                              "unspecified"
              proxy_sessions         (int)   Optional fallback estimate based on
                                              distinct (date, task_id or task)
                                              pairs when session_id coverage is low
              proxy_session_note     (str)   Optional warning describing when
                                              proxy_sessions was emitted
              mean_helpfulness        (float) Mean helpfulness score across all
                                              ACCESS entries that carry the field
              helpfulness_sample_size (int)   Number of entries with a
                                              helpfulness score
              computed_at             (str)   ISO date of computation
        """
        root = get_root()
        repo = get_repo()
        signals = _compute_maturity_signals(root, repo)
        return _dump_payload(signals)

    # ------------------------------------------------------------------
    # MCP-native resources

    return {
        "memory_session_health_check": memory_session_health_check,
        "memory_check_aggregation_triggers": memory_check_aggregation_triggers,
        "memory_aggregate_access": memory_aggregate_access,
        "memory_run_periodic_review": memory_run_periodic_review,
        "memory_session_bootstrap": memory_session_bootstrap,
        "memory_prepare_unverified_review": memory_prepare_unverified_review,
        "memory_prepare_promotion_batch": memory_prepare_promotion_batch,
        "memory_prepare_periodic_review": memory_prepare_periodic_review,
        "memory_audit_trust": memory_audit_trust,
        "memory_validate": memory_validate,
        "memory_get_maturity_signals": memory_get_maturity_signals,
        "_build_session_health_payload": _build_session_health_payload,
    }
