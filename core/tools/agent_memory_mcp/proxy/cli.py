"""CLI entry point for the optional Engram proxy."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import inspect
import json
import os
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from ..server import create_mcp
from ..sidecar.access_logger import AccessLogger, MCPToolClient
from ..sidecar.cli import SessionIdAllocator, SidecarStateStore
from ..sidecar.dialogue_logger import DialogueLogger
from ..sidecar.lifecycle import SessionLifecycleManager
from ..sidecar.parser import ParsedSession, ToolCall
from ..sidecar.trace_logger import TraceLogger
from .auto_checkpoint import AutoCheckpointConfig, AutoCheckpointMonitor
from .compaction import CompactionConfig, CompactionMonitor
from .injection import ContextInjector, InjectionConfig
from .server import ProxyConfig, ProxyObservation, ProxyServer

_DEFAULT_HOST = "127.0.0.1"
_DEFAULT_PORT = 8400
_DEFAULT_REQUEST_TIMEOUT = 60.0
_DEFAULT_FLUSH_THRESHOLD = 0.85
_DEFAULT_RESET_THRESHOLD = 0.6
_DEFAULT_IDLE_TIMEOUT = timedelta(minutes=30)
_DEFAULT_MAINTENANCE_INTERVAL = 30.0
_SESSION_ID_HEADER = "x-engram-session-id"
_PROJECT_HEADER = "x-engram-project"
_CHAT_ID_RE = re.compile(
    r"^memory/activity/(?:[a-z0-9]+(?:-[a-z0-9]+)*/)?\d{4}/\d{2}/\d{2}/chat-\d{3}$"
)


@dataclass(slots=True)
class ProxyCliConfig:
    """Runtime configuration for engram-proxy."""

    repo_root: Path
    content_root: Path
    listen_host: str
    listen_port: int
    upstream_base_url: str
    request_timeout: float
    model_context_window: int | None
    flush_threshold: float
    reset_threshold: float
    enable_injection: bool
    enable_checkpointing: bool
    with_sidecar: bool
    state_path: Path


@dataclass(slots=True)
class _ObservedProxySession:
    session: ParsedSession
    request_user_count: int = 0
    seen_tool_call_fingerprints: set[str] = field(default_factory=set)


class _InProcessToolRegistry:
    """Invoke registered MCP tool callables without starting a transport."""

    def __init__(self, tools: Mapping[str, object], loop: asyncio.AbstractEventLoop) -> None:
        self._tools = dict(tools)
        self._loop = loop

    async def call_async(self, name: str, arguments: dict[str, object] | None = None) -> Any:
        result = self._invoke(name, arguments)
        if inspect.isawaitable(result):
            return await result
        return result

    def call_sync(self, name: str, arguments: dict[str, object] | None = None) -> Any:
        result = self._invoke(name, arguments)
        if not inspect.isawaitable(result):
            return result

        try:
            running_loop = asyncio.get_running_loop()
        except RuntimeError:
            running_loop = None
        if running_loop is self._loop:
            raise RuntimeError(
                f"Cannot synchronously invoke async tool {name!r} on the active loop"
            )

        future = asyncio.run_coroutine_threadsafe(result, self._loop)
        return future.result()

    def _invoke(self, name: str, arguments: dict[str, object] | None) -> Any:
        tool = self._tools.get(name)
        if tool is None or not callable(tool):
            raise ValueError(f"Unknown in-process MCP tool: {name}")
        return tool(**(arguments or {}))


class _SyncToolCaller:
    def __init__(self, registry: _InProcessToolRegistry) -> None:
        self._registry = registry

    def call_tool(self, name: str, arguments: dict[str, object] | None = None) -> Any:
        return self._registry.call_sync(name, arguments)


class _AsyncToolClient(MCPToolClient):
    def __init__(self, registry: _InProcessToolRegistry) -> None:
        self._registry = registry

    async def call_tool(self, name: str, arguments: dict[str, object] | None = None) -> Any:
        return await self._registry.call_async(name, arguments)


class ProxySidecarObserver:
    """Consume proxy observations and reuse sidecar ACCESS/lifecycle logic."""

    def __init__(
        self,
        config: ProxyCliConfig,
        *,
        tool_client: MCPToolClient,
        state_store: SidecarStateStore,
        loop: asyncio.AbstractEventLoop,
        now_factory: Callable[[], datetime] | None = None,
    ) -> None:
        self._config = config
        self._tool_client = tool_client
        self._state_store = state_store
        self._loop = loop
        self._now_factory = now_factory or (lambda: datetime.now(timezone.utc))
        self._state = state_store.load()
        self._allocator = SessionIdAllocator(config.content_root, self._state)
        self._access_logger = AccessLogger(tool_client)
        self._trace_logger = TraceLogger(config.content_root)
        self._dialogue_logger = DialogueLogger(config.content_root)
        self._lifecycle = SessionLifecycleManager(
            tool_client,
            content_root=config.content_root,
            session_id_factory=self._memory_session_id_for,
            inactivity_threshold=_DEFAULT_IDLE_TIMEOUT,
        )
        self._sessions: dict[str, _ObservedProxySession] = {}
        self._queue: asyncio.Queue[ProxyObservation | None] = asyncio.Queue()
        self._worker: asyncio.Task[None] | None = None
        self._maintenance_task: asyncio.Task[None] | None = None
        self._closed = False

    async def start(self) -> None:
        if self._worker is not None:
            return
        self._worker = asyncio.create_task(self._run(), name="engram-proxy-sidecar")
        self._maintenance_task = asyncio.create_task(
            self._maintenance_loop(),
            name="engram-proxy-sidecar-maintenance",
        )

    def submit(self, observation: ProxyObservation) -> None:
        if self._closed:
            return
        self._loop.call_soon_threadsafe(self._queue.put_nowait, observation)

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        await self._queue.put(None)
        if self._worker is not None:
            await self._worker
            self._worker = None
        if self._maintenance_task is not None:
            self._maintenance_task.cancel()
            try:
                await self._maintenance_task
            except asyncio.CancelledError:
                pass
            self._maintenance_task = None
        await self._finalize_all()

    async def _run(self) -> None:
        while True:
            observation = await self._queue.get()
            if observation is None:
                break
            await self._process_observation(observation)

    async def _maintenance_loop(self) -> None:
        try:
            while True:
                await asyncio.sleep(_DEFAULT_MAINTENANCE_INTERVAL)
                await self._close_inactive_sessions(self._now_factory())
        except asyncio.CancelledError:
            raise

    async def _process_observation(self, observation: ProxyObservation) -> None:
        await self._close_inactive_sessions(observation.observed_at)

        observed_session_id = _observed_session_id(observation)
        tracked = self._sessions.get(observed_session_id)
        if tracked is None:
            tracked = _ObservedProxySession(
                session=ParsedSession(
                    session_id=observed_session_id,
                    start_time=observation.observed_at,
                    end_time=observation.observed_at,
                )
            )
            self._sessions[observed_session_id] = tracked

        user_updates = _new_user_messages(tracked, observation)
        assistant_updates = _assistant_updates(observation)
        tool_updates = _new_tool_calls(tracked, observation)
        file_updates = _extract_files_referenced(tool_updates)

        if user_updates:
            tracked.session.user_messages.extend(user_updates)
        if assistant_updates:
            tracked.session.assistant_messages.extend(assistant_updates)
        if tool_updates:
            tracked.session.tool_calls.extend(tool_updates)
        if file_updates:
            tracked.session.files_referenced.extend(file_updates)
        tracked.session.end_time = observation.observed_at

        memory_session_id = self._memory_session_id_for(tracked.session)
        if tool_updates:
            await self._access_logger.log_session_access(
                ParsedSession(
                    session_id=tracked.session.session_id,
                    start_time=tracked.session.start_time,
                    end_time=observation.observed_at,
                    user_messages=user_updates,
                    assistant_messages=assistant_updates,
                    tool_calls=tool_updates,
                    files_referenced=file_updates,
                ),
                session_id=memory_session_id,
            )
            self._trace_logger.persist_tool_spans(memory_session_id, tracked.session)

        if user_updates or assistant_updates or tool_updates:
            dialogue_entries = self._dialogue_logger.build_dialogue_entries(tracked.session)
            await self._lifecycle.observe_session(
                tracked.session,
                transcript_path=f"proxy://{observed_session_id}",
                transcript_closed=False,
                dialogue_entries=dialogue_entries,
            )
            self._state_store.save(self._state)

    async def _close_inactive_sessions(self, reference_time: datetime) -> None:
        finalized = await self._lifecycle.close_inactive_sessions(reference_time)
        if not finalized:
            return
        for result in finalized:
            self._sessions.pop(result.observed_session_id, None)
        self._state_store.save(self._state)

    async def _finalize_all(self) -> None:
        if not self._sessions:
            return
        await self._close_inactive_sessions(self._now_factory() + timedelta(days=3650))

    def _memory_session_id_for(self, session: ParsedSession) -> str:
        if _is_canonical_memory_session_id(session.session_id):
            return session.session_id
        return self._allocator.session_id_for(session, platform="proxy")


class ProxyRuntime:
    """Own the proxy server and optional in-process sidecar bridge."""

    def __init__(
        self,
        config: ProxyCliConfig,
        *,
        loop: asyncio.AbstractEventLoop | None = None,
        sync_tool_caller: Any | None = None,
        async_tool_client: MCPToolClient | None = None,
    ) -> None:
        self._config = config
        self._loop = loop or asyncio.get_running_loop()
        self._registry: _InProcessToolRegistry | None = None

        if sync_tool_caller is None or async_tool_client is None:
            _mcp, tools, _root, _repo = create_mcp(repo_root=config.repo_root)
            self._registry = _InProcessToolRegistry(tools, self._loop)
        if sync_tool_caller is None:
            if self._registry is None:
                raise RuntimeError("Proxy runtime requires a tool registry for sync tool calls")
            sync_tool_caller = _SyncToolCaller(self._registry)
        if async_tool_client is None:
            if self._registry is None:
                raise RuntimeError("Proxy runtime requires a tool registry for async tool calls")
            async_tool_client = _AsyncToolClient(self._registry)
        self._sync_tool_caller = sync_tool_caller
        self._async_tool_client = async_tool_client

        context_injector = None
        if config.enable_injection:
            context_injector = ContextInjector(
                self._sync_tool_caller,
                InjectionConfig(model_context_window=config.model_context_window),
            )

        compaction_monitor = CompactionMonitor(
            self._sync_tool_caller,
            CompactionConfig(
                default_model_context_window=config.model_context_window,
                flush_threshold=config.flush_threshold,
                reset_threshold=config.reset_threshold,
            ),
        )

        auto_checkpoint_monitor = None
        if config.enable_checkpointing:
            auto_checkpoint_monitor = AutoCheckpointMonitor(
                self._sync_tool_caller,
                AutoCheckpointConfig(),
            )

        self._sidecar: ProxySidecarObserver | None = None
        observation_sink = None
        if config.with_sidecar:
            self._sidecar = ProxySidecarObserver(
                config,
                tool_client=self._async_tool_client,
                state_store=SidecarStateStore(config.state_path),
                loop=self._loop,
            )
            observation_sink = self._sidecar.submit

        self.server = ProxyServer(
            ProxyConfig(
                listen_host=config.listen_host,
                listen_port=config.listen_port,
                upstream_base_url=config.upstream_base_url,
                request_timeout=config.request_timeout,
            ),
            context_injector=context_injector,
            compaction_monitor=compaction_monitor,
            auto_checkpoint_monitor=auto_checkpoint_monitor,
            observation_sink=observation_sink,
        )

    async def start(self) -> None:
        if self._sidecar is not None:
            await self._sidecar.start()
        self.server.start()

    async def close(self) -> None:
        self.server.close()
        if self._sidecar is not None:
            await self._sidecar.close()

    async def __aenter__(self) -> ProxyRuntime:
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments for engram-proxy."""

    parser = argparse.ArgumentParser(prog="engram-proxy")
    parser.add_argument("--host", help="Proxy listen host (default: 127.0.0.1).")
    parser.add_argument("--port", type=int, help="Proxy listen port (default: 8400).")
    parser.add_argument("--upstream", help="Upstream model API base URL.")
    parser.add_argument(
        "--request-timeout", type=float, help="Upstream request timeout in seconds."
    )
    parser.add_argument(
        "--model-context-window",
        type=int,
        help="Default model context window when the request omits the proxy header.",
    )
    parser.add_argument("--flush-threshold", type=float, help="Context-pressure flush threshold.")
    parser.add_argument("--reset-threshold", type=float, help="Compaction reset threshold.")
    parser.add_argument(
        "--enable-injection",
        dest="enable_injection",
        action="store_true",
        help="Enable context injection.",
    )
    parser.add_argument(
        "--no-injection",
        dest="enable_injection",
        action="store_false",
        help="Disable context injection.",
    )
    parser.add_argument(
        "--enable-checkpointing",
        dest="enable_checkpointing",
        action="store_true",
        help="Enable automatic checkpoint extraction.",
    )
    parser.add_argument(
        "--no-checkpointing",
        dest="enable_checkpointing",
        action="store_false",
        help="Disable automatic checkpoint extraction.",
    )
    parser.set_defaults(enable_injection=None, enable_checkpointing=None)
    parser.add_argument(
        "--with-sidecar",
        action="store_true",
        help="Run sidecar-style ACCESS logging and session lifecycle in process.",
    )
    parser.add_argument(
        "--repo-root",
        help="Memory repo root (default: MEMORY_REPO_ROOT or repo-relative detection).",
    )
    parser.add_argument("--state-file", help="Optional path for local proxy/sidecar state.")
    return parser.parse_args(list(argv) if argv is not None else None)


