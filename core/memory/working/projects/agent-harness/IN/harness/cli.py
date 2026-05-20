from __future__ import annotations
import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

import anthropic
from dotenv import load_dotenv
from openai import OpenAI

from harness.loop import run
from harness.memory import FileMemory
from harness.stream import NullStreamSink, StderrStreamPrinter
from harness.tools import Tool
from harness.tools.bash import Bash
from harness.tools.fs import (
    CopyPath,
    DeletePath,
    EditFile,
    GlobFiles,
    GrepWorkspace,
    ListFiles,
    Mkdir,
    MovePath,
    PathStat,
    ReadFile,
    WorkspaceScope,
    WriteFile,
)
from harness.tools.git import Git, GitCommit, GitDiff, GitLog, GitStatus
from harness.tools.search import WebSearch
from harness.tools.todos import AnalyzeTodos, ReadTodos, UpdateTodo, WriteTodos
from harness.tools.x_search import XSearch
from harness.trace import CompositeTracer, ConsoleTracePrinter, Tracer


def build_tools(scope: WorkspaceScope) -> dict[str, Tool]:
    return {
        t.name: t
        for t in [
            ReadFile(scope),
            ListFiles(scope),
            PathStat(scope),
            GlobFiles(scope),
            Mkdir(scope),
            EditFile(scope),
            WriteFile(scope),
            DeletePath(scope),
            MovePath(scope),
            CopyPath(scope),
            GrepWorkspace(scope),
            Bash(scope),
            GitStatus(scope),
            GitDiff(scope),
            GitLog(scope),
            GitCommit(scope),
            Git(scope),
            WriteTodos(scope),
            ReadTodos(scope),
            UpdateTodo(scope),
            AnalyzeTodos(scope),
            WebSearch(),
            XSearch(),  # Dedicated real-time X (Twitter) search with strong X bias
        ]
    }


def _find_git_root(start: Path) -> Path | None:
    cur = start.resolve()
    for p in [cur, *cur.parents]:
        if (p / ".git").exists():
            return p
    return None


def _normalize_gitignore_line(line: str) -> str | None:
    line = line.split("#", 1)[0].strip()
    if not line or line.startswith("!"):
        return None
    if line.startswith("./"):
        line = line[2:]
    stripped = line.rstrip("/")
    return stripped or None


def _workspace_gitignore_pattern(workspace: Path, git_root: Path) -> str | None:
    try:
        rel = workspace.resolve().relative_to(git_root.resolve())
    except ValueError:
        return None
    if rel == Path(".") or not rel.parts:
        return None
    return f"{rel.as_posix().rstrip('/')}/"


def _ensure_workspace_in_gitignore(workspace: Path) -> None:
    git_root = _find_git_root(workspace)
    if git_root is None:
        return
    pattern = _workspace_gitignore_pattern(workspace, git_root)
    if pattern is None:
        return
    ignore_path = git_root / ".gitignore"
    existing = ignore_path.read_text(encoding="utf-8") if ignore_path.exists() else ""
    canon = _normalize_gitignore_line(pattern)
    if canon is None:
        return
    for line in existing.splitlines():
        token = _normalize_gitignore_line(line)
        if token is not None and token == canon:
            return
    with ignore_path.open("a", encoding="utf-8") as f:
        if existing and not existing.endswith("\n"):
            f.write("\n")
        f.write(f"{pattern}\n")


