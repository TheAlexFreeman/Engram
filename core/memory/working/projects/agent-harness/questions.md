---
type: questions
source: agent-generated
created: '2026-04-19'
---

# Open Questions — Agent Harness

- ~~**Q1 (integration-surface):** Should `EngramMemory.recall()` use `memory_search` or `memory_semantic_search`?~~ **Resolved 2026-04-19:** Both, with semantic as primary and keyword as fallback. Also exposed as a model-callable `recall_memory` tool.

- ~~**Q2 (session-lifecycle):** How should `EngramMemory` map to Engram session tools?~~ **Resolved 2026-04-19:** `start_session` → `memory_session_bootstrap` + `memory_semantic_search`; `end_session` → `memory_record_session`. Session IDs use `act-NNN` prefix.

- ~~**Q3 (governed-writes):** Should `record()` use scratchpad or governed writes?~~ **Resolved 2026-04-19:** Errors go to `memory_record_trace` (structured spans); notes go to `memory_append_scratchpad` (ungoverned). Only `end_session` produces governed artifacts via `memory_record_session`.

- **Q4 (trace-to-activity):** Harness JSONL traces contain rich tool-call data (timing, args, results, costs). Should we build a post-run pipeline that converts trace files into Engram activity entries, or is the `memory_record_trace` per-error approach sufficient?

- **Q5 (recall-caching):** `recall_memory` hits Engram on every invocation. For long multi-turn sessions, should we cache recent recall results to avoid redundant embedding lookups?
