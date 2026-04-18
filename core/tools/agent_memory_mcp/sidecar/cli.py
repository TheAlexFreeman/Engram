"""CLI entry point for the Engram sidecar observer."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import sys
from collections.abc import Mapping, Sequence
from contextlib import AsyncExitStack
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Protocol

from ..path_policy import namespace_session_id, validate_slug
from .access_logger import AccessLogger, MCPToolClient
from .dialogue_logger import DialogueLogger
from .lifecycle import SessionLifecycleManager
from .parser import ParsedSession, TranscriptParser
from .parsers import PARSER_REGISTRY, build_parsers_from_registry
from .trace_logger import TraceLogger

_DEFAULT_PLATFORM = "auto"
_DEFAULT_POLL_INTERVAL = 30.0
_DEFAULT_LOOKBACK = timedelta(days=1)
_DEFAULT_MCP_URL = "stdio://engram-mcp"
_STATE_SCHEMA_VERSION = 1
_CHAT_ID_RE = re.compile(
    r"^memory/activity/(?:(?P<user_id>[a-z0-9]+(?:-[a-z0-9]+)*)/)?(?P<day>\d{4}/\d{2}/\d{2})/chat-(?P<number>\d{3})$"
)


def _resolve_sidecar_user_id() -> str | None:
    raw_user_id = os.environ.get("MEMORY_USER_ID", "").strip()
    if not raw_user_id:
        return None
    return validate_slug(raw_user_id, field_name="MEMORY_USER_ID")


@dataclass(slots=True)
class SidecarConfig:
    """Runtime configuration for the sidecar CLI."""

    repo_root: Path
    content_root: Path
    platform: str
    once: bool
    since: datetime
    poll_interval: float
    mcp_url: str
    state_path: Path


@dataclass(slots=True)
class SidecarRunResult:
    """High-level counters for one sidecar processing cycle."""

    processed_transcripts: int = 0
    access_entries_logged: int = 0
    finalized_sessions: int = 0
    trace_spans_logged: int = 0
    dialogue_entries_logged: int = 0


@dataclass(slots=True)
class SidecarState:
    """Persistent local state for sidecar replay suppression."""

    transcript_watermarks: dict[str, str] = field(default_factory=dict)
    session_ids: dict[str, str] = field(default_factory=dict)


class ClientFactory(Protocol):
    def __call__(self, config: SidecarConfig) -> "AsyncClientContext":
        """Build an async context manager yielding an MCP tool client."""


class ParserFactory(Protocol):
    def __call__(self, config: SidecarConfig) -> list[TranscriptParser]:
        """Build parser instances for the configured sidecar platform set."""


class StateStoreFactory(Protocol):
    def __call__(self, config: SidecarConfig) -> "SidecarStateStore":
        """Build the sidecar state store for the current configuration."""


class AsyncClientContext(Protocol):
    async def __aenter__(self) -> MCPToolClient:
        """Open the MCP client context and return the connected client."""

    async def __aexit__(self, exc_type, exc, tb) -> None:
        """Close the MCP client context."""


class SidecarStateStore:
    """Load and save persistent sidecar state outside the memory repo."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def load(self) -> SidecarState:
        if not self._path.exists():
            return SidecarState()

        payload = json.loads(self._path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            return SidecarState()

        transcript_watermarks = payload.get("transcript_watermarks")
        session_ids = payload.get("session_ids")
        return SidecarState(
            transcript_watermarks=(
                {
                    str(key): str(value)
                    for key, value in transcript_watermarks.items()
                    if isinstance(key, str) and isinstance(value, str)
                }
                if isinstance(transcript_watermarks, dict)
                else {}
            ),
            session_ids=(
                {
                    str(key): str(value)
                    for key, value in session_ids.items()
                    if isinstance(key, str) and isinstance(value, str)
                }
                if isinstance(session_ids, dict)
                else {}
            ),
        )

    def save(self, state: SidecarState) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": _STATE_SCHEMA_VERSION,
            "transcript_watermarks": state.transcript_watermarks,
            "session_ids": state.session_ids,
        }
        self._path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


