---
source: agent-generated
trust: medium
created: 2026-03-28
origin_session: memory/activity/2026/03/28/cowork-session
tags: [session-management, compaction-flush, sidecar, proxy, openclaw]
---

# Session Management: Integrated Roadmap

Design for adding session lifecycle infrastructure to Engram in three phases, integrating the 5-point compaction flush design with a sidecar observer, optional proxy, and enriched MCP server. Informed by comparative analysis of OpenClaw's memory architecture.

## Background: The core constraint

OpenClaw's compaction flush works because OpenClaw owns the runtime — it controls the conversation loop, knows exact token counts, and can inject synthetic turns. Engram is a memory layer consumed by many platforms via MCP: it sees tool calls but has no visibility into the host's context window state, no ability to inject turns, and no way to intercept compaction before it happens.

This roadmap addresses the question: how do you implement session lifecycle management when you don't control the runtime?

---

## Phase 1: Sidecar observer — bootstrap the feedback loops

### Primary purpose

Solve the chicken-and-egg problem gating Engram's designed-but-dormant features. The curation algorithms, co-retrieval clustering, helpfulness-weighted retrieval reranking, and knowledge amplification protocol all need ACCESS data flowing. ACCESS.jsonl files are currently empty because logging depends on agent self-reporting.

### Capabilities

**Auto-populate ACCESS.jsonl.** Read conversation transcripts (Claude Code transcripts, Cursor chat history, etc.), identify which memory files the agent retrieved during the session, and log ACCESS entries with:
- Timestamps
- Task descriptions extracted from user messages
- Helpfulness scores estimated from whether retrieved content appeared in the agent's response (textual similarity between retrieved content and response content)
- Provenance flag: `"estimator": "sidecar"` (distinct from `"estimator": "agent"`) so curation algorithms can weight differently

**Auto-trigger aggregation.** When ACCESS.jsonl entries accumulate past the threshold (currently 15 in `INIT.md`), call `memory_run_aggregation` via MCP. The curation algorithms get data to work with: SUMMARY files reflect actual usage, co-retrieval clustering Phase 1 produces real cluster candidates.

**Session lifecycle management.** Detect session start/end from transcript activity. Call `memory_record_session` and `memory_record_chat_summary` automatically. Guarantees session lifecycle always fires even if the agent forgets.

**Flush monitoring (passive).** If the sidecar detects a long session where `memory_checkpoint` hasn't been called, log that as a session health signal. Does not intervene — informs the metrics that feed Phase 3.

### Implementation shape

- Python process, using `watchdog` or polling to monitor transcript files
- Connects to Engram MCP server as a client
- Ships as `engram-sidecar` alongside `engram-mcp`
- Config surface: platform transcript format, transcript location on disk, polling interval

### Concurrent MCP-side work (no sidecar dependency)

- **`memory_checkpoint` tool:** Append-only to scratchpad, automatic-tier, no governance. Possibly extend `memory_append_scratchpad` with a `checkpoint: true` mode that adds timestamp and session context.
- **Session skill updates:** Update `session-start.md` and `session-sync.md` to instruct agents to checkpoint after decisions, discoveries, and task completions.

### Design question: helpfulness estimation

The sidecar approximates the agent's self-reported helpfulness heuristically:
- Agent quotes/paraphrases content from a retrieved file → 0.7+
- Agent retrieved a file but response doesn't reference it → 0.2–0.4
- File not retrieved at all → not logged

This is a heuristic. Imperfect ACCESS data at volume is vastly more useful than perfect ACCESS data that doesn't exist.

---

## Phase 2: Optional proxy — add pre-emptive capabilities

### What changes from Phase 1

Moves from observation to intervention. Instead of watching transcripts after the fact, sits in the API call path and can inject context and trigger flushes.

### Capabilities

**Pre-query context injection.** Before each user message hits the model, call `memory_context_home` or `memory_context_project` and prepend the assembled context. Agent doesn't need to "remember" to load memory at session start. This is the context injector feature automated rather than requiring the agent or platform to call it.

**Token-aware compaction flush.** Proxy counts tokens (sees the full request payload) and triggers `memory_session_flush` at a configurable threshold (e.g., 85% capacity). Not a proxy metric heuristic — actual token counting. Proxy knows the model's context window from the API endpoint.

**Transparent checkpointing.** Extract memory-worthy content from model responses and call `memory_checkpoint` without agent action. Upgrades the agent habit (flush point 1) to automated capture. Session skill instructions become belt-and-suspenders redundancy.

### Relationship to Phase 1

The sidecar doesn't go away — it shifts role. Options:
- Sidecar watches the proxy's session log instead of platform-native transcripts (cleaner data)
- Merge: proxy *is* the sidecar, with observation + intervention capabilities
- ACCESS logging, aggregation triggering, and session lifecycle from Phase 1 still run

### Deployment model

