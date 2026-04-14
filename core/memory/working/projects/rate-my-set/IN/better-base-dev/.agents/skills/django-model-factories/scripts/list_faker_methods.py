#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib
import inspect
import pkgutil
import sys
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from faker import Faker
from faker import providers as faker_providers


@dataclass(frozen=True)
class MethodInfo:
    name: str
    signature: str
    sample: str | None


def _is_public_callable(v: Any) -> bool:
    return callable(v) and not getattr(v, "__name__", "").startswith("_")


def _can_call_without_required_args(fn: Callable[..., Any]) -> bool:
    try:
        sig = inspect.signature(fn)
    except TypeError, ValueError:
        return False

    for param in sig.parameters.values():
        if param.kind in (
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
        ):
            continue
        if param.default is inspect._empty:
            return False
    return True


def _stringify_sample(v: Any) -> str:
    text = repr(v)
    if len(text) > 120:
        text = text[:117] + "..."
    return text


def _collect_provider_methods(fake: Faker) -> dict[str, list[MethodInfo]]:
    providers: dict[str, dict[str, MethodInfo]] = defaultdict(dict)

    # Stable deterministic outputs for generated samples.
    Faker.seed(20260227)
    fake.seed_instance(20260227)

    for provider in fake.get_providers():
        module = provider.__class__.__module__
        if "faker.providers" not in module:
            continue

        provider_key = module.split("faker.providers.", 1)[-1].split(".", 1)[0]

        for method_name, candidate in provider.__class__.__dict__.items():
            if method_name.startswith("_") or not _is_public_callable(candidate):
                continue

            bound = getattr(provider, method_name)

            try:
                signature = str(inspect.signature(bound))
            except TypeError, ValueError:
                signature = "(...)"

            sample: str | None = None
            if _can_call_without_required_args(bound):
                try:
                    sample = _stringify_sample(bound())
                except Exception:
                    sample = None

            providers[provider_key][method_name] = MethodInfo(
                name=method_name,
                signature=signature,
                sample=sample,
            )

    return {
        k: sorted(v.values(), key=lambda m: m.name)
        for k, v in sorted(providers.items())
    }


def _add_all_standard_providers(fake: Faker) -> None:
    provider_names = {
        module_info.name
        for module_info in pkgutil.iter_modules(faker_providers.__path__)
        if not module_info.name.startswith("_")
    }
    for provider_name in sorted(provider_names):
        module_name = f"{faker_providers.__name__}.{provider_name}"
        try:
            module = importlib.import_module(module_name)
            provider_cls = module.Provider
            fake.add_provider(provider_cls)
        except Exception:
            # Keep this helper best-effort so it remains resilient across faker versions.
            continue


def _render_markdown(data: dict[str, list[MethodInfo]]) -> str:
    lines: list[str] = []
    lines.append("# Faker Methods By Provider")
    lines.append("")
    lines.append(
        "Generated from installed faker version and active locale/provider config."
    )
    lines.append("")

    for provider, methods in data.items():
        lines.append(f"## {provider}")
        lines.append("")
        for info in methods:
            sample_suffix = (
                f" -> sample: `{info.sample}`" if info.sample is not None else ""
            )
            lines.append(f"- `{info.name}{info.signature}`{sample_suffix}")
        lines.append("")

    return "\n".join(lines)


def _render_json(data: dict[str, list[MethodInfo]]) -> str:
    import json

    as_dict = {
        provider: [
            {"name": m.name, "signature": m.signature, "sample": m.sample}
            for m in methods
        ]
        for provider, methods in data.items()
    }
    return json.dumps(as_dict, indent=2, ensure_ascii=True)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="List faker methods available in the current environment by provider."
    )
    parser.add_argument(
        "--locale",
        default="en_US",
        help="faker locale to instantiate (default: en_US)",
    )
    parser.add_argument(
        "--format",
        choices=("markdown", "json"),
        default="markdown",
        help="output format",
    )
    args = parser.parse_args()

    fake = Faker(args.locale)
    _add_all_standard_providers(fake)
    data = _collect_provider_methods(fake)

    if args.format == "json":
        sys.stdout.write(_render_json(data) + "\n")
    else:
        sys.stdout.write(_render_markdown(data) + "\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
