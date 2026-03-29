from __future__ import annotations

import http.client
import importlib
import json
import sys
import tempfile
import time
import unittest
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from types import ModuleType
from typing import Any, ClassVar, cast

REPO_ROOT = Path(__file__).resolve().parents[3]


def load_proxy_module(module_name: str) -> ModuleType:
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    return importlib.import_module(module_name)


class _FakeToolCaller:
    def __init__(self, responses: dict[str, Any]) -> None:
        self._responses = responses
        self.calls: list[tuple[str, dict[str, object]]] = []

    def call_tool(self, name: str, arguments: dict[str, object] | None = None) -> Any:
        self.calls.append((name, arguments or {}))
        return self._responses[name]


class _SequenceTokenCounter:
    def __init__(self, counts: list[int]) -> None:
        self._counts = counts
        self._index = 0

    def count_tokens(self, inspection) -> int:  # type: ignore[no-untyped-def]
        if self._index >= len(self._counts):
            return self._counts[-1]
        value = self._counts[self._index]
        self._index += 1
        return value


@dataclass(slots=True)
class _UpstreamState:
    requests: list[dict[str, Any]] = field(default_factory=list)
    response_status: int = 200
    response_headers: dict[str, str] = field(default_factory=dict)
    response_body: bytes = b""


class _TestHTTPServer:
    def __init__(self, state: _UpstreamState) -> None:
        self._httpd = ThreadingHTTPServer(("127.0.0.1", 0), self._build_handler(state))
        self._httpd.daemon_threads = True
        self._thread: Thread | None = None

    @property
    def base_url(self) -> str:
        host, port = self._httpd.server_address[:2]
        if isinstance(host, bytes):
            host = host.decode("utf-8")
        return f"http://{host}:{port}"

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()

    def close(self) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None

    def __enter__(self) -> "_TestHTTPServer":
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    @staticmethod
    def _build_handler(state: _UpstreamState) -> type[BaseHTTPRequestHandler]:
        class UpstreamHandler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def do_POST(self) -> None:
                content_length = int(self.headers.get("Content-Length", "0"))
                body = self.rfile.read(content_length) if content_length else b""
                state.requests.append(
                    {
                        "method": self.command,
                        "path": self.path,
                        "headers": {key: value for key, value in self.headers.items()},
                        "body": body,
                    }
                )
                self.send_response(state.response_status)
                for header_name, header_value in state.response_headers.items():
                    self.send_header(header_name, header_value)
                self.send_header("Content-Length", str(len(state.response_body)))
                self.send_header("Connection", "close")
                self.end_headers()
                self.wfile.write(state.response_body)
                self.wfile.flush()
                time.sleep(0.01)
                self.close_connection = True

            def log_message(self, format: str, *args: object) -> None:
                return None

        return UpstreamHandler


