"""Structured YAML plan schema helpers."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date as date_type
from pathlib import Path
from typing import Any, TypedDict

import yaml  # type: ignore[import-untyped]

from .errors import DuplicateContentError, NotFoundError, ValidationError
from .path_policy import validate_session_id, validate_slug
from .plan_approvals import (
    APPROVAL_RESOLUTIONS,
    APPROVAL_STATUSES,
    ApprovalDocument,
    _check_approval_expiry,
    _find_approvals_root,  # noqa: F401
    approval_filename,
    approvals_summary_path,
    load_approval,
    materialize_expired_approval,
    regenerate_approvals_summary,
    save_approval,
)
from .plan_registry import (
    COST_TIERS,
    PolicyCheckResult,
    ToolDefinition,
    _all_registry_tools,
    _command_matches_tool,
    _parse_rate_limit,  # noqa: F401
    _resolve_tool_policies,
    check_tool_policy,
    load_registry,
    regenerate_registry_summary,
    registry_file_path,
    registry_summary_path,
    save_registry,
)
from .plan_run_state import (
    RunState,
    RunStateError,
    RunStatePhase,
    check_run_state_staleness,
    load_run_state,
    prune_run_state,
    run_state_path,
    save_run_state,
    update_run_state,
    validate_run_state_against_plan,
)
from .plan_trace import (
    TRACE_SPAN_TYPES,
    TRACE_STATUSES,
    TraceSpan,
    _sanitize_metadata,  # noqa: F401
    estimate_cost,
    record_trace,
    trace_file_path,
)

PLAN_STATUSES = {"draft", "active", "blocked", "paused", "completed", "abandoned"}
PHASE_STATUSES = {"pending", "blocked", "in-progress", "completed", "skipped"}
PLAN_OUTCOMES = {"completed", "partial", "abandoned"}
CHANGE_ACTIONS = {"create", "rewrite", "update", "delete", "rename"}
SOURCE_TYPES = {"internal", "external", "mcp"}
POSTCONDITION_TYPES = {"check", "grep", "test", "manual"}
VERIFICATION_RESULT_STATUSES = {"pass", "fail", "error", "skip"}
CHANGE_ACTION_ALIASES = {"modify": "update"}
SOURCE_TYPE_ALIASES = {"code": "internal"}
POSTCONDITION_TYPE_ALIASES = {"file_check": "check"}

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_PLAN_SLUG_PATTERN = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"
_SESSION_ID_PATTERN = (
    r"^memory/activity/(?:[a-z0-9]+(?:-[a-z0-9]+)*/)?\d{4}/\d{2}/\d{2}/(?:chat|act)-\d{3}$"
)


def _normalize_enum_alias(value: str, aliases: dict[str, str]) -> str:
    if not isinstance(value, str):
        return value
    normalized = value.strip()
    return aliases.get(normalized, normalized)


def _build_validation_error(errors: list[str]) -> ValidationError:
    normalized = [str(error).strip() for error in errors if str(error).strip()]
    if not normalized:
        error = ValidationError("invalid plan input")
        setattr(error, "errors", ["invalid plan input"])
        return error
    if len(normalized) == 1:
        message = normalized[0]
    else:
        message = f"{len(normalized)} validation errors:\n" + "\n".join(
            f"- {item}" for item in normalized
        )
    error = ValidationError(message)
    setattr(error, "errors", normalized)
    return error


def _raise_collected_validation_errors(errors: list[str]) -> None:
    if errors:
        raise _build_validation_error(errors)


def validation_error_messages(error: ValidationError) -> list[str]:
    details = getattr(error, "errors", None)
    if isinstance(details, list) and details:
        return [str(item).strip() for item in details if str(item).strip()]
    message = str(error).strip()
    return [message] if message else []


def _prefix_validation_errors(path: str, error: ValidationError) -> list[str]:
    return [f"{path}: {message}" for message in validation_error_messages(error)]


def verification_results_item_schema() -> dict[str, Any]:
    """Return the shared schema for stored plan verification-result items."""

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
                        "x-aliases": dict(sorted(POSTCONDITION_TYPE_ALIASES.items())),
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
            "Verification context item accepted by plan failure records. Tool-generated "
            "verify flows return the structured branch; legacy authored failure payloads "
            "may still include custom objects."
        ),
    }


def plan_create_input_schema() -> dict[str, Any]:
    """Return the nested input schema for ``memory_plan_create`` as JSON-serializable data."""

    source_item = {
        "type": "object",
        "description": "Source to consult before executing phase changes. Unknown keys are ignored.",
        "required": ["path", "type", "intent"],
        "additionalProperties": True,
        "properties": {
            "path": {
                "type": "string",
                "description": (
                    "Repo-relative path for internal sources; descriptive identifier for external or MCP sources."
                ),
            },
            "type": {
                "type": "string",
                "enum": sorted(SOURCE_TYPES),
                "description": "Canonical source type.",
                "x-aliases": dict(sorted(SOURCE_TYPE_ALIASES.items())),
            },
            "intent": {
                "type": "string",
                "minLength": 1,
                "description": "Why the phase should consult this source.",
            },
            "uri": {
                "type": "string",
                "description": "Required when type='external'.",
            },
            "mcp_server": {
                "type": "string",
                "description": "Required with mcp_tool when type='mcp'.",
            },
            "mcp_tool": {
                "type": "string",
                "description": "Required with mcp_server when type='mcp'.",
            },
            "mcp_arguments": {
                "type": "object",
                "description": "Optional arguments passed to the MCP tool when type='mcp'.",
            },
        },
        "allOf": [
            {
                "if": {"properties": {"type": {"const": "external"}}},
                "then": {"required": ["uri"]},
            },
            {
                "if": {"properties": {"type": {"const": "mcp"}}},
                "then": {"required": ["mcp_server", "mcp_tool"]},
            },
        ],
    }
    postcondition_object = {
        "type": "object",
        "description": "Formal postcondition object. Unknown keys are ignored.",
        "required": ["description"],
        "additionalProperties": True,
        "properties": {
            "description": {
                "type": "string",
                "minLength": 1,
                "description": "Human-readable success criterion.",
            },
            "type": {
                "type": "string",
                "enum": sorted(POSTCONDITION_TYPES),
                "default": "manual",
                "description": (
                    "Canonical validator type. check=file exists, grep=regex in file, test=allowlisted command, manual=human verification."
                ),
                "x-aliases": dict(sorted(POSTCONDITION_TYPE_ALIASES.items())),
            },
            "target": {
                "type": "string",
                "description": "Required when type is check, grep, or test.",
            },
        },
        "allOf": [
            {
                "if": {"properties": {"type": {"enum": ["check", "grep", "test"]}}},
                "then": {"required": ["target"]},
            }
        ],
    }
    change_item = {
        "type": "object",
        "description": "Planned file change. Unknown keys are ignored.",
        "required": ["path", "action", "description"],
        "additionalProperties": True,
        "properties": {
            "path": {
                "type": "string",
                "description": "Repo-relative path affected by the phase.",
            },
            "action": {
                "type": "string",
                "enum": sorted(CHANGE_ACTIONS),
                "description": "Canonical change action.",
                "x-aliases": dict(sorted(CHANGE_ACTION_ALIASES.items())),
            },
            "description": {
                "type": "string",
                "minLength": 1,
                "description": "Short explanation of the intended change.",
            },
        },
    }
    failure_item = {
        "type": "object",
        "description": "Recorded phase failure. Usually tool-generated rather than authored manually.",
        "required": ["timestamp", "reason"],
        "additionalProperties": True,
        "properties": {
            "timestamp": {"type": "string", "minLength": 1},
            "reason": {"type": "string", "minLength": 1},
            "verification_results": {
                "type": "array",
                "items": verification_results_item_schema(),
            },
            "attempt": {
                "type": "integer",
                "minimum": 1,
                "default": 1,
            },
        },
    }
    phase_item = {
        "type": "object",
        "description": "Single ordered phase in the plan. Unknown keys are ignored.",
        "required": ["id", "title", "changes"],
        "additionalProperties": True,
        "properties": {
            "id": {
                "type": "string",
                "pattern": _PLAN_SLUG_PATTERN,
                "description": "Kebab-case phase identifier.",
            },
            "title": {
                "type": "string",
                "minLength": 1,
                "description": "Human-readable phase title.",
            },
            "status": {
                "type": "string",
                "enum": sorted(PHASE_STATUSES),
                "default": "pending",
            },
            "commit": {
                "type": ["string", "null"],
                "description": "Optional commit SHA recorded when the phase completes.",
            },
            "blockers": {
                "type": "array",
                "items": {"type": "string", "minLength": 1},
                "description": "Phase ids or cross-plan references that must complete first.",
            },
            "sources": {
                "type": "array",
                "items": source_item,
            },
            "postconditions": {
                "type": "array",
                "description": "Success criteria. Strings are shorthand for manual postconditions.",
                "items": {
                    "oneOf": [
                        {
                            "type": "string",
                            "minLength": 1,
                            "description": "Shorthand manual postcondition.",
                        },
                        postcondition_object,
                    ]
                },
            },
            "requires_approval": {
                "type": "boolean",
                "default": False,
                "description": "Extra HITL gate for the phase beyond change-class-based approvals.",
            },
            "changes": {
                "type": "array",
                "minItems": 1,
                "items": change_item,
            },
            "failures": {
                "type": "array",
                "items": failure_item,
            },
        },
    }
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "schema_version": 1,
        "tool_name": "memory_plan_create",
        "title": "memory_plan_create input schema",
        "type": "object",
        "required": [
            "plan_id",
            "project_id",
            "purpose_summary",
            "purpose_context",
            "phases",
            "session_id",
        ],
        "additionalProperties": False,
        "properties": {
            "plan_id": {
                "type": "string",
                "pattern": _PLAN_SLUG_PATTERN,
                "description": "Kebab-case plan identifier.",
            },
            "project_id": {
                "type": "string",
                "pattern": _PLAN_SLUG_PATTERN,
                "description": "Kebab-case project identifier.",
            },
            "purpose_summary": {
                "type": "string",
                "minLength": 1,
                "description": "Short purpose summary shown in project navigation.",
            },
            "purpose_context": {
                "type": "string",
                "minLength": 1,
                "description": "Longer context block stored in the plan document.",
            },
            "phases": {
                "type": "array",
                "minItems": 1,
                "items": phase_item,
                "description": "Ordered plan phases.",
            },
            "session_id": {
                "type": "string",
                "pattern": _SESSION_ID_PATTERN,
                "description": "Canonical origin session id.",
            },
            "questions": {
                "type": ["array", "null"],
                "items": {"type": "string", "minLength": 1},
                "description": "Optional open questions stored under purpose.questions.",
            },
            "budget": {
                "type": ["object", "null"],
                "description": "Optional execution budget.",
                "additionalProperties": True,
                "properties": {
                    "deadline": {
                        "type": "string",
                        "pattern": _DATE_RE.pattern,
                        "description": "YYYY-MM-DD deadline.",
                    },
                    "max_sessions": {
                        "type": "integer",
                        "minimum": 1,
                        "description": "Maximum session budget.",
                    },
                    "advisory": {
                        "type": "boolean",
                        "default": True,
                        "description": "Whether budget overruns are advisory or hard-gated downstream.",
                    },
                },
            },
            "status": {
                "type": "string",
                "enum": ["draft", "active"],
                "default": "active",
                "description": "Allowed initial plan status for creation.",
            },
            "preview": {
                "type": "boolean",
                "default": False,
                "description": "When true, valid requests return the normal preview envelope and invalid requests return structured validation feedback without writing.",
            },
        },
        "x-notes": [
            "Nested phase mappings currently ignore unknown keys rather than rejecting them.",
            "Canonical enum values are always serialized back to the stored plan document.",
            "Use memory_plan_schema when callers need the nested contract without guessing from validation errors.",
        ],
    }


def project_plan_path(project_id: str, plan_id: str) -> str:
    return (
        f"memory/working/projects/{validate_slug(project_id, field_name='project_id')}"
        f"/plans/{validate_slug(plan_id, field_name='plan_id')}.yaml"
    )


# Known content-prefix directories (e.g. "core/").  Used as a fallback when
# root is the repository root but project_plan_path returns content-relative
# paths, or when SourceSpec paths redundantly include the content prefix while
# root is already the content root.
_CONTENT_PREFIXES = ("core",)


def _resolve_plan_file(root: Path, project_id: str, plan_id: str) -> Path | None:
    """Locate a plan YAML, tolerating both content-root and repo-root as *root*.

    ``project_plan_path`` returns a content-relative path (``memory/working/…``).
    If *root* is the content root the direct join works.  When *root* is the
    repository root we fall back to checking known content-prefix subdirectories.
    Returns the resolved ``Path`` or ``None`` if the file cannot be found.
    """
    rel = project_plan_path(project_id, plan_id)
    direct = root / rel
    if direct.exists():
        return direct
    for prefix in _CONTENT_PREFIXES:
        candidate = root / prefix / rel
        if candidate.exists():
            return candidate
    return None


def _resolve_content_root(root: Path) -> Path:
    if (root / "memory").exists():
        return root
    for prefix in _CONTENT_PREFIXES:
        candidate = root / prefix
        if (candidate / "memory").exists():
            return candidate
    return root


def _resolve_repo_root(root: Path) -> Path:
    content_root = _resolve_content_root(root)
    if content_root.name in _CONTENT_PREFIXES:
        return content_root.parent
    return content_root


def project_operations_log_path(project_id: str) -> str:
    return (
        f"memory/working/projects/{validate_slug(project_id, field_name='project_id')}"
        "/operations.jsonl"
    )


def project_outbox_root(project_id: str, plan_id: str) -> str:
    return (
        f"memory/working/projects/OUT/{validate_slug(project_id, field_name='project_id')}"
        f"/{validate_slug(plan_id, field_name='plan_id')}"
    )


def outbox_summary_path() -> str:
    return "memory/working/projects/OUT/SUMMARY.md"


def _normalize_repo_relative_path(raw_path: str, *, field_name: str = "path") -> str:
    if not isinstance(raw_path, str) or not raw_path.strip():
        raise ValidationError(f"{field_name} must be a non-empty repo-relative path")

    normalized = raw_path.replace("\\", "/").strip()
    if normalized.startswith("/") or normalized.startswith("../") or "/../" in normalized:
        raise ValidationError(f"{field_name} must be repo-relative: {raw_path!r}")
    if re.match(r"^[A-Za-z]:[/\\]", normalized):
        raise ValidationError(f"{field_name} must be repo-relative: {raw_path!r}")
    return normalized.rstrip("/")


class _PlanDumper(yaml.SafeDumper):
    pass


def _represent_string(dumper: yaml.SafeDumper, value: str) -> yaml.nodes.ScalarNode:
    style = "|" if "\n" in value else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", value, style=style)


_PlanDumper.add_representer(str, _represent_string)


@dataclass(slots=True)
class ChangeSpec:
    path: str
    action: str
    description: str

    def __post_init__(self) -> None:
        self.path = _normalize_repo_relative_path(self.path)
        self.action = _normalize_enum_alias(self.action, CHANGE_ACTION_ALIASES)
        if self.action not in CHANGE_ACTIONS:
            raise ValidationError(
                f"change action must be one of {sorted(CHANGE_ACTIONS)}: {self.action!r}"
            )
        if not isinstance(self.description, str) or not self.description.strip():
            raise ValidationError("change description must be a non-empty string")
        self.description = self.description.strip()

    def to_dict(self) -> dict[str, str]:
        return {
            "path": self.path,
            "action": self.action,
            "description": self.description,
        }


@dataclass(slots=True)
class SourceSpec:
    """A source to read/analyze before executing phase changes."""

    path: str
    type: str
    intent: str
    uri: str | None = None
    mcp_server: str | None = None
    mcp_tool: str | None = None
    mcp_arguments: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        self.type = _normalize_enum_alias(self.type, SOURCE_TYPE_ALIASES)
        if self.type not in SOURCE_TYPES:
            raise ValidationError(
                f"source type must be one of {sorted(SOURCE_TYPES)}: {self.type!r}"
            )
        if not isinstance(self.intent, str) or not self.intent.strip():
            raise ValidationError("source intent must be a non-empty string")
        self.intent = self.intent.strip()
        if self.type == "internal":
            self.path = _normalize_repo_relative_path(self.path, field_name="source path")
        else:
            if not isinstance(self.path, str) or not self.path.strip():
                raise ValidationError("source path must be a non-empty string")
            self.path = self.path.strip()
        if self.type == "external" and not self.uri:
            raise ValidationError("external sources must include a uri")
        if self.mcp_server is not None:
            if self.type != "mcp":
                raise ValidationError("mcp_server is only valid for source type 'mcp'")
            if not isinstance(self.mcp_server, str) or not self.mcp_server.strip():
                raise ValidationError("mcp_server must be a non-empty string when provided")
            self.mcp_server = self.mcp_server.strip()
        if self.mcp_tool is not None:
            if self.type != "mcp":
                raise ValidationError("mcp_tool is only valid for source type 'mcp'")
            if not isinstance(self.mcp_tool, str) or not self.mcp_tool.strip():
                raise ValidationError("mcp_tool must be a non-empty string when provided")
            self.mcp_tool = self.mcp_tool.strip()
        if (self.mcp_server is None) != (self.mcp_tool is None):
            raise ValidationError("mcp sources must provide both mcp_server and mcp_tool")
        if self.mcp_arguments is not None:
            if self.type != "mcp":
                raise ValidationError("mcp_arguments is only valid for source type 'mcp'")
            if not isinstance(self.mcp_arguments, dict):
                raise ValidationError("mcp_arguments must be a mapping when provided")

    def validate_exists(self, root: Path) -> None:
        """Raise if this is an internal source and the file does not exist.

        Handles both conventions: paths may be content-relative (relative to
        the content root, e.g. ``tools/file.py``) or git-relative (including
        the content prefix, e.g. ``core/tools/file.py``).  When *root* is the
        content root and the path redundantly starts with the content-prefix
        directory name we strip the prefix before checking.

        Also checks the repository root (root.parent) when root is a known
        content-prefix directory, so paths like ``HUMANS/docs/DESIGN.md``
        that live outside the content prefix are found.
        """
        if self.type != "internal":
            return
        if (root / self.path).exists():
            return
        # Backward compat: path may include a content prefix that root
        # already incorporates (e.g. root="…/core", path="core/tools/…").
        first, _, rest = self.path.partition("/")
        if first and rest and root.name == first and (root / rest).exists():
            return
        # Repo-root fallback: when root is a content-prefix directory, check
        # the parent (repo root) for paths that live outside the prefix.
        if root.name in _CONTENT_PREFIXES and (root.parent / self.path).exists():
            return
        raise ValidationError(f"internal source does not exist: {self.path}")

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "path": self.path,
            "type": self.type,
            "intent": self.intent,
        }
        if self.uri is not None:
            payload["uri"] = self.uri
        if self.mcp_server is not None:
            payload["mcp_server"] = self.mcp_server
        if self.mcp_tool is not None:
            payload["mcp_tool"] = self.mcp_tool
        if self.mcp_arguments is not None:
            payload["mcp_arguments"] = self.mcp_arguments
        return payload


@dataclass(slots=True)
class PostconditionSpec:
    """A success criterion for a phase.

    Always has a free-text description. Optionally includes a formal
    validator type and target for automation.
    """

    description: str
    type: str = "manual"
    target: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.description, str) or not self.description.strip():
            raise ValidationError("postcondition description must be a non-empty string")
        self.description = self.description.strip()
        self.type = _normalize_enum_alias(self.type, POSTCONDITION_TYPE_ALIASES)
        if self.type not in POSTCONDITION_TYPES:
            raise ValidationError(
                f"postcondition type must be one of {sorted(POSTCONDITION_TYPES)}: {self.type!r}"
            )
        if self.type != "manual" and not self.target:
            raise ValidationError(f"postcondition type '{self.type}' requires a non-empty target")
        if self.target is not None:
            if not isinstance(self.target, str) or not self.target.strip():
                raise ValidationError("postcondition target must be a non-empty string")
            self.target = self.target.strip()

    def to_dict(self) -> dict[str, Any]:
        if self.type == "manual" and self.target is None:
            return {"description": self.description}
        payload: dict[str, Any] = {
            "description": self.description,
            "type": self.type,
        }
        if self.target is not None:
            payload["target"] = self.target
        return payload


@dataclass(slots=True)
class PhaseFailure:
    """Record of a failed attempt on a phase."""

    timestamp: str
    reason: str
    verification_results: list[dict[str, Any]] | None = None
    attempt: int = 1

    def __post_init__(self) -> None:
        if not isinstance(self.timestamp, str) or not self.timestamp.strip():
            raise ValidationError("failure timestamp must be a non-empty string")
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise ValidationError("failure reason must be a non-empty string")
        self.timestamp = self.timestamp.strip()
        self.reason = self.reason.strip()
        if not isinstance(self.attempt, int) or self.attempt < 1:
            raise ValidationError("failure attempt must be an integer >= 1")

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "timestamp": self.timestamp,
            "reason": self.reason,
            "attempt": self.attempt,
        }
        if self.verification_results is not None:
            payload["verification_results"] = self.verification_results
        return payload


@dataclass(slots=True)
class PlanPhase:
    id: str
    title: str
    status: str = "pending"
    commit: str | None = None
    blockers: list[str] = field(default_factory=list)
    sources: list[SourceSpec] = field(default_factory=list)
    postconditions: list[PostconditionSpec] = field(default_factory=list)
    requires_approval: bool = False
    changes: list[ChangeSpec] = field(default_factory=list)
    failures: list[PhaseFailure] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.id = validate_slug(self.id, field_name="phase_id")
        if not isinstance(self.title, str) or not self.title.strip():
            raise ValidationError("phase title must be a non-empty string")
        self.title = self.title.strip()
        if self.status not in PHASE_STATUSES:
            raise ValidationError(
                f"phase status must be one of {sorted(PHASE_STATUSES)}: {self.status!r}"
            )
        if self.commit is not None and not isinstance(self.commit, str):
            raise ValidationError("phase commit must be a string or null")
        validated_blockers: list[str] = []
        for blocker in self.blockers:
            if not isinstance(blocker, str) or not blocker.strip():
                raise ValidationError("blockers must be non-empty strings")
            validated_blockers.append(blocker.strip())
        self.blockers = validated_blockers

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": self.id,
            "title": self.title,
            "status": self.status,
            "commit": self.commit,
            "blockers": list(self.blockers),
        }
        if self.sources:
            payload["sources"] = [source.to_dict() for source in self.sources]
        if self.postconditions:
            payload["postconditions"] = [pc.to_dict() for pc in self.postconditions]
        if self.requires_approval:
            payload["requires_approval"] = True
        payload["changes"] = [change.to_dict() for change in self.changes]
        if self.failures:
            payload["failures"] = [f.to_dict() for f in self.failures]
        return payload


@dataclass(slots=True)
class PlanPurpose:
    summary: str
    context: str
    questions: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        errors: list[str] = []
        if not isinstance(self.summary, str) or not self.summary.strip():
            errors.append("purpose.summary must be a non-empty string")
        if not isinstance(self.context, str) or not self.context.strip():
            errors.append("purpose.context must be a non-empty string")
        normalized_questions: list[str] = []
        for index, question in enumerate(self.questions):
            if not isinstance(question, str) or not question.strip():
                errors.append(f"purpose.questions[{index}] must be a non-empty string")
                continue
            normalized_questions.append(question.strip())
        _raise_collected_validation_errors(errors)
        self.summary = self.summary.strip()
        self.context = self.context.strip("\n")
        self.questions = normalized_questions

    def to_dict(self) -> dict[str, Any]:
        return {
            "summary": self.summary,
            "context": self.context,
            "questions": list(self.questions),
        }


@dataclass(slots=True)
class PlanReview:
    completed: str
    completed_session: str
    outcome: str
    purpose_assessment: str
    unresolved: list[dict[str, str]] = field(default_factory=list)
    follow_up: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.completed, str) or not self.completed.strip():
            raise ValidationError("review.completed must be a non-empty date string")
        validate_session_id(self.completed_session)
        if self.outcome not in PLAN_OUTCOMES:
            raise ValidationError(
                f"review.outcome must be one of {sorted(PLAN_OUTCOMES)}: {self.outcome!r}"
            )
        if not isinstance(self.purpose_assessment, str) or not self.purpose_assessment.strip():
            raise ValidationError("review.purpose_assessment must be a non-empty string")
        normalized_unresolved: list[dict[str, str]] = []
        for item in self.unresolved:
            if not isinstance(item, dict):
                raise ValidationError("review.unresolved must contain mapping items")
            question = item.get("question")
            note = item.get("note")
            if not isinstance(question, str) or not question.strip():
                raise ValidationError("review.unresolved.question must be a non-empty string")
            if not isinstance(note, str) or not note.strip():
                raise ValidationError("review.unresolved.note must be a non-empty string")
            normalized_unresolved.append({"question": question.strip(), "note": note.strip()})
        self.unresolved = normalized_unresolved
        if self.follow_up is not None:
            self.follow_up = validate_slug(self.follow_up, field_name="follow_up")
        self.purpose_assessment = self.purpose_assessment.strip("\n")

    def to_dict(self) -> dict[str, Any]:
        return {
            "completed": self.completed,
            "completed_session": self.completed_session,
            "outcome": self.outcome,
            "purpose_assessment": self.purpose_assessment,
            "unresolved": list(self.unresolved),
            "follow_up": self.follow_up,
        }


@dataclass(slots=True)
class PlanBudget:
    """Execution budget constraints for a plan."""

    deadline: str | None = None
    max_sessions: int | None = None
    advisory: bool = True

    def __post_init__(self) -> None:
        errors: list[str] = []
        if self.deadline is not None:
            if not isinstance(self.deadline, str) or not _DATE_RE.match(self.deadline):
                errors.append(f"budget.deadline must be YYYY-MM-DD format: {self.deadline!r}")
        if self.max_sessions is not None:
            if not isinstance(self.max_sessions, int) or self.max_sessions < 1:
                errors.append("budget.max_sessions must be an integer >= 1")
        _raise_collected_validation_errors(errors)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        if self.deadline is not None:
            payload["deadline"] = self.deadline
        if self.max_sessions is not None:
            payload["max_sessions"] = self.max_sessions
        if not self.advisory:
            payload["advisory"] = False
        return payload


@dataclass(slots=True)
class PlanDocument:
    id: str
    project: str
    created: str
    origin_session: str
    status: str
    purpose: PlanPurpose
    phases: list[PlanPhase]
    review: PlanReview | None = None
    budget: PlanBudget | None = None
    sessions_used: int = 0

    def __post_init__(self) -> None:
        self.id = validate_slug(self.id, field_name="plan_id")
        self.project = validate_slug(self.project, field_name="project_id")
        validate_session_id(self.origin_session)
        if not isinstance(self.created, str) or not self.created.strip():
            raise ValidationError("created must be a non-empty date string")
        if self.status not in PLAN_STATUSES:
            raise ValidationError(
                f"plan status must be one of {sorted(PLAN_STATUSES)}: {self.status!r}"
            )
        if not self.phases:
            raise ValidationError("work.phases must contain at least one phase")
        phase_ids = [phase.id for phase in self.phases]
        if len(set(phase_ids)) != len(phase_ids):
            raise ValidationError("work.phases ids must be unique within a plan")

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": self.id,
            "project": self.project,
            "created": self.created,
            "origin_session": self.origin_session,
            "status": self.status,
        }
        if self.budget is not None:
            payload["budget"] = self.budget.to_dict()
        if self.sessions_used > 0:
            payload["sessions_used"] = self.sessions_used
        payload["purpose"] = self.purpose.to_dict()
        payload["work"] = {"phases": [phase.to_dict() for phase in self.phases]}
        payload["review"] = None if self.review is None else self.review.to_dict()
        return payload


class ChangeSpecInput(TypedDict):
    path: str
    action: str
    description: str


class _RequiredSourceSpecInput(TypedDict):
    path: str
    type: str
    intent: str


class SourceSpecInput(_RequiredSourceSpecInput, total=False):
    uri: Any
    mcp_server: Any
    mcp_tool: Any
    mcp_arguments: Any


class _RequiredPostconditionSpecInput(TypedDict):
    description: str


class PostconditionSpecInput(_RequiredPostconditionSpecInput, total=False):
    type: str
    target: Any


class _RequiredPhaseFailureInput(TypedDict):
    timestamp: str
    reason: str


class PhaseFailureInput(_RequiredPhaseFailureInput, total=False):
    verification_results: Any
    attempt: Any


class _RequiredPhaseSpecInput(TypedDict):
    id: str
    title: str
    changes: list[ChangeSpecInput]


class PhaseSpecInput(_RequiredPhaseSpecInput, total=False):
    status: str
    commit: str | None
    blockers: list[str]
    sources: list[SourceSpecInput]
    postconditions: list[PostconditionSpecInput]
    failures: list[PhaseFailureInput]
    requires_approval: bool


def _coerce_change_spec_input(raw_change: dict[str, Any]) -> ChangeSpecInput:
    return {
        "path": str(raw_change.get("path", "")),
        "action": _normalize_enum_alias(str(raw_change.get("action", "")), CHANGE_ACTION_ALIASES),
        "description": str(raw_change.get("description", "")),
    }


def _coerce_source_spec_input(raw_source: dict[str, Any]) -> SourceSpecInput:
    payload: SourceSpecInput = {
        "path": str(raw_source.get("path", "")),
        "type": _normalize_enum_alias(str(raw_source.get("type", "internal")), SOURCE_TYPE_ALIASES),
        "intent": str(raw_source.get("intent", "")),
    }
    if "uri" in raw_source:
        payload["uri"] = raw_source.get("uri")
    if "mcp_server" in raw_source:
        payload["mcp_server"] = raw_source.get("mcp_server")
    if "mcp_tool" in raw_source:
        payload["mcp_tool"] = raw_source.get("mcp_tool")
    if "mcp_arguments" in raw_source:
        payload["mcp_arguments"] = raw_source.get("mcp_arguments")
    return payload


def _coerce_postcondition_spec_input(
    raw_postcondition: str | dict[str, Any],
) -> PostconditionSpecInput:
    if isinstance(raw_postcondition, str):
        return {"description": raw_postcondition}
    payload: PostconditionSpecInput = {
        "description": str(raw_postcondition.get("description", "")),
        "type": _normalize_enum_alias(
            str(raw_postcondition.get("type", "manual")),
            POSTCONDITION_TYPE_ALIASES,
        ),
    }
    if "target" in raw_postcondition:
        payload["target"] = raw_postcondition.get("target")
    return payload


def _coerce_failure_input(raw_failure: dict[str, Any]) -> PhaseFailureInput:
    payload: PhaseFailureInput = {
        "timestamp": str(raw_failure.get("timestamp", "")),
        "reason": str(raw_failure.get("reason", "")),
    }
    if "verification_results" in raw_failure:
        payload["verification_results"] = raw_failure.get("verification_results")
    if "attempt" in raw_failure:
        attempt: Any = raw_failure.get("attempt")
        try:
            payload["attempt"] = int(attempt)
        except (TypeError, ValueError):
            payload["attempt"] = attempt
    return payload


def _coerce_change_spec_inputs(
    raw_changes: Any, *, field_path: str = "changes"
) -> list[ChangeSpecInput]:
    if not isinstance(raw_changes, list) or not raw_changes:
        raise _build_validation_error([f"{field_path}: phase changes must be a non-empty list"])
    items: list[ChangeSpecInput] = []
    errors: list[str] = []
    for index, raw_change in enumerate(raw_changes):
        item_path = f"{field_path}[{index}]"
        if not isinstance(raw_change, dict):
            errors.append(f"{item_path}: phase changes must contain mapping items")
            continue
        items.append(_coerce_change_spec_input(raw_change))
    _raise_collected_validation_errors(errors)
    return items


def _coerce_source_spec_inputs(
    raw_sources: Any, *, field_path: str = "sources"
) -> list[SourceSpecInput]:
    if raw_sources is None:
        return []
    if not isinstance(raw_sources, list):
        raise _build_validation_error([f"{field_path}: phase sources must be a list when provided"])
    items: list[SourceSpecInput] = []
    errors: list[str] = []
    for index, raw_source in enumerate(raw_sources):
        item_path = f"{field_path}[{index}]"
        if not isinstance(raw_source, dict):
            errors.append(f"{item_path}: phase sources must contain mapping items")
            continue
        items.append(_coerce_source_spec_input(raw_source))
    _raise_collected_validation_errors(errors)
    return items


def _coerce_postcondition_spec_inputs(
    raw_postconditions: Any, *, field_path: str = "postconditions"
) -> list[PostconditionSpecInput]:
    if raw_postconditions is None:
        return []
    if not isinstance(raw_postconditions, list):
        raise _build_validation_error(
            [f"{field_path}: phase postconditions must be a list when provided"]
        )
    items: list[PostconditionSpecInput] = []
    errors: list[str] = []
    for index, item in enumerate(raw_postconditions):
        item_path = f"{field_path}[{index}]"
        if isinstance(item, str) or isinstance(item, dict):
            items.append(_coerce_postcondition_spec_input(item))
            continue
        errors.append(f"{item_path}: postconditions must contain strings or mapping items")
    _raise_collected_validation_errors(errors)
    return items


def _coerce_failure_inputs(
    raw_failures: Any, *, field_path: str = "failures"
) -> list[PhaseFailureInput]:
    if raw_failures is None:
        return []
    if not isinstance(raw_failures, list):
        raise _build_validation_error(
            [f"{field_path}: phase failures must be a list when provided"]
        )
    items: list[PhaseFailureInput] = []
    errors: list[str] = []
    for index, item in enumerate(raw_failures):
        item_path = f"{field_path}[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{item_path}: phase failures must contain mapping items")
            continue
        items.append(_coerce_failure_input(item))
    _raise_collected_validation_errors(errors)
    return items


def _build_change_specs(
    change_inputs: list[ChangeSpecInput], *, field_path: str = "changes"
) -> list[ChangeSpec]:
    changes: list[ChangeSpec] = []
    errors: list[str] = []
    for index, change_input in enumerate(change_inputs):
        item_path = f"{field_path}[{index}]"
        try:
            changes.append(ChangeSpec(**change_input))
        except ValidationError as exc:
            errors.extend(_prefix_validation_errors(item_path, exc))
    _raise_collected_validation_errors(errors)
    return changes


def _build_source_specs(
    source_inputs: list[SourceSpecInput], *, field_path: str = "sources"
) -> list[SourceSpec]:
    sources: list[SourceSpec] = []
    errors: list[str] = []
    for index, source_input in enumerate(source_inputs):
        item_path = f"{field_path}[{index}]"
        try:
            sources.append(SourceSpec(**source_input))
        except ValidationError as exc:
            errors.extend(_prefix_validation_errors(item_path, exc))
    _raise_collected_validation_errors(errors)
    return sources


def _build_postconditions(
    postcondition_inputs: list[PostconditionSpecInput], *, field_path: str = "postconditions"
) -> list[PostconditionSpec]:
    specs: list[PostconditionSpec] = []
    errors: list[str] = []
    for index, postcondition_input in enumerate(postcondition_inputs):
        item_path = f"{field_path}[{index}]"
        try:
            specs.append(PostconditionSpec(**postcondition_input))
        except ValidationError as exc:
            errors.extend(_prefix_validation_errors(item_path, exc))
    _raise_collected_validation_errors(errors)
    return specs


def _build_failures(
    failure_inputs: list[PhaseFailureInput], *, field_path: str = "failures"
) -> list[PhaseFailure]:
    failures: list[PhaseFailure] = []
    errors: list[str] = []
    for index, failure_input in enumerate(failure_inputs):
        item_path = f"{field_path}[{index}]"
        try:
            failures.append(
                PhaseFailure(
                    timestamp=failure_input["timestamp"],
                    reason=failure_input["reason"],
                    verification_results=failure_input.get("verification_results"),
                    attempt=failure_input.get("attempt", len(failures) + 1),
                )
            )
        except ValidationError as exc:
            errors.extend(_prefix_validation_errors(item_path, exc))
    _raise_collected_validation_errors(errors)
    return failures


def _coerce_phase_input(raw_phase: dict[str, Any], *, field_path: str) -> PhaseSpecInput:
    phase_errors: list[str] = []
    blockers = raw_phase.get("blockers")
    if blockers is None:
        normalized_blockers: list[str] = []
    elif not isinstance(blockers, list):
        phase_errors.append(f"{field_path}.blockers: phase blockers must be a list when provided")
        normalized_blockers = []
    else:
        normalized_blockers = [str(blocker) for blocker in blockers]

    payload: PhaseSpecInput = {
        "id": str(raw_phase.get("id", "")),
        "title": str(raw_phase.get("title", "")),
        "status": str(raw_phase.get("status", "pending")),
        "commit": (
            raw_phase.get("commit")
            if raw_phase.get("commit") is None
            else str(raw_phase.get("commit"))
        ),
        "blockers": normalized_blockers,
        "requires_approval": bool(raw_phase.get("requires_approval", False)),
        "changes": [],
    }
    try:
        payload["sources"] = _coerce_source_spec_inputs(
            raw_phase.get("sources"), field_path=f"{field_path}.sources"
        )
    except ValidationError as exc:
        phase_errors.extend(validation_error_messages(exc))
    try:
        payload["postconditions"] = _coerce_postcondition_spec_inputs(
            raw_phase.get("postconditions"),
            field_path=f"{field_path}.postconditions",
        )
    except ValidationError as exc:
        phase_errors.extend(validation_error_messages(exc))
    try:
        payload["changes"] = _coerce_change_spec_inputs(
            raw_phase.get("changes"), field_path=f"{field_path}.changes"
        )
    except ValidationError as exc:
        phase_errors.extend(validation_error_messages(exc))
    try:
        payload["failures"] = _coerce_failure_inputs(
            raw_phase.get("failures"), field_path=f"{field_path}.failures"
        )
    except ValidationError as exc:
        phase_errors.extend(validation_error_messages(exc))
    _raise_collected_validation_errors(phase_errors)
    return payload


def _coerce_change_specs(raw_changes: Any, *, field_path: str = "changes") -> list[ChangeSpec]:
    return _build_change_specs(
        _coerce_change_spec_inputs(raw_changes, field_path=field_path),
        field_path=field_path,
    )


def _coerce_source_specs(raw_sources: Any, *, field_path: str = "sources") -> list[SourceSpec]:
    return _build_source_specs(
        _coerce_source_spec_inputs(raw_sources, field_path=field_path),
        field_path=field_path,
    )


def _coerce_postconditions(
    raw_postconditions: Any, *, field_path: str = "postconditions"
) -> list[PostconditionSpec]:
    return _build_postconditions(
        _coerce_postcondition_spec_inputs(raw_postconditions, field_path=field_path),
        field_path=field_path,
    )


def _coerce_failures(raw_failures: Any, *, field_path: str = "failures") -> list[PhaseFailure]:
    return _build_failures(
        _coerce_failure_inputs(raw_failures, field_path=field_path),
        field_path=field_path,
    )


def _coerce_budget(raw_budget: Any) -> PlanBudget | None:
    if raw_budget is None:
        return None
    if not isinstance(raw_budget, dict):
        raise _build_validation_error(["budget: budget must be null or a mapping"])
    deadline = raw_budget.get("deadline")
    max_sessions = raw_budget.get("max_sessions")
    advisory = raw_budget.get("advisory", True)
    coerced_max_sessions: Any = None
    if max_sessions is not None:
        try:
            coerced_max_sessions = int(max_sessions)
        except (TypeError, ValueError):
            coerced_max_sessions = max_sessions
    try:
        return PlanBudget(
            deadline=None if deadline is None else str(deadline),
            max_sessions=coerced_max_sessions,
            advisory=bool(advisory),
        )
    except ValidationError as exc:
        raise _build_validation_error(_prefix_validation_errors("budget", exc)) from exc


def _coerce_phases(raw_phases: Any) -> list[PlanPhase]:
    if not isinstance(raw_phases, list) or not raw_phases:
        raise _build_validation_error(["work.phases must be a non-empty list"])
    phases: list[PlanPhase] = []
    errors: list[str] = []
    for index, raw_phase in enumerate(raw_phases):
        phase_path = f"work.phases[{index}]"
        if not isinstance(raw_phase, dict):
            errors.append(f"{phase_path}: work.phases must contain mapping items")
            continue
        phase_errors: list[str] = []
        phase_input: PhaseSpecInput | None = None
        sources: list[SourceSpec] = []
        postconditions: list[PostconditionSpec] = []
        changes: list[ChangeSpec] = []
        failures: list[PhaseFailure] = []
        try:
            phase_input = _coerce_phase_input(raw_phase, field_path=phase_path)
        except ValidationError as exc:
            phase_errors.extend(validation_error_messages(exc))
        if phase_input is not None:
            try:
                sources = _build_source_specs(
                    phase_input.get("sources", []),
                    field_path=f"{phase_path}.sources",
                )
            except ValidationError as exc:
                phase_errors.extend(validation_error_messages(exc))
            try:
                postconditions = _build_postconditions(
                    phase_input.get("postconditions", []),
                    field_path=f"{phase_path}.postconditions",
                )
            except ValidationError as exc:
                phase_errors.extend(validation_error_messages(exc))
            try:
                changes = _build_change_specs(
                    phase_input["changes"],
                    field_path=f"{phase_path}.changes",
                )
            except ValidationError as exc:
                phase_errors.extend(validation_error_messages(exc))
            try:
                failures = _build_failures(
                    phase_input.get("failures", []),
                    field_path=f"{phase_path}.failures",
                )
            except ValidationError as exc:
                phase_errors.extend(validation_error_messages(exc))
        if phase_input is not None:
            try:
                phase = PlanPhase(
                    id=phase_input["id"],
                    title=phase_input["title"],
                    status=phase_input.get("status", "pending"),
                    commit=phase_input.get("commit"),
                    blockers=phase_input.get("blockers", []),
                    sources=sources,
                    postconditions=postconditions,
                    requires_approval=phase_input.get("requires_approval", False),
                    changes=changes,
                    failures=failures,
                )
            except ValidationError as exc:
                phase_errors.extend(_prefix_validation_errors(phase_path, exc))
                phase = None
        else:
            phase = None
        if phase_errors:
            errors.extend(phase_errors)
            continue
        if phase is not None:
            phases.append(phase)
    _raise_collected_validation_errors(errors)
    return phases


def _coerce_review(raw_review: Any) -> PlanReview | None:
    if raw_review is None:
        return None
    if not isinstance(raw_review, dict):
        raise ValidationError("review must be null or a mapping")
    unresolved = raw_review.get("unresolved") or []
    if not isinstance(unresolved, list):
        raise ValidationError("review.unresolved must be a list")
    follow_up = raw_review.get("follow_up")
    return PlanReview(
        completed=str(raw_review.get("completed", "")),
        completed_session=str(raw_review.get("completed_session", "")),
        outcome=str(raw_review.get("outcome", "")),
        purpose_assessment=str(raw_review.get("purpose_assessment", "")),
        unresolved=[dict(item) for item in unresolved],
        follow_up=None if follow_up is None else str(follow_up),
    )


def load_plan(abs_path: Path, root: Path | None = None) -> PlanDocument:
    try:
        raw = yaml.safe_load(abs_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValidationError(f"Invalid YAML plan file: {abs_path.name}: {exc}") from exc

    if not isinstance(raw, dict):
        raise ValidationError(f"Plan file must contain a top-level mapping: {abs_path.name}")

    purpose = raw.get("purpose")
    if not isinstance(purpose, dict):
        raise ValidationError("purpose must be a mapping")
    work = raw.get("work")
    if not isinstance(work, dict):
        raise ValidationError("work must be a mapping")

    plan = PlanDocument(
        id=str(raw.get("id", "")),
        project=str(raw.get("project", "")),
        created=str(raw.get("created", "")),
        origin_session=str(raw.get("origin_session", "")),
        status=str(raw.get("status", "")),
        purpose=PlanPurpose(
            summary=str(purpose.get("summary", "")),
            context=str(purpose.get("context", "")),
            questions=[str(item) for item in purpose.get("questions", []) or []],
        ),
        phases=_coerce_phases(work.get("phases")),
        review=_coerce_review(raw.get("review")),
        budget=_coerce_budget(raw.get("budget")),
        sessions_used=int(raw.get("sessions_used", 0)),
    )
    if root is not None:
        validate_plan_references(plan, root)
    return plan


def save_plan(abs_path: Path, plan: PlanDocument, root: Path | None = None) -> None:
    if root is not None:
        validate_plan_references(plan, root)
    abs_path.parent.mkdir(parents=True, exist_ok=True)
    text = yaml.dump(
        plan.to_dict(),
        Dumper=_PlanDumper,
        sort_keys=False,
        allow_unicode=False,
        width=88,
    )
    abs_path.write_text(text, encoding="utf-8")


def _resolve_phase(plan: PlanDocument, phase_id: str) -> PlanPhase:
    for phase in plan.phases:
        if phase.id == phase_id:
            return phase
    raise NotFoundError(f"Plan '{plan.id}' does not define phase '{phase_id}'")


def validate_plan_references(plan: PlanDocument, root: Path) -> None:
    for phase in plan.phases:
        for blocker in phase.blockers:
            if ":" not in blocker:
                _resolve_phase(plan, blocker)
                continue
            other_plan_id, other_phase_id = blocker.split(":", 1)
            other_plan_path = _resolve_plan_file(root, plan.project, other_plan_id)
            if other_plan_path is None:
                raise ValidationError(
                    f"blocker references missing plan '{other_plan_id}' in project '{plan.project}'"
                )
            other_plan = load_plan(other_plan_path)
            _resolve_phase(other_plan, other_phase_id)
        for source in phase.sources:
            source.validate_exists(root)


def plan_title(plan: PlanDocument) -> str:
    return plan.purpose.summary


def plan_progress(plan: PlanDocument) -> tuple[int, int]:
    completed = sum(1 for phase in plan.phases if phase.status == "completed")
    return completed, len(plan.phases)


def next_phase(plan: PlanDocument) -> PlanPhase | None:
    for phase in plan.phases:
        if phase.status in {"pending", "blocked", "in-progress"}:
            return phase
    return None


def next_action(plan: PlanDocument) -> dict[str, Any] | None:
    """Return a structured directive for the next actionable phase.

    Returns a dict with id, title, sources, requires_approval so the
    calling agent knows what to read and whether to pause for approval.
    """
    phase = next_phase(plan)
    if phase is None:
        return None
    directive: dict[str, Any] = {
        "id": phase.id,
        "title": phase.title,
        "requires_approval": phase.requires_approval,
    }
    if phase.sources:
        directive["sources"] = [source.to_dict() for source in phase.sources]
    if phase.postconditions:
        directive["postconditions"] = [pc.to_dict() for pc in phase.postconditions]
    attempt_number = len(phase.failures) + 1
    directive["attempt_number"] = attempt_number
    directive["has_prior_failures"] = bool(phase.failures)
    if len(phase.failures) >= 3:
        directive["suggest_revision"] = True
    return directive


def phase_change_class(phase: PlanPhase) -> str:
    for change in phase.changes:
        if not change.path.startswith("memory/"):
            return "protected"
    return "proposed"


def phase_blockers(
    plan: PlanDocument,
    phase: PlanPhase,
    root: Path,
) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    for index, candidate in enumerate(plan.phases):
        if candidate.id != phase.id:
            continue
        if index > 0:
            previous = plan.phases[index - 1]
            satisfied = previous.status in {"completed", "skipped"}
            blockers.append(
                {
                    "reference": previous.id,
                    "kind": "implicit",
                    "satisfied": satisfied,
                    "status": previous.status,
                    "commit": previous.commit,
                    "detail": previous.title,
                }
            )
        break

    for blocker in phase.blockers:
        if ":" not in blocker:
            other_phase = _resolve_phase(plan, blocker)
            blockers.append(
                {
                    "reference": blocker,
                    "kind": "intra-plan",
                    "satisfied": other_phase.status in {"completed", "skipped"},
                    "status": other_phase.status,
                    "commit": other_phase.commit,
                    "detail": other_phase.title,
                }
            )
            continue

        other_plan_id, other_phase_id = blocker.split(":", 1)
        other_plan_path = _resolve_plan_file(root, plan.project, other_plan_id)
        if other_plan_path is None:
            blockers.append(
                {
                    "reference": blocker,
                    "kind": "inter-plan",
                    "satisfied": False,
                    "status": "missing-plan",
                    "commit": None,
                    "detail": f"Missing plan {other_plan_id}",
                }
            )
            continue
        other_plan = load_plan(other_plan_path)
        other_phase = _resolve_phase(other_plan, other_phase_id)
        blockers.append(
            {
                "reference": blocker,
                "kind": "inter-plan",
                "satisfied": other_phase.status in {"completed", "skipped"}
                and bool(other_phase.commit),
                "status": other_phase.status,
                "commit": other_phase.commit,
                "detail": other_phase.title,
            }
        )
    return blockers


def unresolved_blockers(plan: PlanDocument, phase: PlanPhase, root: Path) -> list[dict[str, Any]]:
    return [entry for entry in phase_blockers(plan, phase, root) if not entry["satisfied"]]


def budget_status(plan: PlanDocument) -> dict[str, Any] | None:
    """Return budget consumption info, or None if no budget is set."""
    if plan.budget is None:
        return None
    status: dict[str, Any] = {
        "sessions_used": plan.sessions_used,
        "advisory": plan.budget.advisory,
    }
    if plan.budget.deadline is not None:
        from datetime import date as date_type

        try:
            deadline = date_type.fromisoformat(plan.budget.deadline)
            today = date_type.today()
            status["deadline"] = plan.budget.deadline
            status["days_remaining"] = (deadline - today).days
            status["past_deadline"] = today > deadline
        except ValueError:
            status["deadline"] = plan.budget.deadline
            status["days_remaining"] = None
            status["past_deadline"] = False
    if plan.budget.max_sessions is not None:
        status["max_sessions"] = plan.budget.max_sessions
        status["sessions_remaining"] = plan.budget.max_sessions - plan.sessions_used
        status["over_session_budget"] = plan.sessions_used >= plan.budget.max_sessions
    status["over_budget"] = status.get("past_deadline", False) or status.get(
        "over_session_budget", False
    )
    return status


def phase_payload(plan: PlanDocument, phase: PlanPhase, root: Path) -> dict[str, Any]:
    blockers = phase_blockers(plan, phase, root)
    phase_dict: dict[str, Any] = {
        "id": phase.id,
        "title": phase.title,
        "status": phase.status,
        "commit": phase.commit,
        "blockers": blockers,
        "changes": [change.to_dict() for change in phase.changes],
        "change_class": phase_change_class(phase),
        "approval_required": (
            phase.requires_approval or phase_change_class(phase) in {"proposed", "protected"}
        ),
        "requires_approval": phase.requires_approval,
    }
    if phase.sources:
        phase_dict["sources"] = [source.to_dict() for source in phase.sources]
    if phase.postconditions:
        phase_dict["postconditions"] = [pc.to_dict() for pc in phase.postconditions]
    phase_dict["failures"] = [f.to_dict() for f in phase.failures]
    phase_dict["attempt_number"] = len(phase.failures) + 1

    result: dict[str, Any] = {
        "plan_id": plan.id,
        "project_id": plan.project,
        "plan_status": plan.status,
        "phase": phase_dict,
        "purpose": plan.purpose.to_dict(),
        "progress": {
            "done": plan_progress(plan)[0],
            "total": plan_progress(plan)[1],
            "next_action": next_action(plan),
        },
    }
    bs = budget_status(plan)
    if bs is not None:
        result["budget_status"] = bs
    result["tool_policies"] = _resolve_tool_policies(phase, root)
    fetch_directives: list[dict[str, Any]] = []
    mcp_calls: list[dict[str, Any]] = []
    for index, source in enumerate(phase.sources):
        if _resolve_verify_path(root, source.path) is not None:
            continue
        if source.type == "external":
            fetch_directives.append(
                {
                    "source_index": index,
                    "action": "fetch_and_stage",
                    "source_path": source.path,
                    "source_uri": source.uri,
                    "suggested_filename": Path(source.path).name or source.path,
                    "target_project": plan.project,
                    "intent": source.intent,
                    "reason": (
                        "Source file does not exist on disk; fetch and stage before "
                        "starting phase work."
                    ),
                }
            )
        elif source.type == "mcp" and source.mcp_server and source.mcp_tool:
            mcp_calls.append(
                {
                    "source_index": index,
                    "server": source.mcp_server,
                    "tool": source.mcp_tool,
                    "arguments": source.mcp_arguments or {},
                    "source_path": source.path,
                    "suggested_filename": Path(source.path).name or source.path,
                    "target_project": plan.project,
                    "intent": source.intent,
                }
            )
    result["fetch_directives"] = fetch_directives
    result["mcp_calls"] = mcp_calls
    return result


def _serialized_length(value: Any) -> int:
    try:
        return len(json.dumps(value, ensure_ascii=False, sort_keys=True))
    except TypeError:
        return len(str(value))


def _truncate_briefing_text(text: str, limit: int) -> tuple[str, bool]:
    if limit <= 0:
        return "", bool(text)
    if len(text) <= limit:
        return text, False

    marker = "\n...\n"
    if limit <= len(marker) + 20:
        return text[:limit], True

    head = max(1, (limit - len(marker)) // 2)
    tail = max(1, limit - len(marker) - head)
    return f"{text[:head]}{marker}{text[-tail:]}", True


def _allocate_source_budgets(lengths: list[int], total_budget: int) -> list[int]:
    if not lengths:
        return []
    if total_budget <= 0:
        return [0] * len(lengths)

    total_length = sum(lengths)
    if total_length <= total_budget:
        return list(lengths)

    minimum = 200
    count = len(lengths)
    if total_budget < minimum * count:
        even_share = total_budget // count
        return [min(length, even_share) for length in lengths]

    budgets = [min(length, minimum) for length in lengths]
    remaining = total_budget - sum(budgets)
    desired = [max(length - budget, 0) for length, budget in zip(lengths, budgets, strict=False)]
    desired_total = sum(desired)

    if remaining <= 0 or desired_total <= 0:
        return budgets

    allocations = [0] * count
    allocated = 0
    for index, want in enumerate(desired):
        share = min(want, (remaining * want) // desired_total)
        allocations[index] = share
        allocated += share

    leftover = remaining - allocated
    for index, want in sorted(enumerate(desired), key=lambda item: item[1], reverse=True):
        if leftover <= 0:
            break
        spare = want - allocations[index]
        if spare <= 0:
            continue
        bump = min(spare, leftover)
        allocations[index] += bump
        leftover -= bump

    return [
        min(length, budget + allocations[index])
        for index, (length, budget) in enumerate(zip(lengths, budgets, strict=False))
    ]


def _failure_summary(phase: PlanPhase) -> list[dict[str, Any]]:
    summary: list[dict[str, Any]] = []
    for failure in reversed(phase.failures):
        entry = {
            "attempt": failure.attempt,
            "timestamp": failure.timestamp,
            "reason": failure.reason,
        }
        failed_postconditions: list[str] = []
        for result in failure.verification_results or []:
            status = str(result.get("status", ""))
            if status not in {"fail", "error"}:
                continue
            description = result.get("description") or result.get("target") or result.get("type")
            if description is not None:
                failed_postconditions.append(str(description))
        if failed_postconditions:
            entry["failed_postconditions"] = failed_postconditions
        summary.append(entry)
    return summary


def _collect_recent_plan_traces(
    root: Path,
    plan_id: str,
    *,
    session_id: str | None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    def _matching_from_files(trace_files: list[Path]) -> list[dict[str, Any]]:
        spans: list[dict[str, Any]] = []
        for trace_file in trace_files:
            try:
                lines = trace_file.read_text(encoding="utf-8").splitlines()
            except OSError:
                continue
            for raw_line in reversed(lines):
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    span = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(span, dict):
                    continue
                metadata = span.get("metadata")
                if not isinstance(metadata, dict) or metadata.get("plan_id") != plan_id:
                    continue
                spans.append(
                    {
                        "span_type": span.get("span_type"),
                        "name": span.get("name"),
                        "status": span.get("status"),
                        "duration_ms": span.get("duration_ms"),
                        "timestamp": span.get("timestamp"),
                    }
                )
                if len(spans) >= limit:
                    return spans
        return spans

    preferred_files: list[Path] = []
    seen_files: set[Path] = set()
    if session_id:
        preferred = root / trace_file_path(session_id)
        if preferred.exists():
            preferred_files.append(preferred)
            seen_files.add(preferred)

    preferred_spans = _matching_from_files(preferred_files)
    if preferred_spans:
        return preferred_spans[:limit]

    activity_root = root / "memory" / "activity"
    if not activity_root.is_dir():
        return []

    fallback_files = [
        trace_file
        for trace_file in sorted(activity_root.rglob("*.traces.jsonl"), reverse=True)
        if trace_file not in seen_files
    ]
    return _matching_from_files(fallback_files)[:limit]


def assemble_briefing(
    plan: PlanDocument,
    phase: PlanPhase,
    root: Path,
    *,
    max_context_chars: int = 8000,
    include_sources: bool = True,
    include_traces: bool = True,
    include_approval: bool = True,
    session_id: str | None = None,
) -> dict[str, Any]:
    """Assemble a single-call briefing packet for a plan phase."""
    if max_context_chars < 0:
        raise ValidationError("max_context_chars must be >= 0")

    phase_section = phase_payload(plan, phase, root)
    failure_summary = _failure_summary(phase)

    approval_status: dict[str, Any] | None = None
    if include_approval and phase.requires_approval:
        approval = load_approval(root, plan.id, phase.id)
        if approval is not None:
            approval_status = approval.to_dict()

    recent_traces: list[dict[str, Any]] = []
    trace_truncated = False
    if include_traces:
        recent_traces = _collect_recent_plan_traces(root, plan.id, session_id=session_id)
        if max_context_chars > 0:
            trace_budget = max(0, int(max_context_chars * 0.15))
            while recent_traces and _serialized_length(recent_traces) > trace_budget:
                recent_traces.pop()
                trace_truncated = True

    run_state_section: dict[str, Any] | None = None
    rs = load_run_state(root, plan.project, plan.id)
    if rs is not None:
        phase_outputs = (
            rs.phase_states[phase.id].intermediate_outputs if phase.id in rs.phase_states else []
        )
        run_state_section = {
            "current_task": rs.current_task,
            "next_action_hint": rs.next_action_hint,
            "last_checkpoint": rs.last_checkpoint,
            "error_context": (None if rs.error_context is None else rs.error_context.to_dict()),
            "intermediate_outputs": phase_outputs,
        }

    phase_chars = _serialized_length(phase_section)
    failure_chars = _serialized_length(failure_summary)
    approval_chars = _serialized_length(approval_status) if approval_status is not None else 0
    trace_chars = _serialized_length(recent_traces)
    run_state_chars = _serialized_length(run_state_section) if run_state_section is not None else 0

    source_contents: list[dict[str, Any]] = []
    internal_sources: list[tuple[dict[str, Any], str]] = []
    if include_sources:
        for source in phase.sources:
            entry: dict[str, Any] = {
                "path": source.path,
                "type": source.type,
                "intent": source.intent,
            }
            if source.uri is not None:
                entry["uri"] = source.uri
            if source.mcp_server is not None:
                entry["mcp_server"] = source.mcp_server
            if source.mcp_tool is not None:
                entry["mcp_tool"] = source.mcp_tool
            if source.mcp_arguments is not None:
                entry["mcp_arguments"] = source.mcp_arguments

            if source.type != "internal":
                entry["content"] = None
                source_contents.append(entry)
                continue

            resolved = _resolve_verify_path(root, source.path)
            if resolved is None or not resolved.is_file():
                entry["content"] = None
                entry["error"] = "file not found"
                source_contents.append(entry)
                continue

            try:
                text = resolved.read_text(encoding="utf-8")
            except OSError as exc:
                entry["content"] = None
                entry["error"] = str(exc)
                source_contents.append(entry)
                continue

            internal_sources.append((entry, text))

        source_budget = 0
        if max_context_chars == 0:
            source_budgets = [len(text) for _, text in internal_sources]
        else:
            fixed_chars = (
                phase_chars + failure_chars + approval_chars + trace_chars + run_state_chars
            )
            source_budget = max(max_context_chars - fixed_chars, 0)
            source_budgets = _allocate_source_budgets(
                [len(text) for _, text in internal_sources],
                source_budget,
            )

        for (entry, text), budget in zip(internal_sources, source_budgets, strict=False):
            content = text
            truncated = False
            if max_context_chars != 0:
                content, truncated = _truncate_briefing_text(text, budget)
            entry["content"] = content
            entry["full_length"] = len(text)
            entry["truncated"] = truncated
            source_contents.append(entry)

    source_chars = _serialized_length(source_contents)
    total_chars = (
        phase_chars + failure_chars + approval_chars + trace_chars + source_chars + run_state_chars
    )
    truncated = trace_truncated or any(entry.get("truncated") for entry in source_contents)

    return {
        "plan_id": plan.id,
        "project_id": plan.project,
        "phase_id": phase.id,
        "phase": phase_section,
        "source_contents": source_contents,
        "failure_summary": failure_summary,
        "recent_traces": recent_traces,
        "approval_status": approval_status,
        "run_state": run_state_section,
        "context_budget": {
            "max_context_chars": max_context_chars,
            "total_chars": total_chars,
            "estimated_tokens": (total_chars + 3) // 4,
            "truncated": truncated,
            "breakdown": {
                "phase": phase_chars,
                "source_contents": source_chars,
                "failure_summary": failure_chars,
                "recent_traces": trace_chars,
                "approval_status": approval_chars,
                "run_state": run_state_chars,
            },
        },
    }


_MAX_STAGED_EXTERNAL_CHARS = 500_000


def _project_root(root: Path, project_id: str) -> Path:
    project_slug = validate_slug(project_id, field_name="project_id")
    content_root = _resolve_content_root(root)
    return content_root / "memory" / "working" / "projects" / project_slug


def _sanitize_origin_url(source_url: str) -> str:
    from urllib.parse import urlsplit, urlunsplit

    if not isinstance(source_url, str) or not source_url.strip():
        raise ValidationError("source_url must be a non-empty string")
    parts = urlsplit(source_url.strip())
    if not parts.scheme:
        raise ValidationError("source_url must include a URI scheme")
    if parts.scheme != "file" and not parts.netloc:
        raise ValidationError("source_url must include a network location")
    sanitized = urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))
    if not sanitized:
        raise ValidationError("source_url could not be sanitized")
    return sanitized


def _normalize_staged_filename(filename: str) -> str:
    if not isinstance(filename, str) or not filename.strip():
        raise ValidationError("filename must be a non-empty string")
    normalized = filename.replace("\\", "/").strip()
    if normalized in {".", ".."} or "/" in normalized:
        raise ValidationError("filename must not include directory segments")
    return normalized


def _staged_hash_registry_path(root: Path, project_id: str) -> Path:
    return _project_root(root, project_id) / ".staged-hashes.jsonl"


def _read_staged_hash_registry(root: Path, project_id: str) -> dict[str, str]:
    registry_path = _staged_hash_registry_path(root, project_id)
    if not registry_path.exists():
        return {}
    registry: dict[str, str] = {}
    try:
        lines = registry_path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ValidationError(f"Could not read staged hash registry: {exc}") from exc
    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValidationError(f"Invalid staged hash registry entry: {exc}") from exc
        if not isinstance(entry, dict):
            continue
        content_hash = entry.get("hash")
        filename = entry.get("filename")
        if isinstance(content_hash, str) and isinstance(filename, str):
            registry[content_hash] = filename
    return registry


def stage_external_file(
    project: str,
    filename: str,
    content: str,
    source_url: str,
    fetched_date: str,
    source_label: str,
    *,
    root: Path,
    session_id: str | None = None,
    dry_run: bool = False,
    reflects_upstream_as_of: str | None = None,
) -> dict[str, Any]:
    """Stage external content into a project IN/ folder with governed frontmatter.

    Frontmatter records two freshness axes:

    - ``fetched_date`` / ``snapshot_taken_at`` — when this snapshot was captured
      into IN/. They are normally the same; ``snapshot_taken_at`` is kept as a
      distinct field so tooling that reasons about snapshot age has a stable
      name independent of the callers' ``fetched_date`` semantics.
    - ``reflects_upstream_as_of`` — optional caller-supplied marker describing
      the upstream state the snapshot reflects (e.g. a commit sha, release tag,
      or ISO date). Included verbatim when provided; omitted when absent so
      legacy readers are not forced to interpret an empty string.
    """
    import hashlib

    if not isinstance(content, str) or not content:
        raise ValidationError("content must be a non-empty string")
    if len(content) > _MAX_STAGED_EXTERNAL_CHARS:
        raise ValidationError(
            f"content exceeds maximum size of {_MAX_STAGED_EXTERNAL_CHARS} characters"
        )
    if not isinstance(fetched_date, str) or not _DATE_RE.match(fetched_date.strip()):
        raise ValidationError("fetched_date must be in YYYY-MM-DD format")
    if not isinstance(source_label, str) or not source_label.strip():
        raise ValidationError("source_label must be a non-empty string")
    if reflects_upstream_as_of is not None:
        if not isinstance(reflects_upstream_as_of, str) or not reflects_upstream_as_of.strip():
            raise ValidationError(
                "reflects_upstream_as_of must be a non-empty string when provided"
            )
    if session_id is not None:
        validate_session_id(session_id)

    project_root = _project_root(root, project)
    if not project_root.exists():
        raise NotFoundError(f"Project not found: memory/working/projects/{project}")

    staged_filename = _normalize_staged_filename(filename)
    sanitized_url = _sanitize_origin_url(source_url)
    content_hash = f"sha256:{hashlib.sha256(content.encode('utf-8')).hexdigest()}"
    registry = _read_staged_hash_registry(root, project)
    if content_hash in registry:
        raise DuplicateContentError(
            f"Duplicate staged content already exists: {registry[content_hash]}",
            content_hash=content_hash,
            existing_filename=registry[content_hash],
        )

    target_path = project_root / "IN" / staged_filename
    if target_path.exists():
        raise ValidationError(f"target file already exists: {target_path.name}")

    normalized_fetched_date = fetched_date.strip()
    frontmatter_preview: dict[str, Any] = {
        "source": "external-research",
        "trust": "low",
        "origin_url": sanitized_url,
        "fetched_date": normalized_fetched_date,
        "snapshot_taken_at": normalized_fetched_date,
        "source_label": source_label.strip(),
        "created": date_type.today().isoformat(),
        "origin_session": session_id or "unknown",
        "staged_by": "memory_stage_external",
    }
    if reflects_upstream_as_of is not None:
        frontmatter_preview["reflects_upstream_as_of"] = reflects_upstream_as_of.strip()
    envelope = {
        "action": "stage_external",
        "project": validate_slug(project, field_name="project_id"),
        "target_path": target_path.relative_to(_resolve_content_root(root)).as_posix(),
        "frontmatter_preview": frontmatter_preview,
        "content_chars": len(content),
        "content_hash": content_hash,
        "duplicate": False,
        "staged": False,
    }
    if dry_run:
        return envelope

    target_path.parent.mkdir(parents=True, exist_ok=True)
    frontmatter_text = yaml.dump(
        frontmatter_preview,
        Dumper=_PlanDumper,
        sort_keys=False,
        allow_unicode=False,
        width=88,
    )
    body = content if content.endswith("\n") else f"{content}\n"
    target_path.write_text(f"---\n{frontmatter_text}---\n\n{body}", encoding="utf-8")

    registry_path = _staged_hash_registry_path(root, project)
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    staged_at = date_type.today().isoformat()
    with registry_path.open("a", encoding="utf-8") as handle:
        handle.write(
            json.dumps(
                {
                    "hash": content_hash,
                    "filename": staged_filename,
                    "staged_at": staged_at,
                },
                ensure_ascii=False,
            )
            + "\n"
        )
    envelope["staged"] = True
    return envelope


def _read_watch_folders(root: Path) -> list[dict[str, Any]]:
    import tomllib

    repo_root = _resolve_repo_root(root)
    bootstrap_path = repo_root / "agent-bootstrap.toml"
    if not bootstrap_path.exists():
        return []
    try:
        raw = tomllib.loads(bootstrap_path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ValidationError(f"Could not load agent-bootstrap.toml: {exc}") from exc
    watch_folders = raw.get("watch_folders", [])
    if watch_folders is None:
        return []
    if not isinstance(watch_folders, list):
        raise ValidationError("watch_folders must be an array of tables")
    normalized: list[dict[str, Any]] = []
    for item in watch_folders:
        if not isinstance(item, dict):
            raise ValidationError("watch_folders entries must be mappings")
        normalized.append(item)
    return normalized


def _extract_pdf_text(abs_path: Path) -> tuple[str | None, str | None]:
    try:
        from pypdf import PdfReader  # type: ignore[import-not-found]

        reader = PdfReader(str(abs_path))
        text = "\n".join(page.extract_text() or "" for page in reader.pages).strip()
        if not text:
            return None, "PDF extraction produced no text"
        return text, None
    except ModuleNotFoundError:
        pass
    except Exception as exc:  # noqa: BLE001
        return None, f"PDF extraction failed: {exc}"

    try:
        from pdfminer.high_level import extract_text  # type: ignore[import-not-found]

        text = extract_text(str(abs_path)).strip()
        if not text:
            return None, "PDF extraction produced no text"
        return text, None
    except ModuleNotFoundError:
        return None, "PDF extraction unavailable; install pdfminer.six or pypdf"
    except Exception as exc:  # noqa: BLE001
        return None, f"PDF extraction failed: {exc}"


def scan_drop_zone(
    *,
    root: Path,
    project_filter: str | None = None,
    session_id: str | None = None,
) -> dict[str, Any]:
    """Scan configured watch folders and stage new content into project inboxes."""
    repo_root = _resolve_repo_root(root)
    watch_folders = _read_watch_folders(root)
    if project_filter is not None:
        project_filter = validate_slug(project_filter, field_name="project_filter")

    items: list[dict[str, Any]] = []
    folders_scanned = 0
    files_found = 0
    staged_count = 0
    duplicate_count = 0
    error_count = 0

    for entry in watch_folders:
        target_project = validate_slug(
            str(entry.get("target_project", "")), field_name="target_project"
        )
        if project_filter is not None and target_project != project_filter:
            continue
        raw_path = str(entry.get("path", "")).strip()
        if not raw_path:
            error_count += 1
            items.append(
                {
                    "filename": "",
                    "target_project": target_project,
                    "outcome": "error",
                    "hash": None,
                    "error_message": "watch_folders entry is missing path",
                }
            )
            continue
        folder_path = Path(raw_path)
        if not folder_path.is_absolute():
            folder_path = (repo_root / folder_path).resolve()
        else:
            folder_path = folder_path.resolve()

        try:
            folder_path.relative_to(repo_root)
            inside_repo = True
        except ValueError:
            inside_repo = False
        if inside_repo:
            error_count += 1
            items.append(
                {
                    "filename": folder_path.name,
                    "target_project": target_project,
                    "outcome": "error",
                    "hash": None,
                    "error_message": "watch_folder cannot point inside the Engram repository",
                }
            )
            continue

        folders_scanned += 1
        if not folder_path.exists() or not folder_path.is_dir():
            error_count += 1
            items.append(
                {
                    "filename": folder_path.name,
                    "target_project": target_project,
                    "outcome": "error",
                    "hash": None,
                    "error_message": f"watch_folder not found: {folder_path}",
                }
            )
            continue

        source_label = str(entry.get("source_label", "")).strip() or folder_path.name
        recursive = bool(entry.get("recursive", False))
        extensions = entry.get("extensions") or [".md", ".txt", ".pdf"]
        if not isinstance(extensions, list):
            raise ValidationError("watch_folders.extensions must be a list when provided")
        normalized_extensions = {str(ext).lower() for ext in extensions}
        iterator = folder_path.rglob("*") if recursive else folder_path.glob("*")

        for abs_file in sorted(path for path in iterator if path.is_file()):
            if abs_file.suffix.lower() not in normalized_extensions:
                continue
            files_found += 1
            try:
                if abs_file.suffix.lower() == ".pdf":
                    content, error_message = _extract_pdf_text(abs_file)
                    if content is None:
                        error_count += 1
                        items.append(
                            {
                                "filename": abs_file.name,
                                "target_project": target_project,
                                "outcome": "error",
                                "hash": None,
                                "error_message": error_message,
                            }
                        )
                        continue
                    stage_filename = f"{abs_file.stem}.md"
                else:
                    content = abs_file.read_text(encoding="utf-8", errors="replace")
                    stage_filename = abs_file.name

                envelope = stage_external_file(
                    target_project,
                    stage_filename,
                    content,
                    abs_file.resolve().as_uri(),
                    date_type.fromtimestamp(abs_file.stat().st_mtime).isoformat(),
                    source_label,
                    root=root,
                    session_id=session_id,
                    dry_run=False,
                )
                staged_count += 1
                items.append(
                    {
                        "filename": abs_file.name,
                        "target_project": target_project,
                        "outcome": "staged",
                        "hash": envelope["content_hash"],
                        "error_message": None,
                    }
                )
            except DuplicateContentError as exc:
                duplicate_count += 1
                items.append(
                    {
                        "filename": abs_file.name,
                        "target_project": target_project,
                        "outcome": "duplicate",
                        "hash": exc.content_hash or None,
                        "error_message": exc.existing_filename or str(exc),
                    }
                )
            except (OSError, ValidationError, NotFoundError) as exc:
                error_count += 1
                items.append(
                    {
                        "filename": abs_file.name,
                        "target_project": target_project,
                        "outcome": "error",
                        "hash": None,
                        "error_message": str(exc),
                    }
                )

    return {
        "folders_scanned": folders_scanned,
        "files_found": files_found,
        "staged_count": staged_count,
        "duplicate_count": duplicate_count,
        "error_count": error_count,
        "items": items,
    }


def resolve_phase(plan: PlanDocument, phase_id: str | None = None) -> PlanPhase:
    if phase_id is not None:
        return _resolve_phase(plan, validate_slug(phase_id, field_name="phase_id"))
    phase = next_phase(plan)
    if phase is None:
        raise NotFoundError(f"Plan '{plan.id}' has no pending phases")
    return phase


def build_review_from_input(
    raw_review: dict[str, Any], completed: str, session_id: str
) -> PlanReview:
    return PlanReview(
        completed=completed,
        completed_session=session_id,
        outcome=str(raw_review.get("outcome", "completed")),
        purpose_assessment=str(raw_review.get("purpose_assessment", "")),
        unresolved=[dict(item) for item in raw_review.get("unresolved", []) or []],
        follow_up=(
            None if raw_review.get("follow_up") is None else str(raw_review.get("follow_up"))
        ),
    )


def coerce_phase_inputs(phases: list[dict[str, Any]]) -> list[PlanPhase]:
    return _coerce_phases(phases)


def coerce_budget_input(raw_budget: dict[str, Any] | None) -> PlanBudget | None:
    """Public wrapper for budget coercion from tool-layer dicts."""
    return _coerce_budget(raw_budget)


def raise_collected_validation_errors(errors: list[str]) -> None:
    """Raise a single ValidationError carrying every collected message."""
    _raise_collected_validation_errors(errors)


def build_plan_document_from_create_input(
    *,
    plan_id: str,
    project_id: str,
    created: str,
    session_id: str,
    status: str,
    purpose_summary: str,
    purpose_context: str,
    questions: list[str] | None,
    phases: list[dict[str, Any]],
    budget: dict[str, Any] | None,
) -> PlanDocument:
    """Build a plan-create document while aggregating top-level validation errors."""
    errors: list[str] = []

    if status not in {"draft", "active"}:
        errors.append("memory_plan_create status must be 'draft' or 'active'")

    try:
        validate_session_id(session_id)
    except ValidationError as exc:
        errors.extend(validation_error_messages(exc))

    normalized_questions: list[str] = []
    if questions is None:
        normalized_questions = []
    elif not isinstance(questions, list):
        errors.append("purpose.questions must be a list when provided")
    else:
        normalized_questions = list(questions)

    purpose: PlanPurpose | None = None
    try:
        purpose = PlanPurpose(
            summary=purpose_summary,
            context=purpose_context,
            questions=normalized_questions,
        )
    except ValidationError as exc:
        errors.extend(validation_error_messages(exc))

    coerced_phases: list[PlanPhase] = []
    try:
        coerced_phases = coerce_phase_inputs(phases)
    except ValidationError as exc:
        errors.extend(validation_error_messages(exc))
    else:
        phase_ids = [phase.id for phase in coerced_phases]
        if len(set(phase_ids)) != len(phase_ids):
            errors.append("work.phases ids must be unique within a plan")

    coerced_budget: PlanBudget | None = None
    try:
        coerced_budget = coerce_budget_input(budget)
    except ValidationError as exc:
        errors.extend(validation_error_messages(exc))

    raise_collected_validation_errors(errors)

    assert purpose is not None
    return PlanDocument(
        id=plan_id,
        project=project_id,
        created=created,
        origin_session=session_id,
        status=status,
        purpose=purpose,
        phases=coerced_phases,
        review=None,
        budget=coerced_budget,
    )


def exportable_artifacts(root: Path, plan: PlanDocument) -> list[str]:
    plan_path = project_plan_path(plan.project, plan.id)
    artifacts: list[str] = []
    seen: set[str] = set()
    for phase in plan.phases:
        for change in phase.changes:
            if change.path == plan_path or change.path.endswith("/SUMMARY.md"):
                continue
            if change.path in seen:
                continue
            abs_path = root / change.path
            if abs_path.is_file():
                artifacts.append(change.path)
                seen.add(change.path)
    return artifacts


# ── Postcondition verification ──────────────────────────────────────────

# Command prefixes considered safe for test-type postconditions.
# Each entry is a prefix: the target command (after whitespace normalization)
# must start with one of these strings.
VERIFY_TEST_ALLOWLIST: tuple[str, ...] = (
    "pre-commit run",
    "pytest",
    "python -m pytest",
    "ruff check",
    "ruff format --check",
    "mypy",
)

# Shell metacharacters that indicate command chaining / injection.
_SHELL_META_RE = re.compile(r"[;|&`$]")


def _resolve_verify_path(root: Path, target: str) -> Path | None:
    """Resolve a postcondition target path using the same fallback logic as SourceSpec."""
    candidate = root / target
    if candidate.exists():
        return candidate
    # Content-prefix fallback: path may include "core/" when root already is core/.
    first, _, rest = target.partition("/")
    if first and rest and root.name == first and (root / rest).exists():
        return root / rest
    # Repo-root fallback: when root is a content-prefix dir.
    if root.name in _CONTENT_PREFIXES and (root.parent / target).exists():
        return root.parent / target
    return None


def _validate_check(root: Path, target: str) -> dict[str, Any]:
    """Validate a 'check' postcondition (file exists)."""
    resolved = _resolve_verify_path(root, target)
    if resolved is not None and resolved.is_file():
        return {"status": "pass", "detail": None}
    return {"status": "fail", "detail": f"file not found: {target}"}


def _validate_grep(root: Path, target: str) -> dict[str, Any]:
    """Validate a 'grep' postcondition (pattern found in file)."""
    if "::" not in target:
        return {"status": "error", "detail": "grep target must use pattern::path format"}
    pattern, path = target.split("::", 1)
    resolved = _resolve_verify_path(root, path)
    if resolved is None or not resolved.is_file():
        return {"status": "error", "detail": f"grep target file not found: {path}"}
    try:
        compiled = re.compile(pattern)
    except re.error as exc:
        return {"status": "error", "detail": f"invalid regex: {exc}"}
    try:
        contents = resolved.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return {"status": "error", "detail": f"cannot read file: {exc}"}
    if compiled.search(contents):
        return {"status": "pass", "detail": None}
    return {"status": "fail", "detail": f"pattern not found: {pattern}"}


def _validate_test(root: Path, target: str) -> dict[str, Any]:
    """Validate a 'test' postcondition (shell command exits 0).

    Requires ENGRAM_TIER2=1 and the command must match the allowlist.
    """
    import os
    import subprocess

    if os.environ.get("ENGRAM_TIER2", "").strip().lower() not in {"1", "true", "yes", "on"}:
        return {
            "status": "error",
            "detail": "test-type postconditions require ENGRAM_TIER2=1",
        }
    normalized = " ".join(target.split())
    if not any(normalized.startswith(prefix) for prefix in VERIFY_TEST_ALLOWLIST):
        return {
            "status": "error",
            "detail": (
                f"command not in allowlist: {normalized!r}. "
                f"Allowed prefixes: {', '.join(VERIFY_TEST_ALLOWLIST)}"
            ),
        }
    # Reject shell metacharacters beyond the allowlisted prefix
    # to prevent injection like "pytest; rm -rf /"
    for prefix in VERIFY_TEST_ALLOWLIST:
        if normalized.startswith(prefix):
            suffix = normalized[len(prefix) :]
            if _SHELL_META_RE.search(suffix):
                return {
                    "status": "error",
                    "detail": f"shell metacharacters not allowed in command arguments: {normalized!r}",
                }
            break
    # Policy enforcement: check registered tool policies before execution
    all_tools = _all_registry_tools(root)
    for tool in all_tools:
        if _command_matches_tool(normalized, tool.name):
            policy = check_tool_policy(root, tool.name, tool.provider)
            if not policy.allowed:
                record_trace(
                    root,
                    os.environ.get("MEMORY_SESSION_ID", "").strip() or None,
                    span_type="policy_violation",
                    name="check_tool_policy",
                    status="denied",
                    metadata={
                        "tool_name": tool.name,
                        "provider": tool.provider,
                        "violation_type": policy.violation_type,
                        "reason": policy.reason,
                    },
                )
                return {
                    "status": "error",
                    "detail": f"policy blocked: {policy.reason}",
                    "policy_result": policy.to_dict(),
                }
            break

    # Strip proxy env vars as defense-in-depth.
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.lower().startswith(("http_proxy", "https_proxy", "no_proxy"))
    }
    try:
        result = subprocess.run(
            normalized,
            shell=True,
            cwd=str(root),
            env=env,
            capture_output=True,
            timeout=30,
            text=True,
        )
    except subprocess.TimeoutExpired:
        return {"status": "fail", "detail": "command timed out after 30 seconds"}
    except OSError as exc:
        return {"status": "error", "detail": f"command execution failed: {exc}"}
    if result.returncode == 0:
        return {"status": "pass", "detail": None}
    output = (result.stdout + result.stderr).strip()
    if len(output) > 2000:
        output = output[:2000] + "\n... (truncated)"
    return {"status": "fail", "detail": output or f"exit code {result.returncode}"}


def verify_postconditions(
    plan: PlanDocument,
    phase: PlanPhase,
    root: Path,
) -> dict[str, Any]:
    """Evaluate all postconditions on a phase.

    Returns a dict with verification_results, summary, and all_passed.
    Does not modify plan state.
    """
    results: list[dict[str, Any]] = []
    for pc in phase.postconditions:
        entry: dict[str, Any] = {
            "postcondition": pc.description,
            "type": pc.type,
        }
        if pc.type == "manual":
            entry["status"] = "skip"
            entry["detail"] = None
        elif pc.type == "check":
            outcome = _validate_check(root, pc.target or "")
            entry.update(outcome)
        elif pc.type == "grep":
            outcome = _validate_grep(root, pc.target or "")
            entry.update(outcome)
        elif pc.type == "test":
            outcome = _validate_test(root, pc.target or "")
            entry.update(outcome)
        else:
            entry["status"] = "error"
            entry["detail"] = f"unknown postcondition type: {pc.type}"
        results.append(entry)

    passed = sum(1 for r in results if r["status"] == "pass")
    failed = sum(1 for r in results if r["status"] == "fail")
    skipped = sum(1 for r in results if r["status"] == "skip")
    errors = sum(1 for r in results if r["status"] == "error")
    return {
        "verification_results": results,
        "summary": {
            "total": len(results),
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "errors": errors,
        },
        "all_passed": failed == 0 and errors == 0,
    }


def append_operations_log(
    root: Path,
    project_id: str,
    *,
    session_id: str | None,
    action: str,
    plan_id: str,
    phase_id: str | None = None,
    commit: str | None = None,
    detail: str = "",
) -> tuple[str, str]:
    log_path = project_operations_log_path(project_id)
    abs_log = root / log_path
    abs_log.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "session": session_id,
        "actor": "agent",
        "action": action,
        "project": project_id,
        "plan": plan_id,
        "phase": phase_id,
        "commit": commit,
        "detail": detail,
    }
    line = json.dumps(payload, sort_keys=True)
    with abs_log.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")
    return log_path, line


__all__ = [
    "APPROVAL_RESOLUTIONS",
    "APPROVAL_STATUSES",
    "CHANGE_ACTIONS",
    "COST_TIERS",
    "PLAN_STATUSES",
    "PHASE_STATUSES",
    "POSTCONDITION_TYPES",
    "SOURCE_TYPES",
    "TRACE_SPAN_TYPES",
    "TRACE_STATUSES",
    "VERIFICATION_RESULT_STATUSES",
    "ApprovalDocument",
    "ChangeSpec",
    "PhaseFailure",
    "PlanBudget",
    "PolicyCheckResult",
    "PlanDocument",
    "PlanPhase",
    "PlanPurpose",
    "PlanReview",
    "PostconditionSpec",
    "RunState",
    "RunStateError",
    "RunStatePhase",
    "SourceSpec",
    "ToolDefinition",
    "TraceSpan",
    "_all_registry_tools",
    "_check_approval_expiry",
    "append_operations_log",
    "approval_filename",
    "approvals_summary_path",
    "budget_status",
    "build_review_from_input",
    "check_run_state_staleness",
    "check_tool_policy",
    "coerce_budget_input",
    "coerce_phase_inputs",
    "estimate_cost",
    "exportable_artifacts",
    "load_approval",
    "materialize_expired_approval",
    "load_plan",
    "load_registry",
    "load_run_state",
    "next_action",
    "next_phase",
    "outbox_summary_path",
    "phase_blockers",
    "phase_change_class",
    "phase_payload",
    "plan_create_input_schema",
    "plan_progress",
    "plan_title",
    "project_operations_log_path",
    "project_outbox_root",
    "project_plan_path",
    "prune_run_state",
    "record_trace",
    "regenerate_approvals_summary",
    "regenerate_registry_summary",
    "registry_file_path",
    "registry_summary_path",
    "resolve_phase",
    "run_state_path",
    "save_approval",
    "save_plan",
    "save_registry",
    "save_run_state",
    "trace_file_path",
    "unresolved_blockers",
    "update_run_state",
    "validate_plan_references",
    "validate_run_state_against_plan",
    "validation_error_messages",
    "verification_results_item_schema",
    "verify_postconditions",
    "VERIFY_TEST_ALLOWLIST",
]
