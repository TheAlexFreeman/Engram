---
name: flow-trace
description: >-
  Trace how operations execute through a codebase — following requests, commands,
  jobs, or events from entry point through every architectural layer, recording
  boundary crossings, data transformations, and implicit couplings. Complements
  the codebase-survey by mapping what happens rather than what exists.
compatibility: Requires host repo access for code reading; uses agent-memory MCP for knowledge persistence

source: agent-generated
origin_session: manual
created: 2026-04-04
last_verified: 2026-04-04
trust: low
---

# Flow Trace

## When to use this skill

Use this skill to trace how operations actually execute through a codebase — following a request, command, job, or event from its entry point through every architectural layer it touches, recording the boundary crossings, data transformations, and implicit couplings along the way.

Flow tracing complements the architectural survey. Where the codebase-survey skill maps *what exists* (modules, entities, operations, decisions), flow tracing maps *what happens* — the characteristic paths that the system's operations carve through its structure. The output is a `knowledge/codebase/flows.md` file plus cross-references into the existing architectural knowledge files.

### When to reach for this skill

- **During initial survey**: after entry points are identified (either by the codebase-survey or by a quick scan), trace one representative flow to anchor the rest of the survey in concrete execution paths.
- **During deepening rounds**: when the codebase-survey's reflective loop identifies a subsystem that's poorly understood, trace a flow through it.
- **Cold start**: if no prior survey exists, a single flow trace is often the fastest way to build an initial mental model — it reveals the architectural layers, key abstractions, and wiring conventions all at once.
- **Before modifying unfamiliar code**: trace the flow you're about to change so you understand what's upstream and downstream of your edit.

### Relationship to codebase-survey

If `knowledge/codebase/architecture.md` already has entry points mapped, start there — those are your candidate flows. If not, this skill includes guidance for finding good starting flows from scratch. Either way, findings from flow tracing should be cross-referenced back into the architectural files (`architecture.md`, `data-model.md`, etc.) when they reveal structural facts those files don't yet capture.

## Core technique: boundary-first tracing

The central idea is to trace execution across *architectural boundaries* rather than through every function call. This keeps traces compact and structurally informative.

At each step, ask: **"Am I still in the same architectural layer?"** If the answer is yes, keep scanning but don't record every function — you're looking for the exit. When execution crosses a boundary (API layer -> business logic, business logic -> persistence, synchronous -> async), record:

1. **The crossing point**: which function/method/message hands off to which
2. **What crosses the boundary**: the data or message shape, not the full payload
3. **What comes back**: return values, side effects, or "fire-and-forget"
4. **Any transformation**: where data changes shape, gets validated, denormalized, or enriched

This is the difference between "here are 47 function calls" and "request enters at the API serializer, gets validated, dispatched to OrderService.create(), which writes to the orders table and enqueues a confirmation email." The second version is shorter and more useful.

### Why boundary-first works

An agent that records every function call within a layer produces notes that are both long and fragile — they break whenever someone refactors internals. Boundary crossings are more stable because they tend to be the parts of the code that are maintained as contracts. They're also the parts that matter most for understanding blast radius: if you change something in the service layer, the boundaries tell you what's upstream (what calls you) and downstream (what you call).

## Steps

### 1. Select a flow to trace

**If architectural survey exists**: scan `knowledge/codebase/architecture.md` for entry points and pick the one that looks most structurally connected — the route, command, or handler that touches the most layers. In a web app, this is usually the primary CRUD operation, not the health check. In a CLI tool, it's the main command, not `--version`.

**Cold start (no prior survey)**: use these heuristics to find a good starting flow:
- Look for URL routes, CLI command registrations, or event handler bindings
- Pick whichever one has the most imports or the deepest apparent call chain
- When in doubt, look for the operation that most closely represents the system's core purpose — what would a user describe as "the thing this app does"

**Scaling down**: for a focused investigation of a subsystem, pick a flow that enters and exits that subsystem. You don't need to trace the full request lifecycle — just the slice you're trying to understand.

Record your choice and reasoning briefly in the project scratchpad or `IN/` directory before starting the trace. This helps future agents understand why this flow was chosen and whether it's still representative.

### 2. Trace the flow, boundary by boundary

Starting from the entry point, follow execution forward. At each architectural boundary crossing, record the four elements: crossing point, what crosses, what returns, and any transformation.

**Practical techniques:**

- **Follow imports for the happy path first.** Don't get pulled into error handling, edge cases, or branching logic on the first pass. You can note "branches here for permission check" and come back to it.
- **Name the layers as you discover them.** Part of the value of flow tracing is identifying what the architectural layers actually *are* in this specific codebase, which may not match textbook patterns. If the codebase has a "coordinator" layer between controllers and services, name it.
- **Watch for indirection.** When you can't follow execution through static imports — dependency injection, event/signal dispatch, dynamic routing, config-driven behavior, message queues — flag it explicitly. Record *how to discover the connection* (e.g., "task routing configured in celery.py", "signal handlers registered in apps.py:ready()"). These implicit couplings are among the highest-value things to document because they're invisible to casual code readers.
- **Note lifecycle context.** Is this code running per-request? At startup? On a schedule? In a migration? The execution context affects everything from error handling expectations to performance constraints, and it's easy to lose track of when reading code statically.

**When to stop descending:** stop when you reach an external boundary (database query, HTTP call to another service, filesystem write, message publish) or when you enter a well-understood library/framework layer where the behavior is standard. You don't need to trace into Django's ORM internals — "calls `Order.objects.create()`" is sufficient.

