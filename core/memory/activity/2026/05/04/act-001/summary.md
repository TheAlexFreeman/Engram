---
created: '2026-05-04'
errors: 0
retrievals: 8
session: memory/activity/2026/05/04/act-001
session_id: act-001
source: agent-generated
subagent_count: 7
subagent_total_cost_usd: 5.4437
tool: harness
tool_calls: 25
total_cost_usd: 1.9838
trust: medium
---

# Session act-001

**Task:** Ok, here's another version of Better Base that's been expanded into a demo with a few different apps and some AI integration prep. What inspiration can we take from this project for our Engram Tasks platform?

- Turns: 17
- Tool calls: 25 (0 errors)
- Tokens (in/out): 618,951 / 8,460
- Cost: $1.9838

## Summary

Here's the full synthesis of what the expanded Better Base demo teaches us, organized by insight type:

---

## What the Expanded Demo Shows

This isn't a minor update — the expanded BB now has **six product apps**: requests (feature tracker), docs (markdown editor), checklists (polymorphic), agents (AI control plane), inbound_emails, and notifications. The agents app in particular is production-quality, not prototype-quality.

---

## Patterns to Steal Directly

### 1. `AgentSession` model — steal as-is
This solves the "how do we track AI operations in Postgres" question completely. The model gives you: status lifecycle (`pending → running → completed/error/stopped`), cost tracking (`cost_budget_usd`, `cost_consumed_usd`), turn counting, `final_text`, and a `harness_session_id` foreign key into the external system. **This is the receipt for every AI action.** Engram Tasks should use it exactly.

### 2. The SSE proxy pattern — steal as-is
`AgentSessionViewSet.events()` proxies the harness SSE stream through Django as a `StreamingHttpResponse`. The harness never has to be public-facing. The frontend subscribes to `/api/sessions/{id}/events/` on Django, Django forwards from the harness. Headers `Cache-Control: no-cache` + `X-Accel-Buffering: no` handle nginx buffering. This is the right architecture for live agent updates.

### 3. Tier → Tool Profile → Memory namespace mapping
```
WORKER → read_only → can recall, cannot write
ADMIN  → no_shell  → can draft/propose, user approves  
DEV    → full      → can autonomously act
```
This three-tier model maps perfectly to Engram Tasks' agent permission hierarchy. Build it in from day one, not as an afterthought.

### 4. `ChecklistItem` completion attribution → `TaskItem` subtask model
The `ChecklistItem` pattern (ordered by `position`, `completed_by` + `completed_at` paired constraint, race-safe appending via `select_for_update`) is exactly the right shape for AI-generated task decompositions. An agent produces subtasks → they land as `ChecklistItem` rows → the existing `ChecklistsPanel` component displays them with no new UI work. **The AI decomposition MVP needs zero new frontend components.**

### 5. `RequestEvent` audit log → `TaskActivity` pattern
Every mutation fires an immutable event row in the same transaction. `SET_NULL` + payload JSON snapshot (`title`, `short_id`) means the audit trail survives deletion. This is the event-sourcing-lite pattern, and it's already done correctly here.

### 6. `@mention` resolution → `@agent` mentions
The mention system parses `@<token>` from comment bodies and resolves to users. **Extend this to resolve agent names.** `@engram` on a task comment = invoke the account's default WORKER agent scoped to that task. The infrastructure is already there; it just needs a new resolution branch.

### 7. Dashboard delta pattern → AI KPIs
The `DashboardSerializer` computes "this period vs. last period" deltas for every stat. Add AI-native KPIs here from day one: agent sessions run, cost consumed, memories created, avg. recall latency. The pattern is already established — just add columns.

---

## New Inspirations Not in Prior Notes

### A. `inbound_emails` → `inbound_tasks`
The email ingestion app (receive webhook → store metadata → async fetch content via Celery) is a general pattern for external task creation. A CI system, a Slack bot, or a forwarded email can all create tasks by POSTing to a verified endpoint. **Build `backend.inbound_tasks` following this exact pattern.** No new architectural thinking needed — just swap email payloads for task payloads.

### B. Docs as memory shadow records
The `Doc` model (markdown, tags, DOC_SHARED fan-out notification) is extremely close to what a memory file UI entry should look like. **When the Engram proxy writes a knowledge file to disk, also create a `Doc` shadow row in Postgres.** This makes memory files queryable, notifiable, and explorable in the existing UI without building a separate memory viewer. The `DocEditor` split-pane (markdown left, preview right) becomes the AI draft review surface for free.

### C. `validate_can_*` ops as AI governance gates
The ops layer's pre-condition validators currently enforce human business rules. For Engram Tasks, **they also become AI governance**. Before `dispatch_agent_session()` fires, `validate_can_dispatch()` checks: tier vs. requested action, remaining cost budget, account-level AI feature flag. If validation fails, the rejection message becomes the agent's feedback signal. The ops layer is the right place for AI governance — not the view, not the harness.

### D. `AgentAPIKey` prefix scheme → `MemoryAccessKey`
The `bb_agent_` prefix + 8-char plaintext lookup + hashed full key pattern is reusable for any API surface. External systems that need to read/write Engram memory (a CI bot, an external integration) can be issued a `MemoryAccessKey` using the exact same auth backend pattern. Memory namespaces become first-class API-accessible resources.

---

## Resolved Questions

