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

## `memory_context_worktree` — Host-codebase sidecar context

**Purpose:** Optimized for worktree-mode sessions where the agent's primary task is working in a host codebase and Engram provides supporting context. Inverts the relationship of the other injectors: instead of centering the memory system, it asks "what does this memory know about the code I'm about to touch?"

**Parameters:**
- `max_chars: int = 16000` — soft character budget
- `knowledge_domain: str | None = None` — specific knowledge domain to load (e.g., `codebase`, `software-engineering`); if None, auto-detect from codebase-survey project or fall back to general software knowledge
- `include_host_activity: bool = True` — scan recent host-repo git log for active files/modules to prioritize knowledge retrieval
- `include_coding_profile: bool = True` — compact user profile filtered to coding preferences, stack, and style (not full intellectual portrait)
- `include_active_plan: bool = True` — load active plan scoped to host-repo work
- `observation_hints: bool = True` — return a lightweight observation schema suggesting what the agent should report back about the codebase

**Return format:** Markdown with JSON metadata header.

**Content assembled (priority order):**
- P0: Coding-relevant user profile (stack, style preferences, tool chain — extracted from users/SUMMARY.md, filtered for relevance)
- P1: Codebase knowledge files from `knowledge/{domain}/` — prioritized by ACCESS helpfulness scores if available, otherwise by recency
- P2: Active plan state (if a project plan references the host repo or codebase domain)
- P3: Relevant skills (codebase-survey, any code-review or PR skills that have developed)
- P4: Observation hints — structured prompts telling the agent what kinds of discoveries to report back: architectural patterns, undocumented conventions, dependency relationships, pain points, test coverage gaps

**Bidirectional design:**
The observation hints (P4) make this injector the entry point for the codebase knowledge feedback loop:
1. `memory_context_worktree` provides context + observation hints at session start
2. Agent works in host codebase, notices patterns the hints prompted it to look for
3. Session wrapup stages observations via `memory_stage_external` into the codebase knowledge domain
4. Next session's `memory_context_worktree` serves the enriched knowledge back
5. Over time, recurring observations graduate to skills ("how to run tests for module X"), and eventually the most stable skills could be exported to the host repo's own agent instructions (CLAUDE.md, AGENTS.md)

This is the form/content graduation pipeline applied to codebase knowledge: raw observations (content) → codebase knowledge files (structured content) → codebase-specific skills (procedures) → host-repo agent instructions (form).

**Prerequisites:**
- Real worktree usage data — need a few sessions of manual flow to learn what context agents actually reach for
- Codebase survey project should have produced initial knowledge files to serve
- `HOST_REPO_ROOT` env var must be set for host-repo git operations
- Coding-profile extraction helper (filter users/SUMMARY.md to stack/style subset)

**Consumer:** Agents working in worktree mode — Claude Code, Codex, Cursor with MCP connected to the memory worktree. This is the "memory as sidecar to real work" pattern.

**Key tradeoff:** Most specialized injector. Only useful in worktree deployments. But it's the tool that makes Engram valuable for day-to-day coding work, not just self-building. The observation hints are speculative — need to validate that agents actually produce useful structured observations when prompted.

**Design connection — form/content graduation:**
A worktree-deployed Engram used against the same codebase for weeks will develop codebase-specific skills. These skills are the same content that agent instruction files (CLAUDE.md, AGENTS.md) capture today, but emerging from observed usage patterns rather than being hand-authored. The graduation pipeline: raw session observations → codebase knowledge files → codebase-specific skills → host-repo agent instructions → potentially MCP tools for the most stable operations. This is the speciation story: each Engram instance adapts to its host codebase.

---

## Implementation sequencing

1. **Now:** `memory_context_home` + `memory_context_project` (predictable, no search dependency)
2. **After initial worktree usage data:** `memory_context_worktree` (needs real codebase knowledge files + usage patterns to validate design)
3. **After Calibration or ≥50 ACCESS entries:** `memory_context_query` (search-dependent)
4. **After compaction protocol is battle-tested:** `memory_context_resume` (needs real usage data)
