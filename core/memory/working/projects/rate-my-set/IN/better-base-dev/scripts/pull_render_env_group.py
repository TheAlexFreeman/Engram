from __future__ import annotations

import argparse
import json
import os
from typing import Any

import httpx
from rich import print as rprint
from rich import print_json as rprint_json
from rich.syntax import Syntax


def get_env_group_details(env_group_id: str) -> dict[str, Any]:
    if not (api_key := os.getenv("RENDER_API_KEY")):
        raise ValueError("RENDER_API_KEY environment variable is not set")

    headers: dict[str, str] = {
        "Accept": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    url = f"https://api.render.com/v1/env-groups/{env_group_id}"
    timeout = httpx.Timeout(15.0)
    response = httpx.get(url, headers=headers, timeout=timeout)
    response.raise_for_status()

    response_data = response.json()
    response_data["envVars"] = sorted(response_data["envVars"], key=lambda x: x["key"])

    return dict(sorted(response_data.items(), key=lambda x: x[0]))


def print_render_yaml(env_group_details: dict[str, Any]) -> None:
    if not (env_vars := env_group_details.get("envVars")):
        raise ValueError("No environment variables found in environment group")

    import yaml

    yaml_dict = {"envVars": env_vars}
    yaml_str = yaml.dump(yaml_dict, sort_keys=True, default_flow_style=False)

    rprint(Syntax(yaml_str, "yaml"))


def main():
    parser = argparse.ArgumentParser(
        description="Pull environment variables from a Render environment group"
    )
    parser.add_argument("--id", required=True, help="Render environment group ID")
    parser.add_argument(
        "-t", "--transform", choices=["render.yaml"], help="Transform output format"
    )
    args = parser.parse_args()

    env_group_id = args.id

    try:
        env_group_details = get_env_group_details(env_group_id)
        rprint("[green]Environment Group Details:[/green]")
        if args.transform == "render.yaml":
            print_render_yaml(env_group_details)
        else:
            assert not args.transform, f"Unknown transform: {args.transform}"
            rprint_json(json.dumps(env_group_details, indent=2, sort_keys=True))
    except httpx.HTTPError as e:
        rprint(f"[red]Error fetching environment group: {e}[/red]")
    except ValueError as e:
        rprint(f"[red]{e}[/red]")


if __name__ == "__main__":
    main()
