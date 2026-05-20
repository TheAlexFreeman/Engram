---
created: '2026-04-28'
errors: 1
retrievals: 0
session: memory/activity/2026/04/28/act-002
session_id: act-002
source: agent-generated
tool: harness
tool_calls: 16
total_cost_usd: 1.2286
trust: medium
---

# Session act-002

**Task:** We'll definitely use Better Base's Postgres DB for a more robust search feature but keep files as the source of truth for knowledge, skills, and activity summaries. The activity *logs* are programmatic enough and append-only, so they could just be replaced by DB tables for an app-integrated harness. What sorts of Django models could help us capture relevant information about different kinds of agent actions?

- Turns: 16
- Tool calls: 16 (1 errors)
- Tokens (in/out): 382,757 / 5,353
- Cost: $1.2286

## Summary

[Grok Reasoning]
The task from the prior session notes is: "We'll definitely use Better Base's Postgres DB for a more robust search feature but keep files as the source of truth for knowledge, skills, and activity sum...

**I created a new project `engram-harness-better-base-demo`** (with goal, initial questions, and auto-generated SUMMARY.md) to track the ongoing harness + Better Base integration work, including this modeling task.

**I then wrote a detailed working note** at `projects/engram-harness-better-base-demo/notes/django-models-for-agent-actions.md`. It proposes a clean, extensible set of Django models that align with the existing codebase patterns (e.g. `CoreModel`/`TimeStampedModel`, `RequestEvent` + `RequestEventVerb` TextChoices, JSONField payloads, structlog-friendly tracing, transaction guards, GIN indexes for search, and `memory_path` links back to the canonical Markdown files).

### Key Proposed Models
- **`AgentSession`**: Groups one harness run (`session_id` like "act-002", project link, goal snapshot, totals for tool calls/tokens/cost, status, `summary_path` to the generated Markdown SUMMARY.md, trace correlation).
- **`AgentEvent`** (the core append-only log): Uses a `verb` (e.g. `TOOL_CALL`, `MEMORY_RECALL`, `MEMORY_REMEMBER`, `MEMORY_PROMOTE`, `FILE_READ`/`FILE_EDIT`, `TRACE_EVENT`, `PLAN_ADVANCE`, `PAUSE_FOR_USER`, `ERROR`, plus extensibility for web_search, git ops, code exec, etc.). Includes `session`, `actor`, `memory_path`, `tool_name`, flexible `payload` (JSONB), trace/span IDs, success/duration. Heavy indexing for fast Postgres queries/search.
- Optional specialized tables (e.g. `MemoryAccessLog` for ACCESS.jsonl-style tracking, dedicated `AgentToolCall` or `AgentTraceEvent` if analytics need deeper relations).

### Design Rationale (Hybrid Files + DB)
- **Files remain source of truth**: Models log *what happened* (immutable events) and reference `memory_path`. Post-session, a harness op or management command can query events to *generate* the Markdown activity summaries/SUMMARY.md (counts, key findings, timelines). No duplication of rich knowledge/skills content.
- **DB for robust search & app integration**: Postgres excels at filtering ("all `memory_promote` for a project in last 30 days"), aggregation (tool usage, error rates, cost), full-text/JSONB/GIN search, and future pgvector semantics. Perfect for an "Engram Explorer" dashboard page in the Better Base demo.
- Follows existing Better Base patterns (transactional recording like request events, query_runner discoverability, structlog correlation, CoreModel repr/indexing).
- Extensible and lightweight—new action kinds are just new verb choices + payload shapes.

The note includes usage guidance for the harness (hooks on tool/memory/trace calls), benefits, and concrete next steps (new `backend/engram/models.py`, admin/serializers for the demo, safe exposure via query runner).

This directly addresses the bootstrap question while advancing the active threads around the Better Base demo, memory visualization, and harness expansion. Let me know if you'd like me to implement the models, generate a migration skeleton, refine the verbs/payload schemas, add serializers/views, or promote parts of the note to durable `memory/knowledge/`. (I can also update threads or create a formal plan in the project.)

## Tool usage

- `list_files`: 4
- `read_file`: 4
- `grep_workspace`: 3
- `work_note`: 2 (1 err)
- `work_status`: 1
- `memory_context`: 1
- `work_project_create`: 1

## Notable tool calls

- `work_note` (turn 12, error): ValueError: project 'engram-harness-better-base-demo' does not exist

Traceback (most recent call last):
  File "C:\User

## Notable events

- `2026-04-28T22:34:30` [error] work_note failed: ValueError: project 'engram-harness-better-base-demo' does not exist

Traceback (most recent call last):
  File "C:\Users\Owner\code\personal\engram-harness\harness\tools\__init__.py", line 337, in ex