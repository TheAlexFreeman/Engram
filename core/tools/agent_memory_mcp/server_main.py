"""CLI entrypoint for the Engram MCP namespace."""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from collections.abc import Sequence

from .cli.plan_help import build_plan_create_help_text
from .plan_utils import plan_create_input_schema


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
        description=build_plan_create_help_text(plan_create_input_schema()),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    plan_create_parser.add_argument(
        "--json-schema",
        action="store_true",
        help="Print the raw JSON schema used by memory_plan_schema.",
    )
    return parser, plan_parser, plan_create_parser


def _load_mcp() -> object:
    server_module = importlib.import_module(".server", __package__)
    return server_module.mcp


def main(argv: Sequence[str] | None = None) -> int:
    args_list = list(argv) if argv is not None else sys.argv[1:]
    if not args_list:
        _load_mcp().run()
        return 0

    parser, plan_parser, plan_create_parser = _build_parser()
    args = parser.parse_args(args_list)

    if args.command == "serve":
        _load_mcp().run()
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
