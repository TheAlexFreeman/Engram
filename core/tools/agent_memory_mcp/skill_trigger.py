"""Shared trigger schemas, validators, and formatting helpers for skills."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .errors import ValidationError

SKILL_TRIGGER_EVENTS = frozenset(
    {
        "session-start",
        "session-end",
        "session-checkpoint",
        "pre-tool-use",
        "post-tool-use",
        "on-demand",
        "periodic",
        "project-active",
    }
)

SKILL_TRIGGER_MATCHER_KEYS = frozenset({"tool_name", "project_id", "condition", "interval"})
_SKILL_TRIGGER_OBJECT_KEYS = frozenset({"event", "matcher", "priority"})


def skill_trigger_value_schema(*, description: str | None = None) -> dict[str, Any]:
    """Return the JSON schema fragment for a trigger frontmatter value."""

    matcher_schema: dict[str, Any] = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "tool_name": {
                "type": "string",
                "minLength": 1,
            },
            "project_id": {
                "type": "string",
                "minLength": 1,
            },
            "condition": {
                "type": "string",
                "minLength": 1,
            },
            "interval": {
                "type": "string",
                "minLength": 1,
            },
        },
    }
    trigger_object_schema: dict[str, Any] = {
        "type": "object",
        "additionalProperties": False,
        "required": ["event"],
        "properties": {
            "event": {
                "type": "string",
                "enum": sorted(SKILL_TRIGGER_EVENTS),
            },
            "matcher": matcher_schema,
            "priority": {
                "type": "integer",
            },
        },
    }
    schema: dict[str, Any] = {
        "oneOf": [
            {
                "type": "string",
                "enum": sorted(SKILL_TRIGGER_EVENTS),
            },
            trigger_object_schema,
            {
                "type": "array",
                "minItems": 1,
                "items": {
                    "oneOf": [
                        {
                            "type": "string",
                            "enum": sorted(SKILL_TRIGGER_EVENTS),
                        },
                        trigger_object_schema,
                    ]
                },
            },
        ]
    }
    if description:
        schema["description"] = description
    return schema


def validate_skill_trigger(trigger_value: object, *, context: str = "trigger") -> None:
    """Validate the supported trigger frontmatter shapes."""

    def validate_matcher(matcher: object, *, matcher_context: str) -> None:
        if not isinstance(matcher, Mapping):
            raise ValidationError(f"{matcher_context} must be a mapping")
        unknown = sorted(set(matcher.keys()) - SKILL_TRIGGER_MATCHER_KEYS)
        if unknown:
            raise ValidationError(
                f"{matcher_context} contains unsupported keys: {', '.join(unknown)}"
            )
        for key, value in matcher.items():
            if not isinstance(value, str) or not value.strip():
                raise ValidationError(f"{matcher_context}.{key} must be a non-empty string")

    def validate_trigger_object(trigger: Mapping[str, object], *, item_context: str) -> None:
        unknown = sorted(set(trigger.keys()) - _SKILL_TRIGGER_OBJECT_KEYS)
        if unknown:
            raise ValidationError(f"{item_context} contains unsupported keys: {', '.join(unknown)}")
        event = trigger.get("event")
        if not isinstance(event, str) or event not in SKILL_TRIGGER_EVENTS:
            raise ValidationError(
                f"{item_context}.event must be one of {sorted(SKILL_TRIGGER_EVENTS)}"
            )
        if "matcher" in trigger:
            validate_matcher(trigger["matcher"], matcher_context=f"{item_context}.matcher")
        if "priority" in trigger and type(trigger["priority"]) is not int:
            raise ValidationError(f"{item_context}.priority must be an integer")

    def validate_single_trigger(item: object, *, item_context: str) -> None:
        if isinstance(item, str):
            if item not in SKILL_TRIGGER_EVENTS:
                raise ValidationError(
                    f"{item_context} must be one of {sorted(SKILL_TRIGGER_EVENTS)}"
                )
            return
        if isinstance(item, Mapping):
            validate_trigger_object(item, item_context=item_context)
            return
        raise ValidationError(f"{item_context} must be a trigger event string or trigger mapping")

    if isinstance(trigger_value, list):
        if not trigger_value:
            raise ValidationError(f"{context} must not be an empty list")
        for index, item in enumerate(trigger_value):
            validate_single_trigger(item, item_context=f"{context}[{index}]")
        return

    validate_single_trigger(trigger_value, item_context=context)


def summarize_skill_trigger(trigger_value: object) -> str | None:
    """Return a compact human-readable trigger summary for catalogs and listings."""

    def summarize_single(item: object) -> str | None:
        if isinstance(item, str):
            return item
        if not isinstance(item, Mapping):
            return None
        event = item.get("event")
        if not isinstance(event, str) or not event.strip():
            return None
        details: list[str] = []
        matcher = item.get("matcher")
        if isinstance(matcher, Mapping):
            for key in ("condition", "project_id", "tool_name", "interval"):
                value = matcher.get(key)
                if isinstance(value, str) and value.strip():
                    details.append(f"{key}={value.strip()}")
        priority = item.get("priority")
        if type(priority) is int and priority != 0:
            details.append(f"priority={priority}")
        if not details:
            return event
        return f"{event} ({', '.join(details)})"

    if isinstance(trigger_value, list):
        summaries = [summary for item in trigger_value if (summary := summarize_single(item))]
        if not summaries:
            return None
        return "; ".join(summaries)
    return summarize_single(trigger_value)


__all__ = [
    "SKILL_TRIGGER_EVENTS",
    "SKILL_TRIGGER_MATCHER_KEYS",
    "skill_trigger_value_schema",
    "summarize_skill_trigger",
    "validate_skill_trigger",
]
