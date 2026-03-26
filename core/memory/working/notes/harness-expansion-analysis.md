---
title: "Agent Harness Expansion Analysis"
source: agent-generated
trust: medium
created: 2026-03-26
context: "Analysis of deep research report on LLM agent harness best practices, mapped against Engram's current architecture"
---

# From Memory System to Agent Harness: Gap Analysis and Expansion Path

## What the report defines as a harness

The report converges on seven subsystems that make an agent loop production-reliable:

1. **Orchestration** — control structure for multi-step execution (loop, state machine, workflow engine)
2. **Tool interface + execution runtime** — schemas, routing, timeouts, sandboxing, error normalization
3. **State and memory** — short-term context, persisted run state, long-term recall
4. **Retrieval augmentation** — grounding in external knowledge
5. **Reliability mechanisms** — verification loops, self-consistency, human approvals
6. **Evaluation + observability** — offline evals, production monitoring, step-level tracing
7. **Safety guardrails** — policies enforced before and after tool execution

## Where Engram already delivers

### Memory and state (strongest coverage)

Engram is genuinely ahead of the curve on the report's tier-3 recommendation ("long-horizon success depends more on state management than on raw model capability"). Specifically:

- **Tiered memory** is already implemented: compressed short-term (HOME.md, CURRENT.md), structured run state (plans with YAML execution state), and retrieval-based long-term recall (knowledge/ with ACCESS-driven curation). The report calls this the "winning pattern."
- **Run state vs. recall memory separation** — the report explicitly warns against mixing these. Engram already separates `working/` (run state) from `knowledge/` (recall) and `activity/` (episodic).
- **Compression and summarization** — the report calls these "first-class mechanisms, not hacks." Engram's progressive compression hierarchy (leaf → month → year) and context budget system are exactly this.
- **Resumability** — plans persist across sessions with phase/task state, allowing resume without reprocessing. The report's "durable execution" pattern.

### Safety and guardrails (strong coverage)

The report's safety section maps almost 1:1 to existing Engram architecture:

- **Least privilege** → Three-tier MCP tool surface; Tier 2 gated behind env flag.
- **Quarantine for untrusted content** → `_unverified/` staging zone with promotion workflow.
- **Trust-weighted retrieval** → Structural enforcement via path-policy layer.
- **Instruction containment** → Only `skills/` and `governance/` may instruct; folder-level contract.
- **Anomaly detection** → Identity churn tracking, knowledge flooding alarms, dormancy spike detection.
- **Audit trail** → Git-backed provenance on every write; belief-diff log for drift detection.

The report notes "security and safety are not prompt additions" — Engram's defense-in-depth is structural, not prompt-based.

### Governance (unique strength, not in report)

The report doesn't deeply cover self-evolving governance — maturity stages, evidence-based threshold adjustment, periodic review — but this is one of Engram's most distinctive features. The maturity model (Exploration → Calibration → Consolidation) with quantitative transition signals is essentially what the report would call "meta-evaluation of the harness itself."

## The gaps

### 1. Orchestration layer — THE critical missing piece

**Report says:** "Represent the agent run as steps with saved state; resume without repeating completed work; support human inspection/modification of state."

**Engram has:** Plans that document work, but no runtime that executes them. A plan is a passive YAML document, not a state machine that drives agent behavior. There's no:
- Agent lifecycle model (idle → active → waiting → complete)
- Step-by-step execution with automatic checkpointing
- Conditional branching based on tool results
- Automatic retry/recovery on failure
- Budget enforcement (max iterations, time, cost)

**What it would take:** This is the single largest expansion. Two approaches:

*Option A: Thin orchestration inside MCP.* Extend `memory_plan_execute` to return structured "next action" directives. The agent still drives the loop, but the plan becomes a stateful router that tracks which step to execute, what the stopping conditions are, and what to do on failure. This stays close to Engram's "memory as data" philosophy.

*Option B: External orchestration with Engram as state backend.* Integrate with LangGraph, Temporal, or a custom workflow engine. Engram provides the persistent state store; the orchestrator provides the execution loop. This is more powerful but adds a hard dependency.

**Recommendation:** Start with Option A. It's the minimal viable harness — the plan system already stores phases and tasks; making it return execution directives is an incremental step, not a rewrite.

### 2. Tool interface design — partial coverage

**Report says:** "Treat tools as an API product. Clear schemas, compact outputs, namespacing."

**Engram has:** 73 well-designed tools with tiered access and path-policy enforcement — but these are all *memory tools*. The harness needs a way to:
- Register and manage *external* tools (APIs, shell commands, code execution)
- Enforce tool policies (which tools require approval, rate limits, cost caps)
- Normalize tool outputs for model consumption
- Handle timeouts and sandbox execution

**What it would take:** A tool registry in `core/memory/skills/` or a new `core/tools/registry/` that stores tool definitions with metadata: schema, approval requirements, cost tier, timeout. The MCP server could expose a `memory_register_tool` and `memory_get_tool_policy` surface. This doesn't mean Engram *runs* the tools — it means Engram *knows about* them and can advise the orchestrator on policies.