| Question | Answer |
|---|---|
| Which BB primitives map to Engram? | `AgentSession` = harness bridge; `Account` = memory namespace root; `Agent` tier = tool profile |
| What new apps to build? | `backend.tasks`, then extend existing `backend.agents`, then `backend.engram_proxy`, then `backend.inbound_tasks` — agents app already exists and is production-quality |
| How to surface AI features? | Progressively disclosed: AI panel is a collapsible sidebar; AI comments are badged but live in the same thread; `@agent` mentions work like `@user` |
| Persistence split? | Postgres owns metadata (paths, trust levels, access timestamps); Engram owns file content — never store file content in Postgres |
| MVP scope? | Task CRUD + activity log + "Ask AI" button → `AgentSession` → poll → AI comment + read-only memory panel. 2 new apps, 4 views, 3 components |

---

## Bottom Line

The expanded BB demo removes most of the "what do we build?" uncertainty. The `backend.agents` app is essentially production-ready — don't duplicate it. The checklist, docs, and notifications systems are immediately reusable for the task platform with minimal adaptation. The big remaining gap is `backend.tasks` (the core work primitive) and `backend.engram_proxy` (the Postgres ↔ Engram bridge). Everything else can be assembled from existing BB patterns.

**Next decision:** which phase to build first — the tasks app data model or the engram_proxy stub?

## Tool usage

- `list_files`: 6
- `work_project_resolve`: 5
- `work_list`: 4
- `spawn_subagents`: 2
- `memory_recall`: 2
- `work_read`: 2
- `work_status`: 1
- `work_project_status`: 1
- `work_note`: 1
- `work_thread`: 1

## Subagent runs

- **subagent-001** (4 turns, 27 tool calls, $0.2272):
  Task: 'Explore the backend/agents app in the workspace at C:\\Users\\Owner\\code\\personal\\Engram\\core. Read the following files and return their contents:\n1. backend/agents/models/ - list files then read each m'
  Tools: read_file(19), list_files(8)
- **subagent-002** (4 turns, 23 tool calls, $0.1706):
  Task: 'Explore the backend/checklists app in the workspace at C:\\Users\\Owner\\code\\personal\\Engram\\core. Read the following:\n1. backend/checklists/models/ - list files then read each model file\n2. backend/che'
  Tools: read_file(14), list_files(9)
- **subagent-004** (7 turns, 64 tool calls, $0.6460):
  Task: 'Explore the backend structure of the workspace at C:\\Users\\Owner\\code\\personal\\Engram\\core. Read the following:\n1. backend/accounts/ - list files, read models and a sample API file\n2. backend/requests'
  Tools: read_file(33), list_files(31)
- **subagent-003** (9 turns, 84 tool calls, 6 errors, $1.1360):
  Task: 'Explore the frontend structure of the workspace at C:\\Users\\Owner\\code\\personal\\Engram\\core. Focus on:\n1. frontend/routes/ - list ALL files recursively, then read a sample of route files (especially a'
  Tools: read_file(50), list_files(32), glob_files(2)
- **subagent-005** (4 turns, 34 tool calls, $0.2985):
  Task: "Explore the backend/agents app in the workspace at C:\\Users\\Owner\\code\\personal\\Engram\\core. I need to understand what's NEW in this expanded version. Read these files:\n\n1. backend/agents/models/ - li"
  Tools: read_file(26), list_files(8)
- **subagent-006** (13 turns, 69 tool calls, 3 errors, $1.4555):
  Task: 'Explore the frontend/routes directory in the workspace at C:\\Users\\Owner\\code\\personal\\Engram\\core. I need to understand ALL routes in the app.\n\n1. First list ALL files recursively in frontend/routes/'
  Tools: read_file(48), list_files(20), glob_files(1)
- **subagent-007** (13 turns, 78 tool calls, $1.5100):
  Task: 'Explore new and interesting parts of the workspace at C:\\Users\\Owner\\code\\personal\\Engram\\core. I need to see what apps/features have been added beyond the basic Better Base starter. Focus on:\n\n1. bac'
  Tools: read_file(54), list_files(21), glob_files(3)

## Memory recall

- memory/knowledge/software-engineering/devops/better-base-toolchain.md ← 'Engram Tasks platform AI-native task tracking Better Base' (trust=low score=0.029)
- memory/knowledge/ai/frontier/multimodal/multimodal-synthesis-agent-implications.md ← 'Engram Tasks platform AI-native task tracking Better Base' (trust=medium score=0.029)
- memory/knowledge/self/_archive/session-2026-03-20-cowork-review.md ← 'Engram Tasks platform AI-native task tracking Better Base' (trust=medium score=0.021)
- memory/knowledge/ai/tools/ai-tools-landscape-2026.md ← 'Engram Tasks platform AI-native task tracking Better Base' (trust=medium score=0.020)
- memory/knowledge/ai/frontier/multimodal/embodied-ai-rt2-gato-saycan.md ← 'Engram Tasks platform AI-native task tracking Better Base' (trust=medium score=0.016)
- memory/knowledge/self/_archive/session-2026-03-20-cowork-review.md ← 'Engram Tasks platform design memory as first-class feature task tracking' (trust=medium score=0.021)
- memory/knowledge/ai/tools/mcp/mcp-2026-roadmap-update.md ← 'Engram Tasks platform design memory as first-class feature task tracking' (trust=medium score=0.021)
- memory/knowledge/philosophy/phenomenology/heidegger-readiness-presence-at-hand.md ← 'Engram Tasks platform design memory as first-class feature task tracking' (trust=medium score=0.016)