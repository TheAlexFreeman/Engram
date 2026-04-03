"""Shared input schema registry for selected MCP tools."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .errors import ValidationError
from .plan_approvals import APPROVAL_RESOLUTIONS
from .plan_utils import (
    CHANGE_ACTION_ALIASES,
    CHANGE_ACTIONS,
    PLAN_OUTCOMES,
    POSTCONDITION_TYPE_ALIASES,
    POSTCONDITION_TYPES,
    SOURCE_TYPE_ALIASES,
    SOURCE_TYPES,
    _PLAN_SLUG_PATTERN,
    _SESSION_ID_PATTERN,
    plan_create_input_schema,
)

ACCESS_MODES = frozenset({"read", "write", "update", "create"})
FRONTMATTER_BULK_MAX_UPDATES = 100
KNOWLEDGE_BATCH_TRUST_LEVELS = frozenset({"medium", "high"})
REVIEW_PRIORITIES = frozenset({"normal", "urgent"})
REVIEW_VERDICTS = frozenset({"approve", "reject", "defer"})
SKILL_CREATE_TRUST_LEVELS = frozenset({"high", "medium", "low"})
UPDATE_MODES = frozenset({"upsert", "append", "replace"})
VERIFICATION_RESULT_STATUSES = frozenset({"pass", "fail", "error", "skip"})

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
    return {
        "anyOf": [
            {
                "type": "object",
                "additionalProperties": False,
                "required": ["postcondition", "type", "status"],
                "description": "Structured verification result returned by verify=true plan execution flows.",
                "properties": {
                    "postcondition": {
                        "type": "string",
                        "minLength": 1,
                        "description": "Original postcondition description from the plan phase.",
                    },
                    "type": {
                        "type": "string",
                        "enum": sorted(POSTCONDITION_TYPES),
                        "x-aliases": dict(POSTCONDITION_TYPE_ALIASES),
                        "description": "Canonical postcondition type.",
                    },
                    "status": {
                        "type": "string",
                        "enum": sorted(VERIFICATION_RESULT_STATUSES),
                        "description": "Verification outcome.",
                    },
                    "detail": {
                        "oneOf": [
                            {"type": "string"},
                            {"type": "null"},
                        ],
                        "description": "Optional diagnostic detail; null on successful or manual-skip outcomes.",
                    },
                    "policy_result": {
                        "type": "object",
                        "additionalProperties": True,
                        "description": "Optional tool-policy payload when a test postcondition is denied by policy.",
                    },
                },
            },
            {
                "type": "object",
                "additionalProperties": True,
                "description": "Legacy or caller-supplied verification context item stored verbatim on failure records.",
            },
        ],
        "description": (
            "Verification context item accepted by memory_plan_execute. Tool-generated "
            "verify flows return the structured branch; record_failure also accepts "
            "legacy caller-supplied objects."
        ),
    }


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


TOOL_INPUT_SCHEMAS: dict[str, ToolSchemaBuilder] = {
    "memory_flag_for_review": flag_for_review_input_schema,
    "memory_log_access_batch": log_access_batch_input_schema,
    "memory_mark_reviewed": mark_reviewed_input_schema,
    "memory_plan_create": plan_create_input_schema,
    "memory_plan_execute": plan_execute_input_schema,
    "memory_promote_knowledge_batch": promote_knowledge_batch_input_schema,
    "memory_record_session": record_session_input_schema,
    "memory_request_approval": request_approval_input_schema,
    "memory_resolve_approval": resolve_approval_input_schema,
    "memory_update_frontmatter_bulk": update_frontmatter_bulk_input_schema,
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
    "REVIEW_PRIORITIES",
    "REVIEW_VERDICTS",
    "SKILL_CREATE_TRUST_LEVELS",
    "TOOL_INPUT_SCHEMAS",
    "UPDATE_MODES",
    "VERIFICATION_RESULT_STATUSES",
    "access_entry_input_schema",
    "get_tool_input_schema",
    "list_tool_schema_names",
    "log_access_batch_input_schema",
    "mark_reviewed_input_schema",
    "plan_execute_input_schema",
    "promote_knowledge_batch_input_schema",
    "request_approval_input_schema",
    "record_session_input_schema",
    "resolve_approval_input_schema",
    "update_frontmatter_bulk_input_schema",
    "update_skill_input_schema",
    "update_user_trait_input_schema",
]
