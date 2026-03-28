"""Extract person names from the knowledge base and write NAMES.md index.

Run from the repo root:
    python HUMANS/tooling/scripts/extract_names.py

Writes: core/memory/knowledge/NAMES.md
Reads:  everything under core/memory/knowledge/ except _unverified/
"""

from __future__ import annotations

from pathlib import Path

from engram_mcp.agent_memory_mcp.tools.name_index import generate_names_index, write_names_index


def main() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    payload = generate_names_index(repo_root / "core")
    target = write_names_index(repo_root / "core", payload["draft"], payload["output_path"])

    print(f"Scanned {payload['files_scanned']} files under core/{payload['knowledge_path']}")
    print(f"Raw candidates extracted: {payload['raw_candidates']}")
    print(f"After filtering: {payload['names_count']} names")
    print(f"Written: {target.relative_to(repo_root).as_posix()}")


if __name__ == "__main__":
    main()
