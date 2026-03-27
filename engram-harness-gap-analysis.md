# Engram → Agent Harness: Gap Analysis & Next Steps

**Date:** 2026-03-27
**Context:** Review of Engram's current architecture against the "Best Practices for LLM Agent Harnesses" deep research report, with concrete recommendations for closing the gaps.

---

## Where Engram stands today

Engram is a sophisticated **memory governance and curation system** — it does the "memory" part of an agent harness exceptionally well. Tiered memory (users/knowledge/skills/activity/working), trust-weighted retrieval, semantic search with hybrid scoring, ACCESS-based curation, temporal decay, anomaly detection, and a governance layer with maturity stages — this is all well beyond what most agent frameworks offer for long-term memory.

But the research report defines six pillars of a production agent harness. Here's an honest assessment of where each one stands:

| Pillar | Engram status | Key gap |
|--------|--------------|---------|
| **Memory & state management** | Strong (the core strength) | Run state and recall memory are conflated — no dedicated run-state schema |
| **Tool interface & execution** | Partial — tool registry stores metadata | No runtime enforcement; tools are documented, not gated |
| **Orchestration** | Partial — plan state machine exists | No autonomous step executor; plans are passive state, not workflows |
| **Reliability (verification loops)** | Partial — postcondition validators defined in schema | Validators aren't executed; no self-consistency or reflection loops |
| **Eval & observability** | Partial — TRACES.jsonl + eval schema exist | No trace query tool; eval scenarios can't be run; no dashboards |
| **Safety & guardrails** | Partial — path policy + governance docs | No runtime input/output validation; guardrails are prose, not code |

The recurring theme: **Engram has excellent schemas and designs for harness features, but the execution layer is incomplete.** The plan system stores phases and tracks status, but doesn't execute them. The eval framework defines scenarios and metrics, but can't run them. The tool registry records policies, but doesn't enforce them. Traces are written, but can't be queried.

---

## What the research report says Engram should prioritize

The report's #1 recommendation is: *"start with the smallest architecture that can work."* Engram should resist the urge to build a full multi-agent orchestrator and instead focus on **completing the execution layer for what's already designed**. The schemas are good. The missing piece is making them operational.

The report's most relevant finding for Engram specifically is the separation principle: *"run state is for correctness and resumability; memory is for recall and personalization. Mixing them tends to cause state drift."* Engram currently stores everything in the same git-backed markdown hierarchy. Introducing a formal run-state layer — distinct from the memory store — would be the single highest-leverage architectural change.

---

## Recommended next steps (in priority order)

### 1. Wire up the eval runner (Phase 7 completion)

**Why first:** You can't measure improvement without evals. The research report's #6 recommendation is "evals and observability from the start," and Engram already has `EvalScenario`, `EvalStep`, `EvalAssertion`, and `compute_eval_metrics()` — all defined but not executable. This is the lowest-risk, highest-leverage completion.

**What to build:**
- A `memory_run_eval` MCP tool that takes a scenario YAML, creates an isolated test context, executes each `EvalStep` against the plan tools, runs assertions, and returns a `ScenarioResult`
- A basic CI integration that runs eval scenarios on PR
- 3–5 eval scenarios covering the critical paths: plan lifecycle, knowledge promotion, approval workflows

**Effort:** Medium. The schemas and metrics code exist. The main work is the step executor and test isolation.

### 2. Add the trace query tool (Phase 3 completion)

**Why:** Traces are being written to `{session}.traces.jsonl` but there's no way to query them through the MCP interface. Without queryable traces, the observability pillar is write-only — useful for post-mortem file reads, but not for runtime debugging or eval-driven analysis.

**What to build:**
- `memory_query_traces` MCP tool: filter by session, span_type, status, time range; return structured results
- Populate the `cost` field on trace spans (currently defined but always empty)
- Wire parent_span_id to enable call-tree reconstruction

**Effort:** Small-medium. The `TraceSpan` dataclass and `_load_trace_spans()` parser exist. This is mostly plumbing.

### 3. Expose the context briefing tool (Phase 8 completion)

**Why:** `assemble_briefing()` is fully implemented — it assembles phase payloads, truncates sources, includes failure summaries and recent traces, manages budgets. But it's not exposed as an MCP tool, so agents can't use it. This is the lowest-hanging fruit in the entire project.