def load_config(
    args: argparse.Namespace,
    *,
    env: Mapping[str, str] | None = None,
) -> ProxyCliConfig:
    """Resolve CLI arguments and environment variables into runtime config."""

    environment = dict(env or os.environ)
    repo_root = _resolve_repo_root(args.repo_root, environment)
    content_root = _resolve_content_root(repo_root, environment)

    listen_host = (args.host or environment.get("PROXY_HOST") or _DEFAULT_HOST).strip()
    listen_port = int(
        args.port if args.port is not None else environment.get("PROXY_PORT", _DEFAULT_PORT)
    )
    request_timeout = float(
        args.request_timeout
        if args.request_timeout is not None
        else environment.get("PROXY_REQUEST_TIMEOUT", _DEFAULT_REQUEST_TIMEOUT)
    )
    upstream_base_url = (
        args.upstream or environment.get("PROXY_UPSTREAM_URL") or _default_upstream_url(environment)
    ).strip()

    model_context_window = args.model_context_window
    if model_context_window is None and environment.get("PROXY_MODEL_CONTEXT_WINDOW"):
        model_context_window = int(environment["PROXY_MODEL_CONTEXT_WINDOW"])

    flush_threshold = float(
        args.flush_threshold
        if args.flush_threshold is not None
        else environment.get("PROXY_FLUSH_THRESHOLD", _DEFAULT_FLUSH_THRESHOLD)
    )
    reset_threshold = float(
        args.reset_threshold
        if args.reset_threshold is not None
        else environment.get("PROXY_RESET_THRESHOLD", _DEFAULT_RESET_THRESHOLD)
    )

    enable_injection = _resolve_bool(
        args.enable_injection,
        environment.get("PROXY_ENABLE_INJECTION"),
        default=True,
    )
    enable_checkpointing = _resolve_bool(
        args.enable_checkpointing,
        environment.get("PROXY_ENABLE_CHECKPOINTING"),
        default=True,
    )
    with_sidecar = args.with_sidecar or _env_flag(environment.get("PROXY_WITH_SIDECAR"), False)

    state_path = (
        Path(args.state_file).expanduser().resolve()
        if args.state_file
        else _default_state_path(repo_root)
    )

    return ProxyCliConfig(
        repo_root=repo_root,
        content_root=content_root,
        listen_host=listen_host,
        listen_port=listen_port,
        upstream_base_url=upstream_base_url,
        request_timeout=request_timeout,
        model_context_window=model_context_window,
        flush_threshold=flush_threshold,
        reset_threshold=reset_threshold,
        enable_injection=enable_injection,
        enable_checkpointing=enable_checkpointing,
        with_sidecar=with_sidecar,
        state_path=state_path,
    )


