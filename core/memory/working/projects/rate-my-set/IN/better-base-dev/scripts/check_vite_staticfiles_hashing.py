#!/usr/bin/env python3
"""
Check that Vite static files under `bundler/` are not re-hashed by Django's manifest storage.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

DOUBLE_HASH_PATTERN = re.compile(r"\.[0-9a-f]{12}\.")


def load_manifest(manifest_path: Path) -> dict[str, str]:
    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest file not found at {manifest_path}.")

    data = json.loads(manifest_path.read_text())
    raw_paths = data.get("paths")
    if not isinstance(raw_paths, dict):
        raise ValueError("Manifest file does not contain a valid `paths` mapping.")

    paths: dict[str, str] = {}
    for key, value in raw_paths.items():
        if not isinstance(key, str) or not isinstance(value, str):
            raise ValueError("Manifest paths must map strings to strings.")
        paths[key] = value

    return paths


def check_bundler_entries(
    paths: dict[str, str], prefix: str
) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    bundler_paths = {
        key: value for key, value in paths.items() if key.startswith(prefix)
    }
    rehashed = [(key, value) for key, value in bundler_paths.items() if key != value]
    double_hashed = [
        (key, value)
        for key, value in bundler_paths.items()
        if DOUBLE_HASH_PATTERN.search(value)
    ]
    return rehashed, double_hashed


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Verify that Vite assets under `bundler/` are not re-hashed in "
            "Django's staticfiles manifest."
        )
    )
    parser.add_argument(
        "--manifest",
        default="staticfiles/staticfiles.json",
        help="Path to the staticfiles manifest JSON.",
    )
    parser.add_argument(
        "--prefix",
        default="bundler/",
        help="Prefix for Vite assets in the manifest.",
    )
    parser.add_argument(
        "--allow-empty",
        action="store_true",
        help="Exit successfully when no bundler entries are found.",
    )
    args = parser.parse_args()

    manifest_path = Path(args.manifest)
    try:
        paths = load_manifest(manifest_path)
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)  # noqa: T201
        return 2

    bundler_entries = {
        key: value for key, value in paths.items() if key.startswith(args.prefix)
    }
    if not bundler_entries:
        message = f"No manifest entries found with prefix {args.prefix!r}."
        if args.allow_empty:
            print(message)  # noqa: T201
            return 0
        print(message, file=sys.stderr)  # noqa: T201
        return 2

    rehashed, double_hashed = check_bundler_entries(paths, args.prefix)
    print(f"Manifest: {manifest_path}")  # noqa: T201
    print(f"Bundler entries: {len(bundler_entries)}")  # noqa: T201
    print(f"Rehashed entries: {len(rehashed)}")  # noqa: T201
    print(f"Double-hash entries: {len(double_hashed)}")  # noqa: T201

    if rehashed or double_hashed:
        if rehashed:
            print("Sample rehashed entries:", file=sys.stderr)  # noqa: T201
            for key, value in rehashed[:10]:
                print(f"  {key} -> {value}", file=sys.stderr)  # noqa: T201
        if double_hashed:
            print("Sample double-hash entries:", file=sys.stderr)  # noqa: T201
            for key, value in double_hashed[:10]:
                print(f"  {key} -> {value}", file=sys.stderr)  # noqa: T201
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
