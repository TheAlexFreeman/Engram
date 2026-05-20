from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from harness.memory import MemoryBackend
from harness.modes.base import Mode
from harness.pricing import PricingTable, compute_cost, load_pricing
from harness.stream import StreamSink
from harness.tools import Tool, execute
from harness.trace import TraceSink
from harness.usage import Usage


@dataclass
class RunResult:
    final_text: str
    usage: Usage


def run(
    task: str,
    mode: Mode,
    tools: dict[str, Tool],
    memory: MemoryBackend,
    tracer: TraceSink,
    max_turns: int = 100,
    pricing: PricingTable | None = None,
    max_parallel_tools: int = 4,
    stream_sink: StreamSink | None = None,
) -> RunResult:
    if pricing is None:
        pricing = load_pricing()

    prior = memory.start_session(task)
    messages = mode.initial_messages(task=task, prior=prior, tools=tools)
    tracer.event("session_start", task=task)

    total = Usage.zero()

    for turn in range(max_turns):
        response = mode.complete(messages, stream=stream_sink)
        tracer.event("model_response", turn=turn)

        turn_usage = compute_cost(mode.extract_usage(response), pricing)
        total = total + turn_usage
        tracer.event("usage", turn=turn, **turn_usage.as_trace_dict())

        messages.append(mode.as_assistant_message(response))

        tool_calls = mode.extract_tool_calls(response)
        if not tool_calls:
            final = mode.final_text(response)
            memory.end_session(summary=final[:500])
            tracer.event("session_usage", **total.as_trace_dict())
            tracer.event("session_end", turns=turn + 1)
            return RunResult(final_text=final, usage=total)

        for call in tool_calls:
            tracer.event("tool_call", name=call.name, args=call.args)

        if max_parallel_tools <= 1 or len(tool_calls) == 1:
            results = [execute(c, tools) for c in tool_calls]
        else:
            workers = min(max_parallel_tools, len(tool_calls))
            tracer.event(
                "tool_dispatch",
                count=len(tool_calls),
                max_parallel=workers,
            )
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = [pool.submit(execute, c, tools) for c in tool_calls]
                results = [f.result() for f in futures]

        for result in results:
            tracer.event(
                "tool_result",
                name=result.call.name,
                is_error=result.is_error,
                content_preview=result.content[:200],
            )
            if result.is_error:
                memory.record(
                    f"{result.call.name} failed: {result.content[:200]}",
                    kind="error",
                )

        tool_results_msg = mode.as_tool_results_message(results)
        if isinstance(tool_results_msg, list):
            messages.extend(tool_results_msg)
        else:
            messages.append(tool_results_msg)

    tracer.event("session_usage", **total.as_trace_dict())
    tracer.event("session_end", turns=max_turns, reason="max_turns")
    memory.end_session(summary="(max turns reached)")
    return RunResult(
        final_text="(max turns reached without completion)",
        usage=total,
    )
