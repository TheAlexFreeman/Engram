---
type: note
source: agent-generated
created: '2026-04-19'
trust: medium
---

# Engram Integration Analysis — Agent Harness

## The gap

The harness defines a `MemoryBackend` protocol with four methods. The current
`FileMemory` implementation is intentionally naive — it appends to a flat
markdown file and `recall()` always returns an empty list. The docstring on
`MemoryBackend` is explicit: *"FileMemory honors it naively; Engram will honor
it properly."*

This note maps each protocol method to the Engram MCP tools that should back it.

## Protocol method → Engram MCP mapping

### `start_session(task: str) -> str`

**Purpose:** Return prior context to seed the agent's first turn.

**Engram tools:**

1. `memory_session_bootstrap` — returns active plans, pending reviews, and
   resume context. This is the canonical cold-start entry point.
2. `memory_semantic_search(query=task)` — retrieve past sessions and knowledge
   relevant to the current task. Use the task description as the query.
3. `memory_context_project` or `memory_context_project_lite` — if the task
   names a known project, pull the enriched project bundle.

**Return value:** Concatenate the bootstrap bundle + top-k semantic search
results into a single context string. The harness injects this as `prior` into
the mode's `initial_messages()`.

**Design choice:** The harness currently passes `prior` as a user-message
prefix. For richer context, `EngramMemory` could return structured sections
(e.g. `## Active plans\n...` / `## Related sessions\n...`) so the model can
parse them distinctly.

### `recall(query: str, k: int = 5) -> list[Memory]`

**Purpose:** Mid-session query-based retrieval.

**Engram tools:**

1. `memory_semantic_search(query=query, limit=k)` — primary path. Hybrid
   ranking (vector + BM25 + freshness + helpfulness) is a direct upgrade over
   FileMemory's empty return.
2. `memory_search(query=query, max_results=k)` — fallback if semantic search
   is unavailable (missing sentence-transformers). Keyword/regex search with
   optional freshness weighting.

**Return value:** Map each search result to a `Memory(content, timestamp, kind)`
dataclass. The `kind` field can be derived from the result's frontmatter `type`
(or default to `"note"`).

**Note:** The harness loop currently never calls `recall()` — it's only used if
the model explicitly asks for memory retrieval via a tool. This is a future
extension point: the harness could auto-recall on each turn to inject relevant
context, or expose `recall` as a tool the model can call.

### `record(content: str, kind: str = "note") -> None`

**Purpose:** Capture observations during the session (currently only tool
errors).

**Engram tools:**

1. `memory_append_scratchpad(target="current", content=...)` — best fit for
   high-frequency, ungoverned in-flight notes. These are ephemeral working
   memory, not promoted knowledge.
2. `memory_record_trace(span_type="tool_call", name=kind, status="error"|"ok", ...)`
   — for structured error/event recording that feeds the trace pipeline.

**Design choice:** Use scratchpad for human-readable notes and trace spans for
machine-consumable events. The `kind` parameter maps naturally to `span_type`:
`"error"` → tool_call/error, `"decision"` → plan_action/ok, `"note"` →
scratchpad only.

### `end_session(summary: str) -> None`

**Purpose:** Wrap up and persist.

**Engram tools:**

1. `memory_record_session(session_id=..., summary=summary)` — the canonical
   session-end tool. Atomically writes session summary, optional reflection,
   chat index update, and ACCESS entries in a single commit.
2. `memory_record_reflection(...)` — optionally attach a structured reflection
   (memory retrieved, influence, outcome quality, gaps noticed). This could be
   auto-generated from the session's trace data.

**Design choice:** `EngramMemory` needs to generate or receive a `session_id`
at start time (from `memory_session_bootstrap` or a deterministic ID like
`memory/activity/YYYY/MM/DD/harness-NNN`). This ID threads through all
mid-session `record_trace` calls and the final `record_session`.

## Implementation sketch

```python
class EngramMemory:
    """MemoryBackend backed by Engram MCP tools."""

    def __init__(self, mcp_client):
        self.mcp = mcp_client
        self.session_id: str | None = None

    def start_session(self, task: str) -> str:
        # 1. Bootstrap
        bootstrap = self.mcp.call("memory_session_bootstrap")

        # 2. Semantic search for task-relevant context
        results = self.mcp.call("memory_semantic_search",
                                query=task, limit=5)

        # 3. Generate session ID
        self.session_id = self._generate_session_id()

        # 4. Build context string
        return self._format_prior(bootstrap, results)

    def recall(self, query: str, k: int = 5) -> list[Memory]:
        results = self.mcp.call("memory_semantic_search",
                                query=query, limit=k)
        return [self._to_memory(r) for r in results]

    def record(self, content: str, kind: str = "note") -> None:
        if kind == "error":
            self.mcp.call("memory_record_trace",
                          session_id=self.session_id,
                          span_type="tool_call",
                          name="harness_error",
                          status="error",
                          metadata={"content": content})
        else:
            self.mcp.call("memory_append_scratchpad",
                          target="current",
                          content=f"[{kind}] {content}")

    def end_session(self, summary: str) -> None:
        self.mcp.call("memory_record_session",
                      session_id=self.session_id,
                      summary=summary,
                      key_topics="agent-harness")
```

## Open integration questions

1. **MCP transport:** The harness runs as a standalone CLI process. Engram's MCP
   tools are normally served over stdio to an LLM host. `EngramMemory` needs
   either: (a) an in-process Python import of the MCP server's tool functions,
   (b) an MCP client that connects over stdio/SSE, or (c) a thin HTTP wrapper.
   Option (a) is simplest since both are Python — import `agent-memory-mcp` and
   call the tool functions directly.

2. **Session ID generation:** The harness doesn't currently produce Engram-style
   session IDs (`memory/activity/YYYY/MM/DD/chat-NNN`). `EngramMemory` should
   either query the next available ID or use a harness-specific prefix like
   `memory/activity/YYYY/MM/DD/harness-NNN`.

3. **Recall as a tool:** Currently `recall()` is only called programmatically.
   A more powerful pattern would be to expose it as a harness `Tool` so the
   model can query memory on demand — essentially giving the agent a
   `search_memory` tool alongside `read_file`, `bash`, etc.
