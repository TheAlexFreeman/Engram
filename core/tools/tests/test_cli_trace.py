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


cmd_trace = _load_module("engram_mcp.agent_memory_mcp.cli.cmd_trace")
cli_main = _load_module("engram_mcp.agent_memory_mcp.cli.main")


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _trace_args(
    *,
    json_output: bool = False,
    session_id: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    span_type: str | None = None,
    plan_id: str | None = None,
    status: str | None = None,
    limit: int = 100,
):
    return type(
        "Args",
        (),
        {
            "json": json_output,
            "session_id": session_id,
            "date_from": date_from,
            "date_to": date_to,
            "span_type": span_type,
            "plan_id": plan_id,
            "status": status,
            "limit": limit,
        },
    )()


def _seed_trace_repo(tmp_path: Path) -> tuple[Path, Path]:
    repo_root = tmp_path / "repo"
    content_root = repo_root / "core"
    _write(
        content_root / "memory" / "activity" / "2026" / "04" / "01" / "chat-001.traces.jsonl",
        "\n".join(
            [
                json.dumps(
                    {
                        "span_id": "aaaa1111aaaa",
                        "session_id": "memory/activity/2026/04/01/chat-001",
                        "timestamp": "2026-04-01T09:00:00.000Z",
                        "span_type": "plan_action",
                        "name": "start",
                        "status": "ok",
                        "duration_ms": 25,
                        "metadata": {
                            "plan_id": "tracked-plan",
                            "phase_id": "phase-a",
                            "action": "start",
                        },
                        "cost": {"tokens_in": 8, "tokens_out": 3},
                    }
                ),
                json.dumps(
                    {
                        "span_id": "bbbb2222bbbb",
                        "session_id": "memory/activity/2026/04/01/chat-001",
                        "timestamp": "2026-04-01T09:05:00.000Z",
                        "span_type": "retrieval",
                        "name": "briefing",
                        "status": "ok",
                        "duration_ms": 5,
                    }
                ),
            ]
        )
        + "\n",
    )
    _write(
        content_root / "memory" / "activity" / "2026" / "04" / "03" / "chat-010.traces.jsonl",
        "\n".join(
            [
                json.dumps(
                    {
                        "span_id": "cccc3333cccc",
                        "session_id": "memory/activity/2026/04/03/chat-010",
                        "timestamp": "2026-04-03T10:00:00.000Z",
                        "span_type": "verification",
                        "name": "check-postconditions",
                        "status": "error",
                        "duration_ms": 50,
                        "metadata": {
                            "plan_id": "tracked-plan",
                            "phase_id": "phase-b",
                            "action": "verify",
                        },
                        "cost": {"tokens_in": 12, "tokens_out": 4},
                    }
                ),
                json.dumps(
                    {
                        "span_id": "dddd4444dddd",
                        "session_id": "memory/activity/2026/04/03/chat-010",
                        "timestamp": "2026-04-03T10:05:00.000Z",
                        "span_type": "tool_call",
                        "name": "memory_plan_show",
                        "status": "ok",
                        "duration_ms": 10,
                        "metadata": {"plan_id": "other-plan", "phase_id": "phase-z"},
                    }
                ),
            ]
        )
        + "\n",
    )
    return repo_root, content_root


def test_trace_human_output_is_empty_when_no_spans_exist(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo_root = tmp_path / "repo"
    content_root = repo_root / "core"
    content_root.mkdir(parents=True, exist_ok=True)

    exit_code = cmd_trace.run_trace(
        _trace_args(limit=5), repo_root=repo_root, content_root=content_root
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Trace query" in output
    assert "No trace spans found." in output


def test_trace_json_filters_by_plan_and_reports_aggregates(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo_root, content_root = _seed_trace_repo(tmp_path)

    exit_code = cmd_trace.run_trace(
        _trace_args(json_output=True, plan_id="tracked-plan", limit=10),
        repo_root=repo_root,
        content_root=content_root,
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["total_matched"] == 2
    assert payload["spans"][0]["span_id"] == "cccc3333cccc"
    assert payload["spans"][1]["span_id"] == "aaaa1111aaaa"
    assert payload["aggregates"]["total_duration_ms"] == 75
    assert payload["aggregates"]["total_cost"] == {"tokens_in": 20, "tokens_out": 7}
    assert payload["aggregates"]["by_type"] == {"plan_action": 1, "verification": 1}
    assert payload["aggregates"]["by_status"] == {"error": 1, "ok": 1}
    assert payload["aggregates"]["error_rate"] == 0.5


def test_trace_session_id_overrides_date_file_discovery(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo_root, content_root = _seed_trace_repo(tmp_path)

    exit_code = cmd_trace.run_trace(
        _trace_args(
            json_output=True,
            session_id="memory/activity/2026/04/01/chat-001",
            date_from="2026-04-03",
            date_to="2026-04-03",
            limit=10,
        ),
        repo_root=repo_root,
        content_root=content_root,
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["total_matched"] == 2
    assert {span["span_id"] for span in payload["spans"]} == {"aaaa1111aaaa", "bbbb2222bbbb"}


def test_trace_human_output_renders_filters_and_metadata(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo_root, content_root = _seed_trace_repo(tmp_path)

    exit_code = cmd_trace.run_trace(
        _trace_args(plan_id="tracked-plan", status="error", limit=5),
        repo_root=repo_root,
        content_root=content_root,
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Trace query (plan=tracked-plan, status=error)" in output
    assert "Matched spans: 1" in output
    assert "[verification/error] check-postconditions" in output
    assert "metadata: action=verify | phase_id=phase-b | plan_id=tracked-plan" in output
    assert "cost: in=12 out=4" in output


def test_trace_rejects_invalid_date_in_json_mode(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo_root, content_root = _seed_trace_repo(tmp_path)

    exit_code = cmd_trace.run_trace(
        _trace_args(json_output=True, date_from="2026/04/03"),
        repo_root=repo_root,
        content_root=content_root,
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 2
    assert payload["valid"] is False
    assert payload["errors"] == ["date_from must be in YYYY-MM-DD format"]


def test_trace_command_is_registered_in_main_parser() -> None:
    parser = cli_main.build_parser()
    args = parser.parse_args(["trace", "--plan", "tracked-plan", "--json"])

    assert args.command == "trace"
    assert args.plan_id == "tracked-plan"
    assert args.json is True
    assert args.handler is cmd_trace.run_trace
