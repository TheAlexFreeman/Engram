"""
Intended Usage:
Step 1: (If not already done) Make sure you're in your Python virtual environment or
        similar if necessary or desired.
Step 2: Run `python scripts/upgrade_python_reqs.py`.
Step 3: Run `python scripts/sync_upgraded_python_reqs.py`.
Step 4 (Optional): Look at `pyproject.toml` and sanity check the changes.
Step 5: Run `uv sync` (unless you ran `sync_upgraded_python_reqs` with `--sync` or `-s`).

* NOTE: See `scripts/sync_upgraded_python_reqs.py` for more details.
"""

from __future__ import annotations

import re
import subprocess
import tomllib
from collections.abc import Iterator
from functools import cached_property
from typing import Any

from attrs import define

_PACKAGE_NAME_PATTERN = re.compile(r"^\s*(?P<name>[A-Za-z0-9][A-Za-z0-9._-]*)")


def _normalize_package_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


@define(frozen=True, kw_only=True, slots=True)
class DependencyEntry:
    section: str
    package: str
    whole_line: str


class Handler:
    @cached_property
    def pyproject(self) -> dict[str, Any]:
        with open("pyproject.toml", "rb") as file:
            return tomllib.load(file)

    @property
    def dependency_entries(self) -> Iterator[DependencyEntry]:
        dependencies: list[str] = self.pyproject["project"]["dependencies"]
        for dependency in dependencies:
            package_match = _PACKAGE_NAME_PATTERN.match(dependency)
            assert isinstance(package_match, re.Match), "Pre-condition"
            package = package_match.group("name")
            yield DependencyEntry(
                section="project.dependencies",
                package=package,
                whole_line=dependency,
            )

        dependency_groups: dict[str, list[str]] = self.pyproject.get(
            "dependency-groups", {}
        )
        for group_name, group_dependencies in dependency_groups.items():
            for group_dependency in group_dependencies:
                package_match = _PACKAGE_NAME_PATTERN.match(group_dependency)
                assert isinstance(package_match, re.Match), "Pre-condition"
                package = package_match.group("name")
                yield DependencyEntry(
                    section=f"dependency-groups.{group_name}",
                    package=package,
                    whole_line=group_dependency,
                )

    def upgrade_entries(self) -> None:
        deduped_packages: dict[str, str] = {}
        for entry in self.dependency_entries:
            normalized_package = _normalize_package_name(entry.package)
            deduped_packages.setdefault(normalized_package, entry.package)

        for normalized_package in sorted(deduped_packages):
            package = deduped_packages[normalized_package]
            subprocess.run(["uv", "pip", "install", "--upgrade", package], check=True)

    def run(self) -> None:
        self.upgrade_entries()


if __name__ == "__main__":
    handler = Handler()
    handler.run()
