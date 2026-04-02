"""Schema-backed help builders for plan-related CLI commands."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


def format_enum_list(values: Sequence[str]) -> str:
    return " | ".join(str(value) for value in values)


def format_alias_list(aliases: Mapping[str, str] | None) -> str:
    if not aliases:
        return "none"
    return ", ".join(f"{src} -> {dest}" for src, dest in aliases.items())


def _mapping_field(mapping: Mapping[str, Any], key: str, *, label: str) -> Mapping[str, Any]:
    value = mapping.get(key)
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must define a mapping field '{key}'")
    return value


def _required_list(mapping: Mapping[str, Any], *, label: str) -> list[str]:
    required = mapping.get("required")
    if not isinstance(required, list) or not all(isinstance(item, str) for item in required):
        raise ValueError(f"{label} must define a string list 'required'")
    return required


def _find_variant_by_type(
    schema: Mapping[str, Any], *, key: str, variant_type: str, label: str
) -> Mapping[str, Any]:
    variants = schema.get(key)
    if not isinstance(variants, list):
        raise ValueError(f"{label} must define a list '{key}'")
    for variant in variants:
        if isinstance(variant, Mapping) and variant.get("type") == variant_type:
            return variant
    raise ValueError(f"{label} must include a '{variant_type}' variant in '{key}'")


def build_plan_create_help_text(schema: Mapping[str, Any]) -> str:
    properties = _mapping_field(schema, "properties", label="plan schema")
    phases = _mapping_field(properties, "phases", label="plan schema.properties")
    phase_item = _mapping_field(phases, "items", label="plan schema.properties.phases")
    phase_properties = _mapping_field(
        phase_item, "properties", label="plan schema.properties.phases.items"
    )
    source_item = _mapping_field(phase_properties["sources"], "items", label="phase sources")
    postcondition_items = _mapping_field(
        phase_properties["postconditions"], "items", label="phase postconditions"
    )
    postcondition_item = _find_variant_by_type(
        postcondition_items,
        key="oneOf",
        variant_type="object",
        label="phase postconditions.items",
    )
    change_item = _mapping_field(phase_properties["changes"], "items", label="phase changes")
    budget_properties = _mapping_field(properties["budget"], "properties", label="plan budget")
    phase_required = _required_list(phase_item, label="phase item")
    top_level_required = _required_list(schema, label="plan schema")

    source_type = _mapping_field(
        _mapping_field(source_item, "properties", label="source item"),
        "type",
        label="source properties",
    )
    postcondition_type = _mapping_field(
        _mapping_field(postcondition_item, "properties", label="postcondition item"),
        "type",
        label="postcondition properties",
    )
    change_action = _mapping_field(
        _mapping_field(change_item, "properties", label="change item"),
        "action",
        label="change properties",
    )

    lines = [
        "Schema-backed help for plan creation.",
        "",
        "This help is generated from the same nested contract used by memory_plan_schema.",
        "",
        "Top-level required fields:",
        f"- {', '.join(top_level_required)}",
        "",
        "Phase required fields:",
        f"- {', '.join(phase_required)}",
        "",
        "Phase optional fields:",
        f"- {', '.join(sorted(set(phase_properties) - set(phase_required)))}",
        "",
        "Sources:",
        f"- type: {format_enum_list(source_type['enum'])}",
        f"- aliases: {format_alias_list(source_type.get('x-aliases'))}",
        "- uri is required when type = external",
        "- mcp_server and mcp_tool are required when type = mcp",
        "",
        "Postconditions:",
        "- strings are shorthand for manual postconditions",
        f"- type: {format_enum_list(postcondition_type['enum'])}",
        f"- aliases: {format_alias_list(postcondition_type.get('x-aliases'))}",
        "- check = file exists",
        "- grep = regex::path match",
        "- test = allowlisted command behind ENGRAM_TIER2=1",
        "- target is required when type != manual",
        "",
        "Changes:",
        f"- action: {format_enum_list(change_action['enum'])}",
        f"- aliases: {format_alias_list(change_action.get('x-aliases'))}",
        "",
        "Budget:",
        f"- fields: {', '.join(budget_properties)}",
        "",
        "Use --json-schema to print the raw JSON schema.",
    ]
    return "\n".join(lines)
