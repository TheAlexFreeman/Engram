---
source: agent-generated
trust: medium
created: 2026-03-26
origin_session: memory/activity/2026/03/26/chat-002
title: "Phase 3 Design: Observability"
---

# Phase 3 Design: Observability

## Motivation

The harness report identifies observability as "the biggest operational gap": "You cannot manage what you cannot see. End-to-end traces across model calls, tool calls, retrieval, and guardrails." Engram currently has:

- `ACCESS.jsonl` files per namespace (activity, knowledge, skills, users) designed for retrieval tracking — but currently empty.
- Git history capturing every write with commit messages.
- Session summaries as narrative records.
- `operations.jsonl` per project capturing plan actions.

What's missing: structured traces with timing, cost, outcome metrics, and a human-readable view. This phase adds a trace recording and query surface without requiring Engram to become a full APM system.

---

## Extension 1: Trace schema — `TRACES.jsonl`

### Problem

There's no structured record of what happened during a session at the operation level — which tools were called, how long they took, whether they succeeded, and what they cost.

### Design

Per-session trace file stored alongside session summaries:

```
core/memory/activity/YYYY/MM/DD/
├── chat-NNN.md          # Session summary (existing)
└── chat-NNN.traces.jsonl # Trace spans (new)
```

Each line is a JSON span object:

```json
{
  "span_id": "abc123",
  "parent_span_id": null,
  "session_id": "memory/activity/2026/04/01/chat-001",
  "timestamp": "2026-04-01T14:30:00.123Z",
  "span_type": "tool_call",
  "name": "memory_plan_execute",
  "duration_ms": 250,
  "status": "ok",
  "metadata": {
    "plan_id": "verification-phase-2",
    "action": "inspect",
    "phase_id": "verify-tool-design"
  },
  "cost": {
    "tokens_in": null,
    "tokens_out": null
  }
}
```

### Span types

| Span type | When emitted | `name` contains | `metadata` contains |
|---|---|---|---|
| `tool_call` | Every MCP tool invocation | Tool name | Tool-specific parameters (sanitized) |
| `plan_action` | Plan execute/verify/create | Action name | plan_id, phase_id, action, outcome |
| `retrieval` | Memory reads via search/read tools | File path or query | helpfulness score, category |
| `verification` | Postcondition checks (Phase 2) | Phase being verified | pass/fail counts, failed postconditions |
| `guardrail_check` | Path policy, content boundary checks | Check name | allowed/denied, reason |

### Schema fields

| Field | Type | Required | Description |
|---|---|---|---|
| `span_id` | string | yes | Unique identifier (UUID4 hex, 12 chars) |
| `parent_span_id` | string | no | Parent span for nested operations |
| `session_id` | string | yes | Session path (e.g., `memory/activity/2026/04/01/chat-001`) |
| `timestamp` | string | yes | ISO 8601 with milliseconds |
| `span_type` | string | yes | One of: `tool_call`, `plan_action`, `retrieval`, `verification`, `guardrail_check` |
| `name` | string | yes | Human-readable operation name |
| `duration_ms` | int | no | Wall-clock duration in milliseconds |
| `status` | string | yes | `ok`, `error`, `denied` |
| `metadata` | object | no | Type-specific context (sanitized, no secrets) |
| `cost` | object | no | Token counts if available |

### Behavioral contract

- Trace files are append-only within a session.
- Trace recording is **non-blocking**: failures to write traces never cause tool errors.
- Traces are not access-tracked (they are observability data, not memory).
- Trace files follow the same git commit pattern as other writes.

---

## Extension 2: `memory_record_trace` — Trace recording tool

### Problem

Agents and the MCP server need a way to emit trace spans.

### Design

New MCP tool: `memory_record_trace`

```
Parameters:
  session_id: str        — current session path
  span_type: str         — one of the defined span types
  name: str              — operation name
  status: str            — ok | error | denied
  duration_ms: int | null
  metadata: dict | null  — type-specific context
  cost: dict | null      — {tokens_in, tokens_out}
  parent_span_id: str | null

Returns: MemoryWriteResult with new_state containing:
  span_id: str           — generated span ID
  trace_file: str        — path to the traces file
```

### Internal recording

