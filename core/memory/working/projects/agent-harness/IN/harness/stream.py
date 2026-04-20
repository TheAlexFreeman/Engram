from __future__ import annotations

import sys
import threading
from typing import IO, Any, Protocol


class StreamSink(Protocol):
    """Receives delta events emitted while a model response is streaming.

    Modes call these methods as events arrive from the provider; sinks decide
    how to render or persist them. All methods must be safe to call in any
    order (e.g. a block may open, deltas flow, then the block closes)."""

    def on_block_start(
        self,
        kind: str,
        *,
        index: int | None = None,
        name: str | None = None,
        call_id: str | None = None,
    ) -> None: ...

    def on_text_delta(self, text: str) -> None: ...

    def on_reasoning_delta(self, text: str) -> None: ...

    def on_tool_args_delta(
        self,
        text: str,
        *,
        index: int | None = None,
        call_id: str | None = None,
        name: str | None = None,
    ) -> None: ...

    def on_block_end(self, kind: str, *, index: int | None = None) -> None: ...

    def on_error(self, exc: BaseException) -> None: ...

    def flush(self) -> None: ...


class NullStreamSink:
    """No-op ``StreamSink``. Used when live streaming is disabled so mode code
    can unconditionally call the sink without branching on ``None``."""

    def on_block_start(
        self,
        kind: str,
        *,
        index: int | None = None,
        name: str | None = None,
        call_id: str | None = None,
    ) -> None:
        pass

    def on_text_delta(self, text: str) -> None:
        pass

    def on_reasoning_delta(self, text: str) -> None:
        pass

    def on_tool_args_delta(
        self,
        text: str,
        *,
        index: int | None = None,
        call_id: str | None = None,
        name: str | None = None,
    ) -> None:
        pass

    def on_block_end(self, kind: str, *, index: int | None = None) -> None:
        pass

    def on_error(self, exc: BaseException) -> None:
        pass

    def flush(self) -> None:
        pass


class StderrStreamPrinter:
    """Write streaming model output to a text stream (default ``sys.stderr``).

    Rendering model:
    - Each block opens with a header line (``\\n[assistant]``, ``\\n[reasoning]``,
      ``\\n[tool_use:<name> id=<call_id>]``) so it stands apart from trace lines.
    - Deltas are written inline, unbuffered, with ``flush()`` after each write.
    - ``on_block_end`` emits a single trailing newline so whatever prints next
      (typically a ``ConsoleTracePrinter`` line) starts on a fresh line.
    - A soft cap (``max_block_chars``) limits per-block output; once reached,
      further deltas are dropped and a ``... (+N more)`` suffix is appended on
      ``on_block_end`` to keep stderr readable for giant tool-argument JSON.

    A ``threading.Lock`` serializes writes. ``complete()`` itself is single-
    threaded today, but the lock keeps partial writes coherent if a trace
    printer or another thread ever interleaves."""

    _HEADERS: dict[str, str] = {
        "text": "[assistant]",
        "assistant": "[assistant]",
        "reasoning": "[reasoning]",
        "thinking": "[reasoning]",
    }

    def __init__(
        self,
        stream: IO[str] | None = None,
        *,
        max_block_chars: int = 4000,
    ) -> None:
        self._stream: IO[str] = stream if stream is not None else sys.stderr
        self._max_block_chars = max_block_chars
        self._lock = threading.Lock()
        self._block_chars = 0
        self._block_dropped = 0
        self._block_open = False
        self._current_kind: str | None = None

    def _write(self, s: str) -> None:
        if not s:
            return
        self._stream.write(s)
        try:
            self._stream.flush()
        except Exception:
            pass

    def _write_delta(self, text: str) -> None:
        if not text:
            return
        remaining = self._max_block_chars - self._block_chars
        if remaining <= 0:
            self._block_dropped += len(text)
            return
        if len(text) <= remaining:
            self._write(text)
            self._block_chars += len(text)
            return
        self._write(text[:remaining])
        self._block_chars += remaining
        self._block_dropped += len(text) - remaining

    def _header_for(
        self,
        kind: str,
        *,
        name: str | None,
        call_id: str | None,
    ) -> str:
        if kind in ("tool_use", "function_call"):
            parts: list[str] = ["tool_use"]
            if name:
                parts.append(name)
            label = ":".join(parts)
            if call_id:
                return f"[{label} id={call_id}]"
            return f"[{label}]"
        if kind in ("web_search_call", "x_search_call"):
            return f"[{kind}]"
        return self._HEADERS.get(kind, f"[{kind}]")

    def on_block_start(
        self,
        kind: str,
        *,
        index: int | None = None,
        name: str | None = None,
        call_id: str | None = None,
    ) -> None:
        with self._lock:
            if self._block_open:
                self._close_block_locked(self._current_kind or kind)
            header = self._header_for(kind, name=name, call_id=call_id)
            self._write(f"\n{header}\n")
            self._block_open = True
            self._current_kind = kind
            self._block_chars = 0
            self._block_dropped = 0

    def on_text_delta(self, text: str) -> None:
        with self._lock:
            self._write_delta(text)

    def on_reasoning_delta(self, text: str) -> None:
        with self._lock:
            self._write_delta(text)

    def on_tool_args_delta(
        self,
        text: str,
        *,
        index: int | None = None,
        call_id: str | None = None,
        name: str | None = None,
    ) -> None:
        with self._lock:
            self._write_delta(text)

    def _close_block_locked(self, kind: str) -> None:
        if not self._block_open:
            return
        if self._block_dropped > 0:
            self._write(f"... (+{self._block_dropped} more)")
        self._write("\n")
        self._block_open = False
        self._current_kind = None
        self._block_chars = 0
        self._block_dropped = 0

    def on_block_end(self, kind: str, *, index: int | None = None) -> None:
        with self._lock:
            self._close_block_locked(kind)

    def on_error(self, exc: BaseException) -> None:
        with self._lock:
            if self._block_open:
                self._write("\n")
                self._block_open = False
                self._current_kind = None
                self._block_chars = 0
                self._block_dropped = 0
            self._write(f"[stream error] {type(exc).__name__}: {exc}\n")

    def flush(self) -> None:
        with self._lock:
            try:
                self._stream.flush()
            except Exception:
                pass
