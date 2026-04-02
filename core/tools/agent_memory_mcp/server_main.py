"""CLI entrypoint for the Engram MCP namespace."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence

from .plan_utils import plan_create_input_schema
from .server import mcp


def _enum_list(values: list[str]) -> str:
    return " | ".join(values)


def _alias_list(aliases: dict[str, str]) -> str:
    if not aliases:
        return "none"
    return ", ".join(f"{src} -> {dest}" for src, dest in aliases.items())


def _plan_create_help_text() -> str:
    schema = plan_create_input_schema()
    phase_properties = schema["properties"]["phases"]["items"]["properties"]
    source_item = phase_properties["sources"]["items"]
    postcondition_item = phase_properties["postconditions"]["items"]["oneOf"][1]
    change_item = phase_properties["changes"]["items"]
    budget_properties = schema["properties"]["budget"]["properties"]

    lines = [
        "Schema-backed help for plan creation.",
        "",
        "This help is generated from the same nested contract used by memory_plan_schema.",
        "",
        "Top-level required fields:",
        f"- {', '.join(schema['required'])}",
        "",
        "Phase required fields:",
        f"- {', '.join(schema['properties']['phases']['items']['required'])}",
        "",
        "Phase optional fields:",
        f"- {', '.join(sorted(set(phase_properties) - set(schema['properties']['phases']['items']['required'])))}",
        "",
        "Sources:",
        f"- type: {_enum_list(source_item['properties']['type']['enum'])}",
        f"- aliases: {_alias_list(source_item['properties']['type'].get('x-aliases', {}))}",
        "- uri is required when type = external",
        "- mcp_server and mcp_tool are required when type = mcp",
        "",
        "Postconditions:",
        "- strings are shorthand for manual postconditions",
        f"- type: {_enum_list(postcondition_item['properties']['type']['enum'])}",
        f"- aliases: {_alias_list(postcondition_item['properties']['type'].get('x-aliases', {}))}",
        "- check = file exists",
        "- grep = regex::path match",
        "- test = allowlisted command behind ENGRAM_TIER2=1",
        "- target is required when type != manual",
        "",
        "Changes:",
        f"- action: {_enum_list(change_item['properties']['action']['enum'])}",
        f"- aliases: {_alias_list(change_item['properties']['action'].get('x-aliases', {}))}",
        "",
        "Budget:",
        f"- fields: {', '.join(budget_properties)}",
        "",
        "Use --json-schema to print the raw JSON schema.",
    ]
    return "\n".join(lines)


def _build_parser() -> tuple[
    argparse.ArgumentParser, argparse.ArgumentParser, argparse.ArgumentParser
]:
    parser = argparse.ArgumentParser(
        prog="engram-mcp",
        description=(
            "Run the Engram MCP server or inspect schema-backed plan help.\n"
            "With no arguments, the MCP server starts."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("serve", help="Run the Engram MCP server.")

    plan_parser = subparsers.add_parser(
        "plan",
        help="Plan-related CLI helpers.",
    )
    plan_subparsers = plan_parser.add_subparsers(dest="plan_command")
    plan_create_parser = plan_subparsers.add_parser(
        "create",
        help="Show schema-backed help for plan creation.",
        description=_plan_create_help_text(),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    plan_create_parser.add_argument(
        "--json-schema",
        action="store_true",
        help="Print the raw JSON schema used by memory_plan_schema.",
    )
    return parser, plan_parser, plan_create_parser


def main(argv: Sequence[str] | None = None) -> int:
    args_list = list(argv) if argv is not None else sys.argv[1:]
    if not args_list:
        mcp.run()
        return 0

    parser, plan_parser, plan_create_parser = _build_parser()
    args = parser.parse_args(args_list)

    if args.command == "serve":
        mcp.run()
        return 0
    if args.command == "plan":
        if args.plan_command == "create":
            if args.json_schema:
                print(json.dumps(plan_create_input_schema(), indent=2))
                return 0
            plan_create_parser.print_help()
            return 0
        plan_parser.print_help()
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
