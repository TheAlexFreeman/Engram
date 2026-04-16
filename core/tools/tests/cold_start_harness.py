"""Cold-start latency reproduction harness (P0-A step 2).

Calls ``memory_context_project`` for every project discovered under
``memory/working/projects/`` in the live repo, extracts per-span timings from
the response metadata, and reports wall time plus span breakdowns per project.

Three usage patterns:

1. CLI report (primary use):

   .. code-block:: text

       python core/tools/tests/cold_start_harness.py
       python core/tools/tests/cold_start_harness.py --json
       python core/tools/tests/cold_start_harness.py --project rate-my-set

2. Library entry point: ``run_harness(repo_root)`` returns a list of
   per-project result dicts. Suitable for integration with
   ``memory_session_health_check`` or external latency regression tooling.

3. Pytest smoke test: the ``TestColdStartHarness`` class below runs the
   harness in a minimal synthetic repo so the harness itself is covered by the
   regular test suite. It does **not** regress-check live-repo latency — that
   is the operator's responsibility, since CI runs against synthetic fixtures
   without the full project tree.

The roadmap (P0-A step 3) will add a hard server-side budget and
graceful-degradation flags to the tool itself; once those land, this harness
gains teeth as a regression gate (fail the run if any project exceeds the
budget by more than a small margin).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from typing import Any, cast

REPO_ROOT = Path(__file__).resolve().parents[3]

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.tools.agent_memory_mcp.server import create_mcp  # noqa: E402

# Projects directory names we always skip. ``OUT`` is the repo-level emitted
# artifacts folder; names starting with ``_`` or ``.`` are tombstoned/hidden
# per the Engram convention.
_SKIP_PROJECT_NAMES = frozenset({"OUT"})


def _parse_context_response(payload: str) -> tuple[dict[str, Any], str]:
    """Split the tool's ``markdown+json-header`` payload into metadata + body."""
    prefix = "```json\n"
    if not payload.startswith(prefix):
        raise ValueError("memory_context_project response missing JSON header prefix")
    metadata_text, body = payload[len(prefix) :].split("\n```\n\n", 1)
    return cast(dict[str, Any], json.loads(metadata_text)), body


def discover_projects(content_root: Path) -> list[str]:
    """Return the list of project IDs under ``memory/working/projects/``.

    Filters out ``OUT`` and any name starting with ``_`` or ``.``. Returns a
    stable sort order so harness output is diffable across runs.
    """
    projects_dir = content_root / "memory" / "working" / "projects"
    if not projects_dir.is_dir():
        return []
    return sorted(
        entry.name
        for entry in projects_dir.iterdir()
        if entry.is_dir()
        and entry.name not in _SKIP_PROJECT_NAMES
        and not entry.name.startswith(("_", "."))
    )


async def _probe_project(tool: Any, project_id: str) -> dict[str, Any]:
    """Call ``memory_context_project`` for a single project and record timings.

    Returns a result dict with:
    - ``project``: project ID
    - ``wall_ms``: wall-clock time for the tool call (harness-side)
    - ``server_total_ms``: total from the tool's internal timing collector
    - ``spans``: list of {name, duration_ms, status} dicts
    - ``error``: string if the tool raised, else None
    - ``loaded_files``: list of files the tool read (for cross-checking scope)
    """
    started_ns = time.perf_counter_ns()
    try:
        payload = await tool(project=project_id)
    except Exception as exc:  # noqa: BLE001 — harness records every failure
        wall_ms = (time.perf_counter_ns() - started_ns) / 1_000_000
        return {
            "project": project_id,
            "wall_ms": round(wall_ms, 3),
            "server_total_ms": None,
            "spans": [],
            "loaded_files": [],
            "error": f"{type(exc).__name__}: {exc}",
        }

    wall_ms = (time.perf_counter_ns() - started_ns) / 1_000_000
    try:
        metadata, _ = _parse_context_response(payload)
    except ValueError as exc:
        return {
            "project": project_id,
            "wall_ms": round(wall_ms, 3),
            "server_total_ms": None,
            "spans": [],
            "loaded_files": [],
            "error": f"response parse error: {exc}",
        }

    timings = metadata.get("timings", {})
    return {
        "project": project_id,
        "wall_ms": round(wall_ms, 3),
        "server_total_ms": timings.get("total_ms"),
        "spans": timings.get("spans", []),
        "loaded_files": metadata.get("loaded_files", []),
        "error": None,
    }


def run_harness(repo_root: Path, *, only_project: str | None = None) -> list[dict[str, Any]]:
    """Run the harness synchronously and return per-project results."""
    _, tools, _, repo = create_mcp(repo_root)
    tool = tools["memory_context_project"]
    content_root = repo.content_root
    projects = discover_projects(content_root)
    if only_project is not None:
        projects = [p for p in projects if p == only_project]
        if not projects:
            raise SystemExit(f"project {only_project!r} not found under {content_root}")

    async def _run_all() -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for project_id in projects:
            results.append(await _probe_project(tool, project_id))
        return results

    return asyncio.run(_run_all())


