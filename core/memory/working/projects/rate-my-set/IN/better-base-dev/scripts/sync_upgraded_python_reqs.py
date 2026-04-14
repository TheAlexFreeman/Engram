"""
Intended Usage:
Step 1: (If not already done) Make sure you're in your Python virtual environment or
        similar if necessary or desired.
Step 2: Run `python scripts/upgrade_python_reqs.py`.
Step 3: Run `python scripts/sync_upgraded_python_reqs.py`.
Step 4 (Optional): Look at `pyproject.toml` and sanity check the changes.
Step 5: Run `uv sync` (unless you ran `sync_upgraded_python_reqs` with `--sync` or `-s`).

By default, this script formats `pyproject.toml` via `bun run fmt:toml` after
updating pinned versions. Pass `--no-format` if you explicitly want to skip that step.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import tomllib
from collections.abc import Sequence
from functools import cached_property
from pathlib import Path
from typing import Any

from attrs import define

_PINNED_DEPENDENCY_PATTERN = re.compile(
    r"^\s*"
    r"(?P<name>[A-Za-z0-9][A-Za-z0-9._-]*)"
    r"(?P<extras>\[[^\]]+\])?"
    r"\s*==\s*"
    r"(?P<version>[A-Za-z0-9][A-Za-z0-9._!*+\-]*)"
    r"(?P<marker>\s*;.*)?"
    r"\s*$"
)
_QUOTED_VERSION_PATTERN = re.compile(r'(["\'])(\d+\.\d+)\1')


def _normalize_package_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


@define(frozen=True, kw_only=True, slots=True)
class PinnedDependency:
    name: str
    extras: str
    version: str
    marker: str


@define(frozen=True, kw_only=True, slots=True)
class RunOptions:
    should_format: bool
    should_sync: bool


class Handler:
    @cached_property
    def pyproject(self) -> dict[str, Any]:
        with open("pyproject.toml", "rb") as file:
            return tomllib.load(file)

    @cached_property
    def latest_versions(self) -> dict[str, str]:
        output_str = subprocess.check_output(["uv", "pip", "freeze"], text=True)

        output_dict: dict[str, str] = {}
        for raw_line in output_str.splitlines():
            line = raw_line.strip()
            if not line or "==" not in line:
                continue

            package, version = line.split("==", 1)
            normalized_package = _normalize_package_name(package)
            output_dict[normalized_package] = version

        return output_dict

    @cached_property
    def dependency_strings(self) -> list[str]:
        all_dependencies: list[str] = []

        project_dependencies: list[str] = self.pyproject["project"]["dependencies"]
        all_dependencies.extend(project_dependencies)

        dependency_groups: dict[str, list[str]] = self.pyproject.get(
            "dependency-groups", {}
        )
        for dependency_group_values in dependency_groups.values():
            all_dependencies.extend(dependency_group_values)

        return all_dependencies

    @cached_property
    def django_target_version(self) -> str | None:
        for dependency in self.pyproject["project"]["dependencies"]:
            pinned_dependency = self.parse_pinned_dependency(dependency)
            if pinned_dependency is None:
                continue

            if _normalize_package_name(pinned_dependency.name) != "django":
                continue

            version_match = re.match(
                r"^(?P<major>\d+)\.(?P<minor>\d+)", pinned_dependency.version
            )
            assert isinstance(version_match, re.Match), "Pre-condition"
            return f"{version_match.group('major')}.{version_match.group('minor')}"

        return None

    def parse_pinned_dependency(self, dependency: str) -> PinnedDependency | None:
        dependency_match = _PINNED_DEPENDENCY_PATTERN.match(dependency)
        if dependency_match is None:
            return None

        version = dependency_match.group("version")
        if "*" in version:
            return None

        extras = dependency_match.group("extras") or ""
        marker = dependency_match.group("marker") or ""

        return PinnedDependency(
            name=dependency_match.group("name"),
            extras=extras,
            version=version,
            marker=marker,
        )

    @cached_property
    def dependency_replacements(self) -> dict[str, str]:
        replacements: dict[str, str] = {}
        for dependency in self.dependency_strings:
            pinned_dependency = self.parse_pinned_dependency(dependency)
            if pinned_dependency is None:
                continue

            normalized_name = _normalize_package_name(pinned_dependency.name)
            latest_version = self.latest_versions.get(normalized_name)
            if latest_version is None:
                continue

            if pinned_dependency.version == latest_version:
                continue

            replacements[dependency] = (
                f"{pinned_dependency.name}{pinned_dependency.extras}"
                f"=={latest_version}{pinned_dependency.marker}"
            )

        return replacements

    def replace_references(self, contents: str) -> str:
        final_lines: list[str] = []

        for line in contents.splitlines(keepends=True):
            final_line = line
            for old_dependency, new_dependency in self.dependency_replacements.items():
                old_quoted_dependency = f'"{old_dependency}"'
                if old_quoted_dependency not in final_line:
                    continue

                new_quoted_dependency = f'"{new_dependency}"'
                final_line = final_line.replace(
                    old_quoted_dependency, new_quoted_dependency
                )

            final_lines.append(final_line)

        return "".join(final_lines)

    def parse_options(self, argv: Sequence[str] | None = None) -> RunOptions:
        parser = argparse.ArgumentParser()
        parser.set_defaults(should_format=True)

        parser.add_argument(
            "--format",
            "--fmt",
            dest="should_format",
            action="store_true",
            help="Format `pyproject.toml` after dependency updates (default behavior).",
        )
        parser.add_argument(
            "--no-format",
            dest="should_format",
            action="store_false",
            help="Skip formatting `pyproject.toml` after dependency updates.",
        )
        parser.add_argument(
            "--sync",
            "-s",
            dest="should_sync",
            action="store_true",
            default=False,
            help="Run `uv sync` after updating dependencies.",
        )

        args = parser.parse_args(argv)

        return RunOptions(
            should_format=args.should_format,
            should_sync=args.should_sync,
        )

    def format_toml(self, pyproject_toml_path: Path) -> None:
        subprocess.run(
            ["bun", "run", "fmt:toml", "--", str(pyproject_toml_path)], check=True
        )

    def replace_pre_commit_django_target_versions(self, contents: str) -> str:
        target_version = self.django_target_version
        if target_version is None:
            return contents

        final_lines: list[str] = []
        active_hook_id: str | None = None
        django_target_hooks = {"djade", "django-upgrade"}

        for line in contents.splitlines(keepends=True):
            stripped_line = line.strip()
            final_line = line

            if stripped_line.startswith("- id: "):
                active_hook_id = stripped_line.removeprefix("- id: ").strip()
            elif active_hook_id in django_target_hooks and "args:" in stripped_line:
                final_line = _QUOTED_VERSION_PATTERN.sub(
                    lambda match: f"{match.group(1)}{target_version}{match.group(1)}",
                    line,
                    count=1,
                )
                active_hook_id = None

            final_lines.append(final_line)

        return "".join(final_lines)

    def run(self, argv: Sequence[str] | None = None) -> None:
        options = self.parse_options(argv)

        pyproject_toml_path = Path("pyproject.toml")
        initial_contents = pyproject_toml_path.read_text()
        final_contents = self.replace_references(initial_contents)

        if final_contents != initial_contents:
            pyproject_toml_path.write_text(final_contents)

        pre_commit_config_path = Path(".pre-commit-config.yaml")
        if pre_commit_config_path.exists():
            initial_pre_commit_contents = pre_commit_config_path.read_text()
            final_pre_commit_contents = self.replace_pre_commit_django_target_versions(
                initial_pre_commit_contents
            )
            if final_pre_commit_contents != initial_pre_commit_contents:
                pre_commit_config_path.write_text(final_pre_commit_contents)

        if options.should_format:
            self.format_toml(pyproject_toml_path)

        if options.should_sync:
            subprocess.run(["uv", "sync"], check=True)


if __name__ == "__main__":
    handler = Handler()
    handler.run()