In addition to the MCP tool (for agent-initiated traces), the server should instrument key operations internally:

- `plan_tools.py`: emit `plan_action` spans for execute/create/verify/review
- `read_tools.py`: emit `retrieval` spans for memory reads and searches
- `write_tools.py`: emit `tool_call` spans for writes

This is wired via a lightweight `record_trace()` helper function that tools call, not a middleware. The helper is best-effort: exceptions are caught and logged, never propagated.

---

## Extension 3: ACCESS.jsonl extension

### Problem

`ACCESS.jsonl` was designed for retrieval tracking but is currently empty and its schema is underspecified. Tool-call events should be recorded alongside retrieval events.

### Design

Extend the ACCESS.jsonl line format to support both retrieval and tool-call events:

```json
{"timestamp": "2026-04-01T14:30:00Z", "event_type": "retrieval", "session_id": "...", "path": "knowledge/ai/llm-agents.md", "helpfulness": 0.8}
{"timestamp": "2026-04-01T14:30:05Z", "event_type": "tool_call", "session_id": "...", "tool": "memory_plan_execute", "action": "inspect", "status": "ok", "duration_ms": 120}
```

New `event_type` field distinguishes retrieval events from tool-call events. Existing curation algorithms that read ACCESS.jsonl should filter by `event_type: "retrieval"` to preserve current behavior.

### Backward compatibility

- Empty ACCESS.jsonl files continue to work.
- Readers that don't understand `event_type` will see both event types but can safely ignore unknown fields (JSON is extensible).

---

## Extension 4: `memory_query_traces` — Trace query tool

### Problem

Recorded traces need to be queryable for debugging, evaluation, and reporting.

### Design

New MCP tool: `memory_query_traces`

```
Parameters:
  session_id: str | null   — filter by session (exact match)
  date_from: str | null    — YYYY-MM-DD start date (inclusive)
  date_to: str | null      — YYYY-MM-DD end date (inclusive)
  span_type: str | null    — filter by span type
  plan_id: str | null      — filter by plan_id in metadata
  status: str | null       — filter by status (ok|error|denied)
  limit: int = 100         — max spans to return

Returns: dict containing:
  spans: list[dict]        — matching trace spans (newest first)
  total_matched: int       — total matching spans before limit
  aggregates:
    total_duration_ms: int
    by_type: dict[str, int]    — count per span_type
    by_status: dict[str, int]  — count per status
    error_rate: float          — errors / total
```

### Implementation

The tool reads TRACES.jsonl files from the date range, parses and filters, and returns aggregated results. For large date ranges, this scans multiple files — acceptable for an advisory tool, not a production analytics backend.

---

## Extension 5: Session summary enrichment

### Problem

Session summaries are narrative text. Adding trace-derived metrics makes them machine-inspectable and supports evaluation.

### Design

When a session summary is written (via `memory_record_session` or `memory_record_chat_summary`), include a metrics section derived from the session's trace file:

```yaml
---
# existing frontmatter
metrics:
  tool_calls: 15
  plan_actions: 4
  retrievals: 8
  errors: 1
  total_duration_ms: 45000
  verification_passes: 3
  verification_failures: 1
---
```

The metrics are computed by reading the session's TRACES.jsonl file at summary time. If no trace file exists, the metrics section is omitted.

---

## Extension 6: Trace viewer UI

### Problem

Traces need a human-readable view for debugging and evaluation.

### Design

New file: `HUMANS/views/traces.html`

Features:
- Session selector (date picker + session list)
- Timeline/waterfall view of spans within a session
- Color-coded by span_type
- Click-to-expand for metadata details
- Filter by span_type, status
- Summary statistics (total calls, duration, error rate)
- Link to plan phases when plan_id is in metadata

Implementation:
- Follows existing `HUMANS/views/` patterns (engram-shared.css, engram-utils.js)
- Reads trace data via fetch from file system or MCP tool
- Pure client-side rendering (no server required)

---

---

## Finalized design decisions

_Recorded during trace-schema-design phase (2026-03-26). These resolve the open questions from the plan purpose._

### Decision 1: Always-on trace recording (not opt-in)

**Question:** Should trace recording be opt-in per session or always-on?

**Decision: Always-on.**

