"""HTTP pass-through proxy core for the optional Engram proxy."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from http import HTTPStatus
from http.client import HTTPConnection, HTTPResponse, HTTPSConnection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from typing import Callable, cast
from urllib.parse import SplitResult, urlsplit

from .auto_checkpoint import (
    AutoCheckpointMonitor,
    AutoCheckpointResult,
    ResponseInspection,
    inspect_response_body,
)
from .compaction import CompactionMonitor, CompactionResult
from .formats import APIFormat, RequestInspection, detect_api_format, inspect_request_body
from .injection import ContextInjectionResult, ContextInjector, strip_injection_control_headers

_LOGGER = logging.getLogger(__name__)
_HOP_BY_HOP_HEADERS = frozenset(
    {
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "proxy-connection",
        "te",
        "trailers",
        "transfer-encoding",
        "upgrade",
        "host",
    }
)
_STREAMING_CONTENT_TYPES = ("text/event-stream", "application/x-ndjson")
_READ_CHUNK_SIZE = 8192


@dataclass(slots=True)
class ProxyConfig:
    """Runtime configuration for the proxy core."""

    listen_host: str = "127.0.0.1"
    listen_port: int = 8400
    upstream_base_url: str = "http://127.0.0.1:8401"
    request_timeout: float = 60.0

    def __post_init__(self) -> None:
        parsed = urlsplit(self.upstream_base_url)
        if parsed.scheme not in {"http", "https"}:
            raise ValueError("upstream_base_url must use http or https")
        if not parsed.hostname:
            raise ValueError("upstream_base_url must include a hostname")
        if self.listen_port < 0:
            raise ValueError("listen_port must be >= 0")
        if self.request_timeout <= 0:
            raise ValueError("request_timeout must be > 0")


@dataclass(slots=True)
class ProxyLogEntry:
    """Request and response metadata captured by the proxy core."""

    method: str
    path: str
    format_name: APIFormat | None
    upstream_url: str
    status_code: int
    request_bytes: int
    response_bytes: int
    streaming_response: bool
    approximate_input_tokens: int | None
    context_tool_name: str | None = None
    project_hint: str | None = None
    context_budget_chars: int | None = None
    injected_context_chars: int = 0
    counted_input_tokens: int | None = None
    context_window_tokens: int | None = None
    flush_threshold_tokens: int | None = None
    flush_triggered: bool = False
    flush_tool_name: str | None = None
    flush_session_id: str | None = None
    checkpoint_triggered: bool = False
    checkpoint_tool_name: str | None = None
    checkpoint_label: str | None = None
    checkpoint_session_id: str | None = None
    checkpoint_reason: str | None = None


@dataclass(slots=True)
class ProxyObservation:
    """Rich per-request observation emitted for optional in-process sidecar handling."""

    observed_at: datetime
    client_host: str | None
    method: str
    path: str
    format_name: APIFormat | None
    request_headers: dict[str, str]
    request_inspection: RequestInspection | None
    response_headers: dict[str, str]
    response_inspection: ResponseInspection | None
    status_code: int
    streaming_response: bool
    compaction_result: CompactionResult | None = None
    auto_checkpoint_result: AutoCheckpointResult | None = None


class ProxyServer:
    """Threaded HTTP proxy that forwards requests to an upstream model API."""

    def __init__(
        self,
        config: ProxyConfig,
        *,
        context_injector: ContextInjector | None = None,
        compaction_monitor: CompactionMonitor | None = None,
        auto_checkpoint_monitor: AutoCheckpointMonitor | None = None,
        log_sink: Callable[[ProxyLogEntry], None] | None = None,
        observation_sink: Callable[[ProxyObservation], None] | None = None,
    ) -> None:
        self.config = config
        self._context_injector = context_injector
        self._compaction_monitor = compaction_monitor
        self._auto_checkpoint_monitor = auto_checkpoint_monitor
        self.request_log: list[ProxyLogEntry] = []
        self._log_sink = log_sink or self.request_log.append
        self._observation_sink = observation_sink
        self._httpd = ThreadingHTTPServer(
            (config.listen_host, config.listen_port),
            self._build_handler(),
        )
        self._httpd.daemon_threads = True
        self._thread: Thread | None = None

    @property
    def bound_port(self) -> int:
        return int(self._httpd.server_address[1])

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

    def __enter__(self) -> "ProxyServer":
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def _build_handler(self) -> type[BaseHTTPRequestHandler]:
        proxy = self

        class ProxyHTTPRequestHandler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def do_GET(self) -> None:
                proxy._handle_request(self)

            def do_POST(self) -> None:
                proxy._handle_request(self)

            def do_PUT(self) -> None:
                proxy._handle_request(self)

            def do_PATCH(self) -> None:
                proxy._handle_request(self)

            def do_DELETE(self) -> None:
                proxy._handle_request(self)

            def log_message(self, format: str, *args: object) -> None:
                _LOGGER.debug("proxy request: " + format, *args)

        return ProxyHTTPRequestHandler

    def _handle_request(self, handler: BaseHTTPRequestHandler) -> None:
        body = _read_request_body(handler)
        raw_headers = dict(handler.headers.items())
        request_headers = _filter_request_headers(handler)
        original_body = body
        original_headers = strip_injection_control_headers(dict(request_headers))
        format_name = detect_api_format(handler.path, raw_headers)
        inspection = inspect_request_body(format_name, body)
        response_inspection: ResponseInspection | None = None
        injection_result: ContextInjectionResult | None = None
        compaction_result: CompactionResult | None = None
        auto_checkpoint_result: AutoCheckpointResult | None = None

        if self._context_injector is not None:
            try:
                injection_result = self._context_injector.inject_request(
                    path=handler.path,
                    headers=raw_headers,
                    body=body,
                    inspection=inspection,
                )
                request_headers = injection_result.headers
                body = injection_result.body
                if injection_result.api_format is not None:
                    format_name = injection_result.api_format
                inspection = inspect_request_body(format_name, body)
            except Exception:
                _LOGGER.exception("proxy context injection failed; forwarding original request")
                request_headers = original_headers
                body = original_body
                injection_result = None
                inspection = inspect_request_body(format_name, body)

        if self._compaction_monitor is not None:
            try:
                compaction_result = self._compaction_monitor.inspect_request(
                    path=handler.path,
                    headers=raw_headers,
                    body=body,
                    inspection=inspection,
                )
            except Exception:
                _LOGGER.exception("proxy compaction flush failed; forwarding request without flush")
                compaction_result = None

        request_headers = strip_injection_control_headers(request_headers)

        try:
            response, upstream_url = self._forward_request(
                method=handler.command,
                path=handler.path,
                headers=request_headers,
                body=body,
            )
        except OSError as exc:
            self._send_error_response(handler, exc)
            return

        try:
            upstream_response_headers = {name: value for name, value in response.getheaders()}
            upstream_status = response.status
            response_bytes, streaming_response, relayed_body = self._relay_response(
                handler, response
            )
        finally:
            response.close()

        if self._auto_checkpoint_monitor is not None:
            try:
                auto_checkpoint_result = self._auto_checkpoint_monitor.inspect_response(
                    path=handler.path,
                    request_headers=raw_headers,
                    request_inspection=inspection,
                    response_headers=upstream_response_headers,
                    response_body=relayed_body or b"",
                    status_code=upstream_status,
                    streaming_response=streaming_response,
                )
            except Exception:
                _LOGGER.exception(
                    "proxy auto-checkpoint failed; response already relayed to client"
                )
                auto_checkpoint_result = None

        if relayed_body is not None:
            response_inspection = inspect_response_body(format_name, relayed_body)

        self._log_sink(
            ProxyLogEntry(
                method=handler.command,
                path=handler.path,
                format_name=format_name,
                upstream_url=upstream_url,
                status_code=upstream_status,
                request_bytes=len(body),
                response_bytes=response_bytes,
                streaming_response=streaming_response,
                approximate_input_tokens=(
                    inspection.approximate_input_tokens if inspection is not None else None
                ),
                context_tool_name=(
                    injection_result.context_tool_name if injection_result is not None else None
                ),
                project_hint=(
                    injection_result.project_hint if injection_result is not None else None
                ),
                context_budget_chars=(
                    injection_result.context_budget_chars if injection_result is not None else None
                ),
                injected_context_chars=(
                    injection_result.injected_context_chars if injection_result is not None else 0
                ),
                counted_input_tokens=(
                    compaction_result.token_count if compaction_result is not None else None
                ),
                context_window_tokens=(
                    compaction_result.context_window_tokens
                    if compaction_result is not None
                    else None
                ),
                flush_threshold_tokens=(
                    compaction_result.flush_threshold_tokens
                    if compaction_result is not None
                    else None
                ),
                flush_triggered=(
                    compaction_result.flush_triggered if compaction_result is not None else False
                ),
                flush_tool_name=(
                    compaction_result.flush_tool_name if compaction_result is not None else None
                ),
                flush_session_id=(
                    compaction_result.session_id if compaction_result is not None else None
                ),
                checkpoint_triggered=(
                    auto_checkpoint_result.checkpoint_triggered
                    if auto_checkpoint_result is not None
                    else False
                ),
                checkpoint_tool_name=(
                    auto_checkpoint_result.checkpoint_tool_name
                    if auto_checkpoint_result is not None
                    else None
                ),
                checkpoint_label=(
                    auto_checkpoint_result.checkpoint_label
                    if auto_checkpoint_result is not None
                    else None
                ),
                checkpoint_session_id=(
                    auto_checkpoint_result.checkpoint_session_id
                    if auto_checkpoint_result is not None
                    else None
                ),
                checkpoint_reason=(
                    auto_checkpoint_result.reason if auto_checkpoint_result is not None else None
                ),
            )
        )

        if self._observation_sink is not None:
            try:
                client_host = handler.client_address[0] if handler.client_address else None
                self._observation_sink(
                    ProxyObservation(
                        observed_at=datetime.now(timezone.utc),
                        client_host=client_host,
                        method=handler.command,
                        path=handler.path,
                        format_name=format_name,
                        request_headers=dict(raw_headers),
                        request_inspection=inspection,
                        response_headers=upstream_response_headers,
                        response_inspection=response_inspection,
                        status_code=upstream_status,
                        streaming_response=streaming_response,
                        compaction_result=compaction_result,
                        auto_checkpoint_result=auto_checkpoint_result,
                    )
                )
            except Exception:
                _LOGGER.exception("proxy observation sink failed after response relay")

    def _forward_request(
        self,
        *,
        method: str,
        path: str,
        headers: dict[str, str],
        body: bytes,
    ) -> tuple[HTTPResponse, str]:
        parsed = urlsplit(self.config.upstream_base_url)
        hostname = parsed.hostname
        if hostname is None:
            raise ValueError("upstream_base_url must include a hostname")
        connection_cls = HTTPSConnection if parsed.scheme == "https" else HTTPConnection
        connection = connection_cls(hostname, parsed.port, timeout=self.config.request_timeout)
        upstream_path = _build_upstream_path(parsed, path)
        outbound_headers = dict(headers)
        if body:
            outbound_headers["Content-Length"] = str(len(body))
        else:
            outbound_headers.pop("Content-Length", None)
        connection.request(method, upstream_path, body=body or None, headers=outbound_headers)
        return connection.getresponse(), f"{parsed.scheme}://{parsed.netloc}{upstream_path}"

    def _relay_response(
        self,
        handler: BaseHTTPRequestHandler,
        response: HTTPResponse,
    ) -> tuple[int, bool, bytes | None]:
        streaming_response = _is_streaming_response(response)
        handler.send_response(response.status, response.reason)
        for header_name, header_value in response.getheaders():
            if header_name.lower() in _HOP_BY_HOP_HEADERS:
                continue
            handler.send_header(header_name, header_value)
        handler.send_header("Connection", "close")
        handler.end_headers()
        handler.close_connection = True

        response_bytes = 0
        captured_chunks: list[bytes] | None = [] if not streaming_response else None
        while True:
            chunk = response.read(_READ_CHUNK_SIZE)
            if not chunk:
                break
            handler.wfile.write(chunk)
            handler.wfile.flush()
            response_bytes += len(chunk)
            if captured_chunks is not None:
                captured_chunks.append(chunk)
        captured_body = b"".join(captured_chunks) if captured_chunks is not None else None
        return response_bytes, streaming_response, captured_body

    def _send_error_response(self, handler: BaseHTTPRequestHandler, exc: OSError) -> None:
        _LOGGER.exception("proxy upstream request failed")
        payload = json.dumps({"error": str(exc)}).encode("utf-8")
        handler.send_response(HTTPStatus.BAD_GATEWAY)
        handler.send_header("Content-Type", "application/json")
        handler.send_header("Content-Length", str(len(payload)))
        handler.send_header("Connection", "close")
        handler.end_headers()
        handler.wfile.write(payload)
        handler.wfile.flush()
        handler.close_connection = True


def _build_upstream_path(parsed: SplitResult, path: str) -> str:
    request_target = path if path.startswith("/") else f"/{path}"
    prefix = parsed.path.rstrip("/")
    return f"{prefix}{request_target}" if prefix else request_target


def _filter_request_headers(handler: BaseHTTPRequestHandler) -> dict[str, str]:
    return {
        key: value
        for key, value in handler.headers.items()
        if key.lower() not in _HOP_BY_HOP_HEADERS
    }


def _read_request_body(handler: BaseHTTPRequestHandler) -> bytes:
    content_length = handler.headers.get("Content-Length")
    if content_length is None:
        return b""
    try:
        size = int(content_length)
    except ValueError:
        return b""
    if size <= 0:
        return b""
    return cast(bytes, handler.rfile.read(size))


def _is_streaming_response(response: HTTPResponse) -> bool:
    content_type = response.getheader("Content-Type", "").split(";", 1)[0].strip().lower()
    if content_type in _STREAMING_CONTENT_TYPES:
        return True
    if response.getheader("Transfer-Encoding"):
        return True
    return response.getheader("Content-Length") is None


__all__ = ["ProxyConfig", "ProxyLogEntry", "ProxyObservation", "ProxyServer"]
