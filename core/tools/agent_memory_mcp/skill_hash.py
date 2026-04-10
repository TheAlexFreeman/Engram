"""Shared content-hashing utilities for skill directories.

The hashing algorithm follows core/governance/skill-manifest-spec.md:
  1. List all files recursively, sorted lexicographically by relative path.
  2. SHA-256(relative_path + "\\0" + file_contents) for each file.
  3. SHA-256(concatenation of all per-file raw digests) = final content_hash.

This matches generate_skill_manifest.py which is the canonical implementation
that produces SKILLS.lock.
"""

from __future__ import annotations

import hashlib
from pathlib import Path


def compute_content_hash(skill_dir: Path) -> str:
    """Compute deterministic SHA-256 content hash for a skill directory.

    Returns "sha256:{hex}" string, or "" if the directory is empty or missing.
    """
    if not skill_dir.exists():
        return ""

    file_hashes: list[bytes] = []
    for file_path in sorted(skill_dir.rglob("*")):
        if file_path.is_file():
            rel_path_str = str(file_path.relative_to(skill_dir))
            with open(file_path, "rb") as f:
                content = f.read()
            file_hash = hashlib.sha256(rel_path_str.encode("utf-8") + b"\0" + content).digest()
            file_hashes.append(file_hash)

    if not file_hashes:
        return ""

    concatenated = b"".join(file_hashes)
    final_hash = hashlib.sha256(concatenated).hexdigest()
    return f"sha256:{final_hash}"


def get_dir_stats(skill_dir: Path) -> tuple[int, int]:
    """Return (file_count, total_bytes) for a skill directory."""
    file_count = 0
    total_bytes = 0
    for file_path in skill_dir.rglob("*"):
        if file_path.is_file():
            file_count += 1
            total_bytes += file_path.stat().st_size
    return file_count, total_bytes
