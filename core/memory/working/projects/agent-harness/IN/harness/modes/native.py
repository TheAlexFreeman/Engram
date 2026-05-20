from __future__ import annotations
import anthropic

from harness.stream import StreamSink
from harness.tools import Tool, ToolCall, ToolResult
from harness.prompts import system_prompt_native
from harness.usage import Usage


class NativeMode:
    def __init__(self, client: anthropic.Anthropic, model: str, tools: dict[str, Tool]):
        self.client = client
        self.model = model
        self.tools = tools
        self._system = system_prompt_native()
        self._tool_schemas = [
            {
                "name": t.name,
                "description": t.description,
                "input_schema": t.input_schema,
            }
            for t in tools.values()
        ]

    def initial_messages(self, task: str, prior: str, tools: dict[str, Tool]) -> list[dict]:
        user = (
            task
            if not prior.strip()
            else (f"Prior session notes (for context; may be stale):\n\n{prior}\n\n---\n\n{task}")
        )
        return [{"role": "user", "content": user}]

    def complete(self, messages: list[dict], *, stream: StreamSink | None = None):
        if stream is None:
            return self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=self._system,
                tools=self._tool_schemas,
                messages=messages,
            )
        return self._complete_streaming(messages, stream)

    def _complete_streaming(self, messages: list[dict], sink: StreamSink):
        """Stream via ``client.messages.stream``; dispatch content-block events
        to ``sink`` and return the fully reconstructed ``Message`` so downstream
        helpers (``extract_tool_calls``, ``as_assistant_message``,
        ``extract_usage``, ``final_text``) work unchanged."""
        try:
            with self.client.messages.stream(
                model=self.model,
                max_tokens=4096,
                system=self._system,
                tools=self._tool_schemas,
                messages=messages,
            ) as s:
                open_blocks: dict[int, str] = {}
                for event in s:
                    etype = getattr(event, "type", None)
                    if etype == "content_block_start":
                        block = getattr(event, "content_block", None)
                        idx = getattr(event, "index", None)
                        kind = getattr(block, "type", "") or ""
                        name = getattr(block, "name", None)
                        call_id = getattr(block, "id", None)
                        open_blocks[idx] = kind
                        sink.on_block_start(
                            kind, index=idx, name=name, call_id=call_id
                        )
                    elif etype == "content_block_delta":
                        delta = getattr(event, "delta", None)
                        idx = getattr(event, "index", None)
                        dtype = getattr(delta, "type", None)
                        if dtype == "text_delta":
                            sink.on_text_delta(getattr(delta, "text", "") or "")
                        elif dtype == "thinking_delta":
                            sink.on_reasoning_delta(
                                getattr(delta, "thinking", "") or ""
                            )
                        elif dtype == "input_json_delta":
                            sink.on_tool_args_delta(
                                getattr(delta, "partial_json", "") or "",
                                index=idx,
                            )
                    elif etype == "content_block_stop":
                        idx = getattr(event, "index", None)
                        kind = open_blocks.pop(idx, "")
                        sink.on_block_end(kind, index=idx)
                return s.get_final_message()
        except BaseException as exc:
            sink.on_error(exc)
            raise

    def as_assistant_message(self, response) -> dict:
        return {"role": "assistant", "content": response.content}

    def extract_tool_calls(self, response) -> list[ToolCall]:
        calls = []
        for block in response.content:
            if block.type == "tool_use":
                calls.append(ToolCall(name=block.name, args=block.input, id=block.id))
        return calls

    def as_tool_results_message(self, results: list[ToolResult]) -> dict:
        return {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": r.call.id,
                    "content": r.content,
                    "is_error": r.is_error,
                }
                for r in results
            ],
        }

    def final_text(self, response) -> str:
        return "".join(b.text for b in response.content if b.type == "text")

    def extract_usage(self, response) -> Usage:
        u = getattr(response, "usage", None)
        if u is None:
            return Usage(model=self.model)
        return Usage(
            model=self.model,
            input_tokens=int(getattr(u, "input_tokens", 0) or 0),
            output_tokens=int(getattr(u, "output_tokens", 0) or 0),
            cache_read_tokens=int(getattr(u, "cache_read_input_tokens", 0) or 0),
            cache_write_tokens=int(getattr(u, "cache_creation_input_tokens", 0) or 0),
        )
