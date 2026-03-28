---
created: 2026-03-28
source: agent-generated
trust: medium
origin_session: memory/activity/2026/03/28/chat-001
title: "Context Injector Roadmap: Deferred Tools"
---

# Context Injector Roadmap

This note captures the design for two deferred context injector tools that complete the family started by `memory_context_home` and `memory_context_project`. These are not planned for immediate implementation but should be built once their prerequisites are stable.

## `memory_context_query` — Task-optimized retrieval

**Purpose:** Takes a natural-language task description and a token budget, then uses hybrid search (vector + BM25 + freshness + helpfulness) to assemble the most relevant memory payload. Instead of loading a fixed manifest, it answers: "given what this agent is about to do, what memory content would help most?"

**Parameters:**
- `query: str` — required, natural-language task description
- `max_chars: int = 12000` — soft character budget
- `include_user_profile: bool = True` — prepend compact user portrait
- `include_working_state: bool = True` — include CURRENT.md and active plan summary
- `search_scope: str = "all"` — one of `all`, `knowledge`, `skills`, `activity`, `projects`
- `min_relevance: float = 0.3` — minimum hybrid score threshold

**Return format:** Markdown with JSON metadata header (loaded_files, trust levels, relevance scores, budget report).

**Prerequisites:**
- `memory_semantic_search` must be stable and well-calibrated (requires `search` optional dependency)
- ACCESS helpfulness data needs enough volume to meaningfully weight results
- Recommend waiting until Calibration stage or ≥50 ACCESS entries with helpfulness scores

**Consumer:** Any agent mid-session needing targeted recall. Also useful for harness integrations where the orchestrator requests relevant context per step.

**Key tradeoff:** Most powerful but least predictable injector. Response content varies per query. Quality depends on search ranking calibration. Degrades gracefully to BM25-only when sentence-transformers is unavailable.

---

## `memory_context_resume` — Session continuation after compaction

**Purpose:** Designed for the context-window compaction boundary. When an agent hits 75–95% context and compacts, this tool captures and restores the critical working state that compaction might lose. Addresses the known problem that "compaction doesn't always pass perfectly clear instructions to the next agent."

**Parameters:**
- `include_session_history: bool = True` — include recent session reflections
- `checkpoint_id: str | None = None` — resume from a specific RunState checkpoint
- `max_chars: int = 12000` — soft character budget

**Return format:** Markdown with JSON metadata header.

**Content assembled:**
- Active scratchpad state (CURRENT.md)
- Active plan's current phase (via RunState if available, plan YAML otherwise)
- Uncommitted working notes
- Most recent activity summary
- Any in-progress approval requests

**Prerequisites:**
- Pre-compaction flush protocol needs production usage data
- RunState checkpoint system (from harness Phase 10) should be exercised across multiple real sessions
- `memory_plan_resume` covers the plan-specific subset; this tool is broader

**Consumer:** Long-running agents that survive compaction events. Particularly relevant for Alex's marathon sessions with multiple compactions.

**Key tradeoff:** Narrow use case but addresses a real pain point. The existing `memory_plan_resume` handles the plan axis; this adds scratchpad, working notes, and session continuity.

---

## Implementation sequencing

1. **Now:** `memory_context_home` + `memory_context_project` (predictable, no search dependency)
2. **After Calibration or ≥50 ACCESS entries:** `memory_context_query` (search-dependent)
3. **After compaction protocol is battle-tested:** `memory_context_resume` (needs real usage data)