class SessionIdAllocator:
    """Allocate stable canonical memory/activity session IDs."""

    def __init__(self, content_root: Path, state: SidecarState) -> None:
        self._content_root = content_root
        self._state = state
        self._user_id = _resolve_sidecar_user_id()
        self._assigned_by_day: dict[str, set[int]] = {}
        for session_id in state.session_ids.values():
            parsed = _parse_chat_session_id(session_id)
            if parsed is None:
                continue
            day_key, number = parsed
            self._assigned_by_day.setdefault(day_key, set()).add(number)

    def session_id_for(self, session: ParsedSession, *, platform: str) -> str:
        allocation_key = self._allocation_key(session, platform=platform)
        existing = self._state.session_ids.get(allocation_key)
        if existing:
            return existing

        day_key = _utc(session.end_time).strftime("%Y/%m/%d")
        assigned = self._assigned_by_day.setdefault(
            day_key, self._existing_numbers_for_day(day_key)
        )
        next_number = 1
        while next_number in assigned:
            next_number += 1
        if next_number > 999:
            activity_scope = (
                f"memory/activity/{self._user_id}/{day_key}"
                if self._user_id is not None
                else f"memory/activity/{day_key}"
            )
            raise RuntimeError(f"No available chat ids remain for {activity_scope}")

        assigned.add(next_number)
        session_id = namespace_session_id(
            f"memory/activity/{day_key}/chat-{next_number:03d}",
            user_id=self._user_id,
        )
        self._state.session_ids[allocation_key] = session_id
        return session_id

    def _allocation_key(self, session: ParsedSession, *, platform: str) -> str:
        return "|".join(
            [
                platform,
                session.session_id,
                _utc(session.start_time).isoformat(),
            ]
        )

    def _existing_numbers_for_day(self, day_key: str) -> set[int]:
        existing: set[int] = set()
        activity_day = self._content_root / PurePosixPath("memory/activity")
        if self._user_id is not None:
            activity_day = activity_day / self._user_id
        activity_day = activity_day / PurePosixPath(day_key)
        if activity_day.exists() and activity_day.is_dir():
            for child in activity_day.iterdir():
                if not child.is_dir() or not child.name.startswith("chat-"):
                    continue
                try:
                    existing.add(int(child.name.split("-", 1)[1]))
                except (IndexError, ValueError):
                    continue
        return existing


class StdioMCPToolClient(MCPToolClient):
    """MCP client that talks to engram-mcp over stdio."""

    def __init__(self, config: SidecarConfig) -> None:
        self._config = config
        self._stack: AsyncExitStack | None = None
        self._session: Any = None

    async def __aenter__(self) -> "StdioMCPToolClient":
        from mcp.client.session import ClientSession
        from mcp.client.stdio import StdioServerParameters, stdio_client

        env = {**os.environ, "MEMORY_REPO_ROOT": str(self._config.repo_root)}
        if "MEMORY_CORE_PREFIX" in os.environ:
            env["MEMORY_CORE_PREFIX"] = os.environ["MEMORY_CORE_PREFIX"]

        command, args = _stdio_server_command(self._config)
        server = StdioServerParameters(
            command=command,
            args=args,
            cwd=str(self._config.repo_root),
            env=env,
        )

        self._stack = AsyncExitStack()
        read_stream, write_stream = await self._stack.enter_async_context(stdio_client(server))
        self._session = await self._stack.enter_async_context(
            ClientSession(read_stream, write_stream)
        )
        await self._session.initialize()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._stack is not None:
            await self._stack.aclose()
        self._stack = None
        self._session = None

    async def call_tool(self, name: str, arguments: dict[str, object] | None = None) -> Any:
        if self._session is None:
            raise RuntimeError("stdio MCP client has not been initialized")
        return await self._session.call_tool(name, arguments or {})


