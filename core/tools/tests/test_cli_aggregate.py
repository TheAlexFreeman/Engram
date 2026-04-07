from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]


def _load_module(module_name: str) -> ModuleType:
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    return importlib.import_module(module_name)


cmd_aggregate = _load_module("engram_mcp.agent_memory_mcp.cli.cmd_aggregate")
cli_main = _load_module("engram_mcp.agent_memory_mcp.cli.main")


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _aggregate_args(*, json_output: bool = False, namespace: str | None = None):
    return type(
        "Args",
        (),
        {
            "json": json_output,
            "namespace": namespace,
            "dry_run": False,
        },
    )()


def _seed_aggregate_repo(tmp_path: Path) -> tuple[Path, Path]:
    repo_root = tmp_path / "repo"
    content_root = repo_root / "core"
    _write(
        content_root / "INIT.md",
        "# Session Init\n\n"
        "| Parameter | Active value | Stage |\n"
        "|---|---|---|\n"
        "| Aggregation trigger | 3 entries | Exploration |\n",
    )
    _write(content_root / "memory" / "knowledge" / "topic.md", "# Topic\n")
    _write(content_root / "memory" / "working" / "projects" / "demo.md", "# Demo\n")
    _write(content_root / "memory" / "skills" / "session-start" / "SKILL.md", "# Session Start\n")
    _write(
        content_root / "memory" / "knowledge" / "SUMMARY.md",
        "# Knowledge\n\n## Usage patterns\n\n_No access data yet._\n",
    )
    _write(
        content_root / "memory" / "working" / "projects" / "SUMMARY.md",
        "# Plans\n\n## Usage patterns\n\n_No access data yet._\n",
    )
    _write(
        content_root / "memory" / "skills" / "SUMMARY.md",
        "# Skills\n\n## Usage patterns\n\n_No access data yet._\n",
    )
    _write(
        content_root / "memory" / "knowledge" / "ACCESS.jsonl",
        "\n".join(
            [
                json.dumps(
                    {
                        "date": "2026-03-18",
                        "session_id": "memory/activity/2026/03/18/chat-001",
                        "file": "memory/knowledge/topic.md",
                        "helpfulness": 0.8,
                    }
                ),
                json.dumps(
                    {
                        "date": "2026-03-19",
                        "session_id": "memory/activity/2026/03/19/chat-001",
                        "file": "memory/knowledge/topic.md",
                        "helpfulness": 0.8,
                    }
                ),
                json.dumps(
                    {
                        "date": "2026-03-20",
                        "session_id": "memory/activity/2026/03/20/chat-001",
                        "file": "memory/knowledge/topic.md",
                        "helpfulness": 0.8,
                    }
                ),
            ]
        )
        + "\n",
    )
    _write(
        content_root / "memory" / "working" / "projects" / "ACCESS.jsonl",
        "\n".join(
            [
                json.dumps(
                    {
                        "date": "2026-03-18",
                        "session_id": "memory/activity/2026/03/18/chat-001",
                        "file": "memory/working/projects/demo.md",
                        "helpfulness": 0.7,
                    }
                ),
                json.dumps(
                    {
                        "date": "2026-03-19",
                        "session_id": "memory/activity/2026/03/19/chat-001",
                        "file": "memory/working/projects/demo.md",
                        "helpfulness": 0.7,
                    }
                ),
                json.dumps(
                    {
                        "date": "2026-03-20",
                        "session_id": "memory/activity/2026/03/20/chat-001",
                        "file": "memory/working/projects/demo.md",
                        "helpfulness": 0.7,
                    }
                ),
            ]
        )
        + "\n",
    )
    _write(
        content_root / "memory" / "skills" / "ACCESS.jsonl",
        "\n".join(
            [
                json.dumps(
                    {
                        "date": "2026-03-18",
                        "session_id": "memory/activity/2026/03/18/chat-001",
                        "file": "memory/skills/session-start/SKILL.md",
                        "helpfulness": 0.9,
                    }
                ),
                json.dumps(
                    {
                        "date": "2026-03-19",
                        "session_id": "memory/activity/2026/03/19/chat-001",
                        "file": "memory/skills/session-start/SKILL.md",
                        "helpfulness": 0.9,
                    }
                ),
                json.dumps(
                    {
                        "date": "2026-03-20",
                        "session_id": "memory/activity/2026/03/20/chat-001",
                        "file": "memory/skills/session-start/SKILL.md",
                        "helpfulness": 0.9,
                    }
                ),
            ]
        )
        + "\n",
    )
    return repo_root, content_root


def test_aggregate_human_output_reports_preview(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo_root, content_root = _seed_aggregate_repo(tmp_path)

    exit_code = cmd_aggregate.run_aggregate(
        _aggregate_args(),
        repo_root=repo_root,
        content_root=content_root,
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Aggregation preview" in output
    assert "Entries processed: 9" in output
    assert "- memory/knowledge/SUMMARY.md" in output
    assert (
        "1. memory/knowledge/topic.md + memory/skills/session-start/SKILL.md + memory/working/projects/demo.md (3 session groups)"
        in output
    )


def test_aggregate_json_filters_by_namespace(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo_root, content_root = _seed_aggregate_repo(tmp_path)

    exit_code = cmd_aggregate.run_aggregate(
        _aggregate_args(json_output=True, namespace="knowledge"),
        repo_root=repo_root,
        content_root=content_root,
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["namespace"] == "knowledge"
    assert payload["entries_processed"] == 3
    assert payload["hot_access_targets"] == ["memory/knowledge/ACCESS.jsonl"]
    assert payload["summary_materialization_targets"] == ["memory/knowledge/SUMMARY.md"]
    assert payload["clusters"] == []


def test_aggregate_json_includes_threshold_reports(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo_root, content_root = _seed_aggregate_repo(tmp_path)

    exit_code = cmd_aggregate.run_aggregate(
        _aggregate_args(json_output=True),
        repo_root=repo_root,
        content_root=content_root,
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["aggregation_trigger"] == 3
    assert payload["reports"][0]["status"] == "above"
    assert payload["reports"][0]["remaining_to_trigger"] == 0
    assert sorted(payload["above_trigger"]) == [
        "memory/knowledge/ACCESS.jsonl",
        "memory/skills/ACCESS.jsonl",
        "memory/working/projects/ACCESS.jsonl",
    ]


def test_aggregate_command_is_registered_in_main_parser() -> None:
    parser = cli_main.build_parser()
    args = parser.parse_args(["aggregate", "--namespace", "knowledge", "--json"])

    assert args.command == "aggregate"
    assert args.namespace == "knowledge"
    assert args.json is True
    assert args.handler is cmd_aggregate.run_aggregate
