#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def export_data(
    output_path: Path | None = None,
    *,
    prettify_output: bool = False,
    without_docker: bool = False,
    compose_file: str = "dc.prod.yml",
) -> int:
    base_cmd: list[str] = ["python", "-Xutf8", "manage.py"]
    if not without_docker:
        base_cmd = [
            "docker",
            "compose",
            "-f",
            compose_file,
            "run",
            "--rm",
            "django",
        ] + base_cmd
    cmd = base_cmd + [
        "dumpdata",
        "accounts.Account",
        "accounts.User",
        "accounts.Membership",
        "accounts.UserAppState",
    ]
    cmd_str = " ".join(cmd)

    try:
        result = subprocess.run(
            cmd_str,
            shell=True,
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            print(f"Command failed with exit code {result.returncode}", file=sys.stderr)  # noqa: T201
            print("Error output:", file=sys.stderr)  # noqa: T201
            print(result.stderr, file=sys.stderr)  # noqa: T201
            return result.returncode

        output_data = result.stdout
        if "[INFO  tini (1)]" in output_data:
            output_data = output_data.split("[INFO  tini (1)]")[0]

        if prettify_output:
            # Parse JSON, sort keys and add indentation.
            json_data = json.loads(output_data)
            output_data = json.dumps(json_data, sort_keys=True, indent=2)

        if output_path:
            output_path.write_text(output_data)
        else:
            sys.stdout.write(output_data)

        return 0

    except subprocess.CalledProcessError as e:
        print(f"Error executing command: {e}", file=sys.stderr)  # noqa: T201
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Back up important Django model fixtures from the database."
    )
    parser.add_argument(
        "-o",
        "--output-path",
        type=Path,
        help="Path to write the output (defaults to stdout if not provided).",
    )
    parser.add_argument(
        "-p",
        "--pretty",
        action="store_true",
        help="Pretty print the JSON output with sorted keys and indentation?",
    )
    parser.add_argument(
        "-wd",
        "--without-docker",
        action="store_true",
        help="Run without Docker (directly using python)?",
    )
    parser.add_argument(
        "-cf",
        "--compose-file",
        type=str,
        default="dc.prod.yml",
        help=(
            "If running with Docker, the Docker Compose file to use "
            "(defaults to dc.prod.yml)."
        ),
    )

    args = parser.parse_args()

    return export_data(
        args.output_path,
        prettify_output=args.pretty,
        without_docker=args.without_docker,
        compose_file=args.compose_file,
    )


if __name__ == "__main__":
    sys.exit(main())
