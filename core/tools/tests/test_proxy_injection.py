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


def _context_response(tool_name: str, body: str) -> str:
    metadata = {
        "tool": tool_name,
        "loaded_files": ["memory/context-source.md"],
        "budget_report": {"total_chars": len(body)},
        "body_sections": [{"name": "Injected", "path": "memory/context-source.md"}],
    }
    return "```json\n" + json.dumps(metadata) + "\n```\n\n" + body


class _FakeContextToolCaller:
    def __init__(self, responses: dict[str, str]) -> None:
        self._responses = responses
        self.calls: list[tuple[str, dict[str, object]]] = []

    def call_tool(self, name: str, arguments: dict[str, object] | None = None) -> str:
        self.calls.append((name, arguments or {}))
        return self._responses[name]


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


class ProxyInjectionTests(unittest.TestCase):
    injection_module: ClassVar[ModuleType]
    server_module: ClassVar[ModuleType]

    @classmethod
    def setUpClass(cls) -> None:
        cls.injection_module = load_proxy_module("engram_mcp.agent_memory_mcp.proxy.injection")
        cls.server_module = load_proxy_module("engram_mcp.agent_memory_mcp.proxy.server")

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)

    def test_proxy_injection_adds_home_context_to_openai_request(self) -> None:
        caller = _FakeContextToolCaller(
            {
                "memory_context_home": _context_response(
                    "memory_context_home", "## Home Context\n\nInjected home state."
                )
            }
        )
        injector = self.injection_module.ContextInjector(
            caller,
            self.injection_module.InjectionConfig(default_max_context_chars=1200),
        )
        upstream_state = _UpstreamState(
            response_headers={"Content-Type": "application/json"},
            response_body=b'{"ok": true}',
        )
        with _TestHTTPServer(upstream_state) as upstream:
            config = self.server_module.ProxyConfig(
                listen_port=0, upstream_base_url=upstream.base_url
            )
            with self.server_module.ProxyServer(config, context_injector=injector) as proxy:
                request_body = json.dumps(
                    {
                        "model": "gpt-4o-mini",
                        "messages": [{"role": "user", "content": "Hello proxy."}],
                    }
                ).encode("utf-8")
                connection = http.client.HTTPConnection("127.0.0.1", proxy.bound_port, timeout=5)
                connection.request(
                    "POST",
                    "/v1/chat/completions",
                    body=request_body,
                    headers={"Content-Type": "application/json"},
                )
                response = connection.getresponse()
                response.read()
                connection.close()

        upstream_payload = json.loads(upstream_state.requests[0]["body"].decode("utf-8"))
        self.assertEqual(caller.calls[0][0], "memory_context_home")
        self.assertEqual(
            caller.calls[0][1],
            {"max_context_chars": 1200, "include_project_index": True},
        )
        self.assertEqual(upstream_payload["messages"][0]["role"], "system")
        self.assertIn("## Home Context", upstream_payload["messages"][0]["content"])
        self.assertEqual(proxy.request_log[0].context_tool_name, "memory_context_home")
        self.assertGreater(proxy.request_log[0].injected_context_chars, 0)

    def test_proxy_injection_uses_project_hint_and_respects_token_budget(self) -> None:
        caller = _FakeContextToolCaller(
            {
                "memory_context_project": _context_response(
                    "memory_context_project",
                    "## Project Summary\n\nInjected project context.",
                )
            }
        )
        injector = self.injection_module.ContextInjector(
            caller,
            self.injection_module.InjectionConfig(
                default_max_context_chars=500,
                reserve_tokens=5,
                chars_per_token=4,
            ),
        )
        upstream_state = _UpstreamState(
            response_headers={"Content-Type": "application/json"},
            response_body=b'{"ok": true}',
        )
        with _TestHTTPServer(upstream_state) as upstream:
            config = self.server_module.ProxyConfig(
                listen_port=0, upstream_base_url=upstream.base_url
            )
            with self.server_module.ProxyServer(config, context_injector=injector) as proxy:
                request_body = json.dumps(
                    {
                        "model": "gpt-4o-mini",
                        "messages": [{"role": "user", "content": "one two three four"}],
                    }
                ).encode("utf-8")
                connection = http.client.HTTPConnection("127.0.0.1", proxy.bound_port, timeout=5)
                connection.request(
                    "POST",
                    "/v1/chat/completions",
                    body=request_body,
                    headers={
                        "Content-Type": "application/json",
                        "X-Engram-Project": "demo-project",
                        "X-Engram-Model-Context-Window": "20",
                    },
                )
                response = connection.getresponse()
                response.read()
                connection.close()

        upstream_payload = json.loads(upstream_state.requests[0]["body"].decode("utf-8"))
        self.assertEqual(caller.calls[0][0], "memory_context_project")
        self.assertEqual(
            caller.calls[0][1],
            {
                "project": "demo-project",
                "max_context_chars": 44,
                "include_plan_sources": True,
            },
        )
        self.assertIn("## Project Summary", upstream_payload["messages"][0]["content"])
        self.assertEqual(proxy.request_log[0].project_hint, "demo-project")
        self.assertEqual(proxy.request_log[0].context_budget_chars, 44)

    def test_proxy_injection_prepends_context_to_existing_anthropic_system(self) -> None:
        caller = _FakeContextToolCaller(
            {
                "memory_context_home": _context_response(
                    "memory_context_home", "## Home Context\n\nInjected home state."
                )
            }
        )
        injector = self.injection_module.ContextInjector(
            caller,
            self.injection_module.InjectionConfig(default_max_context_chars=900),
        )
        upstream_state = _UpstreamState(
            response_headers={"Content-Type": "application/json"},
            response_body=b'{"ok": true}',
        )
        with _TestHTTPServer(upstream_state) as upstream:
            config = self.server_module.ProxyConfig(
                listen_port=0, upstream_base_url=upstream.base_url
            )
            with self.server_module.ProxyServer(config, context_injector=injector) as proxy:
                request_body = json.dumps(
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
                    body=request_body,
                    headers={
                        "Content-Type": "application/json",
                        "anthropic-version": "2023-06-01",
                    },
                )
                response = connection.getresponse()
                response.read()
                connection.close()

        upstream_payload = json.loads(upstream_state.requests[0]["body"].decode("utf-8"))
        self.assertTrue(upstream_payload["system"].startswith("## Home Context"))
        self.assertIn("Be concise.", upstream_payload["system"])
        self.assertEqual(proxy.request_log[0].context_tool_name, "memory_context_home")


if __name__ == "__main__":
    unittest.main()
