from __future__ import annotations

import io

from harness.stream import NullStreamSink, StderrStreamPrinter


def _render(events):
    """Play a sequence of method-name/kwargs events against a printer whose
    output is captured in-memory, and return the resulting stderr string."""
    buf = io.StringIO()
    sink = StderrStreamPrinter(stream=buf, max_block_chars=100)
    for method, kwargs in events:
        getattr(sink, method)(**kwargs)
    return buf.getvalue()


def test_text_block_writes_header_then_deltas_then_trailing_newline():
    out = _render(
        [
            ("on_block_start", {"kind": "text", "index": 0}),
            ("on_text_delta", {"text": "Hello"}),
            ("on_text_delta", {"text": ", world"}),
            ("on_block_end", {"kind": "text", "index": 0}),
        ]
    )
    assert out == "\n[assistant]\nHello, world\n"


def test_reasoning_block_uses_reasoning_header():
    out = _render(
        [
            ("on_block_start", {"kind": "thinking", "index": 1}),
            ("on_reasoning_delta", {"text": "let me think"}),
            ("on_block_end", {"kind": "thinking", "index": 1}),
        ]
    )
    assert out == "\n[reasoning]\nlet me think\n"


def test_tool_use_header_includes_name_and_id_and_streams_args():
    out = _render(
        [
            (
                "on_block_start",
                {"kind": "tool_use", "index": 2, "name": "bash", "call_id": "toolu_1"},
            ),
            (
                "on_tool_args_delta",
                {"text": '{"cmd":', "index": 2, "call_id": "toolu_1", "name": "bash"},
            ),
            (
                "on_tool_args_delta",
                {"text": '"ls"}', "index": 2, "call_id": "toolu_1", "name": "bash"},
            ),
            ("on_block_end", {"kind": "tool_use", "index": 2}),
        ]
    )
    assert out == '\n[tool_use:bash id=toolu_1]\n{"cmd":"ls"}\n'


def test_soft_truncation_caps_block_and_appends_dropped_suffix():
    buf = io.StringIO()
    sink = StderrStreamPrinter(stream=buf, max_block_chars=5)
    sink.on_block_start("text", index=0)
    sink.on_text_delta("abc")
    sink.on_text_delta("defghij")
    sink.on_block_end("text", index=0)
    assert buf.getvalue() == "\n[assistant]\nabcde... (+5 more)\n"


def test_opening_new_block_auto_closes_previous_with_newline():
    out = _render(
        [
            ("on_block_start", {"kind": "text", "index": 0}),
            ("on_text_delta", {"text": "A"}),
            ("on_block_start", {"kind": "text", "index": 1}),
            ("on_text_delta", {"text": "B"}),
            ("on_block_end", {"kind": "text", "index": 1}),
        ]
    )
    assert out == "\n[assistant]\nA\n\n[assistant]\nB\n"


def test_on_error_terminates_open_block_and_writes_error_line():
    buf = io.StringIO()
    sink = StderrStreamPrinter(stream=buf, max_block_chars=100)
    sink.on_block_start("text", index=0)
    sink.on_text_delta("partial")
    sink.on_error(RuntimeError("boom"))
    assert buf.getvalue() == "\n[assistant]\npartial\n[stream error] RuntimeError: boom\n"


def test_null_stream_sink_is_callable_and_silent():
    sink = NullStreamSink()
    sink.on_block_start("text", index=0)
    sink.on_text_delta("x")
    sink.on_reasoning_delta("y")
    sink.on_tool_args_delta("z", index=0, call_id="c", name="n")
    sink.on_block_end("text", index=0)
    sink.on_error(RuntimeError("ok"))
    sink.flush()