class ProxyFlushTests(unittest.TestCase):
    compaction_module: ClassVar[ModuleType]
    server_module: ClassVar[ModuleType]

    @classmethod
    def setUpClass(cls) -> None:
        cls.compaction_module = load_proxy_module("engram_mcp.agent_memory_mcp.proxy.compaction")
        cls.server_module = load_proxy_module("engram_mcp.agent_memory_mcp.proxy.server")

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)

    def test_proxy_flush_triggers_once_per_compaction_cycle(self) -> None:
        caller = _FakeToolCaller(
            {
                "memory_session_flush": {
                    "new_state": {"checkpoint_path": "memory/activity/chat/checkpoint.md"}
                }
            }
        )
        monitor = self.compaction_module.CompactionMonitor(
            caller,
            self.compaction_module.CompactionConfig(flush_threshold=0.8, reset_threshold=0.5),
            token_counter=_SequenceTokenCounter([85, 90, 40, 88]),
        )
        upstream_state = _UpstreamState(
            response_headers={"Content-Type": "application/json"},
            response_body=b'{"ok": true}',
        )

        with _TestHTTPServer(upstream_state) as upstream:
            config = self.server_module.ProxyConfig(
                listen_port=0, upstream_base_url=upstream.base_url
            )
            with self.server_module.ProxyServer(config, compaction_monitor=monitor) as proxy:
                for prompt in ("first", "second", "third", "fourth"):
                    self._send_openai_request(
                        proxy.bound_port,
                        prompt,
                        headers={
                            "Content-Type": "application/json",
                            "X-Engram-Session-Id": "memory/activity/2026/03/29/chat-050",
                            "X-Engram-Model-Context-Window": "100",
                        },
                    )

        self.assertEqual(
            [name for name, _ in caller.calls], ["memory_session_flush", "memory_session_flush"]
        )
        self.assertEqual(
            [entry.flush_triggered for entry in proxy.request_log],
            [True, False, False, True],
        )
        self.assertEqual(
            [entry.counted_input_tokens for entry in proxy.request_log], [85, 90, 40, 88]
        )

    def test_proxy_flush_calls_session_flush_with_recovery_summary(self) -> None:
        caller = _FakeToolCaller(
            {"memory_session_flush": json.dumps({"new_state": {"trigger": "context-pressure"}})}
        )
        monitor = self.compaction_module.CompactionMonitor(
            caller,
            self.compaction_module.CompactionConfig(flush_threshold=0.85),
            token_counter=_SequenceTokenCounter([86]),
        )
        upstream_state = _UpstreamState(
            response_headers={"Content-Type": "application/json"},
            response_body=b'{"ok": true}',
        )

        with _TestHTTPServer(upstream_state) as upstream:
            config = self.server_module.ProxyConfig(
                listen_port=0, upstream_base_url=upstream.base_url
            )
            with self.server_module.ProxyServer(config, compaction_monitor=monitor) as proxy:
                self._send_openai_request(
                    proxy.bound_port,
                    "Summarize the proxy compaction work.",
                    assistant_message="Previous assistant context.",
                    headers={
                        "Content-Type": "application/json",
                        "X-Engram-Project": "session-management",
                        "X-Engram-Session-Id": "memory/activity/2026/03/29/chat-051",
                        "X-Engram-Model-Context-Window": "100",
                    },
                )

        self.assertEqual(caller.calls[0][0], "memory_session_flush")
        arguments = caller.calls[0][1]
        summary = cast(str, arguments["summary"])
        self.assertEqual(arguments["session_id"], "memory/activity/2026/03/29/chat-051")
        self.assertEqual(arguments["label"], "Context-pressure flush")
        self.assertEqual(arguments["trigger"], "context_pressure")
        self.assertIn("Context usage: 86 / 100 tokens (86%).", summary)
        self.assertIn("Project hint: session-management", summary)
        self.assertIn("Latest user request:\nSummarize the proxy compaction work.", summary)
        self.assertIn("Recent assistant context:\nPrevious assistant context.", summary)
        self.assertTrue(proxy.request_log[0].flush_triggered)
        self.assertEqual(proxy.request_log[0].flush_tool_name, "memory_session_flush")
        self.assertEqual(
            proxy.request_log[0].flush_session_id, "memory/activity/2026/03/29/chat-051"
        )
        self.assertEqual(proxy.request_log[0].flush_threshold_tokens, 85)

    def _send_openai_request(
        self,
        port: int,
        user_message: str,
        *,
        assistant_message: str | None = None,
        headers: dict[str, str],
    ) -> None:
        messages: list[dict[str, str]] = []
        if assistant_message is not None:
            messages.append({"role": "assistant", "content": assistant_message})
        messages.append({"role": "user", "content": user_message})
        request_body = json.dumps({"model": "gpt-4o-mini", "messages": messages}).encode("utf-8")

        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        connection.request(
            "POST",
            "/v1/chat/completions",
            body=request_body,
            headers=headers,
        )
        response = connection.getresponse()
        response.read()
        connection.close()


if __name__ == "__main__":
    unittest.main()