**What to build:**
- `memory_plan_briefing` MCP tool wrapping `assemble_briefing()`
- Register it in `server.py`

**Effort:** Small. The implementation exists; this is a registration task.

### 4. Introduce a formal run-state layer

**Why:** This is the architectural change the research report most strongly recommends for long-horizon reliability. Currently, plan state lives in YAML files committed to git. This works for plan *design* but conflates the plan definition with execution state. When an agent resumes a multi-session plan, it re-reads the entire plan and infers where it was — there's no explicit checkpoint.

**What to build:**
- A `RunState` schema (JSON, not markdown) stored in `memory/working/projects/{id}/run-state.json`
- Fields: current_phase, current_task, last_checkpoint, intermediate_outputs, next_action, blocked_on, token_budget_remaining
- Auto-saved after each successful step (via `memory_plan_execute`)
- A `memory_plan_resume` tool that loads run state and assembles a minimal context for continuing

**Effort:** Medium-large. This is new architecture, but it builds on the existing plan infrastructure.

### 5. Make tool policies enforceable at runtime

**Why:** The tool registry stores `approval_required`, `cost_tier`, and rate limits, but these are informational. The research report emphasizes that tool policies must be *enforced*, not just documented — "assume every tool output is untrusted input" and "enforce a tool policy layer that can block or require approval based on tool + args + context."

**What to build:**
- A `check_tool_policy()` function called before any Tier 1/2 write operation
- Integration with the existing approval workflow: if a tool has `approval_required: true`, automatically create an `ApprovalDocument` and pause
- Rate limit enforcement using ACCESS.jsonl timestamps
- Start with write tools only — don't try to gate external tool calls yet

**Effort:** Medium. The approval infrastructure exists (Phase 5). The main work is the policy check middleware.

### 6. Add runtime guardrails beyond path validation

**Why:** `path_policy.py` prevents writes to protected directories, but there's no content validation. The research report calls for guardrails as a "parallel control plane" — cheap checks that run before expensive operations.

**What to build:**
- Schema validation on frontmatter before any write (the `frontmatter_utils.py` parser exists but isn't always enforced)
- A content size guard (reject files over a configurable threshold)
- A trust-boundary guard: prevent `trust: high` assignment without explicit user confirmation
- Wire these into the write path as pre-commit validators

**Effort:** Small-medium. Most of the validation logic exists in scattered form; the work is centralizing it into a guard pipeline.

---

## What to explicitly defer

The research report also helps identify what Engram should **not** build yet:

- **Multi-agent orchestration.** Engram is a single-agent memory system. Multi-agent support (shared namespaces, agent identity separation) is on the aspirational roadmap but adds significant complexity. The report says to add this "only when you can name clear specialization boundaries and measure gains." Engram can't measure gains yet (see: eval runner).

- **Vector knowledge graphs.** The semantic search (MiniLM embeddings + BM25 + freshness + helpfulness) is solid. Graph-based reasoning is interesting but premature — the report notes search over candidate thoughts "increases latency/cost and creates more surfaces for self-consistency failures."

- **Fine-tuning.** The report is clear: "set up evals first, then choose the adaptation lever." Engram doesn't have evals running yet.

- **Machine-readable governance extraction** (Phase 3 of the maturity roadmap). The roadmap correctly says "do not build this speculatively." Wait until the MCP server actually needs structured policy data.

---

## Sequencing summary

```
Step 1: Eval runner          ─── gives you measurement
Step 2: Trace query tool     ─── gives you observability
Step 3: Briefing MCP tool    ─── quick win, already built
Step 4: Run-state layer      ─── the big architectural move
Step 5: Tool policy enforce  ─── runtime safety
Step 6: Runtime guardrails   ─── defense in depth
```

Steps 1–3 are completions of existing work (low risk, high signal). Step 4 is the structural investment that turns Engram from a memory system into a proper harness. Steps 5–6 add the safety layer that the research report emphasizes is "not a prompt addition."

---

## One pending item to address

The review queue has an open proposal from 2026-03-26: stale `HEAD.lock` cleanup in `git_repo.py` for FUSE-mounted filesystems. This is a real operational issue in the Cowork VM environment and should be resolved before any of the above work, since git reliability is foundational to everything Engram does.