def _format_text_report(results: list[dict[str, Any]]) -> str:
    """Render a human-readable timing report."""
    lines: list[str] = []
    header = f"{'project':<30} {'wall_ms':>10} {'server_ms':>10} {'status':>10}"
    lines.append(header)
    lines.append("-" * len(header))
    for result in results:
        status = "error" if result["error"] else "ok"
        server_ms = result["server_total_ms"]
        server_display = (
            f"{server_ms:>10.1f}" if isinstance(server_ms, (int, float)) else f"{'-':>10}"
        )
        lines.append(
            f"{result['project']:<30} {result['wall_ms']:>10.1f} {server_display} {status:>10}"
        )
        if result["error"]:
            lines.append(f"    ! {result['error']}")
        for span in result["spans"]:
            lines.append(
                f"    {span['name']:<28} {span['duration_ms']:>10.1f} ms  "
                f"[{span.get('status', '?')}]"
            )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit results as a single JSON array instead of the text report.",
    )
    parser.add_argument(
        "--project",
        metavar="NAME",
        default=None,
        help="Restrict the run to one project ID.",
    )
    parser.add_argument(
        "--repo-root",
        metavar="PATH",
        default=None,
        help=(
            "Override the repo root; defaults to the worktree this script lives "
            "in (auto-detected from __file__)."
        ),
    )
    args = parser.parse_args(argv)
    repo_root = Path(args.repo_root).resolve() if args.repo_root else REPO_ROOT
    results = run_harness(repo_root, only_project=args.project)
    if args.json:
        json.dump(results, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        sys.stdout.write(_format_text_report(results))
    return 0


# ---------------------------------------------------------------------------
# Smoke tests — ensure the harness runs end-to-end on a minimal synthetic repo
# so that future refactors of ``memory_context_project`` or the timing schema
# don't silently break the harness itself. Latency thresholds are deliberately
# NOT enforced here — production thresholds live in the server-side budget
# (P0-A step 3), not in a fixture test.


class TestColdStartHarness(unittest.TestCase):
    def _init_fixture_repo(self, tmp: Path, project_ids: list[str]) -> Path:
        core = tmp / "core"
        memory = core / "memory"
        (memory / "working" / "projects").mkdir(parents=True, exist_ok=True)
        (core / "INIT.md").write_text("# Init\n", encoding="utf-8")
        for project_id in project_ids:
            project_dir = memory / "working" / "projects" / project_id
            project_dir.mkdir(parents=True, exist_ok=True)
            (project_dir / "SUMMARY.md").write_text(
                f"# {project_id}\n\nHarness fixture project.\n", encoding="utf-8"
            )
        subprocess.run(["git", "init"], cwd=tmp, check=True, capture_output=True, text=True)
        subprocess.run(
            ["git", "config", "user.email", "harness@test"],
            cwd=tmp,
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Harness"],
            cwd=tmp,
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(["git", "add", "."], cwd=tmp, check=True, capture_output=True, text=True)
        subprocess.run(
            ["git", "commit", "-m", "seed"],
            cwd=tmp,
            check=True,
            capture_output=True,
            text=True,
        )
        return tmp

    def test_discover_projects_filters_out_and_hidden(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            tmp = Path(tmp_name)
            projects_root = tmp / "memory" / "working" / "projects"
            for name in ("alpha", "beta", "OUT", "_archive", ".hidden"):
                (projects_root / name).mkdir(parents=True)
            discovered = discover_projects(tmp)
            self.assertEqual(discovered, ["alpha", "beta"])

    def test_run_harness_returns_one_entry_per_project(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            tmp = Path(tmp_name)
            self._init_fixture_repo(tmp, ["alpha", "beta"])
            results = run_harness(tmp)

            self.assertEqual([r["project"] for r in results], ["alpha", "beta"])
            for result in results:
                self.assertIsNone(
                    result["error"],
                    msg=f"Unexpected harness error for {result['project']}: {result['error']}",
                )
                self.assertGreaterEqual(result["wall_ms"], 0)
                self.assertIsNotNone(result["server_total_ms"])
                self.assertIsInstance(result["spans"], list)
                span_names = {span["name"] for span in result["spans"]}
                # ``project_summary`` is always attempted; ``plan_selection`` is
                # wrapped even when no plans exist. These assertions fail fast
                # if the timing schema is accidentally renamed.
                self.assertIn("project_summary", span_names)
                self.assertIn("plan_selection", span_names)

    def test_run_harness_restricts_to_single_project(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            tmp = Path(tmp_name)
            self._init_fixture_repo(tmp, ["alpha", "beta"])
            results = run_harness(tmp, only_project="beta")

            self.assertEqual([r["project"] for r in results], ["beta"])

    def test_format_text_report_includes_project_and_spans(self) -> None:
        results = [
            {
                "project": "alpha",
                "wall_ms": 12.34,
                "server_total_ms": 10.0,
                "spans": [{"name": "project_summary", "duration_ms": 2.5, "status": "ok"}],
                "loaded_files": [],
                "error": None,
            }
        ]
        report = _format_text_report(results)

        self.assertIn("alpha", report)
        self.assertIn("project_summary", report)
        self.assertIn("12.3", report)


if __name__ == "__main__":
    raise SystemExit(main())
