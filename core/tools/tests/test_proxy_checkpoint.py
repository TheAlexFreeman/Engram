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


@dataclass(slots=True)
class _UpstreamState:
    requests: list[dict[str, Any]] = field(default_factory=list)
    response_status: int = 200
    response_headers: dict[str, str] = field(default_factory=dict)
    response_body: bytes = b""
    response_chunks: list[bytes] | None = None


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
                chunks = state.response_chunks or [state.response_body]
                if state.response_chunks is None:
                    self.send_header("Content-Length", str(len(state.response_body)))
                self.send_header("Connection", "close")
                self.end_headers()
                for chunk in chunks:
                    self.wfile.write(chunk)
                    self.wfile.flush()
                    time.sleep(0.01)
                self.close_connection = True

            def log_message(self, format: str, *args: object) -> None:
                return None

        return UpstreamHandler


class ProxyCheckpointTests(unittest.TestCase):
    auto_checkpoint_module: ClassVar[ModuleType]
    server_module: ClassVar[ModuleType]

    @classmethod
    def setUpClass(cls) -> None:
        cls.auto_checkpoint_module = load_proxy_module(
            "engram_mcp.agent_memory_mcp.proxy.auto_checkpoint"
        )
        cls.server_module = load_proxy_module("engram_mcp.agent_memory_mcp.proxy.server")

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)

    def test_proxy_checkpoint_calls_memory_checkpoint_for_decision_response(self) -> None:
        caller = _FakeToolCaller(
            {"memory_checkpoint": {"new_state": {"target": "memory/working/CURRENT.md"}}}
        )
        monitor = self.auto_checkpoint_module.AutoCheckpointMonitor(
            caller,
            self.auto_checkpoint_module.AutoCheckpointConfig(min_response_tokens=12),
        )
        upstream_state = _UpstreamState(
            response_headers={"Content-Type": "application/json"},
            response_body=_openai_response(
                "I'll update the proxy server to extract checkpoint-worthy responses after they are returned, and I'll add focused tests so the behavior stays stable."
            ),
        )

        with _TestHTTPServer(upstream_state) as upstream:
            config = self.server_module.ProxyConfig(
                listen_port=0, upstream_base_url=upstream.base_url
            )
            with self.server_module.ProxyServer(
                config,
                auto_checkpoint_monitor=monitor,
            ) as proxy:
                self._send_openai_request(
                    proxy.bound_port,
                    user_message="Continue with phase 4.",
                    headers={
                        "Content-Type": "application/json",
                        "X-Engram-Session-Id": "memory/activity/2026/03/29/chat-060",
                    },
                )

        self.assertEqual([name for name, _ in caller.calls], ["memory_checkpoint"])
        arguments = caller.calls[0][1]
        self.assertEqual(arguments["label"], "Decision")
        self.assertEqual(arguments["session_id"], "memory/activity/2026/03/29/chat-060")
        content = cast(str, arguments["content"])
        self.assertIn("User request:\nContinue with phase 4.", content)
        self.assertIn("Assistant response:\nI'll update the proxy server", content)
        self.assertTrue(proxy.request_log[0].checkpoint_triggered)
        self.assertEqual(proxy.request_log[0].checkpoint_tool_name, "memory_checkpoint")
        self.assertEqual(proxy.request_log[0].checkpoint_label, "Decision")
        self.assertEqual(proxy.request_log[0].checkpoint_reason, "checkpointed")

    def test_proxy_checkpoint_skips_short_response(self) -> None:
        caller = _FakeToolCaller(
            {"memory_checkpoint": {"new_state": {"target": "memory/working/CURRENT.md"}}}
        )
        monitor = self.auto_checkpoint_module.AutoCheckpointMonitor(
            caller,
            self.auto_checkpoint_module.AutoCheckpointConfig(min_response_tokens=12),
        )
        upstream_state = _UpstreamState(
            response_headers={"Content-Type": "application/json"},
            response_body=_openai_response("Done."),
        )

        with _TestHTTPServer(upstream_state) as upstream:
            config = self.server_module.ProxyConfig(
                listen_port=0, upstream_base_url=upstream.base_url
            )
            with self.server_module.ProxyServer(
                config,
                auto_checkpoint_monitor=monitor,
            ) as proxy:
                self._send_openai_request(
                    proxy.bound_port,
                    user_message="Continue.",
                    headers={"Content-Type": "application/json"},
                )

        self.assertEqual(caller.calls, [])
        self.assertFalse(proxy.request_log[0].checkpoint_triggered)
        self.assertEqual(proxy.request_log[0].checkpoint_reason, "short_response")

    def test_proxy_checkpoint_rate_limits_until_more_tool_calls_appear(self) -> None:
        caller = _FakeToolCaller(
            {"memory_checkpoint": {"new_state": {"target": "memory/working/CURRENT.md"}}}
        )
        monitor = self.auto_checkpoint_module.AutoCheckpointMonitor(
            caller,
            self.auto_checkpoint_module.AutoCheckpointConfig(
                min_response_tokens=10,
                min_tool_calls_between_checkpoints=5,
            ),
        )
        upstream_state = _UpstreamState(
            response_headers={"Content-Type": "application/json"},
            response_body=_openai_response(
                "I updated the proxy checkpoint logic to capture the final assistant response and keep the heuristics conservative so it avoids noise."
            ),
        )

        with _TestHTTPServer(upstream_state) as upstream:
            config = self.server_module.ProxyConfig(
                listen_port=0, upstream_base_url=upstream.base_url
            )
            with self.server_module.ProxyServer(
                config,
                auto_checkpoint_monitor=monitor,
            ) as proxy:
                self._send_openai_request(
                    proxy.bound_port,
                    user_message="Keep going.",
                    historical_tool_calls=0,
                    headers={
                        "Content-Type": "application/json",
                        "X-Engram-Session-Id": "memory/activity/2026/03/29/chat-061",
                    },
                )
                self._send_openai_request(
                    proxy.bound_port,
                    user_message="Keep going.",
                    historical_tool_calls=3,
                    headers={
                        "Content-Type": "application/json",
                        "X-Engram-Session-Id": "memory/activity/2026/03/29/chat-061",
                    },
                )
                self._send_openai_request(
                    proxy.bound_port,
                    user_message="Keep going.",
                    historical_tool_calls=5,
                    headers={
                        "Content-Type": "application/json",
                        "X-Engram-Session-Id": "memory/activity/2026/03/29/chat-061",
                    },
                )

        self.assertEqual(
            [name for name, _ in caller.calls], ["memory_checkpoint", "memory_checkpoint"]
        )
        self.assertEqual(
            [entry.checkpoint_triggered for entry in proxy.request_log],
            [True, False, True],
        )
        self.assertEqual(proxy.request_log[1].checkpoint_reason, "rate_limited")

    def test_proxy_checkpoint_uses_user_correction_signal(self) -> None:
        caller = _FakeToolCaller(
            {"memory_checkpoint": {"new_state": {"target": "memory/working/CURRENT.md"}}}
        )
        monitor = self.auto_checkpoint_module.AutoCheckpointMonitor(
            caller,
            self.auto_checkpoint_module.AutoCheckpointConfig(min_response_tokens=12),
        )
        upstream_state = _UpstreamState(
            response_headers={"Content-Type": "application/json"},
            response_body=_openai_response(
                "Understood. The clarified requirement is now the active one: automatic checkpointing stays on final assistant responses only, while streaming deltas remain uncheckpointed to avoid noisy scratchpad writes."
            ),
        )

        with _TestHTTPServer(upstream_state) as upstream:
            config = self.server_module.ProxyConfig(
                listen_port=0, upstream_base_url=upstream.base_url
            )
            with self.server_module.ProxyServer(
                config,
                auto_checkpoint_monitor=monitor,
            ) as proxy:
                self._send_openai_request(
                    proxy.bound_port,
                    user_message="Actually, no, I meant checkpoint only after the final response.",
                    headers={"Content-Type": "application/json"},
                )

        self.assertEqual(caller.calls[0][0], "memory_checkpoint")
        self.assertEqual(caller.calls[0][1]["label"], "User correction")
        self.assertEqual(proxy.request_log[0].checkpoint_label, "User correction")

    def _send_openai_request(
        self,
        port: int,
        *,
        user_message: str,
        headers: dict[str, str],
        historical_tool_calls: int = 0,
    ) -> None:
        messages = _openai_request_messages(
            user_message, historical_tool_calls=historical_tool_calls
        )
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


def _openai_response(text: str) -> bytes:
    return json.dumps(
        {
            "id": "cmpl_123",
            "object": "chat.completion",
            "choices": [{"message": {"role": "assistant", "content": text}}],
        }
    ).encode("utf-8")


def _openai_request_messages(
    user_message: str, *, historical_tool_calls: int
) -> list[dict[str, object]]:
    messages: list[dict[str, object]] = []
    if historical_tool_calls:
        messages.append(
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": f"call-{index}",
                        "type": "function",
                        "function": {"name": f"tool_{index}", "arguments": "{}"},
                    }
                    for index in range(historical_tool_calls)
                ],
            }
        )
    messages.append({"role": "user", "content": user_message})
    return messages


if __name__ == "__main__":
    unittest.main()