class SidecarRunner:
    """Coordinate transcript parsing, ACCESS logging, and lifecycle recording."""

    def __init__(
        self,
        config: SidecarConfig,
        *,
        client: MCPToolClient,
        parsers: list[TranscriptParser],
        state_store: SidecarStateStore,
        now_factory: Callable[[], datetime] | None = None,
    ) -> None:
        self._config = config
        self._client = client
        self._parsers = parsers
        self._state_store = state_store
        self._state = state_store.load()
        self._now_factory = now_factory or (lambda: datetime.now(timezone.utc))
        self._allocator = SessionIdAllocator(config.content_root, self._state)
        self._access_logger = AccessLogger(client)
        self._trace_logger = TraceLogger(config.content_root)
        self._dialogue_logger = DialogueLogger(config.content_root)
        self._lifecycles = {
            parser.platform_name(): SessionLifecycleManager(
                client,
                content_root=config.content_root,
                session_id_factory=self._session_id_factory_for(parser.platform_name()),
            )
            for parser in parsers
        }

    async def process_cycle(self, *, once: bool) -> SidecarRunResult:
        result = SidecarRunResult()
        for parser in self._parsers:
            lifecycle = self._lifecycles[parser.platform_name()]
            for transcript in parser.find_transcripts(self._config.since):
                if self._is_up_to_date(transcript.path, transcript.modified_time):
                    continue

                session = parser.parse_session(transcript)
                memory_session_id = self._allocator.session_id_for(
                    session,
                    platform=parser.platform_name(),
                )
                trace_added = self._trace_logger.persist_tool_spans(memory_session_id, session)
                access_result = await self._access_logger.log_session_access(
                    session,
                    session_id=memory_session_id,
                )
                dialogue_entries = self._dialogue_logger.build_dialogue_entries(session)
                finalized = await lifecycle.observe_session(
                    session,
                    transcript_path=transcript.path.as_posix(),
                    transcript_closed=once,
                    dialogue_entries=dialogue_entries,
                )
                self._state.transcript_watermarks[transcript.path.as_posix()] = _utc(
                    transcript.modified_time
                ).isoformat()
                result.processed_transcripts += 1
                result.access_entries_logged += len(access_result.entries)
                result.trace_spans_logged += trace_added
                result.finalized_sessions += len(finalized)
                result.dialogue_entries_logged += sum(fin.dialogue_rows for fin in finalized)

        if not once:
            reference_time = self._now_factory()
            for lifecycle in self._lifecycles.values():
                finalized = await lifecycle.close_inactive_sessions(reference_time)
                result.finalized_sessions += len(finalized)

        self._state_store.save(self._state)
        return result

    def _is_up_to_date(self, transcript_path: Path, modified_time: datetime) -> bool:
        key = transcript_path.as_posix()
        current = _utc(modified_time)
        stored = self._state.transcript_watermarks.get(key)
        if stored is None:
            return False
        try:
            return _parse_datetime(stored) >= current
        except ValueError:
            return False

    def _session_id_factory_for(self, platform: str) -> Callable[[ParsedSession], str]:
        def _factory(session: ParsedSession) -> str:
            return self._allocator.session_id_for(session, platform=platform)

        return _factory


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments for the Engram sidecar."""

    parser = argparse.ArgumentParser(prog="engram-sidecar")
    parser.add_argument(
        "--once", action="store_true", help="Process matching transcripts and exit."
    )
    parser.add_argument("--platform", help="Platform parser to run (default: auto-detect).")
    parser.add_argument(
        "--since", help="Only process transcripts on or after this ISO date or datetime."
    )
    parser.add_argument("--poll-interval", type=float, help="Polling interval in seconds.")
    parser.add_argument("--mcp-url", help="MCP transport URL (default: stdio://engram-mcp).")
    parser.add_argument(
        "--repo-root",
        help="Memory repo root (default: MEMORY_REPO_ROOT or repo-relative detection).",
    )
    parser.add_argument("--state-file", help="Optional path for the local sidecar state file.")
    return parser.parse_args(list(argv) if argv is not None else None)


def load_config(
    args: argparse.Namespace,
    *,
    env: Mapping[str, str] | None = None,
    now: datetime | None = None,
) -> SidecarConfig:
    """Resolve CLI arguments and environment variables into runtime config."""

    environment = dict(env or os.environ)
    current_time = _utc(now or datetime.now(timezone.utc))

    repo_root = _resolve_repo_root(args.repo_root, environment)
    content_root = _resolve_content_root(repo_root, environment)

    platform = (
        (args.platform or environment.get("SIDECAR_PLATFORM") or _DEFAULT_PLATFORM).strip().lower()
    )
    if platform in {"auto-detect", "autodetect"}:
        platform = _DEFAULT_PLATFORM
    if platform not in {_DEFAULT_PLATFORM, *PARSER_REGISTRY.keys()}:
        raise ValueError(f"Unsupported sidecar platform: {platform}")

    raw_poll_interval = args.poll_interval
    if raw_poll_interval is None:
        env_poll_interval = environment.get("SIDECAR_POLL_INTERVAL")
        raw_poll_interval = (
            float(env_poll_interval) if env_poll_interval else _DEFAULT_POLL_INTERVAL
        )
    if raw_poll_interval <= 0:
        raise ValueError("poll interval must be greater than zero")

    raw_since = args.since.strip() if isinstance(args.since, str) else ""
    since = _parse_since(raw_since, now=current_time)

    mcp_url = (args.mcp_url or environment.get("SIDECAR_MCP_URL") or _DEFAULT_MCP_URL).strip()
    if not mcp_url:
        mcp_url = _DEFAULT_MCP_URL

    state_path = (
        Path(args.state_file).expanduser().resolve()
        if args.state_file
        else _default_state_path(repo_root)
    )

    return SidecarConfig(
        repo_root=repo_root,
        content_root=content_root,
        platform=platform,
        once=bool(args.once),
        since=since,
        poll_interval=float(raw_poll_interval),
        mcp_url=mcp_url,
        state_path=state_path,
    )


def build_parsers(config: SidecarConfig) -> list[TranscriptParser]:
    """Instantiate transcript parsers for the configured platform selection."""

    return build_parsers_from_registry(config.platform)


def build_state_store(config: SidecarConfig) -> SidecarStateStore:
    """Construct the local sidecar state store."""

    return SidecarStateStore(config.state_path)


def build_client(config: SidecarConfig) -> StdioMCPToolClient:
    """Construct the default MCP client transport for the sidecar."""

    if config.mcp_url not in {_DEFAULT_MCP_URL, "stdio", "stdio://", "engram-mcp"}:
        raise ValueError(
            "Unsupported SIDECAR_MCP_URL. Phase 6 supports only the default stdio transport to engram-mcp."
        )
    return StdioMCPToolClient(config)


async def async_main(
    argv: Sequence[str] | None = None,
    *,
    env: Mapping[str, str] | None = None,
    client_factory: ClientFactory | None = None,
    parser_factory: ParserFactory | None = None,
    state_store_factory: StateStoreFactory | None = None,
    now_factory: Callable[[], datetime] | None = None,
    sleep_func: Callable[[float], Any] | None = None,
) -> int:
    """Async CLI entry point to enable direct unit testing."""

    args = parse_args(argv)
    config = load_config(
        args,
        env=env,
        now=(now_factory() if now_factory is not None else None),
    )
    parsers = parser_factory(config) if parser_factory is not None else build_parsers(config)
    state_store = (
        state_store_factory(config)
        if state_store_factory is not None
        else build_state_store(config)
    )
    now_provider = now_factory or (lambda: datetime.now(timezone.utc))
    sleeper = sleep_func or asyncio.sleep

    async with (
        client_factory(config) if client_factory is not None else build_client(config)
    ) as client:
        runner = SidecarRunner(
            config,
            client=client,
            parsers=parsers,
            state_store=state_store,
            now_factory=now_provider,
        )
        if config.once:
            await runner.process_cycle(once=True)
            return 0

        while True:
            try:
                await runner.process_cycle(once=False)
            except Exception as exc:
                print(f"engram-sidecar: processing cycle failed: {exc}", file=sys.stderr)
            await sleeper(config.poll_interval)


def main(argv: Sequence[str] | None = None) -> int:
    """Synchronous console entry point for engram-sidecar."""

    return asyncio.run(async_main(argv))


def _default_state_path(repo_root: Path) -> Path:
    digest = hashlib.sha1(str(repo_root).encode("utf-8")).hexdigest()[:16]
    return Path.home() / ".engram" / "sidecar" / f"{digest}.json"


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


def _parse_since(raw_value: str, *, now: datetime) -> datetime:
    if not raw_value:
        return now - _DEFAULT_LOOKBACK
    try:
        parsed_date = date.fromisoformat(raw_value)
    except ValueError:
        return _parse_datetime(raw_value)
    return datetime(parsed_date.year, parsed_date.month, parsed_date.day, tzinfo=timezone.utc)


def _parse_datetime(raw_value: str) -> datetime:
    normalized = raw_value.strip().replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    return _utc(parsed)


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _parse_chat_session_id(session_id: str) -> tuple[str, int] | None:
    match = _CHAT_ID_RE.fullmatch(session_id)
    if match is None:
        return None
    return match.group("day"), int(match.group("number"))


def _stdio_server_command(config: SidecarConfig) -> tuple[str, list[str]]:
    if config.mcp_url not in {_DEFAULT_MCP_URL, "stdio", "stdio://", "engram-mcp"}:
        raise ValueError(
            "Unsupported SIDECAR_MCP_URL. Phase 6 supports only the default stdio transport to engram-mcp."
        )
    return sys.executable, ["-m", "engram_mcp.agent_memory_mcp.server_main"]


if __name__ == "__main__":
    raise SystemExit(main())