### 3. Identify flow categories

After tracing your first flow, step back and identify what *categories* of flow the system has. Common categories:

- **Synchronous request/response** (HTTP, RPC, CLI commands)
- **Async task processing** (Celery, background jobs, workers)
- **Scheduled/periodic** (cron, beat schedules, timed triggers)
- **Event-driven/reactive** (signals, webhooks, pub/sub handlers)
- **Startup/initialization** (boot sequences, connection setup, cache warming)
- **Migration/one-shot** (schema migrations, data backfills, setup scripts)

Not every codebase has all of these, and some have categories that don't fit these labels. The point is to identify the distinct execution lifecycles so future agents know what *kinds* of flows exist, even before every individual flow is traced.

Record the categories in `flows.md` with at least one concrete example path for each. If you've only traced one flow so far, note the other categories as "identified but not yet traced."

### 4. Trace the convention, then record exceptions

If the codebase is well-organized, most flows within a category will follow the same structural pattern — the same middleware chain, the same service-layer conventions, the same error handling approach. This is the "standard lifecycle" for that flow category.

Document the standard lifecycle once, in detail. Then for subsequent flows, document only the *delta* — where and why they deviate from the standard pattern. This is dramatically more efficient than full traces for every endpoint, and it captures the most valuable information: the exceptions are where the interesting business logic, performance optimizations, and historical workarounds live.

**Example format:**

> **Standard API lifecycle:** Request -> auth middleware -> DRF serializer validation -> viewset action -> service method -> ORM -> response serializer -> response.

> **POST /orders (deviation):** After OrderService.create(), enqueues `send_confirmation` celery task. Also bypasses standard pagination. (Reason: order creation is the only endpoint with async side effects.)

### 5. Record velocity and stability signals

As you trace, note which areas of the code feel stable (well-abstracted, few recent changes, covered by the "standard lifecycle") versus volatile (frequently modified, special-cased, marked with TODOs or "temporary" comments). You don't need a rigorous metric — qualitative impressions are useful.

These signals help future agents calibrate caution: stable contract boundaries deserve careful, conservative changes, while volatile implementation interiors might be actively being reworked.

If git history is available, a quick `git log --oneline -20 <file>` on key files can ground these impressions in evidence.

### 6. Write up findings

**Primary output: `knowledge/codebase/flows.md`**

Structure the file around flow categories, with the standard lifecycle documented first and per-flow deviations listed underneath. Include a section for implicit coupling points and one for untraced flows / open questions.

Suggested structure:

```
# Flows — {project name}

## Flow categories
(Brief list of identified categories with one example each)

## Standard lifecycles
### {Category 1}: standard lifecycle
(Detailed boundary-by-boundary trace of the representative flow)

### {Category 2}: standard lifecycle
...

## Notable deviations
### {Specific operation} — {what's different and why}
...

## Implicit coupling points
(Connections that aren't visible through static imports)

## Velocity notes
(Which areas are stable vs. volatile, with evidence)

## Untraced / open questions
(Flows identified but not yet traced, questions discovered during tracing)
```

**Cross-references into existing files:**

After writing `flows.md`, update the related architectural files:
- In `architecture.md`: add `related` frontmatter pointing to `flows.md`. If flow tracing revealed modules or boundaries not yet documented, add them.
- In `data-model.md`: if the trace revealed data flow patterns (where truth lives, where caches diverge, where data changes shape), add or update those sections.
- In `SUMMARY.md`: add `flows.md` to the file index.

### 7. Verify and assess trust

Before promoting any finding above `trust: low`:
- Confirm that the boundary crossings you recorded actually exist in the current code (a quick grep or file read is sufficient)
- Check that indirection points resolve where you said they do
- If you noted "this code runs on a schedule," verify the schedule configuration exists

Promote to `trust: medium` once the trace is grounded in current source files. Leave unverified impressions (velocity signals, suspected patterns) clearly marked as unverified.

### 8. Handoff for next session

End with an explicit suggestion for the next flow-trace round:
- Which flow category or specific operation would yield the most understanding per effort?
- What open questions from this session's trace would a deeper pass resolve?
- Update `projects/codebase-survey/IN/knowledge-roadmap.md` and `questions.md` if this was part of the survey project.

## Quality criteria

- A future agent can understand what happens when a user triggers an operation *faster from the trace than from re-reading the code*.
- Traces capture boundary crossings and implicit couplings, not function-by-function walkthroughs.
- The standard lifecycle for each flow category is documented once; deviations reference it by delta.
- Indirection points include a note on *how to discover the connection*, not just that it exists.
- Findings are cross-referenced into the architectural knowledge files.

## Anti-patterns

- **Tracing every function call.** If your trace reads like a stack trace, you're too deep. Stay at the boundary level.
- **Ignoring indirection.** The easy parts of a trace (following imports) are the least valuable to document. The hard parts (DI, signals, config-driven routing) are exactly what future agents need.
- **Tracing only the happy path forever.** The first trace should be happy-path, but deepening rounds should cover error paths, retry logic, and failure modes — these are where production surprises live.
- **Writing a separate full trace for every endpoint.** Document the convention, then document exceptions. If you're repeating yourself, you haven't identified the standard lifecycle yet.
- **Skipping cross-references.** A flow trace that lives only in `flows.md` without updating `architecture.md` or `data-model.md` is half-finished. The whole point is that flow knowledge enriches structural knowledge.