async def async_main(
    argv: Sequence[str] | None = None,
    *,
    env: Mapping[str, str] | None = None,
    shutdown_event: asyncio.Event | None = None,
) -> int:
    """Async CLI entry point to enable direct unit testing."""

    config = load_config(parse_args(argv), env=env)
    runtime = ProxyRuntime(config)
    await runtime.start()
    try:
        if shutdown_event is None:
            await asyncio.Future()
        else:
            await shutdown_event.wait()
    finally:
        await runtime.close()
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Console entry point for engram-proxy."""

    return asyncio.run(async_main(argv))


def _observed_session_id(observation: ProxyObservation) -> str:
    session_id = _lookup_header(observation.request_headers, _SESSION_ID_HEADER)
    if session_id:
        return session_id

    project_hint = _lookup_header(observation.request_headers, _PROJECT_HEADER)
    client_host = observation.client_host or "unknown"
    if project_hint:
        return f"proxy/{client_host}/{project_hint}"
    return f"proxy/{client_host}/global"


def _new_user_messages(
    tracked: _ObservedProxySession,
    observation: ProxyObservation,
) -> list[str]:
    inspection = observation.request_inspection
    if inspection is None:
        return []

    current_count = len(inspection.user_messages)
    if current_count < tracked.request_user_count:
        tracked.request_user_count = current_count
        return []
    if current_count == tracked.request_user_count:
        return []

    messages = [
        message.strip()
        for message in inspection.user_messages[tracked.request_user_count :]
        if message.strip()
    ]
    tracked.request_user_count = current_count
    return messages


def _assistant_updates(observation: ProxyObservation) -> list[str]:
    if observation.response_inspection is None:
        return []
    return [
        text.strip() for text in observation.response_inspection.assistant_texts if text.strip()
    ]


def _new_tool_calls(
    tracked: _ObservedProxySession,
    observation: ProxyObservation,
) -> list[ToolCall]:
    updates: list[ToolCall] = []
    inspection = observation.request_inspection
    if inspection is not None:
        for observed in inspection.observed_tool_calls:
            if observed.result is None:
                continue
            tool_call = ToolCall(
                name=observed.name,
                args=observed.args,
                result=observed.result,
            )
            if _track_tool_call(tracked, tool_call):
                updates.append(tool_call)

    if observation.compaction_result is not None and observation.compaction_result.flush_triggered:
        tool_call = ToolCall(
            name=observation.compaction_result.flush_tool_name or "memory_session_flush",
            args={
                "session_id": observation.compaction_result.session_id,
                "project_hint": observation.compaction_result.project_hint,
            },
            result=observation.compaction_result.flush_payload,
        )
        if _track_tool_call(tracked, tool_call):
            updates.append(tool_call)

    if (
        observation.auto_checkpoint_result is not None
        and observation.auto_checkpoint_result.checkpoint_triggered
    ):
        tool_call = ToolCall(
            name=observation.auto_checkpoint_result.checkpoint_tool_name or "memory_checkpoint",
            args={
                "label": observation.auto_checkpoint_result.checkpoint_label,
                "session_id": observation.auto_checkpoint_result.checkpoint_session_id,
            },
            result=observation.auto_checkpoint_result.checkpoint_payload,
        )
        if _track_tool_call(tracked, tool_call):
            updates.append(tool_call)

    return updates


def _track_tool_call(tracked: _ObservedProxySession, tool_call: ToolCall) -> bool:
    fingerprint = json.dumps(
        {
            "name": tool_call.name,
            "args": tool_call.args,
            "result": tool_call.result,
        },
        default=str,
        sort_keys=True,
    )
    if fingerprint in tracked.seen_tool_call_fingerprints:
        return False
    tracked.seen_tool_call_fingerprints.add(fingerprint)
    return True


def _extract_files_referenced(tool_calls: list[ToolCall]) -> list[str]:
    files: list[str] = []
    for tool_call in tool_calls:
        path = _extract_path(tool_call)
        if path:
            files.append(path)
    return files


def _extract_path(tool_call: ToolCall) -> str | None:
    for candidate in (_mapping_path(tool_call.result), _mapping_path(tool_call.args)):
        if candidate:
            normalized = candidate.replace("\\", "/").strip()
            if normalized.startswith("core/"):
                normalized = normalized[len("core/") :]
            return normalized
    return None


def _mapping_path(payload: Any) -> str | None:
    if isinstance(payload, str):
        stripped = payload.strip()
        if stripped and stripped[0] in "[{":
            try:
                payload = json.loads(stripped)
            except json.JSONDecodeError:
                return None
        else:
            return None
    if not isinstance(payload, Mapping):
        return None
    value = payload.get("path")
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _lookup_header(headers: Mapping[str, str], key: str) -> str | None:
    for header_name, header_value in headers.items():
        if header_name.lower() == key:
            stripped = header_value.strip()
            return stripped or None
    return None


def _is_canonical_memory_session_id(value: str) -> bool:
    return _CHAT_ID_RE.fullmatch(value) is not None


def _default_state_path(repo_root: Path) -> Path:
    digest = hashlib.sha1(str(repo_root).encode("utf-8")).hexdigest()[:16]
    return Path.home() / ".engram" / "proxy" / f"{digest}.json"


def _resolve_repo_root(explicit_root: str | None, env: Mapping[str, str]) -> Path:
    for candidate in (explicit_root, env.get("MEMORY_REPO_ROOT"), env.get("AGENT_MEMORY_ROOT")):
        if not candidate:
            continue
        root = Path(candidate).expanduser().resolve()
        if root.is_dir():
            return root
        existing_parent = root
        while not existing_parent.exists() and existing_parent != existing_parent.parent:
            existing_parent = existing_parent.parent
        if existing_parent.is_dir():
            return existing_parent
        raise ValueError(f"Repository root is not a directory: {root}")
    return Path(__file__).resolve().parents[3]


def _resolve_content_root(repo_root: Path, env: Mapping[str, str]) -> Path:
    content_prefix = env.get("MEMORY_CORE_PREFIX", "core")
    candidate = repo_root / content_prefix
    if (candidate / "memory").exists():
        return candidate
    return repo_root


def _resolve_bool(explicit: bool | None, env_value: str | None, *, default: bool) -> bool:
    if explicit is not None:
        return explicit
    return _env_flag(env_value, default)


def _env_flag(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"Invalid boolean flag value: {value}")


def _default_upstream_url(env: Mapping[str, str]) -> str:
    if env.get("ANTHROPIC_API_KEY"):
        return "https://api.anthropic.com"
    if env.get("OPENAI_API_KEY"):
        return "https://api.openai.com"
    return ProxyConfig().upstream_base_url


__all__ = [
    "ProxyCliConfig",
    "ProxyRuntime",
    "ProxySidecarObserver",
    "async_main",
    "load_config",
    "main",
    "parse_args",
]