Rationale:
- Traces are lightweight JSONL appends — the I/O cost is negligible compared to git commits that happen anyway.
- Opt-in requires tracking a "tracing enabled" flag in session state, which adds complexity with no clear benefit. The user would need to remember to enable tracing to get observability.
- The whole value of observability is completeness — a gap in traces (because tracing wasn't enabled for that session) is exactly the situation you want to avoid.
- Non-blocking contract (exceptions caught and swallowed) means always-on carries no reliability risk.

**Implementation:** `record_trace()` helper called unconditionally. If the session ID is unavailable (e.g., automation mode), trace is silently skipped.

---

### Decision 2: Metadata sanitization rules

**Question:** How much metadata should be included in spans (balance detail vs size)?

**Decision: Include structured identifiers and counts; exclude content and long strings.**

Rules:
- **Include:** tool names, plan IDs, phase IDs, action names, file paths (repo-relative), status values, integer counts (pass/fail/skip), boolean flags.
- **Exclude:** file contents, raw query strings, user-entered free text beyond 200 characters, anything matching a credential pattern (strings containing `key`, `token`, `secret`, `password`, `auth` as substrings in field names are sanitized to `[redacted]`).
- **Truncation:** Any string value exceeding 200 characters is truncated to 200 characters with a `[truncated]` suffix.
- **Depth limit:** Metadata objects are at most 2 levels deep. Nested objects beyond depth 2 are serialized as their string representation.
- **Size limit:** Total metadata object, JSON-serialized, must not exceed 2 KB. If exceeded, the tool emits a reduced metadata dict containing only top-level scalar fields.

---

### Decision 3: Retention policy — traces follow session summaries

**Question:** What retention policy should apply to trace files?

**Decision: Trace files follow the session summary lifecycle exactly.**

Rules:
- A trace file (`chat-NNN.traces.jsonl`) is created in the same directory as its session summary (`chat-NNN.md`).
- Trace files are retained for as long as their session summary exists.
- During periodic review archival (when session summaries are moved to compressed monthly/yearly archives), trace files move with them.
- Trace files are never automatically deleted; removal follows the same manual process as session summary archives.
- The rationale: traces are observability data for the session. If you care enough to keep the summary, the traces are similarly valuable. If you archive or delete old summaries, the traces become orphaned and can be pruned too.

**Implementation:** No separate retention logic required — traces live alongside summaries and get archived by the same file operations.

---

### Decision 4: Trace viewer reads files directly (not via MCP tools)

**Question:** Should the trace viewer read files directly or go through MCP tools?

**Decision: Read files directly via `fetch()`**, consistent with existing views.

Rationale:
- All existing `HUMANS/views/` pages (dashboard, knowledge, projects, etc.) read files directly via `fetch()` from the filesystem. This pattern allows the views to work without the MCP server running — a key user-friendliness property of the views.
- The MCP server may not be running when a user opens the trace viewer in a browser. Direct file reads work at `file://` (with appropriate CORS relaxation) and via a simple local HTTP server.
- Following established patterns reduces implementation complexity and maintains consistency.

**Implementation:** `traces.html` reads TRACES.jsonl files directly via `fetch()`, using the same path conventions as other views. The file list is discovered by fetching the session summary directory.

---

### Schema finalization — Span ID format

**Decided:** 12-character lowercase hex string, derived from the first 12 hex characters of a UUID4 (hyphens stripped). Example: `"a3f2c1d8e94b"`. This matches the example in the schema above.

Rationale: 12 hex chars = 48 bits of entropy, sufficient for collision-free span IDs within a session. UUID4 provides randomness without requiring a counter. Shorter than a full UUID4 string (32 chars) while still being human-scannable.

---

## What this phase does NOT include

- **Distributed tracing.** No trace context propagation across services. Traces are local to the MCP server.
- **Real-time streaming.** Traces are written to files, not streamed. The viewer reads completed trace files.
- **Cost estimation.** Token counts are recorded when available (from agent-provided data) but not estimated.
- **Alerting.** No automated alerts on error rates or performance degradation. The viewer is passive.
- **Metric aggregation across sessions.** `memory_query_traces` supports date ranges but doesn't maintain pre-computed aggregates. This is acceptable for the expected query volume.
