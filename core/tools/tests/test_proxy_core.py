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
from typing import Any, ClassVar

REPO_ROOT = Path(__file__).resolve().parents[3]


def load_proxy_module(module_name: str) -> ModuleType:
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    return importlib.import_module(module_name)


@dataclass(slots=True)
class _UpstreamState:
    requests: list[dict[str, Any]] = field(default_factory=list)
    response_status: int = 200
    response_headers: dict[str, str] = field(default_factory=dict)
    response_body: bytes = b""
    response_chunks: list[bytes] | None = None


class _TestHTTPServer:
    def __init__(self, state: _UpstreamState) -> None:
        self._state = state
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


class ProxyCoreTests(unittest.TestCase):
    formats_module: ClassVar[ModuleType]
    server_module: ClassVar[ModuleType]

    @classmethod
    def setUpClass(cls) -> None:
        cls.formats_module = load_proxy_module("engram_mcp.agent_memory_mcp.proxy.formats")
        cls.server_module = load_proxy_module("engram_mcp.agent_memory_mcp.proxy.server")

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)

    def test_detect_api_format_and_openai_injection(self) -> None:
        self.assertEqual(
            self.formats_module.detect_api_format("/v1/chat/completions"),
            "openai",
        )
        self.assertEqual(
            self.formats_module.detect_api_format(
                "/v1/messages", {"anthropic-version": "2023-06-01"}
            ),
            "anthropic",
        )

        adapter = self.formats_module.adapter_for_format("openai")
        payload = {
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": "Summarize the topic."}],
        }
        updated = adapter.inject_system_context(payload, "Injected context.")
        inspection = adapter.inspect_payload(updated)

        self.assertEqual(updated["messages"][0]["role"], "system")
        self.assertIn("Injected context.", inspection.system_messages[0])
        self.assertEqual(inspection.user_messages, ["Summarize the topic."])

    def test_proxy_passes_through_openai_request_and_logs_format(self) -> None:
        upstream_state = _UpstreamState(
            response_headers={"Content-Type": "application/json"},
            response_body=json.dumps({"id": "cmpl_123", "object": "chat.completion"}).encode(
                "utf-8"
            ),
        )
        with _TestHTTPServer(upstream_state) as upstream:
            config = self.server_module.ProxyConfig(
                listen_port=0,
                upstream_base_url=upstream.base_url,
            )
            with self.server_module.ProxyServer(config) as proxy:
                body = json.dumps(
                    {
                        "model": "gpt-4o-mini",
                        "messages": [{"role": "user", "content": "Hello proxy."}],
                    }
                ).encode("utf-8")
                connection = http.client.HTTPConnection("127.0.0.1", proxy.bound_port, timeout=5)
                connection.request(
                    "POST",
                    "/v1/chat/completions",
                    body=body,
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": "Bearer test-secret",
                    },
                )
                response = connection.getresponse()
                payload = response.read()
                connection.close()

        self.assertEqual(response.status, 200)
        self.assertEqual(json.loads(payload), {"id": "cmpl_123", "object": "chat.completion"})
        self.assertEqual(upstream_state.requests[0]["path"], "/v1/chat/completions")
        self.assertEqual(upstream_state.requests[0]["body"], body)
        self.assertEqual(
            upstream_state.requests[0]["headers"]["Authorization"],
            "Bearer test-secret",
        )
        self.assertEqual(proxy.request_log[0].format_name, "openai")
        self.assertTrue(proxy.request_log[0].upstream_url.endswith("/v1/chat/completions"))
        self.assertEqual(proxy.request_log[0].request_bytes, len(body))

    def test_proxy_detects_anthropic_requests(self) -> None:
        upstream_state = _UpstreamState(
            response_headers={"Content-Type": "application/json"},
            response_body=json.dumps({"id": "msg_123", "type": "message"}).encode("utf-8"),
        )
        with _TestHTTPServer(upstream_state) as upstream:
            config = self.server_module.ProxyConfig(
                listen_port=0, upstream_base_url=upstream.base_url
            )
            with self.server_module.ProxyServer(config) as proxy:
                body = json.dumps(
                    {
                        "model": "claude-3-7-sonnet",
                        "system": "Be concise.",
                        "messages": [{"role": "user", "content": "Hello anthropic."}],
                    }
                ).encode("utf-8")
                connection = http.client.HTTPConnection("127.0.0.1", proxy.bound_port, timeout=5)
                connection.request(
                    "POST",
                    "/v1/messages",
                    body=body,
                    headers={
                        "Content-Type": "application/json",
                        "x-api-key": "anthropic-secret",
                        "anthropic-version": "2023-06-01",
                    },
                )
                response = connection.getresponse()
                response.read()
                connection.close()

        self.assertEqual(response.status, 200)
        self.assertEqual(proxy.request_log[0].format_name, "anthropic")
        self.assertEqual(upstream_state.requests[0]["headers"]["x-api-key"], "anthropic-secret")

    def test_proxy_relays_streaming_response_without_modification(self) -> None:
        chunks = [b"data: one\n\n", b"data: two\n\n"]
        upstream_state = _UpstreamState(
            response_headers={"Content-Type": "text/event-stream"},
            response_chunks=chunks,
        )
        with _TestHTTPServer(upstream_state) as upstream:
            config = self.server_module.ProxyConfig(
                listen_port=0, upstream_base_url=upstream.base_url
            )
            with self.server_module.ProxyServer(config) as proxy:
                connection = http.client.HTTPConnection("127.0.0.1", proxy.bound_port, timeout=5)
                connection.request(
                    "POST",
                    "/v1/chat/completions",
                    body=json.dumps(
                        {
                            "model": "gpt-4o-mini",
                            "stream": True,
                            "messages": [{"role": "user", "content": "Stream please."}],
                        }
                    ).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                )
                response = connection.getresponse()
                content_type = response.getheader("Content-Type")
                payload = response.read()
                connection.close()

        self.assertEqual(response.status, 200)
        self.assertEqual(content_type, "text/event-stream")
        self.assertEqual(payload, b"".join(chunks))
        self.assertTrue(proxy.request_log[0].streaming_response)


if __name__ == "__main__":
    unittest.main()
