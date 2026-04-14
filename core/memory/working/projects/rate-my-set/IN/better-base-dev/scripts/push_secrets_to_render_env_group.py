from __future__ import annotations

import argparse
import importlib
import inspect
import os
from typing import Any, Final, Literal

import httpx
from rich import print as rprint

type EnvironmentName = Literal["stage", "prod"]
type EnvironmentPart = Literal["shared", "frontend", "backend"]
type Alias = EnvironmentPart

SPECIFIER_TO_RENDER_ENV_GROUP_ID: Final[dict[tuple[EnvironmentName, Alias], str]] = {
    ("stage", "backend"): "{{ stage_backend_env_group_id }}",
    ("stage", "frontend"): "{{ stage_frontend_env_group_id }}",
    ("stage", "shared"): "{{ stage_shared_env_group_id }}",
    ("prod", "backend"): "{{ prod_backend_env_group_id }}",
    ("prod", "frontend"): "{{ prod_frontend_env_group_id }}",
    ("prod", "shared"): "{{ prod_shared_env_group_id }}",
}


def pull_and_verify_env_group(
    env_group_id: str,
    environment: EnvironmentName,
    alias: Alias,
) -> dict[str, Any]:
    if not (api_key := os.getenv("RENDER_API_KEY")):
        raise ValueError("RENDER_API_KEY environment variable is not set.")

    assert env_group_id and len(env_group_id) >= 10, (
        "Current pre-condition/sanity check."
    )
    assert environment in ("stage", "prod"), "Current pre-condition"
    assert alias in ("shared", "frontend", "backend"), "Current pre-condition"

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

    expected_name = f"better-base-{environment}-{alias}"
    if response_data.get("name") != expected_name:
        raise ValueError(
            f"Environment group name mismatch. Expected {expected_name}, got "
            f"{response_data.get('name', '<NOT_SET>')}"
        )

    return response_data


def update_env_var(
    env_group_id: str,
    key: str,
    value: str,
    *,
    show: bool = False,
) -> None:
    if not (api_key := os.getenv("RENDER_API_KEY")):
        raise ValueError("RENDER_API_KEY environment variable is not set.")

    if show:
        rprint(f"[yellow]Updating {key}={value}[/yellow]")
    else:
        rprint(f"[yellow]Updating {key}=...[/yellow]")

    headers: dict[str, str] = {
        "Accept": "application/json",
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    url = f"https://api.render.com/v1/env-groups/{env_group_id}/env-vars/{key}"
    timeout = httpx.Timeout(15.0)

    data = {"value": value}
    response = httpx.put(url, headers=headers, json=data, timeout=timeout)
    response.raise_for_status()

    if show:
        rprint(f"[green]Updated {key}={value}[/green]")
    else:
        rprint(f"[green]Updated {key}=...[/green]")


def main() -> None:
    parser = argparse.ArgumentParser(description="Update Render environment variables.")
    parser.add_argument(
        "environment", choices=["stage", "prod"], help="Environment (stage or prod)"
    )
    parser.add_argument(
        "alias",
        choices=["shared", "frontend", "backend"],
        help="Environment part alias (shared, frontend, backend)",
    )
    parser.add_argument(
        "--show",
        action="store_true",
        help="Show variables being updated?",
    )
    args = parser.parse_args()

    environment: EnvironmentName = args.environment
    alias: Alias = args.alias
    should_show: bool = bool(args.show)

    env_group_id = SPECIFIER_TO_RENDER_ENV_GROUP_ID.get((environment, alias))
    if not env_group_id:
        raise ValueError(f"No environment group ID found for {environment}-{alias}")

    try:
        pull_and_verify_env_group(env_group_id, environment, alias)

        name_of_module_with_secrets = f"{environment}_{alias}_secrets"
        module_with_secrets = importlib.import_module(name_of_module_with_secrets)

        for name, value in inspect.getmembers(module_with_secrets):
            if name.startswith("ENV_") and name.isupper():
                key = name.removeprefix("ENV_").strip()

                sanitized_value: str
                if isinstance(value, str):
                    sanitized_value = value
                elif isinstance(value, bool):
                    sanitized_value = str(value)
                elif isinstance(value, int):
                    sanitized_value = str(value)
                else:
                    raise ValueError(
                        f"Currently unsupported type for {key}: {type(value)}"
                    )

                update_env_var(env_group_id, key, sanitized_value, show=should_show)

        rprint("[green]Environment variables updated successfully![/green]")

    except httpx.HTTPError as e:
        rprint(f"[red]HTTP Error: {e}[/red]")
    except ImportError as e:
        rprint(f"[red]Failed to import secrets file: {e}[/red]")
    except Exception as e:
        rprint(f"[red]Error: {e}[/red]")


if __name__ == "__main__":
    main()
