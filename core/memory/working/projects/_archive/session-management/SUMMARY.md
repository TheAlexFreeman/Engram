---

## type: project-summary
created: 2026-03-28
project_count: 1
active_plans: 1
plans: 5

# Session Management

**Status:** Phase 2 complete (checkpoint-tool, sidecar-observer, and optional-proxy all complete; enriched-server remains in draft)

## Purpose

Add session lifecycle infrastructure to Engram: automatic ACCESS logging, context compaction defense, and richer session state tracking. Informed by comparative analysis of OpenClaw's memory architecture — adopting its strengths (compaction flush, hybrid retrieval validation, temporal context) while avoiding its weaknesses (no governance, no trust model, no relationship reasoning).

## Three-phase roadmap


| Phase | Component               | What it adds                                                                         |
| ----- | ----------------------- | ------------------------------------------------------------------------------------ |
| 1     | **Sidecar observer**    | Automatic ACCESS logging, session lifecycle management, aggregation triggering       |
| 2     | **Optional proxy**      | Pre-query context injection, token-aware compaction flush, transparent checkpointing |
| 3     | **Enriched MCP server** | Server-side session state, advisory responses, composite context tools               |


Each phase builds on the previous rather than replacing it. See [notes/integrated-roadmap.md](../../notes/integrated-roadmap.md) for the full design.

## Relationship to other projects

- **context-injectors** — Phase 2 proxy automates context injection; Phase 3 enriches the composite tools that context-injectors creates
- **compaction flush** — The 5-point flush design ([notes/compaction-flush-design.md](../../notes/compaction-flush-design.md)) is subsumed by this roadmap; each flush point lands across the three phases

## Key design decisions (so far)

- **Sidecar before proxy** — bootstrap ACCESS feedback loops with zero architectural disruption before adding intervention capabilities
- **Proxy is opt-in** — documented per-platform setup, graceful degradation to sidecar-only mode
- **MCP enrichment is incremental** — extend existing `memory_session_health_check`, don't introduce new server architecture
- **Sidecar helpfulness estimates carry provenance** — `"estimator": "sidecar"` vs `"estimator": "agent"` so curation algorithms can weight differently

## Open questions

- Transcript format parsers: Claude Code first, then which platforms?
- Sidecar deployment: separate process (`engram-sidecar`) or mode of the MCP server?
- Proxy latency budget: what overhead is acceptable per request?
- MCP protocol evolution: when/if server-initiated messages arrive, how does Phase 3 change?

## Plans


| Plan                                                                      | Status   | Phases | Focus                                                                                                                |
| ------------------------------------------------------------------------- | -------- | ------ | -------------------------------------------------------------------------------------------------------------------- |
| [checkpoint-tool](plans/checkpoint-tool.yaml)                             | complete | 3      | `memory_checkpoint` tool, session skill updates, docs                                                                |
| [sidecar-observer](plans/sidecar-observer.yaml)                           | complete | 7      | Transcript parser framework, Claude Code parser, helpfulness estimator, ACCESS logger, session lifecycle, CLI, docs  |
| [optional-proxy](plans/optional-proxy.yaml)                               | complete | 6      | API proxy core, context injection, compaction flush, auto-checkpointing, CLI, docs                                   |
| [enriched-mcp-server](plans/enriched-mcp-server.yaml)                     | active   | 6      | Session state (done), `_session` advisories (in progress), auto-ACCESS, deferred `memory_context_query`, health/docs |
| [sidecar-comprehensive-capture](plans/sidecar-comprehensive-capture.yaml) | active   | 7      | All-tool trace spans, compressed dialogue logs, session metrics, query surface for review agents                     |


**Parallelism:** Enriched MCP server is in flight: session state landed; advisory envelope and health/docs work remain; auto-ACCESS and `memory_context_query` are still open (context query deferred per MCP.md). Sidecar comprehensive capture is independent of the enriched server and can proceed in parallel.

## Deferred

Full orchestration layer (Engram as agent runtime) — acknowledged as possible future direction, but a different product. See [notes/integrated-roadmap.md](../../notes/integrated-roadmap.md) § "Direction C."