def main() -> None:
    load_dotenv()
    load_dotenv(Path(__file__).resolve().parent / ".env")

    parser = argparse.ArgumentParser(prog="harness")
    parser.add_argument("task", help="What you want the agent to do.")
    parser.add_argument(
        "--workspace", default=".", help="Directory the agent may read/write."
    )
    parser.add_argument("--mode", choices=["native", "text"], default="native")
    parser.add_argument(
        "--model",
        default="claude-sonnet-4-6",
        help="Model to use (e.g. claude-3-5-sonnet-20241022, grok-4.20-0309-reasoning). "
        "Grok/xAI models use the Responses API (native web_search/x_search) plus harness tools.",
    )
    parser.add_argument("--max-turns", type=int, default=100)
    parser.add_argument(
        "--max-parallel-tools",
        type=int,
        default=4,
        help="Maximum tool calls from a single turn to execute concurrently. "
        "1 disables parallelism (sequential execution).",
    )
    parser.add_argument(
        "--trace-live",
        dest="trace_live",
        action="store_true",
        default=True,
        help="Print tool/session trace lines to stderr during the run (default: enabled).",
    )
    parser.add_argument(
        "--no-trace-live",
        dest="trace_live",
        action="store_false",
        help="Disable live trace printing to stderr.",
    )
    parser.add_argument(
        "--stream",
        dest="stream",
        action="store_true",
        default=True,
        help="Stream model text, reasoning, and tool-call arguments to stderr "
        "in real time as they arrive (default: enabled).",
    )
    parser.add_argument(
        "--no-stream",
        dest="stream",
        action="store_false",
        help="Disable live streaming; model output only appears after each turn.",
    )
    parser.add_argument(
        "--memory",
        choices=["file", "engram"],
        default="file",
        help="Memory backend. 'file' appends to progress.md (default). "
        "'engram' uses Engram MCP tools for semantic recall, session "
        "lifecycle, and trace recording. Requires engram_mcp to be installed.",
    )
    parser.add_argument(
        "--engram-repo",
        default=None,
        help="Path to the Engram memory repo (used with --memory=engram). "
        "Defaults to MEMORY_REPO_ROOT env var or auto-detection.",
    )
    args = parser.parse_args()

    workspace = Path(args.workspace).resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    _ensure_workspace_in_gitignore(workspace)
    scope = WorkspaceScope(root=workspace)
    tools = build_tools(scope)

    if args.memory == "engram":
        from harness.engram_memory import EngramMemory

        try:
            from engram_mcp.agent_memory_mcp.server import create_mcp
        except ImportError:
            print(
                "engram_mcp is not installed. Install with: "
                "pip install -e /path/to/engram[search]",
                file=sys.stderr,
            )
            sys.exit(1)

        repo_root_arg = args.engram_repo or os.getenv("MEMORY_REPO_ROOT")
        _mcp, engram_tools, repo_root, engram_repo = create_mcp(
            repo_root=repo_root_arg,
        )
        memory = EngramMemory(
            engram_tools,
            repo_root,
            engram_repo,
            user_id=os.getenv("MEMORY_USER_ID"),
        )

        # Add recall_memory tool so the model can query memory on demand
        from harness.tools.recall import RecallMemory

        recall_tool = RecallMemory(memory)
        tools[recall_tool.name] = recall_tool
        print(
            f"Using Engram memory (repo: {repo_root})",
            file=sys.stderr,
        )
    else:
        memory = FileMemory(path=workspace / "progress.md")

    # Support for Grok/xAI: detect by model name (Responses API + native search tools).
    # Falls back to Anthropic for Claude models. Grok provides strong reasoning capabilities.
    is_grok_model = any(k in args.model.lower() for k in ["grok", "xai", "x.ai"])
    if is_grok_model:
        api_key = os.getenv("GROK_API_KEY") or os.getenv("XAI_API_KEY")
        if not api_key:
            raise ValueError(
                "GROK_API_KEY or XAI_API_KEY must be set in .env for Grok models"
            )
        client = OpenAI(
            api_key=api_key,
            base_url="https://api.x.ai/v1",
        )
        from harness.modes.grok import GrokMode

        mode = GrokMode(client=client, model=args.model, tools=tools)
        print(f"Using Grok mode with model {args.model}", file=sys.stderr)
    else:
        client = anthropic.Anthropic()  # ANTHROPIC_API_KEY from env / .env

        if args.mode == "native":
            from harness.modes.native import NativeMode

            mode = NativeMode(client=client, model=args.model, tools=tools)
        else:
            from harness.modes.text import TextMode

            mode = TextMode(client=client, model=args.model, tools=tools)

    trace_path = (
        Path("traces")
        / f"{datetime.now():%Y%m%d-%H%M%S}-{'grok' if is_grok_model else args.mode}.jsonl"
    )

    if args.trace_live:
        tracer_ctx: CompositeTracer | Tracer = CompositeTracer(
            [Tracer(trace_path), ConsoleTracePrinter()]
        )
    else:
        tracer_ctx = Tracer(trace_path)

    stream_sink = StderrStreamPrinter() if args.stream else NullStreamSink()

    with tracer_ctx as tracer:
        result = run(
            args.task,
            mode,
            tools,
            memory,
            tracer,
            max_turns=args.max_turns,
            max_parallel_tools=args.max_parallel_tools,
            stream_sink=stream_sink,
        )

    # Finalize Engram session: copy trace, build dialogue, commit
    u = result.usage
    if args.memory == "engram" and hasattr(memory, "finalize"):
        memory.finalize(
            trace_path,
            model=args.model,
            total_cost_usd=u.total_cost_usd,
            input_tokens=u.input_tokens,
            output_tokens=u.output_tokens,
            cache_read_tokens=u.cache_read_tokens,
            cache_write_tokens=u.cache_write_tokens,
            reasoning_tokens=u.reasoning_tokens,
        )

    print("\n" + "=" * 60)
    print(result.final_text)
    print("=" * 60)
    print(
        f"tokens: in={u.input_tokens:,} out={u.output_tokens:,} "
        f"cache_read={u.cache_read_tokens:,} cache_write={u.cache_write_tokens:,} "
        f"reasoning={u.reasoning_tokens:,}"
    )
    if u.server_search_calls or u.server_sources:
        print(f"search: calls={u.server_search_calls} sources={u.server_sources}")
    print(
        f"cost:  ${u.total_cost_usd:.4f} total  "
        f"(in ${u.input_cost_usd:.4f} / out ${u.output_cost_usd:.4f} / "
        f"cache ${u.cache_read_cost_usd + u.cache_write_cost_usd:.4f} / "
        f"search ${u.search_cost_usd:.4f})"
    )
    if u.pricing_missing:
        models = ", ".join(u.missing_models) or "(unknown)"
        print(f"[warning] no pricing for model(s): {models}", file=sys.stderr)
    print(f"trace: {trace_path}")
    if args.memory == "engram" and hasattr(memory, "session_id"):
        print(f"engram session: {memory.session_id}")
    else:
        print(f"progress: {workspace / 'progress.md'}")
