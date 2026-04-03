"""Shared input schema registry for selected MCP tools."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .errors import ValidationError
from .plan_approvals import APPROVAL_RESOLUTIONS
from .plan_utils import (
    CHANGE_ACTION_ALIASES,
    CHANGE_ACTIONS,
    COST_TIERS,
    PLAN_OUTCOMES,
    POSTCONDITION_TYPE_ALIASES,
    POSTCONDITION_TYPES,
    SOURCE_TYPE_ALIASES,
    SOURCE_TYPES,
    TRACE_SPAN_TYPES,
    TRACE_STATUSES,
    VERIFICATION_RESULT_STATUSES,
    _PLAN_SLUG_PATTERN,
    _SESSION_ID_PATTERN,
    plan_create_input_schema,
    verification_results_item_schema,
)

ACCESS_MODES = frozenset({"read", "write", "update", "create"})
FRONTMATTER_BULK_MAX_UPDATES = 100
KNOWLEDGE_BATCH_TRUST_LEVELS = frozenset({"medium", "high"})
REVIEW_PRIORITIES = frozenset({"normal", "urgent"})
REVIEW_VERDICTS = frozenset({"approve", "reject", "defer"})
SKILL_CREATE_TRUST_LEVELS = frozenset({"high", "medium", "low"})
UPDATE_MODES = frozenset({"upsert", "append", "replace"})
PERIODIC_REVIEW_STAGES = frozenset({"Exploration", "Calibration", "Consolidation"})

ToolSchemaBuilder = Callable[[], dict[str, Any]]


def _base_schema(
    *,
    tool_name: str,
    title: str,
    properties: dict[str, Any],
    required: list[str] | None = None,
    notes: list[str] | None = None,
    all_of: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    schema: dict[str, Any] = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "schema_version": 1,
        "tool_name": tool_name,
        "title": title,
        "type": "object",
        "additionalProperties": False,
        "properties": properties,
    }
    if required:
        schema["required"] = list(required)
    if notes:
        schema["x-notes"] = list(notes)
    if all_of:
        schema["allOf"] = list(all_of)
    return schema


def _session_id_string_schema(
    *,
    description: str,
    allow_empty: bool = False,
    nullable: bool = False,
) -> dict[str, Any]:
    pattern_schema: dict[str, Any] = {
        "type": "string",
        "pattern": _SESSION_ID_PATTERN,
        "description": description,
    }
    if allow_empty and nullable:
        return {
            "oneOf": [
                pattern_schema,
                {"type": "string", "const": ""},
                {"type": "null"},
            ]
        }
    if allow_empty:
        return {
            "oneOf": [
                pattern_schema,
                {"type": "string", "const": ""},
            ]
        }
    if nullable:
        return {
            "oneOf": [
                pattern_schema,
                {"type": "null"},
            ]
        }
    return pattern_schema


def _verification_results_item_schema() -> dict[str, Any]:
    return verification_results_item_schema()


def _plan_review_input_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["purpose_assessment"],
        "description": (
            "Optional final plan review written when the last phase completes. "
            "completed/completed_session are filled automatically by the tool."
        ),
        "properties": {
            "outcome": {
                "type": "string",
                "enum": sorted(PLAN_OUTCOMES),
                "default": "completed",
                "description": "Overall plan outcome for the stored review.",
            },
            "purpose_assessment": {
                "type": "string",
                "minLength": 1,
                "description": "Narrative assessment of whether the plan met its purpose.",
            },
            "unresolved": {
                "type": "array",
                "description": "Optional follow-up questions left open at completion time.",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["question", "note"],
                    "properties": {
                        "question": {
                            "type": "string",
                            "minLength": 1,
                        },
                        "note": {
                            "type": "string",
                            "minLength": 1,
                        },
                    },
                },
            },
            "follow_up": {
                "oneOf": [
                    {
                        "type": "string",
                        "pattern": _PLAN_SLUG_PATTERN,
                        "description": "Optional follow-up plan id in kebab-case.",
                    },
                    {"type": "null"},
                ]
            },
        },
    }


def access_entry_input_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": True,
        "required": ["file", "task", "helpfulness", "note"],
        "description": "Single ACCESS entry payload accepted by batch access logging surfaces.",
        "properties": {
            "file": {
                "type": "string",
                "description": "Repo-relative path under an access-tracked namespace.",
            },
            "task": {
                "type": "string",
                "minLength": 1,
                "description": "Short description of the retrieval task.",
            },
            "helpfulness": {
                "type": "number",
                "minimum": 0.0,
                "maximum": 1.0,
                "description": "Observed retrieval usefulness score.",
            },
            "note": {
                "type": "string",
                "minLength": 1,
                "description": "Short freeform justification for the score.",
            },
            "category": {
                "type": "string",
                "description": (
                    "Optional controlled-vocabulary category. Must match governance/task-categories.md when provided."
                ),
            },
            "mode": {
                "type": "string",
                "enum": sorted(ACCESS_MODES),
                "description": "Optional access mode classification.",
            },
            "task_id": {
                "type": "string",
                "description": (
                    "Optional controlled task id. Must match access_logging.task_ids in HUMANS/tooling/agent-memory-capabilities.toml when provided."
                ),
            },
            "estimator": {
                "type": "string",
                "pattern": _PLAN_SLUG_PATTERN,
                "description": "Optional slug naming the helpfulness estimator used.",
            },
            "min_helpfulness": {
                "type": "number",
                "minimum": 0.0,
                "maximum": 1.0,
                "description": "Optional routing threshold; entries below this are written to ACCESS_SCANS.jsonl.",
            },
        },
    }


def plan_execute_input_schema() -> dict[str, Any]:
    return _base_schema(
        tool_name="memory_plan_execute",
        title="memory_plan_execute input schema",
        required=["plan_id"],
        all_of=[
            {
                "if": {"properties": {"action": {"enum": ["start", "complete", "record_failure"]}}},
                "then": {"required": ["session_id"]},
            },
            {
                "if": {"properties": {"action": {"const": "complete"}}},
                "then": {"required": ["commit_sha"]},
            },
            {
                "if": {"properties": {"action": {"const": "record_failure"}}},
                "then": {"required": ["reason"]},
            },
        ],
        notes=[
            "action='inspect' returns the live phase payload without mutating plan state.",
            "review is only consumed when the final phase completes; completed/completed_session are filled automatically.",
            "verification_results is opaque caller-supplied context on record_failure and tool-generated context on verify flows.",
        ],
        properties={
            "plan_id": {
                "type": "string",
                "pattern": _PLAN_SLUG_PATTERN,
                "description": "Plan id in kebab-case.",
            },
            "project_id": {
                "oneOf": [
                    {"type": "string", "pattern": _PLAN_SLUG_PATTERN},
                    {"type": "null"},
                ],
                "description": "Optional project id when plan lookup needs disambiguation.",
            },
            "phase_id": {
                "oneOf": [
                    {"type": "string", "pattern": _PLAN_SLUG_PATTERN},
                    {"type": "null"},
                ],
                "description": "Optional phase id. When omitted, the next actionable phase is resolved automatically.",
            },
            "action": {
                "type": "string",
                "enum": ["inspect", "start", "complete", "record_failure"],
                "default": "inspect",
                "description": "Requested phase action.",
            },
            "session_id": _session_id_string_schema(
                description="Canonical session id for stateful actions.",
                nullable=True,
            ),
            "commit_sha": {
                "oneOf": [
                    {"type": "string", "minLength": 1},
                    {"type": "null"},
                ],
                "description": "Implementation commit SHA. Required when action='complete'.",
            },
            "review": {
                "oneOf": [
                    _plan_review_input_schema(),
                    {"type": "null"},
                ]
            },
            "verify": {
                "type": "boolean",
                "default": False,
                "description": "When true on action='complete', evaluate postconditions before mutating state.",
            },
            "reason": {
                "oneOf": [
                    {"type": "string", "minLength": 1},
                    {"type": "null"},
                ],
                "description": "Freeform failure reason. Required when action='record_failure'.",
            },
            "verification_results": {
                "oneOf": [
                    {
                        "type": "array",
                        "items": _verification_results_item_schema(),
                    },
                    {"type": "null"},
                ],
                "description": "Optional verification context attached to recorded failures or returned by verify flows.",
            },
            "preview": {
                "type": "boolean",
                "default": False,
                "description": "When true, returns the governed preview envelope instead of writing.",
            },
        },
    )


def log_access_batch_input_schema() -> dict[str, Any]:
    return _base_schema(
        tool_name="memory_log_access_batch",
        title="memory_log_access_batch input schema",
        required=["access_entries"],
        notes=[
            "Each access entry is validated independently; batch errors are reported together.",
            "session_id defaults to memory/activity/CURRENT_SESSION when omitted and the sentinel exists.",
        ],
        properties={
            "access_entries": {
                "type": "array",
                "minItems": 1,
                "items": access_entry_input_schema(),
                "description": "Non-empty list of ACCESS entry objects.",
            },
            "session_id": _session_id_string_schema(
                description="Optional canonical session id applied to all entries in the batch.",
                nullable=True,
            ),
            "min_helpfulness": {
                "oneOf": [
                    {
                        "type": "number",
                        "minimum": 0.0,
                        "maximum": 1.0,
                    },
                    {"type": "null"},
                ],
                "description": "Optional batch-wide routing threshold for ACCESS_SCANS.jsonl.",
            },
        },
    )


def record_session_input_schema() -> dict[str, Any]:
    return _base_schema(
        tool_name="memory_record_session",
        title="memory_record_session input schema",
        required=["session_id", "summary"],
        notes=[
            "Replays are idempotent only when summary, reflection, and ACCESS entries match the already-recorded session content.",
            "access_entries uses the same payload shape as memory_log_access_batch.",
        ],
        properties={
            "session_id": _session_id_string_schema(
                description="Canonical memory/activity/YYYY/MM/DD/chat-NNN id.",
            ),
            "summary": {
                "type": "string",
                "description": "Markdown session summary body written to SUMMARY.md.",
            },
            "reflection": {
                "oneOf": [
                    {"type": "string"},
                    {"type": "null"},
                ],
                "description": "Optional session reflection body written to reflection.md.",
            },
            "key_topics": {
                "type": "string",
                "default": "",
                "description": "Comma-separated topics included in the session summary frontmatter.",
            },
            "access_entries": {
                "oneOf": [
                    {
                        "type": "array",
                        "items": access_entry_input_schema(),
                    },
                    {"type": "null"},
                ],
                "description": "Optional ACCESS entries recorded atomically with the session summary.",
            },
        },
    )


def promote_knowledge_batch_input_schema() -> dict[str, Any]:
    return _base_schema(
        tool_name="memory_promote_knowledge_batch",
        title="memory_promote_knowledge_batch input schema",
        required=["source_paths"],
        notes=[
            "source_paths accepts either a JSON array of repo-relative file paths or a folder path to expand into a flat batch.",
            "target_folder is optional; when omitted, the destination topic folder is inferred from each source path.",
        ],
        properties={
            "source_paths": {
                "type": "string",
                "description": "JSON array of repo-relative paths or a folder path to expand.",
            },
            "trust_level": {
                "type": "string",
                "enum": sorted(KNOWLEDGE_BATCH_TRUST_LEVELS),
                "default": "medium",
                "description": "Trust level assigned to the promoted files.",
            },
            "target_folder": {
                "oneOf": [
                    {"type": "string"},
                    {"type": "null"},
                ],
                "description": "Optional destination topic folder under memory/knowledge/.",
            },
        },
    )


def promote_knowledge_input_schema() -> dict[str, Any]:
    return _base_schema(
        tool_name="memory_promote_knowledge",
        title="memory_promote_knowledge input schema",
        required=["source_path"],
        notes=[
            "target_path is optional; when omitted, the runtime infers the verified destination by replacing memory/knowledge/_unverified/ with memory/knowledge/.",
            "summary_entry is optional; when provided, missing target sections in memory/knowledge/SUMMARY.md may be auto-created.",
        ],
        properties={
            "source_path": {
                "type": "string",
                "description": "Repo-relative file path under memory/knowledge/_unverified/.",
            },
            "trust_level": {
                "type": "string",
                "enum": sorted(KNOWLEDGE_BATCH_TRUST_LEVELS),
                "default": "high",
                "description": "Trust level assigned to the promoted file.",
            },
            "target_path": {
                "oneOf": [
                    {"type": "string"},
                    {"type": "null"},
                ],
                "description": "Optional explicit verified destination path under memory/knowledge/.",
            },
            "summary_entry": {
                "oneOf": [
                    {"type": "string"},
                    {"type": "null"},
                ],
                "description": "Optional markdown summary entry inserted into memory/knowledge/SUMMARY.md.",
            },
            "version_token": {
                "oneOf": [
                    {"type": "string"},
                    {"type": "null"},
                ],
                "description": "Optional optimistic-lock token returned by memory_read_file for the source file.",
            },
            "preview": {
                "type": "boolean",
                "default": False,
                "description": "When true, return the governed preview envelope instead of moving the file.",
            },
        },
    )


def promote_knowledge_subtree_input_schema() -> dict[str, Any]:
    return _base_schema(
        tool_name="memory_promote_knowledge_subtree",
        title="memory_promote_knowledge_subtree input schema",
        required=["source_folder", "dest_folder"],
        notes=[
            "Nested markdown paths are preserved relative to source_folder when constructing destination targets.",
            "dry_run returns planned_moves without writing or staging anything.",
        ],
        properties={
            "source_folder": {
                "type": "string",
                "description": "Repo-relative folder under memory/knowledge/_unverified/ whose markdown subtree should be promoted.",
            },
            "dest_folder": {
                "type": "string",
                "description": "Destination folder under memory/knowledge/ where the subtree should be recreated.",
            },
            "trust_level": {
                "type": "string",
                "enum": sorted(KNOWLEDGE_BATCH_TRUST_LEVELS),
                "default": "medium",
                "description": "Trust level assigned to every promoted file in the subtree.",
            },
            "reason": {
                "type": "string",
                "default": "",
                "description": "Optional freeform reason appended to the commit message.",
            },
            "dry_run": {
                "type": "boolean",
                "default": False,
                "description": "When true, return planned_moves and counts without mutating files.",
            },
        },
    )


def reorganize_path_input_schema() -> dict[str, Any]:
    return _base_schema(
        tool_name="memory_reorganize_path",
        title="memory_reorganize_path input schema",
        required=["source", "dest"],
        notes=[
            "dry_run defaults to true and returns the governed preview envelope without mutating any files.",
            "Apply mode aborts when preview warnings indicate destination conflicts.",
            "Plain body-path mentions may be previewed as warnings even when they are not rewritten automatically.",
        ],
        properties={
            "source": {
                "type": "string",
                "description": "Verified knowledge file or subtree path to move. Archive paths are also accepted.",
            },
            "dest": {
                "type": "string",
                "description": "Destination knowledge or archive path for the moved file or subtree.",
            },
            "dry_run": {
                "type": "boolean",
                "default": True,
                "description": "When true, preview the reorganization plan; when false, apply the move and reference rewrites atomically.",
            },
        },
    )


def update_names_index_input_schema() -> dict[str, Any]:
    return _base_schema(
        tool_name="memory_update_names_index",
        title="memory_update_names_index input schema",
        notes=[
            "path defaults to memory/knowledge and must resolve to memory/knowledge or one of its subfolders.",
            "The output path is always <path>/NAMES.md.",
            "preview returns the governed preview envelope plus generated content_preview.",
        ],
        properties={
            "path": {
                "type": "string",
                "default": "memory/knowledge",
                "description": "Knowledge subtree whose names index should be refreshed.",
            },
            "version_token": {
                "oneOf": [
                    {"type": "string"},
                    {"type": "null"},
                ],
                "description": "Optional optimistic-lock token checked when the destination NAMES.md already exists.",
            },
            "preview": {
                "type": "boolean",
                "default": False,
                "description": "When true, return the governed preview envelope and generated content_preview instead of writing.",
            },
        },
    )


def demote_knowledge_input_schema() -> dict[str, Any]:
    return _base_schema(
        tool_name="memory_demote_knowledge",
        title="memory_demote_knowledge input schema",
        required=["source_path"],
        notes=[
            "source_path must point to a verified file under memory/knowledge/ and cannot already live under memory/knowledge/_unverified/.",
            "The runtime infers the destination by moving the file under memory/knowledge/_unverified/ and resets trust to low.",
            "preview returns the governed preview envelope without mutating files or summaries.",
        ],
        properties={
            "source_path": {
                "type": "string",
                "description": "Repo-relative verified knowledge file path under memory/knowledge/.",
            },
            "reason": {
                "oneOf": [
                    {"type": "string"},
                    {"type": "null"},
                ],
                "description": "Optional freeform reason appended to the commit message.",
            },
            "version_token": {
                "oneOf": [
                    {"type": "string"},
                    {"type": "null"},
                ],
                "description": "Optional optimistic-lock token returned by memory_read_file for the source file.",
            },
            "preview": {
                "type": "boolean",
                "default": False,
                "description": "When true, return the governed preview envelope instead of demoting the file.",
            },
        },
    )


def archive_knowledge_input_schema() -> dict[str, Any]:
    return _base_schema(
        tool_name="memory_archive_knowledge",
        title="memory_archive_knowledge input schema",
        required=["source_path"],
        notes=[
            "source_path may refer to verified or _unverified knowledge; the runtime preserves the path relative to memory/knowledge/ when moving under memory/knowledge/_archive/.",
            "Archival removes the file from the active or unverified summary when that summary exists.",
            "preview returns the governed preview envelope without mutating files or summaries.",
        ],
        properties={
            "source_path": {
                "type": "string",
                "description": "Repo-relative knowledge file path under memory/knowledge/ or memory/knowledge/_unverified/.",
            },
            "reason": {
                "oneOf": [
                    {"type": "string"},
                    {"type": "null"},
                ],
                "description": "Optional freeform reason appended to the commit message.",
            },
            "version_token": {
                "oneOf": [
                    {"type": "string"},
                    {"type": "null"},
                ],
                "description": "Optional optimistic-lock token returned by memory_read_file for the source file.",
            },
            "preview": {
                "type": "boolean",
                "default": False,
                "description": "When true, return the governed preview envelope instead of archiving the file.",
            },
        },
    )


def add_knowledge_file_input_schema() -> dict[str, Any]:
    return _base_schema(
        tool_name="memory_add_knowledge_file",
        title="memory_add_knowledge_file input schema",
        required=["path", "content", "source", "session_id"],
        notes=[
            "path must be under memory/knowledge/_unverified/ and existing files are rejected.",
            "trust is fixed to low for new unverified knowledge files.",
            "summary_entry defaults to the first H1 heading or the filename stem when omitted.",
            "expires, when provided, must be an ISO date in YYYY-MM-DD format.",
        ],
        properties={
            "path": {
                "type": "string",
                "description": "Repo-relative destination path under memory/knowledge/_unverified/.",
            },
            "content": {
                "type": "string",
                "description": "Markdown body written after generated frontmatter.",
            },
            "source": {
                "type": "string",
                "description": "Provenance string stored in frontmatter.",
            },
            "session_id": _session_id_string_schema(
                description="Canonical memory/activity/YYYY/MM/DD/chat-NNN id.",
            ),
            "trust": {
                "type": "string",
                "enum": ["low"],
                "default": "low",
                "description": "Must remain low for new unverified knowledge.",
            },
            "summary_entry": {
                "oneOf": [
                    {"type": "string"},
                    {"type": "null"},
                ],
                "description": "Optional summary text to insert into memory/knowledge/_unverified/SUMMARY.md.",
            },
            "expires": {
                "oneOf": [
                    {
                        "type": "string",
                        "format": "date",
                    },
                    {"type": "null"},
                ],
                "description": "Optional ISO date (YYYY-MM-DD) recorded in frontmatter for time-bound knowledge.",
            },
        },
    )


def mark_reviewed_input_schema() -> dict[str, Any]:
    return _base_schema(
        tool_name="memory_mark_reviewed",
        title="memory_mark_reviewed input schema",
        required=["path", "verdict"],
        properties={
            "path": {
                "type": "string",
                "description": "Repo-relative path under memory/knowledge/_unverified/.",
            },
            "verdict": {
                "type": "string",
                "enum": sorted(REVIEW_VERDICTS),
                "description": "Review decision recorded in REVIEW_LOG.jsonl.",
            },
            "reviewer_notes": {
                "type": "string",
                "default": "",
                "description": "Optional freeform notes stored with the review log entry.",
            },
            "session_id": _session_id_string_schema(
                description="Optional canonical session id associated with the review.",
                allow_empty=True,
            ),
        },
    )


def request_approval_input_schema() -> dict[str, Any]:
    return _base_schema(
        tool_name="memory_request_approval",
        title="memory_request_approval input schema",
        required=["plan_id", "phase_id"],
        notes=[
            "project_id may be omitted when plan ids are unique across projects.",
            "expires_days is a positive review window in days; the runtime clamps legacy non-positive values up to 1.",
        ],
        properties={
            "plan_id": {
                "type": "string",
                "pattern": _PLAN_SLUG_PATTERN,
                "description": "Plan id in kebab-case.",
            },
            "phase_id": {
                "type": "string",
                "pattern": _PLAN_SLUG_PATTERN,
                "description": "Phase id in kebab-case.",
            },
            "project_id": {
                "oneOf": [
                    {"type": "string", "pattern": _PLAN_SLUG_PATTERN},
                    {"type": "null"},
                ],
                "description": "Optional project id used to disambiguate plan lookup.",
            },
            "context": {
                "oneOf": [
                    {"type": "string", "minLength": 1},
                    {"type": "null"},
                ],
                "description": "Optional additional context recorded on the approval document.",
            },
            "expires_days": {
                "type": "integer",
                "minimum": 1,
                "default": 7,
                "description": "Positive number of days before the pending approval expires.",
            },
        },
    )


def resolve_approval_input_schema() -> dict[str, Any]:
    return _base_schema(
        tool_name="memory_resolve_approval",
        title="memory_resolve_approval input schema",
        required=["plan_id", "phase_id", "resolution"],
        properties={
            "plan_id": {
                "type": "string",
                "pattern": _PLAN_SLUG_PATTERN,
                "description": "Plan id in kebab-case.",
            },
            "phase_id": {
                "type": "string",
                "pattern": _PLAN_SLUG_PATTERN,
                "description": "Phase id in kebab-case.",
            },
            "resolution": {
                "type": "string",
                "enum": sorted(APPROVAL_RESOLUTIONS),
                "description": "Approval decision to record.",
            },
            "comment": {
                "oneOf": [
                    {"type": "string"},
                    {"type": "null"},
                ],
                "description": "Optional reviewer comment stored on the resolved approval document.",
            },
        },
    )


def flag_for_review_input_schema() -> dict[str, Any]:
    return _base_schema(
        tool_name="memory_flag_for_review",
        title="memory_flag_for_review input schema",
        required=["path", "reason"],
        properties={
            "path": {
                "type": "string",
                "description": "Repo-relative path to add to the governance review queue.",
            },
            "reason": {
                "type": "string",
                "minLength": 1,
                "description": "Reason the file should be reviewed.",
            },
            "priority": {
                "type": "string",
                "enum": sorted(REVIEW_PRIORITIES),
                "default": "normal",
                "description": "Review queue priority.",
            },
        },
    )


def update_user_trait_input_schema() -> dict[str, Any]:
    return _base_schema(
        tool_name="memory_update_user_trait",
        title="memory_update_user_trait input schema",
        required=["file", "key", "value"],
        properties={
            "file": {
                "type": "string",
                "pattern": _PLAN_SLUG_PATTERN,
                "description": "User file slug under memory/users/.",
            },
            "key": {
                "type": "string",
                "description": "Frontmatter field or markdown section heading to update.",
            },
            "value": {
                "type": "string",
                "description": "Replacement or appended content.",
            },
            "mode": {
                "type": "string",
                "enum": sorted(UPDATE_MODES),
                "default": "upsert",
                "description": "How to merge the supplied value into the target field or section.",
            },
            "version_token": {
                "oneOf": [
                    {"type": "string"},
                    {"type": "null"},
                ],
                "description": "Optional optimistic-lock token returned by memory_read_file.",
            },
            "preview": {
                "type": "boolean",
                "default": False,
                "description": "When true, return the governed preview envelope instead of writing.",
            },
        },
    )


def update_skill_input_schema() -> dict[str, Any]:
    return _base_schema(
        tool_name="memory_update_skill",
        title="memory_update_skill input schema",
        required=["file", "section", "content"],
        all_of=[
            {
                "if": {"properties": {"create_if_missing": {"const": True}}},
                "then": {"required": ["source", "trust", "origin_session"]},
            }
        ],
        notes=[
            "When create_if_missing=false, source/trust/origin_session are ignored.",
            "Protected apply mode requires the approval_token returned by preview mode.",
        ],
        properties={
            "file": {
                "type": "string",
                "pattern": _PLAN_SLUG_PATTERN,
                "description": "Skill file slug under memory/skills/.",
            },
            "section": {
                "type": "string",
                "description": "Frontmatter key or markdown section heading to update.",
            },
            "content": {
                "type": "string",
                "description": "Replacement or appended content.",
            },
            "mode": {
                "type": "string",
                "enum": sorted(UPDATE_MODES),
                "default": "upsert",
                "description": "How to merge the supplied content into the target section.",
            },
            "version_token": {
                "oneOf": [
                    {"type": "string"},
                    {"type": "null"},
                ],
                "description": "Optional optimistic-lock token returned by memory_read_file.",
            },
            "create_if_missing": {
                "type": "boolean",
                "default": False,
                "description": "When true, create the skill file if it does not already exist.",
            },
            "source": {
                "oneOf": [
                    {"type": "string", "minLength": 1},
                    {"type": "null"},
                ],
                "description": "Required when create_if_missing=true.",
            },
            "trust": {
                "oneOf": [
                    {
                        "type": "string",
                        "enum": sorted(SKILL_CREATE_TRUST_LEVELS),
                    },
                    {"type": "null"},
                ],
                "description": "Required when create_if_missing=true.",
            },
            "origin_session": _session_id_string_schema(
                description="Required when create_if_missing=true.",
                nullable=True,
            ),
            "preview": {
                "type": "boolean",
                "default": False,
                "description": "When true, return the governed preview envelope instead of writing.",
            },
            "approval_token": {
                "oneOf": [
                    {"type": "string"},
                    {"type": "null"},
                ],
                "description": "Fresh preview approval token required for protected apply mode.",
            },
        },
    )


def update_frontmatter_bulk_input_schema() -> dict[str, Any]:
    return _base_schema(
        tool_name="memory_update_frontmatter_bulk",
        title="memory_update_frontmatter_bulk input schema",
        required=["updates"],
        notes=[
            "updates is validated as a full batch before any file is staged.",
            f"updates accepts at most {FRONTMATTER_BULK_MAX_UPDATES} files per batch.",
            "Protected directories remain blocked; use Tier 1 semantic tools for governed writes.",
        ],
        properties={
            "updates": {
                "type": "array",
                "minItems": 1,
                "maxItems": FRONTMATTER_BULK_MAX_UPDATES,
                "description": "Batch of frontmatter update objects.",
                "items": {
                    "type": "object",
                    "additionalProperties": True,
                    "required": ["path", "fields"],
                    "properties": {
                        "path": {
                            "type": "string",
                            "minLength": 1,
                            "description": "Repo-relative path to the markdown file whose frontmatter should be updated.",
                        },
                        "fields": {
                            "type": "object",
                            "additionalProperties": True,
                            "description": "Frontmatter key/value pairs to merge into the target file. Values must remain YAML-serializable.",
                        },
                        "version_token": {
                            "oneOf": [
                                {"type": "string"},
                                {"type": "null"},
                            ],
                            "description": "Optional optimistic-lock token returned by memory_read_file.",
                        },
                    },
                },
            },
            "create_missing_keys": {
                "type": "boolean",
                "default": True,
                "description": "When false, ignore fields that do not already exist in the target frontmatter.",
            },
        },
    )


def update_frontmatter_input_schema() -> dict[str, Any]:
    return _base_schema(
        tool_name="memory_update_frontmatter",
        title="memory_update_frontmatter input schema",
        required=["path", "updates"],
        notes=[
            "updates is a JSON object encoded as a string for CLI/MCP compatibility.",
            "Use null values inside the JSON object to remove frontmatter keys.",
            "Protected directories remain blocked; use Tier 1 semantic tools for governed writes.",
        ],
        properties={
            "path": {
                "type": "string",
                "minLength": 1,
                "description": "Repo-relative path to the markdown file whose frontmatter should be updated.",
            },
            "updates": {
                "type": "string",
                "minLength": 2,
                "contentMediaType": "application/json",
                "description": (
                    "JSON object string of frontmatter key/value pairs to set. "
                    'Example: {"status": "complete", "next_action": null}'
                ),
            },
            "version_token": {
                "oneOf": [
                    {"type": "string"},
                    {"type": "null"},
                ],
                "description": "Optional optimistic-lock token returned by memory_read_file.",
            },
        },
    )


def record_trace_input_schema() -> dict[str, Any]:
    return _base_schema(
        tool_name="memory_record_trace",
        title="memory_record_trace input schema",
        required=["session_id", "span_type", "name", "status"],
        notes=[
            "metadata is sanitized before write: credential-like keys are redacted, long strings are truncated, deeply nested objects are stringified, and oversized payloads are reduced to top-level scalars.",
            "cost usually comes from estimate_cost() as {tokens_in, tokens_out}, but arbitrary object payloads remain accepted for compatibility.",
        ],
        properties={
            "session_id": _session_id_string_schema(
                description="Canonical memory/activity/YYYY/MM/DD/chat-NNN id for the trace file.",
            ),
            "span_type": {
                "type": "string",
                "enum": sorted(TRACE_SPAN_TYPES),
                "description": "Trace span classification.",
            },
            "name": {
                "type": "string",
                "minLength": 1,
                "description": "Short span name stored in TRACES.jsonl.",
            },
            "status": {
                "type": "string",
                "enum": sorted(TRACE_STATUSES),
                "description": "Trace span outcome status.",
            },
            "duration_ms": {
                "oneOf": [
                    {"type": "integer", "minimum": 0},
                    {"type": "null"},
                ],
                "description": "Optional span duration in milliseconds.",
            },
            "metadata": {
                "oneOf": [
                    {
                        "type": "object",
                        "additionalProperties": True,
                    },
                    {"type": "null"},
                ],
                "description": "Optional metadata object. Nested content is sanitized before it is written.",
            },
            "cost": {
                "anyOf": [
                    {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["tokens_in", "tokens_out"],
                        "properties": {
                            "tokens_in": {
                                "type": "integer",
                                "minimum": 0,
                                "description": "Estimated input token count.",
                            },
                            "tokens_out": {
                                "type": "integer",
                                "minimum": 0,
                                "description": "Estimated output token count.",
                            },
                        },
                    },
                    {
                        "type": "object",
                        "additionalProperties": True,
                    },
                    {"type": "null"},
                ],
                "description": "Optional usage metadata. estimate_cost() returns {tokens_in, tokens_out}; custom object payloads are also accepted.",
            },
            "parent_span_id": {
                "oneOf": [
                    {"type": "string", "minLength": 1},
                    {"type": "null"},
                ],
                "description": "Optional parent span id for nesting. Generated span ids are 12-character lowercase hex strings.",
            },
        },
    )


def register_tool_input_schema() -> dict[str, Any]:
    return _base_schema(
        tool_name="memory_register_tool",
        title="memory_register_tool input schema",
        required=["name", "description", "provider"],
        notes=[
            "An existing provider/name pair is updated in place; otherwise a new registry entry is created.",
            "schema stores provider-specific parameter metadata; the runtime only requires it to be an object when supplied.",
            "Protected apply mode requires the approval_token returned by preview mode.",
        ],
        properties={
            "name": {
                "type": "string",
                "pattern": _PLAN_SLUG_PATTERN,
                "description": "Tool name slug stored under the provider registry.",
            },
            "description": {
                "type": "string",
                "minLength": 1,
                "description": "Human-readable description of the external tool.",
            },
            "provider": {
                "type": "string",
                "pattern": _PLAN_SLUG_PATTERN,
                "description": "Provider slug naming the registry file.",
            },
            "approval_required": {
                "type": "boolean",
                "default": False,
                "description": "Whether callers should obtain explicit approval before using the external tool.",
            },
            "cost_tier": {
                "type": "string",
                "enum": sorted(COST_TIERS),
                "default": "free",
                "description": "Qualitative cost bucket stored in the tool registry.",
            },
            "schema": {
                "oneOf": [
                    {
                        "type": "object",
                        "additionalProperties": True,
                    },
                    {"type": "null"},
                ],
                "description": "Optional provider-specific parameter or JSON Schema metadata for the external tool.",
            },
            "rate_limit": {
                "oneOf": [
                    {"type": "string", "minLength": 1},
                    {"type": "null"},
                ],
                "description": "Optional rate limit hint such as '60/minute', '500/hour', or '1/session'.",
            },
            "timeout_seconds": {
                "type": "integer",
                "minimum": 1,
                "default": 30,
                "description": "Timeout budget stored with the registry entry.",
            },
            "tags": {
                "oneOf": [
                    {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "minLength": 1,
                        },
                    },
                    {"type": "null"},
                ],
                "description": "Optional tag list used for registry queries and policy filtering.",
            },
            "notes": {
                "oneOf": [
                    {"type": "string"},
                    {"type": "null"},
                ],
                "description": "Optional freeform operator notes stored with the registry entry.",
            },
            "preview": {
                "type": "boolean",
                "default": False,
                "description": "When true, return the governed preview envelope instead of writing.",
            },
            "approval_token": {
                "oneOf": [
                    {"type": "string"},
                    {"type": "null"},
                ],
                "description": "Fresh preview approval token required for protected apply mode.",
            },
        },
    )


def record_periodic_review_input_schema() -> dict[str, Any]:
    return _base_schema(
        tool_name="memory_record_periodic_review",
        title="memory_record_periodic_review input schema",
        required=["review_date", "assessment_summary", "belief_diff_entry"],
        all_of=[
            {
                "if": {
                    "anyOf": [
                        {
                            "required": ["preview"],
                            "properties": {"preview": {"const": False}},
                        },
                        {"not": {"required": ["preview"]}},
                    ]
                },
                "then": {"required": ["approval_token"]},
            }
        ],
        notes=[
            "active_stage may be blank to reuse the current active stage from the live router.",
            "review_queue_entries is appended verbatim when non-empty.",
            "Protected apply mode requires the approval_token returned by preview mode.",
        ],
        properties={
            "review_date": {
                "type": "string",
                "pattern": r"^\d{4}-\d{2}-\d{2}$",
                "format": "date",
                "description": "ISO review date written into the live router and governance outputs.",
            },
            "assessment_summary": {
                "type": "string",
                "minLength": 1,
                "description": "Non-empty assessment text written into the active-stage block.",
            },
            "belief_diff_entry": {
                "type": "string",
                "minLength": 1,
                "description": "Markdown block appended to governance/belief-diff-log.md.",
            },
            "review_queue_entries": {
                "type": "string",
                "default": "",
                "description": "Optional markdown block appended to governance/review-queue.md when non-empty.",
            },
            "active_stage": {
                "oneOf": [
                    {
                        "type": "string",
                        "enum": sorted(PERIODIC_REVIEW_STAGES),
                    },
                    {"type": "string", "const": ""},
                ],
                "default": "",
                "description": "Optional active stage override. Use an empty string to retain the current stage.",
            },
            "preview": {
                "type": "boolean",
                "default": False,
                "description": "When true, return the governed preview envelope and approval token instead of writing.",
            },
            "approval_token": {
                "oneOf": [
                    {"type": "string"},
                    {"type": "null"},
                ],
                "description": "Fresh preview approval token required for protected apply mode.",
            },
        },
    )


def revert_commit_input_schema() -> dict[str, Any]:
    return _base_schema(
        tool_name="memory_revert_commit",
        title="memory_revert_commit input schema",
        required=["sha"],
        all_of=[
            {
                "if": {
                    "required": ["confirm"],
                    "properties": {"confirm": {"const": True}},
                },
                "then": {"required": ["preview_token"]},
            }
        ],
        notes=[
            "Call with confirm=false first to receive eligibility details, conflict metadata, and the preview_token required for apply mode.",
            "preview_token must come from a fresh preview at the current repository HEAD.",
        ],
        properties={
            "sha": {
                "type": "string",
                "pattern": r"^[0-9a-fA-F]{4,64}$",
                "description": "Commit SHA or unique prefix to inspect or revert.",
            },
            "confirm": {
                "type": "boolean",
                "default": False,
                "description": "When false, return preview metadata only. When true, attempt the revert after token validation.",
            },
            "preview_token": {
                "oneOf": [
                    {"type": "string"},
                    {"type": "null"},
                ],
                "description": "Preview token returned by the latest preview run; required when confirm=true.",
            },
        },
    )


TOOL_INPUT_SCHEMAS: dict[str, ToolSchemaBuilder] = {
    "memory_add_knowledge_file": add_knowledge_file_input_schema,
    "memory_archive_knowledge": archive_knowledge_input_schema,
    "memory_demote_knowledge": demote_knowledge_input_schema,
    "memory_flag_for_review": flag_for_review_input_schema,
    "memory_log_access_batch": log_access_batch_input_schema,
    "memory_mark_reviewed": mark_reviewed_input_schema,
    "memory_plan_create": plan_create_input_schema,
    "memory_plan_execute": plan_execute_input_schema,
    "memory_promote_knowledge": promote_knowledge_input_schema,
    "memory_promote_knowledge_batch": promote_knowledge_batch_input_schema,
    "memory_promote_knowledge_subtree": promote_knowledge_subtree_input_schema,
    "memory_record_periodic_review": record_periodic_review_input_schema,
    "memory_record_session": record_session_input_schema,
    "memory_record_trace": record_trace_input_schema,
    "memory_register_tool": register_tool_input_schema,
    "memory_reorganize_path": reorganize_path_input_schema,
    "memory_request_approval": request_approval_input_schema,
    "memory_revert_commit": revert_commit_input_schema,
    "memory_resolve_approval": resolve_approval_input_schema,
    "memory_update_frontmatter": update_frontmatter_input_schema,
    "memory_update_frontmatter_bulk": update_frontmatter_bulk_input_schema,
    "memory_update_names_index": update_names_index_input_schema,
    "memory_update_skill": update_skill_input_schema,
    "memory_update_user_trait": update_user_trait_input_schema,
}


def list_tool_schema_names() -> list[str]:
    return sorted(TOOL_INPUT_SCHEMAS)


def get_tool_input_schema(tool_name: str) -> dict[str, Any]:
    normalized = tool_name.strip()
    if not normalized:
        raise ValidationError("tool_name must be a non-empty string")
    builder = TOOL_INPUT_SCHEMAS.get(normalized)
    if builder is None:
        supported = ", ".join(list_tool_schema_names())
        raise ValidationError(
            f"Unsupported tool schema: {normalized!r}. Supported tools: {supported}"
        )
    return builder()


__all__ = [
    "ACCESS_MODES",
    "FRONTMATTER_BULK_MAX_UPDATES",
    "KNOWLEDGE_BATCH_TRUST_LEVELS",
    "PERIODIC_REVIEW_STAGES",
    "REVIEW_PRIORITIES",
    "REVIEW_VERDICTS",
    "SKILL_CREATE_TRUST_LEVELS",
    "TOOL_INPUT_SCHEMAS",
    "UPDATE_MODES",
    "VERIFICATION_RESULT_STATUSES",
    "access_entry_input_schema",
    "add_knowledge_file_input_schema",
    "archive_knowledge_input_schema",
    "demote_knowledge_input_schema",
    "get_tool_input_schema",
    "list_tool_schema_names",
    "log_access_batch_input_schema",
    "mark_reviewed_input_schema",
    "plan_execute_input_schema",
    "promote_knowledge_input_schema",
    "promote_knowledge_batch_input_schema",
    "promote_knowledge_subtree_input_schema",
    "request_approval_input_schema",
    "record_periodic_review_input_schema",
    "record_session_input_schema",
    "record_trace_input_schema",
    "register_tool_input_schema",
    "reorganize_path_input_schema",
    "revert_commit_input_schema",
    "resolve_approval_input_schema",
    "update_frontmatter_input_schema",
    "update_frontmatter_bulk_input_schema",
    "update_names_index_input_schema",
    "update_skill_input_schema",
    "update_user_trait_input_schema",
]
