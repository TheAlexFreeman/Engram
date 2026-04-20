from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from harness.loop import run
from harness.tools import Tool, ToolCall, ToolResult
from harness.tools.fs import WorkspaceScope
from harness.tools.todos import WriteTodos
from harness.usage import Usage


class SleepingTool:
    """Tool whose run() sleeps for a configurable duration."""

    description = "sleep tool for tests"
    input_schema = {
        "type": "object",
        "properties": {"duration": {"type": "number"}},
    }

    def __init__(self, name: str):
        self.name = name

    def run(self, args: dict) -> str:
        duration = float(args.get("duration", 0.0))
        time.sleep(duration)
        return f"slept {duration}s (tool={self.name}, tag={args.get('tag', '')})"


@dataclass
class _ScriptedResponse:
    tool_calls: list[ToolCall]
    text: str = ""


class ScriptedMode:
    """Mode stub that emits a fixed sequence of responses."""

    def __init__(self, responses: list[_ScriptedResponse]):
        self._responses = list(responses)
        self._idx = 0

    def initial_messages(self, task: str, prior: str, tools: dict[str, Tool]) -> list[dict]:
        return [{"role": "user", "content": task}]

    def complete(self, messages: list[dict], *, stream: Any = None) -> Any:
        resp = self._responses[self._idx]
        self._idx += 1
        return resp

    def as_assistant_message(self, response: Any) -> dict:
        return {"role": "assistant", "content": response.text}

    def extract_tool_calls(self, response: Any) -> list[ToolCall]:
        return response.tool_calls

    def as_tool_results_message(self, results: list[ToolResult]) -> dict:
        return {"role": "user", "content": [r.content for r in results]}

    def final_text(self, response: Any) -> str:
        return response.text

    def extract_usage(self, response: Any) -> Usage:
        return Usage.zero()


class NullTracer:
    def event(self, kind: str, **data: Any) -> None:
        pass

    def close(self) -> None:
        pass


@dataclass
class RecordingMemory:
    prior: str = ""
    notes: list[tuple[str, str]] = field(default_factory=list)
    summary: str | None = None

    def start_session(self, task: str) -> str:
        return self.prior

    def recall(self, query: str, k: int = 5):
        return []

    def record(self, content: str, kind: str = "note") -> None:
        self.notes.append((kind, content))

    def end_session(self, summary: str) -> None:
        self.summary = summary


def _build_run(
    tool_call_args: list[dict],
    tool_name: str = "sleep",
) -> tuple[dict[str, Tool], ScriptedMode, RecordingMemory]:
    tool = SleepingTool(tool_name)
    tools: dict[str, Tool] = {tool_name: tool}
    calls = [
        ToolCall(name=tool_name, args=args, id=f"call_{i}")
        for i, args in enumerate(tool_call_args)
    ]
    mode = ScriptedMode(
        [
            _ScriptedResponse(tool_calls=calls),
            _ScriptedResponse(tool_calls=[], text="done"),
        ]
    )
    return tools, mode, RecordingMemory()


def test_parallel_execution_is_concurrent():
    tools, mode, memory = _build_run(
        [{"duration": 0.3, "tag": str(i)} for i in range(4)]
    )

    start = time.monotonic()
    result = run(
        task="go",
        mode=mode,
        tools=tools,
        memory=memory,
        tracer=NullTracer(),
        max_parallel_tools=4,
    )
    elapsed = time.monotonic() - start

    assert result.final_text == "done"
    # Sequential would be ~1.2s; parallel should be well under 1.0s.
    assert elapsed < 1.0, f"parallel execution too slow: {elapsed:.3f}s"


def test_parallel_preserves_order_with_mixed_latencies():
    durations = [0.3, 0.05, 0.2, 0.1]
    tools, mode, memory = _build_run(
        [{"duration": d, "tag": str(i)} for i, d in enumerate(durations)]
    )

    captured: list[ToolResult] = []
    original = mode.as_tool_results_message

    def capture(results: list[ToolResult]):
        captured.extend(results)
        return original(results)

    mode.as_tool_results_message = capture  # type: ignore[method-assign]

    run(
        task="go",
        mode=mode,
        tools=tools,
        memory=memory,
        tracer=NullTracer(),
        max_parallel_tools=4,
    )

    assert [r.call.id for r in captured] == [f"call_{i}" for i in range(len(durations))]
    for i, r in enumerate(captured):
        assert f"tag={i}" in r.content


def test_max_parallel_tools_one_is_sequential():
    tools, mode, memory = _build_run(
        [{"duration": 0.3, "tag": str(i)} for i in range(4)]
    )

    start = time.monotonic()
    run(
        task="go",
        mode=mode,
        tools=tools,
        memory=memory,
        tracer=NullTracer(),
        max_parallel_tools=1,
    )
    elapsed = time.monotonic() - start

    # Sequential: ~1.2s. Give generous lower bound to avoid flakiness.
    assert elapsed >= 1.1, f"expected sequential behavior, got {elapsed:.3f}s"


def test_todos_save_is_thread_safe(tmp_path: Path):
    scope = WorkspaceScope(root=tmp_path)
    writer = WriteTodos(scope)

    n_threads = 16
    errors: list[BaseException] = []

    def write(i: int) -> None:
        try:
            writer.run(
                {
                    "todos": [
                        {
                            "id": f"writer-{i}",
                            "content": f"content from writer {i}",
                            "status": "pending",
                        }
                    ]
                }
            )
        except BaseException as exc:
            errors.append(exc)

    threads = [threading.Thread(target=write, args=(i,)) for i in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"concurrent writes raised: {errors!r}"

    # Final file must parse cleanly and match exactly one writer's payload.
    path = tmp_path / "todos.json"
    assert path.exists()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, list)
    assert len(data) == 1
    row = data[0]
    assert row["status"] == "pending"
    assert row["id"].startswith("writer-")
    idx = int(row["id"].split("-", 1)[1])
    assert 0 <= idx < n_threads
    assert row["content"] == f"content from writer {idx}"

    # No leftover .tmp files from the unique-tempfile path.
    leftovers = [p.name for p in tmp_path.iterdir() if p.name != "todos.json"]
    assert not leftovers, f"unexpected leftover files: {leftovers}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
