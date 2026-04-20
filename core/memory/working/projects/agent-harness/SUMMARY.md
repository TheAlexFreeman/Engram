---
type: project
source: agent-generated
origin_session: memory/activity/2026/04/19/chat-001
trust: medium
created: '2026-04-19'
status: active
cognitive_mode: exploration
current_focus: EngramMemory backend and RecallMemory tool implemented. Session
  IDs use act-NNN prefix. Next steps are testing the integration end-to-end and
  building a trace-to-activity post-run pipeline.
open_questions: 2
last_activity: '2026-04-19'
active_plans: 0
plans: 0
canonical_source: core/memory/working/projects/agent-harness/IN/harness/
---

# Project: Agent Harness

## Description

A standalone Python CLI for running AI coding agents with tool access against
local workspaces. The harness supports multiple model backends (Anthropic Claude
via native tool_use, xAI Grok via OpenAI Responses API), provides a pluggable
tool system (filesystem, bash, git, search, todos), real-time streaming, JSONL
tracing, and token/cost accounting. It ships with a deliberately naive
`FileMemory` backend that appends session logs to a flat markdown file — the
explicit intent is that Engram replaces this with semantic retrieval, governed
persistence, and cross-session recall.

## Layout

| Path | Contents |
|---|---|
| `IN/harness/` | Staged code snapshot: full Python package (cli, loop, modes, tools, tests, traces) |
| `notes/` | Working notes and integration analysis |
| `docs/` | Promoted reference material |
| `plans/` | Implementation plans (YAML) |
| `OUT/` | Emitted artifacts scoped to this project |

See `memory/working/projects/README.md` for the canonical folder lifecycle.

## Canonical source

The harness code in `IN/harness/` is a point-in-time snapshot. The upstream
source is the harness package itself; `IN/` is read-only from the agent's
perspective.

## Architecture snapshot

The harness is structured around four protocol interfaces:

- **`MemoryBackend`** (`memory.py`): `start_session`, `recall`, `record`,
  `end_session` — the integration surface for Engram.
- **`Mode`** (`modes/base.py`): Abstracts model provider differences (message
  format, tool-call extraction, usage parsing). Implementations: `NativeMode`
  (Claude), `GrokMode` (xAI).
- **`Tool`** (`tools/__init__.py`): `name`, `description`, `input_schema`,
  `run(args)` — pluggable tool protocol with error-safe `execute()` dispatch
  and ThreadPoolExecutor-based parallelism.
- **`TraceSink`** (`trace.py`): `event(kind, **data)` + `close()` — JSONL
  tracing with optional stderr console printer.

The main loop (`loop.py`) orchestrates: seed session from memory, run
model turns, dispatch tool calls (parallel or sequential), record errors,
and flush session summary on completion.

## How to continue

**No active plans yet.** The `EngramMemory` backend and `RecallMemory` tool
are implemented. Next steps:

1. End-to-end test of `--memory=engram` with a real Engram repo
2. Decide on trace-to-activity pipeline (Q4 in `questions.md`)
3. Consider recall caching for long sessions (Q5)

**Recent IN/ items:** Full harness package snapshot including CLI, execution
loop, two model modes (Claude native, Grok), 10+ filesystem/git/search tools,
pytest suite, JSONL traces, pricing infrastructure, plus new `engram_memory.py`
and `tools/recall.py`.

**Key changes to Engram core:** `path_policy.py` and `plan_utils.py` session ID
patterns widened from `chat-NNN` to `{chat|act}-NNN`. `namespace_session_id`
preserves the original type prefix when namespacing.

**Last activity:** 2026-04-19 — EngramMemory backend, RecallMemory tool,
act-NNN session ID support, CLI wiring.
