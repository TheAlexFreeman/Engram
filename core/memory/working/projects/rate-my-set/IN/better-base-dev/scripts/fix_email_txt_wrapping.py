#!/usr/bin/env python3
"""
Pre-Commit/Prek hook to fix word wrapping issues in email txt files. Rejoins lines that
contain template variables like {{ }}, {% %}, etc.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Final, Literal


def fix_invalid_wrapped_template_sections(lines: list[str]) -> tuple[bool, list[str]]:
    needed_fix: bool = False

    buffered_lines: list[str] = []
    left_tag: Final[Literal["{%"]] = "{%"
    right_tag: Final[Literal["%}"]] = "%}"
    left_count: int = 0
    right_count: int = 0
    saw_mismatched_counts: bool = False

    final_lines: list[str] = []

    def clear_buffer() -> None:
        nonlocal needed_fix
        nonlocal left_count
        nonlocal right_count
        nonlocal saw_mismatched_counts

        b_length = len(buffered_lines)
        for b_index, b_line in enumerate(buffered_lines):
            if b_index == 0:
                buffered_lines[b_index] = b_line.rstrip()
            if 0 < b_index < (b_length - 1):
                buffered_lines[b_index] = b_line.strip()
            if b_index == (b_length - 1):
                buffered_lines[b_index] = b_line.lstrip()

        final_buffered_lines: list[str] = []
        space_sequence: list[str] = []
        for b_index, b_line in enumerate(buffered_lines):
            next_is_space: bool = b_line.isspace() or b_line == ""
            is_in_between: bool = 0 < b_index < (b_length - 1)
            is_at_end: bool = b_index == (b_length - 1)
            if is_in_between and next_is_space:
                space_sequence.append(b_line)
            elif is_in_between and not next_is_space:
                if space_sequence:
                    space_sequence.clear()
                final_buffered_lines.append(b_line)
            elif is_at_end and space_sequence:
                space_sequence.clear()
                final_buffered_lines.append(b_line)
            else:
                final_buffered_lines.append(b_line)

        final_lines.append(" ".join(final_buffered_lines))
        buffered_lines.clear()
        saw_mismatched_counts = False
        left_count = 0
        right_count = 0
        needed_fix = True

    for line in lines:
        if saw_mismatched_counts and left_count == right_count:
            clear_buffer()
            final_lines.append(line)
            continue

        left_count += line.count(left_tag)
        right_count += line.count(right_tag)
        if (left_count or right_count) and left_count != right_count:
            saw_mismatched_counts = True
            buffered_lines.append(line)
        elif not saw_mismatched_counts:
            final_lines.append(line)
        else:
            buffered_lines.append(line)

    if buffered_lines:
        if saw_mismatched_counts and left_count == right_count:
            clear_buffer()
        elif saw_mismatched_counts and (left_count or right_count):
            raise ValueError(
                f"{left_count} occurrence(s) of {left_tag} found but {right_count} "
                f"occurrence(s) of {right_tag} found."
            )
        else:
            for buffered_line in buffered_lines:
                final_lines.append(buffered_line)
            buffered_lines.clear()

    return (needed_fix, final_lines)


def process_file(file_path: Path) -> bool:
    if not file_path.exists():
        raise FileNotFoundError(f"File {file_path} does not exist.")

    if file_path.suffix != ".txt":
        raise ValueError(f"File {file_path} is not a .txt file.")

    with open(file_path, encoding="utf-8") as f:
        original_lines = f.readlines()

    needed_fix, fixed_lines = fix_invalid_wrapped_template_sections(original_lines)

    if needed_fix:
        with open(file_path, "w", encoding="utf-8") as f:
            f.writelines(fixed_lines)
            if (not fixed_lines) or (fixed_lines[-1] and not fixed_lines[-1].isspace()):
                f.write(os.linesep)
        print(f"Fixed invalid template section wrapping in `{file_path}`.")  # noqa: T201
        return True

    return False


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fix invalid template section wrapping in email .txt files."
    )
    parser.add_argument("filenames", nargs="*", help="Filenames to check")
    args = parser.parse_args()
    modified_filenames: list[str] = []

    for filename in args.filenames:
        file_path = Path(filename)
        if process_file(file_path):
            modified_filenames.append(filename)

    if modified_filenames:
        print(f"Fixed {len(modified_filenames)} file(s).")  # noqa: T201
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