- Explicitly opt-in, well-documented
- For Claude Code: custom API base URL
- For Cursor: custom API base URL
- For ChatGPT: not possible (can't proxy hosted chat)
- If proxy not running, everything from Phase 1 still works — just lose pre-emptive capabilities
- Needs `HUMANS/docs/PROXY.md` with per-platform setup, gain/loss explanation, latency accounting

### Latency consideration

One extra local HTTP hop per request, plus context injection time. Context injection involves MCP tool calls that do file reads — should be sub-100ms on local disk. Total overhead target: <200ms per request.

---

## Phase 3: Enriched MCP server — absorb the best of both

### Long-term play

As MCP protocol gains richer session semantics (server-initiated messages, session lifecycle events, context budget negotiation), capabilities that required sidecar/proxy migrate into the MCP server.

### Capabilities

**Session state accumulation.** Extend `memory_session_health_check` to maintain a full session model: files read, files written, checkpoint history, estimated working context, time since last flush. Every tool call updates this model.

**Advisory responses.** Every tool response includes `_session` metadata block:
```json
{
  "_session": {
    "flush_recommended": true,
    "unread_relevant_files": ["memory/knowledge/..."],
    "checkpoint_stale": true,
    "tool_calls_since_checkpoint": 23,
    "session_duration_minutes": 45
  }
}
```
Session skills instruct the agent to check and act on these signals. Pull-based version of what server-initiated messages would enable as push.

**Composite context tools.** `memory_context_query` takes a natural language question and returns assembled context (relevant knowledge, applicable skills, related session history) without the agent orchestrating multiple tool calls. Proxy's context injection capability, but agent-initiated.

**ACCESS logging from tool calls.** MCP server already sees every `memory_read_file` and `memory_search` call. Log ACCESS entries automatically for read operations. Agent only self-reports helpfulness after the fact (or sidecar estimates it). Partially solves ACCESS bootstrapping even without sidecar.

### Relationship to Phases 1-2

The enriched MCP server reduces the surface area sidecar/proxy need to cover:
- Sidecar shifts from "primary ACCESS logger" to "helpfulness estimator and session boundary detector"
- Proxy shifts from "context injector and flush trigger" to "transparent enhancement layer for supporting platforms"
- Each component does less, integrated system does more

---

## How the 5-point compaction flush lands across phases

| Flush point | Phase 1 (sidecar) | Phase 2 (proxy) | Phase 3 (enriched MCP) |
|---|---|---|---|
| 1. `memory_checkpoint` | MCP tool, agent-initiated | Proxy auto-extracts from responses | MCP detects uncheckpointed state, advises |
| 2. Session skill instructions | Implemented in session skills | Still active as redundancy | Augmented by advisory signals |
| 3. Activity monitor / advisory | Sidecar detects long sessions, logs signal | Proxy does real token counting, triggers flush | MCP tracks rich session state, embeds advisories |
| 4. `memory_session_flush` | MCP tool; sidecar calls at session end | Proxy calls before compaction threshold | MCP calls when session lifecycle events fire |
| 5. Platform hooks | Claude Code hooks trigger flush | Proxy replaces need for per-platform hooks | MCP session lifecycle events (when protocol supports) |

---

## Suggested initial work (parallelizable)

1. **`memory_checkpoint` tool** — small, self-contained, immediately useful regardless of everything else. Extend `memory_append_scratchpad` with checkpoint mode.

2. **Sidecar Claude Code transcript parser** — since worktree-mode testing against a real codebase is the next hands-on milestone, building the sidecar to watch Claude Code transcripts gives immediate ACCESS data from real usage. Start with one platform, get ACCESS pipeline running end-to-end, then generalize.

3. **MCP server session state** — extend `memory_session_health_check` to maintain a session model across tool calls. Lets the server embed advisory signals in responses and provides instrumentation to measure whether flush mechanisms work.

---

## Directions considered but not pursued (for now)

### Direction C: Full orchestration layer

Engram becomes a complete agent runtime — bring your own model API key, gateway handles everything: message routing, context assembly, tool dispatch, memory management, session lifecycle, multi-platform I/O. Essentially building OpenClaw's architecture with Engram's memory at the core.

**Upside:** Total control; every feature works perfectly.
**Downside:** Competing with Claude Code, Cursor, ChatGPT on the runtime layer. Losing the "plugs into anything" advantage. Implementation surface explodes.
**Verdict:** Possible future direction, but a different product. Revisit if the proxy phase proves the value and the MCP protocol proves too limiting.

### Direction A variant: Thin session proxy (standalone)

A proxy that doesn't build on the sidecar — just intercepts API calls. Rejected in favor of the phased approach because the sidecar solves the ACCESS bootstrapping problem that's more urgent than the compaction problem, and the proxy naturally extends the sidecar rather than being a separate component.

---

## OpenClaw insights that informed this design

- **Compaction flush is OpenClaw's best trick** — but depends on runtime control Engram doesn't have; phased approach works around this
- **Hybrid search (vector + BM25) is validated** — Engram's implementation exists; needs ACCESS data to tune weights dynamically
- **Relationship reasoning is OpenClaw's biggest gap** — Engram's graph tools address this; sidecar ACCESS data enables auto-suggested cross-references
- **Daily log auto-loading provides temporal continuity** — context injectors should incorporate recent session signals
- **Security disasters came from untrusted plugins** — extend quarantine model to skills, not just knowledge
- **Radical simplicity won adoption** — guided_write as default tool profile, full surface opt-in
- **Graceful embedding fallback** — pure-Python cosine fallback ensures semantic search degrades rather than disappears
