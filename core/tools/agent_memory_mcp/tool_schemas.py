"""Shared input schema registry for selected MCP tools."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .errors import ValidationError
from .plan_approvals import APPROVAL_RESOLUTIONS
from .plan_utils import (
    _PLAN_SLUG_PATTERN,
    _SESSION_ID_PATTERN,
    COST_TIERS,
    PLAN_OUTCOMES,
    TRACE_SPAN_TYPES,
    TRACE_STATUSES,
    VERIFICATION_RESULT_STATUSES,
    plan_create_input_schema,
    verification_results_item_schema,
)
from .skill_distributor import BUILTIN_TARGETS
from .skill_trigger import SKILL_TRIGGER_EVENTS, skill_trigger_value_schema

ACCESS_MODES = frozenset({"read", "write", "update", "create"})
FRONTMATTER_BULK_MAX_UPDATES = 100
KNOWLEDGE_BATCH_TRUST_LEVELS = frozenset({"medium", "high"})
REVIEW_PRIORITIES = frozenset({"normal", "urgent"})
REVIEW_VERDICTS = frozenset({"approve", "reject", "defer"})
SKILL_CREATE_TRUST_LEVELS = frozenset({"high", "medium", "low"})
UPDATE_MODES = frozenset({"upsert", "append", "replace"})
PERIODIC_REVIEW_STAGES = frozenset({"Exploration", "Calibration", "Consolidation"})
SKILL_DISTRIBUTION_TARGETS = sorted(BUILTIN_TARGETS)

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
            "metrics": {
                "oneOf": [
                    {"type": "object", "additionalProperties": True},
                    {"type": "null"},
                ],
                "description": (
                    "Optional activity metrics merged into SUMMARY.md frontmatter "
                    "(sidecar fields take precedence over trace-file counters when both exist)."
                ),
            },
            "dialogue_entries": {
                "oneOf": [
                    {
                        "type": "array",
                        "items": {"type": "object", "additionalProperties": True},
                    },
                    {"type": "null"},
                ],
                "description": "Optional compressed dialogue rows written to session dialogue.jsonl.",
            },
        },
    )


def session_flush_input_schema() -> dict[str, Any]:
    return _base_schema(
        tool_name="memory_session_flush",
        title="memory_session_flush input schema",
        required=["summary"],
        notes=[
            "session_id resolves from the explicit argument first, then MEMORY_SESSION_ID, then memory/activity/CURRENT_SESSION.",
            "trigger accepts underscore or hyphen separators; underscores are normalized to hyphens before slug validation.",
        ],
        properties={
            "summary": {
                "type": "string",
                "minLength": 1,
                "description": "Non-empty checkpoint summary written to {session_id}/checkpoint.md.",
            },
            "session_id": _session_id_string_schema(
                description="Optional canonical session id override for the checkpoint target.",
                allow_empty=True,
            ),
            "label": {
                "type": "string",
                "default": "",
                "description": "Optional checkpoint label. When empty, a default context-pressure label is used.",
            },
            "trigger": {
                "type": "string",
                "pattern": r"^[a-z0-9]+(?:[-_][a-z0-9]+)*$",
                "default": "context_pressure",
                "description": "Flush trigger slug. Underscores are normalized to hyphens before validation.",
            },
        },
    )


def log_access_input_schema() -> dict[str, Any]:
    return _base_schema(
        tool_name="memory_log_access",
        title="memory_log_access input schema",
        required=["file", "task", "helpfulness", "note"],
        notes=[
            "session_id resolves from the explicit argument first, then MEMORY_SESSION_ID, then memory/activity/CURRENT_SESSION.",
            "category and task_id require their controlled vocabularies to exist before they can be used.",
            "min_helpfulness routes entries below the threshold to ACCESS_SCANS.jsonl instead of the hot ACCESS.jsonl file.",
        ],
        properties={
            "file": {
                "type": "string",
                "minLength": 1,
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
            "session_id": _session_id_string_schema(
                description="Optional canonical session id associated with the entry.",
                nullable=True,
            ),
            "category": {
                "oneOf": [
                    {"type": "string", "pattern": _PLAN_SLUG_PATTERN},
                    {"type": "null"},
                ],
                "description": "Optional controlled-vocabulary category slug.",
            },
            "mode": {
                "oneOf": [
                    {"type": "string", "enum": sorted(ACCESS_MODES)},
                    {"type": "null"},
                ],
                "description": "Optional access mode classification.",
            },
            "task_id": {
                "oneOf": [
                    {"type": "string", "pattern": _PLAN_SLUG_PATTERN},
                    {"type": "null"},
                ],
                "description": "Optional controlled task-id slug from the capability manifest.",
            },
            "estimator": {
                "oneOf": [
                    {"type": "string", "pattern": _PLAN_SLUG_PATTERN},
                    {"type": "null"},
                ],
                "description": "Optional helpfulness-estimator slug.",
            },
            "min_helpfulness": {
                "oneOf": [
                    {
                        "type": "number",
                        "minimum": 0.0,
                        "maximum": 1.0,
                    },
                    {"type": "null"},
                ],
                "description": "Optional routing threshold for ACCESS_SCANS.jsonl.",
            },
        },
    )


def run_aggregation_input_schema() -> dict[str, Any]:
    allowed_folders = [
        "memory/users",
        "memory/knowledge",
        "memory/knowledge/_unverified",
        "memory/skills",
        "memory/working/projects",
        "memory/activity",
    ]
    return _base_schema(
        tool_name="memory_run_aggregation",
        title="memory_run_aggregation input schema",
        notes=[
            "When folders is omitted or empty, aggregation scans the standard hot ACCESS roots across users, knowledge, skills, projects, and activity.",
            "dry_run defaults to true and previews summary, archive, and hot-log reset targets without mutating files.",
        ],
        properties={
            "folders": {
                "oneOf": [
                    {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": allowed_folders,
                        },
                    },
                    {"type": "null"},
                ],
                "description": "Optional subset of supported ACCESS roots to aggregate.",
            },
            "dry_run": {
                "type": "boolean",
                "default": True,
                "description": "When true, preview summary and archive targets without applying the aggregation commit.",
            },
        },
    )


def reset_session_state_input_schema() -> dict[str, Any]:
    return _base_schema(
        tool_name="memory_reset_session_state",
        title="memory_reset_session_state input schema",
        notes=[
            "This tool accepts no arguments and resets per-session counters such as the identity churn alarm.",
        ],
        properties={},
    )


def analyze_graph_input_schema() -> dict[str, Any]:
    return _base_schema(
        tool_name="memory_analyze_graph",
        title="memory_analyze_graph input schema",
        notes=[
            "path may be empty for the full knowledge base or a scoped folder such as knowledge/mathematics.",
            "include_details adds duplicate-link detail to the otherwise summary-focused graph report.",
        ],
        properties={
            "path": {
                "type": "string",
                "default": "",
                "description": "Optional knowledge-graph scope. Use an empty string for the full knowledge base.",
            },
            "include_details": {
                "type": "boolean",
                "default": False,
                "description": "When true, include duplicate-link details in the returned graph report.",
            },
        },
    )


def prune_redundant_links_input_schema() -> dict[str, Any]:
    return _base_schema(
        tool_name="memory_prune_redundant_links",
        title="memory_prune_redundant_links input schema",
        notes=[
            "path may be empty for the full knowledge base or a scoped folder such as knowledge/mathematics.",
            "dry_run defaults to true and returns the pruning report without staging or committing files.",
        ],
        properties={
            "path": {
                "type": "string",
                "default": "",
                "description": "Optional knowledge-graph scope. Use an empty string for the full knowledge base.",
            },
            "dry_run": {
                "type": "boolean",
                "default": True,
                "description": "When true, preview redundant-link removals without writing or committing changes.",
            },
        },
    )


def audit_link_density_input_schema() -> dict[str, Any]:
    return _base_schema(
        tool_name="memory_audit_link_density",
        title="memory_audit_link_density input schema",
        notes=[
            "path may be empty for the full knowledge base or a scoped folder such as knowledge/rationalist-community.",
            "degree_threshold values below 1 are clamped to 1 before the audit runs.",
        ],
        properties={
            "path": {
                "type": "string",
                "default": "",
                "description": "Optional knowledge-graph scope. Use an empty string for the full knowledge base.",
            },
            "degree_threshold": {
                "type": "integer",
                "default": 6,
                "description": "Minimum node degree examined by the dense-link audit.",
            },
            "clustering_threshold": {
                "type": "number",
                "default": 0.5,
                "description": "Minimum local clustering coefficient examined by the dense-link audit.",
            },
        },
    )


def prune_weak_links_input_schema() -> dict[str, Any]:
    return _base_schema(
        tool_name="memory_prune_weak_links",
        title="memory_prune_weak_links input schema",
        notes=[
            "path restricts pruning to a single file and overrides scope when both are provided.",
            "signal must be one of structural, access, or combined.",
            "dry_run defaults to true and only applies a commit when weak-link removals are written.",
        ],
        properties={
            "path": {
                "type": "string",
                "default": "",
                "description": "Optional single-file target. Overrides scope when non-empty.",
            },
            "scope": {
                "type": "string",
                "default": "",
                "description": "Optional folder scope used when path is empty.",
            },
            "min_structural_score": {
                "type": "number",
                "default": 1.0,
                "description": "Structural-score threshold below which links become pruning candidates.",
            },
            "min_access_score": {
                "type": "integer",
                "default": 0,
                "description": "Access-score threshold below which links become pruning candidates.",
            },
            "signal": {
                "type": "string",
                "enum": ["access", "combined", "structural"],
                "default": "structural",
                "description": "Weak-link scoring mode.",
            },
            "dry_run": {
                "type": "boolean",
                "default": True,
                "description": "When true, preview weak-link removals without writing or committing changes.",
            },
        },
    )


def checkpoint_input_schema() -> dict[str, Any]:
    return _base_schema(
        tool_name="memory_checkpoint",
        title="memory_checkpoint input schema",
        required=["content"],
        notes=[
            "Writes a timestamped entry to memory/working/CURRENT.md, or memory/working/{user_id}/CURRENT.md when MEMORY_USER_ID is set, and stages the file without creating a commit.",
            "session_id is optional but must be canonical when supplied.",
        ],
        properties={
            "content": {
                "type": "string",
                "description": "Checkpoint body appended under a timestamped heading in the active CURRENT.md scratchpad for the resolved user scope.",
            },
            "label": {
                "type": "string",
                "default": "",
                "description": "Optional heading suffix shown after the timestamp.",
            },
            "session_id": _session_id_string_schema(
                description="Optional canonical session id embedded in the checkpoint entry.",
                allow_empty=True,
            ),
        },
    )


def append_scratchpad_input_schema() -> dict[str, Any]:
    return _base_schema(
        tool_name="memory_append_scratchpad",
        title="memory_append_scratchpad input schema",
        required=["target", "content"],
        notes=[
            "target accepts the aliases user/current or a governed memory/working/notes/{slug}.md scratchpad path; when MEMORY_USER_ID is set, writes resolve under memory/working/{user_id}/... while the flat targets remain valid aliases.",
            "When section is supplied, the runtime creates the H2 heading if it does not already exist.",
        ],
        properties={
            "target": {
                "oneOf": [
                    {
                        "type": "string",
                        "enum": ["user", "current"],
                    },
                    {
                        "type": "string",
                        "pattern": r"^memory/working/notes/[a-z0-9]+(?:-[a-z0-9]+)*\.md$",
                    },
                ],
                "description": "Scratchpad target alias or governed notes path, resolved against the active user-scoped working root when applicable.",
            },
            "content": {
                "type": "string",
                "description": "Markdown content appended to the selected scratchpad target.",
            },
            "section": {
                "oneOf": [
                    {"type": "string"},
                    {"type": "null"},
                ],
                "description": "Optional H2 section heading used for targeted insertion.",
            },
        },
    )


def record_chat_summary_input_schema() -> dict[str, Any]:
    return _base_schema(
        tool_name="memory_record_chat_summary",
        title="memory_record_chat_summary input schema",
        required=["session_id", "summary"],
        notes=[
            "Idempotent replay succeeds only when the existing SUMMARY.md content already matches session_id, summary, and key_topics.",
            "Use memory_record_session instead when summary, reflection, and ACCESS writes should land in one commit.",
        ],
        properties={
            "session_id": _session_id_string_schema(
                description="Canonical memory/activity/YYYY/MM/DD/chat-NNN id.",
            ),
            "summary": {
                "type": "string",
                "description": "Markdown session summary written to {session_id}/SUMMARY.md.",
            },
            "key_topics": {
                "type": "string",
                "default": "",
                "description": "Comma-separated topic list written into the session summary frontmatter.",
            },
        },
    )


def record_reflection_input_schema() -> dict[str, Any]:
    return _base_schema(
        tool_name="memory_record_reflection",
        title="memory_record_reflection input schema",
        required=[
            "session_id",
            "memory_retrieved",
            "memory_influence",
            "outcome_quality",
            "gaps_noticed",
        ],
        notes=[
            "The target session folder must already exist; record the chat summary first if needed.",
            "Only one structured reflection is created per session; later edits should use direct editing tools.",
        ],
        properties={
            "session_id": _session_id_string_schema(
                description="Canonical memory/activity/YYYY/MM/DD/chat-NNN id whose reflection should be written.",
            ),
            "memory_retrieved": {
                "type": "string",
                "description": "What memory was retrieved during the session.",
            },
            "memory_influence": {
                "type": "string",
                "description": "How retrieved memory influenced the work.",
            },
            "outcome_quality": {
                "type": "string",
                "description": "Assessment of the session outcome quality.",
            },
            "gaps_noticed": {
                "type": "string",
                "description": "Observed memory or workflow gaps from the session.",
            },
            "system_observations": {
                "type": "string",
                "default": "",
                "description": "Optional additional system observations for the reflection.",
            },
        },
    )


def resolve_review_item_input_schema() -> dict[str, Any]:
    return _base_schema(
        tool_name="memory_resolve_review_item",
        title="memory_resolve_review_item input schema",
        required=["item_id"],
        notes=[
            "Only pending review-queue items can be resolved.",
            "preview returns the governed preview envelope without mutating the review queue.",
        ],
        properties={
            "item_id": {
                "type": "string",
                "pattern": _PLAN_SLUG_PATTERN,
                "description": "Canonical review-queue item slug returned by memory_flag_for_review.",
            },
            "resolution_note": {
                "oneOf": [
                    {"type": "string"},
                    {"type": "null"},
                ],
                "description": "Optional note appended to the resolved review-queue section.",
            },
            "version_token": {
                "oneOf": [
                    {"type": "string"},
                    {"type": "null"},
                ],
                "description": "Optional optimistic-lock token for governance/review-queue.md.",
            },
            "preview": {
                "type": "boolean",
                "default": False,
                "description": "When true, return the governed preview envelope instead of resolving the queue item.",
            },
        },
    )


def plan_review_exports_input_schema() -> dict[str, Any]:
    return _base_schema(
        tool_name="memory_plan_review",
        title="memory_plan_review input schema",
        required=["project_id"],
        all_of=[
            {
                "if": {
                    "required": ["plan_id"],
                    "properties": {"plan_id": {"type": "string"}},
                },
                "then": {"required": ["session_id"]},
            }
        ],
        notes=[
            "When plan_id is omitted, the tool lists completed plans for the project and ignores artifact_paths and session_id.",
            "When plan_id is provided, artifact_paths must be a subset of the plan's exportable outputs and session_id becomes required.",
        ],
        properties={
            "project_id": {
                "type": "string",
                "pattern": _PLAN_SLUG_PATTERN,
                "description": "Project id in kebab-case.",
            },
            "plan_id": {
                "oneOf": [
                    {"type": "string", "pattern": _PLAN_SLUG_PATTERN},
                    {"type": "null"},
                ],
                "description": "Optional completed plan id to export. Omit to list completed plans only.",
            },
            "artifact_paths": {
                "oneOf": [
                    {
                        "type": "array",
                        "items": {"type": "string", "minLength": 1},
                    },
                    {"type": "null"},
                ],
                "description": "Optional subset of exportable artifact paths to copy into the outbox.",
            },
            "session_id": _session_id_string_schema(
                description="Required when exporting artifacts from a specific completed plan.",
                nullable=True,
            ),
            "preview": {
                "type": "boolean",
                "default": False,
                "description": "When true, return the governed export preview envelope instead of copying artifacts.",
            },
        },
    )


def plan_resume_input_schema() -> dict[str, Any]:
    return _base_schema(
        tool_name="memory_plan_resume",
        title="memory_plan_resume input schema",
        required=["plan_id", "session_id"],
        notes=[
            "When a run state already exists, the runtime refreshes the stored session_id before returning the restart context.",
            "max_context_chars must coerce to an integer greater than or equal to zero.",
        ],
        properties={
            "plan_id": {
                "type": "string",
                "pattern": _PLAN_SLUG_PATTERN,
                "description": "Plan id in kebab-case.",
            },
            "session_id": _session_id_string_schema(
                description="Canonical session id used for resume tracing and run-state refresh.",
            ),
            "project_id": {
                "oneOf": [
                    {"type": "string", "pattern": _PLAN_SLUG_PATTERN},
                    {"type": "null"},
                ],
                "description": "Optional project id used to disambiguate plan lookup.",
            },
            "max_context_chars": {
                "type": "integer",
                "minimum": 0,
                "default": 8000,
                "description": "Approximate maximum context budget for the assembled resume briefing.",
            },
        },
    )


def stage_external_input_schema() -> dict[str, Any]:
    return _base_schema(
        tool_name="memory_stage_external",
        title="memory_stage_external input schema",
        required=["project", "filename", "content", "source_url", "fetched_date", "source_label"],
        notes=[
            "content must be a non-empty string and is size-limited by the staging helper.",
            "fetched_date must be an ISO date in YYYY-MM-DD format.",
            "dry_run returns the staging envelope without writing the IN/ file or staged-hash registry.",
            "snapshot_taken_at is derived automatically from fetched_date; reflects_upstream_as_of is an optional caller-supplied upstream marker written verbatim into frontmatter.",
        ],
        properties={
            "project": {
                "type": "string",
                "pattern": _PLAN_SLUG_PATTERN,
                "description": "Project slug under memory/working/projects/.",
            },
            "filename": {
                "type": "string",
                "minLength": 1,
                "description": "Suggested filename for the staged IN/ document.",
            },
            "content": {
                "type": "string",
                "minLength": 1,
                "description": "External content body staged into the project's IN/ folder.",
            },
            "source_url": {
                "type": "string",
                "minLength": 1,
                "description": "Origin URL recorded in frontmatter after sanitization.",
            },
            "fetched_date": {
                "type": "string",
                "pattern": r"^\d{4}-\d{2}-\d{2}$",
                "format": "date",
                "description": "ISO date recorded in the staged frontmatter; also used as snapshot_taken_at.",
            },
            "source_label": {
                "type": "string",
                "minLength": 1,
                "description": "Non-empty provenance label written into the staged frontmatter.",
            },
            "dry_run": {
                "type": "boolean",
                "default": False,
                "description": "When true, return the staging envelope without writing files.",
            },
            "reflects_upstream_as_of": {
                "oneOf": [
                    {"type": "string", "minLength": 1},
                    {"type": "null"},
                ],
                "description": "Optional upstream state marker (commit sha, tag, or ISO date) describing what the snapshot reflects. Omitted from frontmatter when null.",
            },
        },
    )


def run_eval_input_schema() -> dict[str, Any]:
    return _base_schema(
        tool_name="memory_run_eval",
        title="memory_run_eval input schema",
        required=["session_id"],
        notes=[
            "Requires ENGRAM_TIER2=1 because eval scenarios may invoke verification on test-type postconditions.",
            "scenario_id and tag are optional filters; when both are omitted the runtime executes the full suite.",
        ],
        properties={
            "session_id": _session_id_string_schema(
                description="Canonical session id used for trace logging of eval results.",
            ),
            "scenario_id": {
                "oneOf": [
                    {"type": "string", "minLength": 1},
                    {"type": "null"},
                ],
                "description": "Optional scenario id filter.",
            },
            "tag": {
                "oneOf": [
                    {"type": "string", "minLength": 1},
                    {"type": "null"},
                ],
                "description": "Optional scenario tag filter.",
            },
        },
    )


def eval_report_input_schema() -> dict[str, Any]:
    return _base_schema(
        tool_name="memory_eval_report",
        title="memory_eval_report input schema",
        notes=[
            "date_from and date_to, when provided, must be ISO dates in YYYY-MM-DD format.",
            "scenario_id filters the historical eval report to a single scenario.",
        ],
        properties={
            "date_from": {
                "oneOf": [
                    {
                        "type": "string",
                        "pattern": r"^\d{4}-\d{2}-\d{2}$",
                        "format": "date",
                    },
                    {"type": "null"},
                ],
                "description": "Optional inclusive lower date bound for historical eval runs.",
            },
            "date_to": {
                "oneOf": [
                    {
                        "type": "string",
                        "pattern": r"^\d{4}-\d{2}-\d{2}$",
                        "format": "date",
                    },
                    {"type": "null"},
                ],
                "description": "Optional inclusive upper date bound for historical eval runs.",
            },
            "scenario_id": {
                "oneOf": [
                    {"type": "string", "minLength": 1},
                    {"type": "null"},
                ],
                "description": "Optional scenario id filter applied to the report.",
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
        all_of=[
            {
                "if": {
                    "anyOf": [
                        {
                            "required": ["dry_run"],
                            "properties": {"dry_run": {"const": False}},
                        },
                        {"not": {"required": ["dry_run"]}},
                    ]
                },
                "then": {"required": ["preview_token"]},
            }
        ],
        notes=[
            "Nested markdown paths are preserved relative to source_folder when constructing destination targets.",
            "dry_run returns the governed preview envelope, planned_moves, and a preview_token without writing or staging anything.",
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
                "description": "When true, return planned_moves, counts, and a preview_token without mutating files.",
            },
            "preview_token": {
                "oneOf": [
                    {"type": "string"},
                    {"type": "null"},
                ],
                "description": "Fresh preview receipt returned by dry_run=true; required when applying the subtree promotion.",
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
            "preview=true returns the governed preview envelope without writing or committing.",
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
            "preview": {
                "type": "boolean",
                "default": False,
                "description": "Return the governed preview envelope without writing or committing.",
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


def list_pending_reviews_input_schema() -> dict[str, Any]:
    return _base_schema(
        tool_name="memory_list_pending_reviews",
        title="memory_list_pending_reviews input schema",
        notes=[
            "folder_path defaults to memory/knowledge/_unverified and must stay under that subtree.",
            "The result reports only the latest surviving verdict per file, grouped by approve/defer/reject.",
        ],
        properties={
            "folder_path": {
                "type": "string",
                "default": "memory/knowledge/_unverified",
                "description": "Existing directory under memory/knowledge/_unverified whose review log should be summarized.",
            },
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
                "then": {"required": ["preview_token"]},
            }
        ],
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
                "description": "When true, return the governed preview envelope and preview_token instead of writing.",
            },
            "preview_token": {
                "oneOf": [
                    {"type": "string"},
                    {"type": "null"},
                ],
                "description": "Fresh preview receipt required for proposed apply mode.",
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
            },
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
            },
            {
                "if": {"properties": {"section": {"const": "trigger"}}},
                "then": {
                    "properties": {
                        "content": skill_trigger_value_schema(
                            description="Trigger frontmatter value to write when section='trigger'."
                        )
                    }
                },
            },
            {
                "if": {"not": {"properties": {"section": {"const": "trigger"}}}},
                "then": {
                    "properties": {
                        "content": {
                            "type": "string",
                            "description": "Replacement or appended content.",
                        }
                    }
                },
            },
        ],
        notes=[
            "When create_if_missing=false, source/trust/origin_session are ignored.",
            "Protected apply mode requires the opaque approval_token returned by preview mode.",
            "When section='trigger', content may be a trigger event string, a trigger mapping, or a non-empty list of trigger entries.",
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
                "description": "Fresh preview-issued approval receipt required for protected apply mode.",
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
            "An existing provider/name pair is updated in place; otherwise a new registry entry is created.",
            "schema stores provider-specific parameter metadata; the runtime only requires it to be an object when supplied.",
            "Protected apply mode requires the opaque approval_token returned by preview mode.",
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
                "description": "Fresh preview-issued approval receipt required for protected apply mode.",
            },
        },
    )


def get_tool_policy_input_schema() -> dict[str, Any]:
    return _base_schema(
        tool_name="memory_get_tool_policy",
        title="memory_get_tool_policy input schema",
        all_of=[
            {
                "anyOf": [
                    {
                        "required": ["tool_name"],
                        "properties": {"tool_name": {"type": "string", "minLength": 1}},
                    },
                    {
                        "required": ["provider"],
                        "properties": {"provider": {"type": "string", "minLength": 1}},
                    },
                    {
                        "required": ["tags"],
                        "properties": {
                            "tags": {"type": "array", "minItems": 1},
                        },
                    },
                    {
                        "required": ["cost_tier"],
                        "properties": {"cost_tier": {"type": "string", "minLength": 1}},
                    },
                ]
            }
        ],
        notes=[
            "At least one filter parameter is required.",
            "tool_name returns at most one match; the other filters may return multiple registry entries.",
        ],
        properties={
            "tool_name": {
                "oneOf": [
                    {"type": "string", "pattern": _PLAN_SLUG_PATTERN},
                    {"type": "null"},
                ],
                "description": "Optional tool name slug filter.",
            },
            "provider": {
                "oneOf": [
                    {"type": "string", "pattern": _PLAN_SLUG_PATTERN},
                    {"type": "null"},
                ],
                "description": "Optional provider slug filter.",
            },
            "tags": {
                "oneOf": [
                    {
                        "type": "array",
                        "minItems": 1,
                        "items": {"type": "string", "minLength": 1},
                    },
                    {"type": "null"},
                ],
                "description": "Optional non-empty tag list used for policy filtering.",
            },
            "cost_tier": {
                "oneOf": [
                    {"type": "string", "enum": sorted(COST_TIERS)},
                    {"type": "null"},
                ],
                "description": "Optional qualitative cost bucket filter.",
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
            "Protected apply mode requires the opaque approval_token returned by preview mode.",
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
                "description": "When true, return the governed preview envelope and approval_token instead of writing.",
            },
            "approval_token": {
                "oneOf": [
                    {"type": "string"},
                    {"type": "null"},
                ],
                "description": "Fresh preview-issued approval receipt required for protected apply mode.",
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
            "preview_token must come from a fresh preview receipt at the current repository HEAD.",
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
                "description": "Preview receipt returned by the latest preview run; required when confirm=true.",
            },
        },
    )


def list_plans_input_schema() -> dict[str, Any]:
    return _base_schema(
        tool_name="memory_list_plans",
        title="memory_list_plans input schema",
        notes=[
            "status filters the discovered YAML plans by their stored plan.status value.",
            "project_id narrows the scan to one project slug under memory/working/projects/.",
        ],
        properties={
            "status": {
                "oneOf": [
                    {"type": "string", "minLength": 1},
                    {"type": "null"},
                ],
                "description": "Optional exact plan status filter.",
            },
            "project_id": {
                "oneOf": [
                    {"type": "string", "pattern": _PLAN_SLUG_PATTERN},
                    {"type": "null"},
                ],
                "description": "Optional project slug used to narrow the plan scan.",
            },
        },
    )


def plan_verify_input_schema() -> dict[str, Any]:
    return _base_schema(
        tool_name="memory_plan_verify",
        title="memory_plan_verify input schema",
        required=["plan_id", "phase_id"],
        notes=[
            "Evaluates phase postconditions without mutating plan state.",
            "test-type postconditions still require ENGRAM_TIER2=1 during runtime verification.",
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
        },
    )


def query_dialogue_input_schema() -> dict[str, Any]:
    return _base_schema(
        tool_name="memory_query_dialogue",
        title="memory_query_dialogue input schema",
        notes=[
            "sessions, when provided, reads dialogue.jsonl for each canonical session id.",
            "date_from and date_to filter by activity folder date (YYYY-MM-DD) during discovery.",
        ],
        properties={
            "sessions": {
                "oneOf": [
                    {
                        "type": "array",
                        "items": _session_id_string_schema(
                            description="Canonical memory/activity session id.",
                        ),
                    },
                    {"type": "null"},
                ],
                "description": "Optional explicit session ids to read dialogue.jsonl from.",
            },
            "date_from": {
                "oneOf": [
                    {"type": "string", "pattern": r"^\d{4}-\d{2}-\d{2}$", "format": "date"},
                    {"type": "null"},
                ],
                "description": "Optional inclusive lower date bound for dialogue file discovery.",
            },
            "date_to": {
                "oneOf": [
                    {"type": "string", "pattern": r"^\d{4}-\d{2}-\d{2}$", "format": "date"},
                    {"type": "null"},
                ],
                "description": "Optional inclusive upper date bound for dialogue file discovery.",
            },
            "keyword": {
                "oneOf": [
                    {"type": "string"},
                    {"type": "null"},
                ],
                "description": "Optional case-insensitive substring filter on dialogue first_line.",
            },
            "limit": {
                "type": "integer",
                "minimum": 1,
                "default": 100,
                "description": "Maximum rows returned after sorting.",
            },
            "offset": {
                "type": "integer",
                "minimum": 0,
                "default": 0,
                "description": "Number of leading rows to skip after filtering.",
            },
        },
    )


def query_traces_input_schema() -> dict[str, Any]:
    return _base_schema(
        tool_name="memory_query_traces",
        title="memory_query_traces input schema",
        notes=[
            "Provide only one of session_id or sessions when narrowing to known sessions.",
            "date_from and date_to must be ISO dates in YYYY-MM-DD format when supplied.",
            "group_by returns aggregated buckets instead of raw spans when set.",
        ],
        properties={
            "session_id": _session_id_string_schema(
                description="Optional canonical session id whose trace file should be queried directly.",
                nullable=True,
            ),
            "sessions": {
                "oneOf": [
                    {
                        "type": "array",
                        "items": _session_id_string_schema(
                            description="Canonical memory/activity session id.",
                        ),
                    },
                    {"type": "null"},
                ],
                "description": "Optional list of session ids to query trace files for.",
            },
            "date_from": {
                "oneOf": [
                    {"type": "string", "pattern": r"^\d{4}-\d{2}-\d{2}$", "format": "date"},
                    {"type": "null"},
                ],
                "description": "Optional inclusive lower date bound used during trace-file discovery.",
            },
            "date_to": {
                "oneOf": [
                    {"type": "string", "pattern": r"^\d{4}-\d{2}-\d{2}$", "format": "date"},
                    {"type": "null"},
                ],
                "description": "Optional inclusive upper date bound used during trace-file discovery.",
            },
            "span_type": {
                "oneOf": [
                    {"type": "string", "enum": sorted(TRACE_SPAN_TYPES)},
                    {"type": "null"},
                ],
                "description": "Optional trace span type filter.",
            },
            "plan_id": {
                "oneOf": [
                    {"type": "string", "pattern": _PLAN_SLUG_PATTERN},
                    {"type": "null"},
                ],
                "description": "Optional plan id filter matched against metadata.plan_id.",
            },
            "status": {
                "oneOf": [
                    {"type": "string", "enum": sorted(TRACE_STATUSES)},
                    {"type": "null"},
                ],
                "description": "Optional trace status filter.",
            },
            "limit": {
                "type": "integer",
                "minimum": 1,
                "default": 100,
                "description": "Maximum number of spans or group rows returned after sorting.",
            },
            "group_by": {
                "oneOf": [
                    {
                        "type": "string",
                        "enum": ["tool_name", "span_type", "session_id", "date"],
                    },
                    {"type": "null"},
                ],
                "description": "Optional aggregation dimension; when set, spans list is empty and groups are returned.",
            },
        },
    )


def plan_briefing_input_schema() -> dict[str, Any]:
    return _base_schema(
        tool_name="memory_plan_briefing",
        title="memory_plan_briefing input schema",
        required=["plan_id"],
        notes=[
            "When phase_id is omitted, the runtime selects the next actionable phase and returns a summary packet if none exists.",
            "max_context_chars must coerce to an integer greater than or equal to zero.",
        ],
        properties={
            "plan_id": {
                "type": "string",
                "pattern": _PLAN_SLUG_PATTERN,
                "description": "Plan id in kebab-case.",
            },
            "phase_id": {
                "oneOf": [
                    {"type": "string", "pattern": _PLAN_SLUG_PATTERN},
                    {"type": "null"},
                ],
                "description": "Optional phase id override. When omitted, the next actionable phase is selected.",
            },
            "project_id": {
                "oneOf": [
                    {"type": "string", "pattern": _PLAN_SLUG_PATTERN},
                    {"type": "null"},
                ],
                "description": "Optional project id used to disambiguate plan lookup.",
            },
            "max_context_chars": {
                "type": "integer",
                "minimum": 0,
                "default": 8000,
                "description": "Approximate maximum context budget for the assembled briefing.",
            },
            "include_sources": {
                "type": "boolean",
                "default": True,
                "description": "When true, include source excerpts in the assembled phase briefing.",
            },
            "include_traces": {
                "type": "boolean",
                "default": True,
                "description": "When true, include recent trace context in the assembled phase briefing.",
            },
            "include_approval": {
                "type": "boolean",
                "default": True,
                "description": "When true, include approval context in the assembled phase briefing.",
            },
        },
    )


def scan_drop_zone_input_schema() -> dict[str, Any]:
    return _base_schema(
        tool_name="memory_scan_drop_zone",
        title="memory_scan_drop_zone input schema",
        notes=[
            "Scans configured watch_folders from agent-bootstrap.toml and stages new content into project IN/ folders.",
            "When MEMORY_SESSION_ID is set, the runtime also records a tool_call trace span for the scan.",
        ],
        properties={
            "project_filter": {
                "oneOf": [
                    {"type": "string", "pattern": _PLAN_SLUG_PATTERN},
                    {"type": "null"},
                ],
                "description": "Optional project slug used to restrict which configured drop-zone entries are scanned.",
            },
        },
    )


def semantic_search_input_schema() -> dict[str, Any]:
    return _base_schema(
        tool_name="memory_semantic_search",
        title="memory_semantic_search input schema",
        required=["query"],
        notes=[
            "Requires sentence-transformers at runtime; otherwise the tool returns a dependency warning string instead of ranked results.",
            "limit is clamped into the 1..50 range and all weight parameters are clamped into the 0.0..1.0 range before scoring.",
        ],
        properties={
            "query": {
                "type": "string",
                "minLength": 1,
                "description": "Natural-language search query.",
            },
            "scope": {
                "oneOf": [
                    {"type": "string", "minLength": 1},
                    {"type": "null"},
                ],
                "description": "Optional folder path used to restrict semantic search.",
            },
            "limit": {
                "type": "integer",
                "minimum": 1,
                "maximum": 50,
                "default": 10,
                "description": "Maximum number of deduplicated file results returned.",
            },
            "min_trust": {
                "oneOf": [
                    {"type": "string", "enum": ["low", "medium", "high"]},
                    {"type": "null"},
                ],
                "description": "Optional minimum trust threshold applied before ranking truncation.",
            },
            "freshness_weight": {
                "type": "number",
                "minimum": 0.0,
                "maximum": 1.0,
                "default": 0.15,
                "description": "Relative weight of temporal freshness in the hybrid ranking.",
            },
            "helpfulness_weight": {
                "type": "number",
                "minimum": 0.0,
                "maximum": 1.0,
                "default": 0.15,
                "description": "Relative weight of ACCESS helpfulness in the hybrid ranking.",
            },
            "vector_weight": {
                "type": "number",
                "minimum": 0.0,
                "maximum": 1.0,
                "default": 0.4,
                "description": "Relative weight of vector similarity in the hybrid ranking.",
            },
            "bm25_weight": {
                "type": "number",
                "minimum": 0.0,
                "maximum": 1.0,
                "default": 0.3,
                "description": "Relative weight of BM25 lexical matching in the hybrid ranking.",
            },
        },
    )


def skill_manifest_read_input_schema() -> dict[str, Any]:
    return _base_schema(
        tool_name="memory_skill_manifest_read",
        title="memory_skill_manifest_read input schema",
        notes=[
            "Reads and parses SKILLS.yaml, checking lock status for each skill.",
            "For each skill, lock_status is: 'locked' (hash matches), 'stale' (hash mismatch), or 'unlocked' (no lock entry).",
            "Returns schema_version, defaults, and enriched skills dict with lock_status added to each entry.",
        ],
        properties={
            "skill": {
                "oneOf": [
                    {"type": "string", "pattern": _PLAN_SLUG_PATTERN},
                    {"type": "null"},
                ],
                "description": "Optional skill slug to filter to a single entry. If omitted, returns all skills.",
            },
        },
    )


def skill_manifest_write_input_schema() -> dict[str, Any]:
    return _base_schema(
        tool_name="memory_skill_manifest_write",
        title="memory_skill_manifest_write input schema",
        required=["slug", "source", "trust", "description"],
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
            },
        ],
        notes=[
            "Protected apply mode requires the opaque approval_token returned by preview mode.",
            "slug must be kebab-case: /^[a-z0-9]+(?:-[a-z0-9]+)*$/",
            "source must match one of: 'local', 'github:owner/repo', 'git:url', or 'path:./relative'",
            "trust must be one of: high, medium, low",
            "ref is only valid with github: or git: sources and is ignored for source: local",
            "source: local entries always resolve to checked deployment; an explicit gitignored override is invalid.",
            "targets is optional; when omitted the entry inherits defaults.targets or [engram]. Use targets=[] to disable external projections for one skill.",
        ],
        properties={
            "slug": {
                "type": "string",
                "pattern": _PLAN_SLUG_PATTERN,
                "description": "Skill identifier in kebab-case. Must match skill directory name.",
            },
            "source": {
                "type": "string",
                "minLength": 1,
                "description": "Source location: 'local', 'github:owner/repo', 'git:url', or 'path:./relative'.",
            },
            "trust": {
                "type": "string",
                "enum": sorted(SKILL_CREATE_TRUST_LEVELS),
                "description": "Trust level: must match SKILL.md frontmatter trust field.",
            },
            "description": {
                "type": "string",
                "minLength": 1,
                "description": "One-line description for catalog display. Should match SKILL.md frontmatter.",
            },
            "ref": {
                "oneOf": [
                    {"type": "string", "minLength": 1},
                    {"type": "null"},
                ],
                "description": "Optional version pin (git tag, branch, or commit SHA) for remote sources only.",
            },
            "deployment_mode": {
                "oneOf": [
                    {"type": "string", "enum": ["checked", "gitignored"]},
                    {"type": "null"},
                ],
                "description": "Optional override for deployment mode. Inherits from defaults if omitted. source: local cannot use gitignored.",
            },
            "targets": {
                "oneOf": [
                    {
                        "type": "array",
                        "items": {"type": "string", "enum": SKILL_DISTRIBUTION_TARGETS},
                        "uniqueItems": True,
                    },
                    {"type": "null"},
                ],
                "description": "Optional distribution target override. Inherits from defaults.targets if omitted; [] disables external projections.",
            },
            "enabled": {
                "oneOf": [
                    {"type": "boolean"},
                    {"type": "null"},
                ],
                "description": "Optional enabled flag. Default: true. When false, skill is excluded from catalog.",
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
                "description": "Fresh preview-issued approval receipt required for protected apply mode.",
            },
        },
    )


def skill_list_input_schema() -> dict[str, Any]:
    return _base_schema(
        tool_name="memory_skill_list",
        title="memory_skill_list input schema",
        notes=[
            "Read-only discovery interface per skill-lifecycle-spec.md.",
            "Reads SKILLS.yaml manifest and SKILLS.lock to enrich results.",
            "Falls back to SKILL.md frontmatter for orphan skills (on disk but not in manifest).",
            "Returns structured JSON with skill metadata, trust, lock status, and file stats.",
            "All parameters are optional and can be combined to filter results.",
        ],
        properties={
            "trust_level": {
                "oneOf": [
                    {"type": "string", "enum": sorted(SKILL_CREATE_TRUST_LEVELS)},
                    {"type": "null"},
                ],
                "description": "Filter by trust level: high, medium, or low. Omit for all.",
            },
            "source_type": {
                "oneOf": [
                    {"type": "string", "enum": ["local", "github", "git", "path", "remote"]},
                    {"type": "null"},
                ],
                "description": "Filter by source type. 'local' for local skills, 'remote' for any non-local, or specific types: github, git, path.",
            },
            "enabled": {
                "oneOf": [
                    {"type": "boolean"},
                    {"type": "null"},
                ],
                "description": "Filter by enabled state (true/false). Omit to include all.",
            },
            "archived": {
                "type": "boolean",
                "default": False,
                "description": "Include archived skills from _archive/ directory.",
            },
            "include_lock_info": {
                "type": "boolean",
                "default": True,
                "description": "Include content hash, lock date, and freshness for each skill. Set false to skip hash computation.",
            },
            "max_results": {
                "type": "integer",
                "default": 100,
                "description": "Maximum results to return. 0 for unlimited.",
            },
        },
    )


def skill_route_input_schema() -> dict[str, Any]:
    return _base_schema(
        tool_name="memory_skill_route",
        title="memory_skill_route input schema",
        required=["event"],
        notes=[
            "Read-only trigger router for explicit skill dispatch.",
            "Frontmatter trigger metadata takes precedence over SKILLS.yaml trigger fallback.",
            "Catalog fallback contributes triggerless skills only when query or skill_slug is provided in context.",
        ],
        properties={
            "event": {
                "type": "string",
                "enum": sorted(SKILL_TRIGGER_EVENTS),
                "description": "Trigger event to evaluate against skill metadata.",
            },
            "context": {
                "oneOf": [
                    {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "tool_name": {
                                "oneOf": [
                                    {"type": "string", "minLength": 1},
                                    {"type": "null"},
                                ],
                                "description": "Optional tool name used for pre-tool-use and post-tool-use matcher evaluation.",
                            },
                            "project_id": {
                                "oneOf": [
                                    {"type": "string", "pattern": _PLAN_SLUG_PATTERN},
                                    {"type": "null"},
                                ],
                                "description": "Optional active project slug used for project-active matcher evaluation.",
                            },
                            "interval": {
                                "oneOf": [
                                    {"type": "string", "minLength": 1},
                                    {"type": "null"},
                                ],
                                "description": "Optional periodic interval token used for periodic matcher evaluation.",
                            },
                            "condition": {
                                "oneOf": [
                                    {"type": "string", "minLength": 1},
                                    {"type": "null"},
                                ],
                                "description": "Optional single active condition; merged with context.conditions.",
                            },
                            "conditions": {
                                "oneOf": [
                                    {
                                        "type": "array",
                                        "minItems": 1,
                                        "items": {"type": "string", "minLength": 1},
                                    },
                                    {"type": "null"},
                                ],
                                "description": "Optional active condition set for condition matcher evaluation.",
                            },
                            "query": {
                                "oneOf": [
                                    {"type": "string", "minLength": 1},
                                    {"type": "null"},
                                ],
                                "description": "Optional catalog fallback query matched against slug, title, and description.",
                            },
                            "skill_slug": {
                                "oneOf": [
                                    {"type": "string", "pattern": _PLAN_SLUG_PATTERN},
                                    {"type": "null"},
                                ],
                                "description": "Optional exact skill slug to narrow explicit or catalog matches.",
                            },
                        },
                    },
                    {"type": "null"},
                ],
                "description": "Optional routing context for matcher evaluation and catalog fallback.",
            },
            "include_catalog_fallback": {
                "type": "boolean",
                "default": True,
                "description": "Include triggerless catalog matches when query or skill_slug is supplied in context.",
            },
            "include_archived": {
                "type": "boolean",
                "default": False,
                "description": "Include archived skills from core/memory/skills/_archive/.",
            },
            "include_disabled": {
                "type": "boolean",
                "default": False,
                "description": "Include skills disabled in SKILLS.yaml.",
            },
            "max_results": {
                "type": "integer",
                "default": 20,
                "description": "Maximum number of ordered matches to return. 0 for unlimited.",
            },
        },
    )


def skill_install_input_schema() -> dict[str, Any]:
    return _base_schema(
        tool_name="memory_skill_install",
        title="memory_skill_install input schema",
        required=["source"],
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
            },
            {
                "if": {
                    "required": ["source"],
                    "properties": {"source": {"const": "local"}},
                },
                "then": {"required": ["slug"]},
            },
        ],
        notes=[
            "Protected apply mode requires the opaque approval_token returned by preview mode.",
            "Installs a skill from local, path:./..., path:../..., github:owner/repo, or git:url sources.",
            "When slug is omitted, the resolver derives it from the resolved skill directory name.",
            "trust, when provided, rewrites the installed SKILL.md frontmatter to keep manifest and content aligned.",
            "source: local installs always resolve to checked deployment so the skill remains available after clone.",
            "targets is optional; when omitted the installed entry inherits defaults.targets or [engram]. Use targets=[] to disable external projections.",
        ],
        properties={
            "source": {
                "type": "string",
                "minLength": 1,
                "description": "Source string to resolve: local, path:./..., path:../..., github:owner/repo, or git:url.",
            },
            "slug": {
                "oneOf": [
                    {"type": "string", "pattern": _PLAN_SLUG_PATTERN},
                    {"type": "null"},
                ],
                "description": "Optional installed skill slug override. Required when source='local'.",
            },
            "ref": {
                "oneOf": [
                    {"type": "string", "minLength": 1},
                    {"type": "null"},
                ],
                "description": "Optional git/github ref pin. Valid only for github: and git: sources.",
            },
            "trust": {
                "oneOf": [
                    {"type": "string", "enum": sorted(SKILL_CREATE_TRUST_LEVELS)},
                    {"type": "null"},
                ],
                "description": "Optional trust override written into the installed SKILL.md and manifest.",
            },
            "enabled": {
                "oneOf": [
                    {"type": "boolean"},
                    {"type": "null"},
                ],
                "description": "Optional manifest enabled flag; defaults to true.",
            },
            "targets": {
                "oneOf": [
                    {
                        "type": "array",
                        "items": {"type": "string", "enum": SKILL_DISTRIBUTION_TARGETS},
                        "uniqueItems": True,
                    },
                    {"type": "null"},
                ],
                "description": "Optional distribution target override. Inherits from defaults.targets if omitted; [] disables external projections.",
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
                "description": "Fresh preview-issued approval receipt required for protected apply mode.",
            },
        },
    )


def skill_add_input_schema() -> dict[str, Any]:
    return _base_schema(
        tool_name="memory_skill_add",
        title="memory_skill_add input schema",
        required=["slug", "title", "description", "source", "trust", "origin_session"],
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
            },
        ],
        notes=[
            "Protected apply mode requires the opaque approval_token returned by preview mode.",
            "source must be 'template' or path:./relative/path within the repository.",
            "Remote sources (github:, git:) are not supported yet.",
            "deployment_mode is optional; when omitted, the effective mode falls back to defaults.deployment_mode or the trust-aware mapping.",
            "Template-backed skills register as source: local, so they always resolve to checked deployment.",
            "targets is optional; when omitted the new entry inherits defaults.targets or [engram]. Use targets=[] to disable external projections.",
        ],
        properties={
            "slug": {
                "type": "string",
                "pattern": _PLAN_SLUG_PATTERN,
                "description": "Skill directory slug (kebab-case).",
            },
            "title": {
                "type": "string",
                "minLength": 1,
                "description": "Human-readable title for the SKILL.md heading.",
            },
            "description": {
                "type": "string",
                "minLength": 1,
                "description": "One-line description for manifest and SUMMARY.md.",
            },
            "source": {
                "type": "string",
                "minLength": 1,
                "description": "template, or path:./relative/path to copy an existing skill directory.",
            },
            "trust": {
                "type": "string",
                "enum": sorted(SKILL_CREATE_TRUST_LEVELS),
                "description": "Trust level; for path: sources must match SKILL.md frontmatter.",
            },
            "origin_session": _session_id_string_schema(
                description="Session id recorded in new skill frontmatter (template source).",
                nullable=False,
            ),
            "ref": {
                "oneOf": [
                    {"type": "string", "minLength": 1},
                    {"type": "null"},
                ],
                "description": "Reserved for future remote pins; must be omitted for now.",
            },
            "enabled": {
                "oneOf": [
                    {"type": "boolean"},
                    {"type": "null"},
                ],
                "description": "Manifest enabled flag; default true.",
            },
            "deployment_mode": {
                "oneOf": [
                    {"type": "string", "enum": ["checked", "gitignored"]},
                    {"type": "null"},
                ],
                "description": "Optional override for deployment mode. Inherits from defaults if omitted. Template/local skills cannot use gitignored.",
            },
            "targets": {
                "oneOf": [
                    {
                        "type": "array",
                        "items": {"type": "string", "enum": SKILL_DISTRIBUTION_TARGETS},
                        "uniqueItems": True,
                    },
                    {"type": "null"},
                ],
                "description": "Optional distribution target override. Inherits from defaults.targets if omitted; [] disables external projections.",
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
                "description": "Fresh preview-issued approval receipt required for protected apply mode.",
            },
        },
    )


def skill_remove_input_schema() -> dict[str, Any]:
    return _base_schema(
        tool_name="memory_skill_remove",
        title="memory_skill_remove input schema",
        required=["slug"],
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
            },
        ],
        notes=[
            "Protected apply mode requires the opaque approval_token returned by preview mode.",
            "Moves the skill directory to _archive/{slug}/ when present; always refreshes indexes.",
        ],
        properties={
            "slug": {
                "type": "string",
                "pattern": _PLAN_SLUG_PATTERN,
                "description": "Skill slug to archive and unregister.",
            },
            "archive_reason": {
                "oneOf": [
                    {"type": "string", "minLength": 1},
                    {"type": "null"},
                ],
                "description": "Optional reason recorded in _archive/ARCHIVE_INDEX.md when a directory is moved.",
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
                "description": "Fresh preview-issued approval receipt required for protected apply mode.",
            },
        },
    )


def skill_sync_input_schema() -> dict[str, Any]:
    return _base_schema(
        tool_name="memory_skill_sync",
        title="memory_skill_sync input schema",
        notes=[
            "check_only=true returns a JSON report only (no writes).",
            "approval_token is required for apply when archive_orphans or remove_missing_entries "
            "will perform work (orphans on disk or manifest rows with missing directories).",
            "Non-destructive refresh (lock + indexes) does not use approval_token.",
            "verify_symlinks is reserved; symlink_errors in the report stays 0 for now.",
        ],
        properties={
            "check_only": {
                "type": "boolean",
                "default": False,
                "description": "When true, report inconsistencies without modifying files.",
            },
            "fix_stale_locks": {
                "type": "boolean",
                "default": True,
                "description": "Rebuild SKILLS.lock entries from manifest + on-disk skills.",
            },
            "archive_orphans": {
                "type": "boolean",
                "default": False,
                "description": "Move skill directories not listed in the manifest into _archive/.",
            },
            "remove_missing_entries": {
                "type": "boolean",
                "default": False,
                "description": "Remove manifest entries whose SKILL.md directory is missing.",
            },
            "verify_symlinks": {
                "type": "boolean",
                "default": True,
                "description": "Reserved for future symlink verification (currently no-op).",
            },
            "regenerate_indexes": {
                "type": "boolean",
                "default": True,
                "description": "Regenerate SKILL_TREE.md and SUMMARY.md current-skills section.",
            },
            "preview": {
                "type": "boolean",
                "default": False,
                "description": "When true, return a governed preview envelope instead of applying writes.",
            },
            "approval_token": {
                "oneOf": [
                    {"type": "string"},
                    {"type": "null"},
                ],
                "description": "Required for destructive apply (orphan archive or missing-entry removal) after preview.",
            },
        },
    )


def reindex_input_schema() -> dict[str, Any]:
    return _base_schema(
        tool_name="memory_reindex",
        title="memory_reindex input schema",
        notes=[
            "Requires sentence-transformers at runtime; otherwise the tool returns a dependency warning string.",
            "force=false only embeds changed files, while force=true rebuilds the full index.",
        ],
        properties={
            "force": {
                "type": "boolean",
                "default": False,
                "description": "When true, rebuild the full semantic index instead of incrementally updating it.",
            },
        },
    )


def read_file_input_schema() -> dict[str, Any]:
    return _base_schema(
        tool_name="memory_read_file",
        title="memory_read_file input schema",
        required=["path"],
        notes=[
            "Responses are inline by default. Files larger than the inline limit return a byte-range slice plus pagination metadata (`total_bytes`, `has_more`, `next_call_hint`).",
            "offset_bytes and limit_bytes slice the raw bytes of the file; UTF-8 boundary errors at the slice edges are replaced rather than raised.",
            "prefer_temp_file requests a server-side temp path for full-file reads. Ignored when the deployment sets AGENT_MEMORY_CROSS_FILESYSTEM because the path is not resolvable across filesystems.",
        ],
        properties={
            "path": {
                "type": "string",
                "minLength": 1,
                "description": "Repo-relative content path to read.",
            },
            "offset_bytes": {
                "type": "integer",
                "minimum": 0,
                "default": 0,
                "description": "Byte offset to start reading from. Defaults to start of file.",
            },
            "limit_bytes": {
                "oneOf": [
                    {"type": "integer", "minimum": 1},
                    {"type": "null"},
                ],
                "description": "Maximum bytes to return inline. Defaults to the inline threshold when null; hard-capped at the server's maximum.",
            },
            "prefer_temp_file": {
                "type": "boolean",
                "default": False,
                "description": "When true on same-filesystem deployments, also write the full file to a server-side temp path and return it as temp_file. Ignored across filesystems.",
            },
        },
    )


def extract_file_input_schema() -> dict[str, Any]:
    return _base_schema(
        tool_name="memory_extract_file",
        title="memory_extract_file input schema",
        required=["path"],
        notes=[
            "max_sections must be >= 1; preview_chars must be >= 1 at runtime.",
            "section_headings accepts comma- or newline-separated heading text to match.",
        ],
        properties={
            "path": {
                "type": "string",
                "minLength": 1,
                "description": "Repo-relative path to the Markdown file.",
            },
            "section_headings": {
                "type": "string",
                "default": "",
                "description": "Optional CSV or newline-separated headings to extract.",
            },
            "max_sections": {
                "type": "integer",
                "minimum": 1,
                "default": 5,
                "description": "Maximum number of matched sections to return.",
            },
            "preview_chars": {
                "type": "integer",
                "minimum": 1,
                "default": 1200,
                "description": "Maximum characters per preview window.",
            },
            "include_outline": {
                "type": "boolean",
                "default": True,
                "description": "When true, include the heading outline (up to 50 headings).",
            },
        },
    )


def grep_search_input_schema() -> dict[str, Any]:
    return _base_schema(
        tool_name="memory_search",
        title="memory_search input schema",
        required=["query"],
        notes=[
            "max_results is clamped at runtime (default 30, upper bound 100).",
            "context_lines is clamped into 0..10 at runtime.",
            "freshness_weight is clamped into 0.0..1.0 at runtime.",
        ],
        properties={
            "query": {
                "type": "string",
                "minLength": 1,
                "description": "Search string or regex (git grep / Python fallback).",
            },
            "path": {
                "type": "string",
                "default": ".",
                "description": "Folder to search within (repo-relative).",
            },
            "glob_pattern": {
                "type": "string",
                "default": "**/*.md",
                "description": "Glob filter for files under path.",
            },
            "case_sensitive": {
                "type": "boolean",
                "default": False,
                "description": "Case-sensitive matching when true.",
            },
            "max_results": {
                "type": "integer",
                "minimum": 1,
                "default": 30,
                "description": "Maximum matching lines to return.",
            },
            "context_lines": {
                "type": "integer",
                "minimum": 0,
                "default": 0,
                "description": "Surrounding lines before/after each match.",
            },
            "include_humans": {
                "type": "boolean",
                "default": False,
                "description": "Include HUMANS/ when searching broad scopes.",
            },
            "freshness_weight": {
                "type": "number",
                "minimum": 0.0,
                "maximum": 1.0,
                "default": 0.0,
                "description": "Blend weight for temporal freshness reranking.",
            },
        },
    )


def context_home_input_schema() -> dict[str, Any]:
    return _base_schema(
        tool_name="memory_context_home",
        title="memory_context_home input schema",
        notes=[
            "max_context_chars coerces to an integer; 0 means unbounded budget at runtime.",
        ],
        properties={
            "max_context_chars": {
                "type": "integer",
                "default": 16000,
                "description": "Soft character budget for the assembled response.",
            },
            "include_project_index": {
                "type": "boolean",
                "default": True,
                "description": "Include memory/working/projects/SUMMARY.md when budget allows.",
            },
            "include_knowledge_index": {
                "type": "boolean",
                "default": False,
                "description": "Include memory/knowledge/SUMMARY.md when budget allows.",
            },
            "include_skills_index": {
                "type": "boolean",
                "default": False,
                "description": "Include memory/skills/SUMMARY.md when budget allows.",
            },
        },
    )


def context_project_input_schema() -> dict[str, Any]:
    return _base_schema(
        tool_name="memory_context_project",
        title="memory_context_project input schema",
        required=["project"],
        notes=[
            "max_context_chars coerces to an integer; 0 means unbounded budget at runtime.",
            "include_user_profile may be null for auto behavior at runtime.",
            "include_in_manifest accepts false, 'off', 'summary' (default), 'full', or true.",
            "Defaults favor the cold-start fast path: include_plan_sources=False,"
            " include_in_manifest='summary'.",
        ],
        properties={
            "project": {
                "type": "string",
                "minLength": 1,
                "description": "Project slug under memory/working/projects/.",
            },
            "max_context_chars": {
                "type": "integer",
                "default": 24000,
                "description": "Soft character budget for the assembled response.",
            },
            "include_plan_sources": {
                "type": "boolean",
                "default": False,
                "description": (
                    "Include whole-file sources for the active plan phase when budget allows. "
                    "Off by default because source reads are the largest per-call cost."
                ),
            },
            "include_in_manifest": {
                "oneOf": [
                    {"type": "boolean"},
                    {"type": "string", "enum": ["off", "summary", "full"]},
                ],
                "default": "summary",
                "description": (
                    "IN/ staging rendering mode. 'summary' shows a one-line count "
                    "(cold-start default); 'full' (or true) shows the capped manifest table; "
                    "'off' (or false) omits the section entirely."
                ),
            },
            "include_session_notes": {
                "type": "boolean",
                "default": True,
                "description": (
                    "Include memory/working/CURRENT.md when it mentions the project. "
                    "Set false to skip the section outright."
                ),
            },
            "include_user_profile": {
                "oneOf": [
                    {"type": "boolean"},
                    {"type": "null"},
                ],
                "description": "Force include/omit memory/users/SUMMARY.md; null uses auto rules.",
            },
        },
    )


def context_project_lite_input_schema() -> dict[str, Any]:
    return _base_schema(
        tool_name="memory_context_project_lite",
        title="memory_context_project_lite input schema",
        required=["project"],
        notes=[
            "Strictly bounded fast-path: reads SUMMARY.md + plan IDs/status only.",
            "Skips IN/ manifest, plan sources, session notes, user profile, and the",
            " content-hash cache. Guaranteed sub-500ms on projects of any size.",
            "max_context_chars coerces to an integer; 0 means unbounded budget at runtime.",
        ],
        properties={
            "project": {
                "type": "string",
                "minLength": 1,
                "description": "Project slug under memory/working/projects/.",
            },
            "max_context_chars": {
                "type": "integer",
                "default": 8000,
                "description": (
                    "Soft character budget for the assembled response. Lower than"
                    " memory_context_project because the lite bundle is always small."
                ),
            },
        },
    )


def write_input_schema() -> dict[str, Any]:
    return _base_schema(
        tool_name="memory_write",
        title="memory_write input schema",
        required=["path", "content"],
        notes=[
            "Gated behind MEMORY_ENABLE_RAW_WRITE_TOOLS; rejects protected directories at runtime.",
        ],
        properties={
            "path": {
                "type": "string",
                "minLength": 1,
                "description": "Repo-relative path to create or overwrite.",
            },
            "content": {
                "type": "string",
                "description": "Full file body to write.",
            },
            "version_token": {
                "oneOf": [
                    {"type": "string", "minLength": 1},
                    {"type": "null"},
                ],
                "description": "Optional optimistic-lock token from memory_read_file.",
            },
            "create_dirs": {
                "type": "boolean",
                "default": True,
                "description": "Create parent directories when missing.",
            },
        },
    )


def edit_input_schema() -> dict[str, Any]:
    return _base_schema(
        tool_name="memory_edit",
        title="memory_edit input schema",
        required=["path", "old_string", "new_string"],
        notes=[
            "Gated behind MEMORY_ENABLE_RAW_WRITE_TOOLS; rejects protected directories at runtime.",
        ],
        properties={
            "path": {
                "type": "string",
                "minLength": 1,
                "description": "Repo-relative file path.",
            },
            "old_string": {
                "type": "string",
                "description": "Exact substring to replace.",
            },
            "new_string": {
                "type": "string",
                "description": "Replacement text.",
            },
            "replace_all": {
                "type": "boolean",
                "default": False,
                "description": "Replace every occurrence of old_string.",
            },
            "version_token": {
                "oneOf": [
                    {"type": "string", "minLength": 1},
                    {"type": "null"},
                ],
                "description": "Optional optimistic-lock token from memory_read_file.",
            },
        },
    )


def delete_input_schema() -> dict[str, Any]:
    return _base_schema(
        tool_name="memory_delete",
        title="memory_delete input schema",
        required=["path"],
        notes=[
            "Gated behind MEMORY_ENABLE_RAW_WRITE_TOOLS; rejects protected directories at runtime.",
        ],
        properties={
            "path": {
                "type": "string",
                "minLength": 1,
                "description": "Repo-relative file path to delete.",
            },
            "version_token": {
                "oneOf": [
                    {"type": "string", "minLength": 1},
                    {"type": "null"},
                ],
                "description": "Optional optimistic-lock token from memory_read_file.",
            },
        },
    )


def move_input_schema() -> dict[str, Any]:
    return _base_schema(
        tool_name="memory_move",
        title="memory_move input schema",
        required=["source", "dest"],
        notes=[
            "Gated behind MEMORY_ENABLE_RAW_WRITE_TOOLS; validates source/destination governance at runtime.",
        ],
        properties={
            "source": {
                "type": "string",
                "minLength": 1,
                "description": "Repo-relative source path.",
            },
            "dest": {
                "type": "string",
                "minLength": 1,
                "description": "Repo-relative destination path.",
            },
            "version_token": {
                "oneOf": [
                    {"type": "string", "minLength": 1},
                    {"type": "null"},
                ],
                "description": "Optional optimistic-lock token for the source file.",
            },
            "create_dirs": {
                "type": "boolean",
                "default": True,
                "description": "Create destination parent directories when missing.",
            },
        },
    )


def commit_input_schema() -> dict[str, Any]:
    return _base_schema(
        tool_name="memory_commit",
        title="memory_commit input schema",
        required=["message"],
        notes=[
            "Gated behind MEMORY_ENABLE_RAW_WRITE_TOOLS alongside other raw mutation tools.",
        ],
        properties={
            "message": {
                "type": "string",
                "minLength": 1,
                "description": "Git commit message following Engram conventions.",
            },
            "allow_empty": {
                "type": "boolean",
                "default": False,
                "description": "Allow committing with an empty index when true.",
            },
        },
    )


TOOL_INPUT_SCHEMAS: dict[str, ToolSchemaBuilder] = {
    "memory_analyze_graph": analyze_graph_input_schema,
    "memory_add_knowledge_file": add_knowledge_file_input_schema,
    "memory_append_scratchpad": append_scratchpad_input_schema,
    "memory_archive_knowledge": archive_knowledge_input_schema,
    "memory_audit_link_density": audit_link_density_input_schema,
    "memory_checkpoint": checkpoint_input_schema,
    "memory_commit": commit_input_schema,
    "memory_context_home": context_home_input_schema,
    "memory_context_project": context_project_input_schema,
    "memory_context_project_lite": context_project_lite_input_schema,
    "memory_delete": delete_input_schema,
    "memory_demote_knowledge": demote_knowledge_input_schema,
    "memory_edit": edit_input_schema,
    "memory_eval_report": eval_report_input_schema,
    "memory_extract_file": extract_file_input_schema,
    "memory_flag_for_review": flag_for_review_input_schema,
    "memory_get_tool_policy": get_tool_policy_input_schema,
    "memory_list_pending_reviews": list_pending_reviews_input_schema,
    "memory_list_plans": list_plans_input_schema,
    "memory_log_access": log_access_input_schema,
    "memory_log_access_batch": log_access_batch_input_schema,
    "memory_mark_reviewed": mark_reviewed_input_schema,
    "memory_move": move_input_schema,
    "memory_plan_briefing": plan_briefing_input_schema,
    "memory_plan_create": plan_create_input_schema,
    "memory_plan_execute": plan_execute_input_schema,
    "memory_plan_resume": plan_resume_input_schema,
    "memory_plan_verify": plan_verify_input_schema,
    "memory_prune_redundant_links": prune_redundant_links_input_schema,
    "memory_prune_weak_links": prune_weak_links_input_schema,
    "memory_plan_review": plan_review_exports_input_schema,
    "memory_promote_knowledge": promote_knowledge_input_schema,
    "memory_promote_knowledge_batch": promote_knowledge_batch_input_schema,
    "memory_promote_knowledge_subtree": promote_knowledge_subtree_input_schema,
    "memory_query_dialogue": query_dialogue_input_schema,
    "memory_query_traces": query_traces_input_schema,
    "memory_read_file": read_file_input_schema,
    "memory_reindex": reindex_input_schema,
    "memory_record_chat_summary": record_chat_summary_input_schema,
    "memory_record_periodic_review": record_periodic_review_input_schema,
    "memory_record_reflection": record_reflection_input_schema,
    "memory_record_session": record_session_input_schema,
    "memory_record_trace": record_trace_input_schema,
    "memory_register_tool": register_tool_input_schema,
    "memory_reset_session_state": reset_session_state_input_schema,
    "memory_reorganize_path": reorganize_path_input_schema,
    "memory_request_approval": request_approval_input_schema,
    "memory_revert_commit": revert_commit_input_schema,
    "memory_resolve_review_item": resolve_review_item_input_schema,
    "memory_resolve_approval": resolve_approval_input_schema,
    "memory_run_aggregation": run_aggregation_input_schema,
    "memory_run_eval": run_eval_input_schema,
    "memory_scan_drop_zone": scan_drop_zone_input_schema,
    "memory_search": grep_search_input_schema,
    "memory_semantic_search": semantic_search_input_schema,
    "memory_session_flush": session_flush_input_schema,
    "memory_skill_add": skill_add_input_schema,
    "memory_skill_install": skill_install_input_schema,
    "memory_skill_list": skill_list_input_schema,
    "memory_skill_manifest_read": skill_manifest_read_input_schema,
    "memory_skill_manifest_write": skill_manifest_write_input_schema,
    "memory_skill_remove": skill_remove_input_schema,
    "memory_skill_route": skill_route_input_schema,
    "memory_skill_sync": skill_sync_input_schema,
    "memory_stage_external": stage_external_input_schema,
    "memory_update_frontmatter": update_frontmatter_input_schema,
    "memory_update_frontmatter_bulk": update_frontmatter_bulk_input_schema,
    "memory_update_names_index": update_names_index_input_schema,
    "memory_update_skill": update_skill_input_schema,
    "memory_update_user_trait": update_user_trait_input_schema,
    "memory_write": write_input_schema,
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
    "analyze_graph_input_schema",
    "append_scratchpad_input_schema",
    "archive_knowledge_input_schema",
    "audit_link_density_input_schema",
    "checkpoint_input_schema",
    "commit_input_schema",
    "context_home_input_schema",
    "context_project_input_schema",
    "context_project_lite_input_schema",
    "delete_input_schema",
    "demote_knowledge_input_schema",
    "edit_input_schema",
    "extract_file_input_schema",
    "eval_report_input_schema",
    "grep_search_input_schema",
    "get_tool_policy_input_schema",
    "get_tool_input_schema",
    "list_pending_reviews_input_schema",
    "list_plans_input_schema",
    "list_tool_schema_names",
    "log_access_input_schema",
    "log_access_batch_input_schema",
    "mark_reviewed_input_schema",
    "move_input_schema",
    "plan_briefing_input_schema",
    "plan_execute_input_schema",
    "plan_resume_input_schema",
    "plan_review_exports_input_schema",
    "plan_verify_input_schema",
    "prune_redundant_links_input_schema",
    "prune_weak_links_input_schema",
    "promote_knowledge_input_schema",
    "promote_knowledge_batch_input_schema",
    "promote_knowledge_subtree_input_schema",
    "query_dialogue_input_schema",
    "query_traces_input_schema",
    "read_file_input_schema",
    "reindex_input_schema",
    "request_approval_input_schema",
    "record_chat_summary_input_schema",
    "record_periodic_review_input_schema",
    "record_reflection_input_schema",
    "record_session_input_schema",
    "record_trace_input_schema",
    "register_tool_input_schema",
    "reset_session_state_input_schema",
    "reorganize_path_input_schema",
    "revert_commit_input_schema",
    "resolve_review_item_input_schema",
    "resolve_approval_input_schema",
    "run_aggregation_input_schema",
    "run_eval_input_schema",
    "scan_drop_zone_input_schema",
    "semantic_search_input_schema",
    "session_flush_input_schema",
    "skill_install_input_schema",
    "skill_list_input_schema",
    "skill_route_input_schema",
    "skill_manifest_read_input_schema",
    "skill_manifest_write_input_schema",
    "stage_external_input_schema",
    "update_frontmatter_input_schema",
    "update_frontmatter_bulk_input_schema",
    "update_names_index_input_schema",
    "update_skill_input_schema",
    "update_user_trait_input_schema",
    "write_input_schema",
]