### 3. Verification and reliability loops — conceptually present but not automated

**Report says:** "Interleave reasoning with actions; self-consistency for critical decisions; reflection-style memory for learning from failures."

**Engram has:** `memory_record_reflection` for post-session learning, ACCESS helpfulness scoring, and the belief-diff log for drift detection. But these are all *retrospective*, not *inline*.

**What it would take:**
- A verification step type in plans: "after executing step X, run validator Y before proceeding."
- A `memory_verify_step` tool that checks postconditions against expected outputs.
- A reflection-on-failure pattern: when a step fails, automatically record what happened and what the agent tried, making it available for retry reasoning.

### 4. Evaluation and observability — the biggest operational gap

**Report says:** "You cannot manage what you cannot see. End-to-end traces across model calls, tool calls, retrieval, and guardrails."

**Engram has:** ACCESS.jsonl (retrieval tracking), git history (change tracking), session summaries (narrative tracking). But no:
- Structured traces with spans and timing
- Step-level success/failure metrics
- Cost tracking (tokens, compute, wall time)
- Outcome metrics (did the task actually succeed?)
- Dashboard or alerting for production monitoring

**What it would take:** This is where the report's recommendation to "adopt standard telemetry semantics" is relevant. Engram could:
1. Extend ACCESS.jsonl to include tool-call traces (not just retrieval events).
2. Add a `TRACES.jsonl` file per session that records the full step-by-step execution with timing, tool calls, and outcomes.
3. Expose `memory_record_trace` and `memory_query_traces` MCP tools.
4. Build an evaluation view in `HUMANS/views/` that renders trace data.

### 5. Human-in-the-loop — governance exists, workflow doesn't

**Report says:** "Operationalize HITL as an interrupt/resume mechanism with serialized run state."

**Engram has:** Protected-tier changes require approval. The review queue collects items for human review. But there's no:
- Structured approval workflow (request → review → approve/reject → resume)
- Notification mechanism
- Deferred action queue with expiry
- Pause/resume for in-flight plans

**What it would take:** Extend the review queue into a proper approval system. Add an `approvals/` subfolder under `working/` where pending actions are serialized. Plans could declare steps as `requires_approval: true`. The orchestration layer (gap #1) pauses at those steps and writes the pending action. When the user approves (via MCP tool or browser UI), execution resumes.

## Expansion priority order

Based on the report's emphasis that "start with the smallest architecture that can work" and Engram's existing strengths:

### Phase 1: Active plans (orchestration-lite)
- Make plans executable: add stopping conditions, step postconditions, and "next action" directives to plan execution responses.
- Add budget fields to plans (max_steps, max_cost, deadline).
- Add `requires_approval` flag to plan steps.
- *This gives you a minimal agent harness with Engram's memory as the state backend.*

### Phase 2: Inline verification
- Add verification step types to plans.
- Implement `memory_verify_step` tool.
- Add failure recording and retry-with-context pattern.
- *This addresses the report's #1 reliability recommendation: tool-grounded checkpoints.*

### Phase 3: Observability
- Extend session recording to include tool-call traces.
- Add timing, cost, and outcome fields to ACCESS or a parallel trace log.
- Build a trace viewer in HUMANS/views/.
- *This addresses "you cannot manage what you cannot see."*

### Phase 4: External tool registry
- Define a tool-definition schema in memory.
- Store tool policies (approval requirements, rate limits, cost tiers).
- Expose policy-query tools via MCP.
- *This addresses the report's tool-as-API-product recommendation without requiring Engram to become a tool execution runtime.*

### Phase 5: Structured HITL
- Extend review queue into approval workflow.
- Add pause/resume to plan execution.
- Build approval UI in HUMANS/views/.
- *This addresses the report's interrupt/resume pattern.*

## What Engram should NOT become

The report is clear: "start with the smallest architecture that can work." Engram's strength is being a *memory and governance layer*, not a general-purpose agent framework. Some things to avoid:

- **Don't build a tool execution runtime.** Let the host platform (Claude Code, Cursor, etc.) execute tools. Engram should *know about* tools and *enforce policies*, not run them.
- **Don't build multi-agent coordination.** The report warns about "agent soup" and "emergent failure modes." Engram serves individual agents well; multi-agent support should be a consumer of Engram, not built into it.
- **Don't build a vector store.** The report validates RAG but Engram's file-based retrieval with ACCESS-driven curation is a deliberate architectural choice. If semantic search is needed, it should be an optional add-on, not a replacement.
- **Don't build model routing.** The report discusses cheap-model-for-guardrails patterns, but this is an orchestration concern, not a memory concern.

## Bottom line

Engram is already a best-in-class implementation of subsystems 3 (state/memory), 4 (retrieval), and 7 (guardrails) from the report's harness taxonomy. The path to a full harness is: make plans executable (orchestration), add inline verification (reliability), add trace recording (observability), and formalize tool policies (tool interface). Each phase builds on existing architecture without requiring a rewrite.
