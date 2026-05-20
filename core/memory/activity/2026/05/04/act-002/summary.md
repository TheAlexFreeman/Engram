---
created: '2026-05-04'
errors: 0
retrievals: 5
session: memory/activity/2026/05/04/act-002
session_id: act-002
source: agent-generated
subagent_count: 3
subagent_total_cost_usd: 3.0443
tool: harness
tool_calls: 6
total_cost_usd: 0.5197
trust: medium
---

# Session act-002

**Task:** How about the Better Base ops and query CLI?

- Turns: 5
- Tool calls: 6 (0 errors)
- Tokens (in/out): 153,690 / 3,909
- Cost: $0.5197

## Summary

I now have everything. Let me give you a thorough walkthrough.

---

## Better Base: Ops CLI + Query CLI — Full Picture

These two CLIs are **production-quality, fully tested** (253 dedicated tests between them). Here's a clear breakdown of what each one is and what makes them interesting.

---

## The Ops Runner CLI (`python manage.py ops`)

**Big idea:** Every public function in every `backend/**/ops/` module across all installed apps is automatically callable from the shell, with no registration required. Zero config for derived projects.

### Five subcommands

| Subcommand | What it does |
|---|---|
| `ops list [--app L] [--grep S] [--emit-schema]` | Enumerate all discoverable ops. With `--emit-schema`, each op gets its full parameter spec as JSON (name, annotation, required, kind, return type, docstring, source file + line). This is the agent's "I want to know what I can call" surface. |
| `ops show <address>` | Describe one specific op. Faster than list when you already know the address. |
| `ops run <address> [--kw k=v ...] [--input JSON\|@file\|-]` | Invoke an op. Annotation-driven coercion handles Django model instances (pass pk, gets fetched), enums, UUIDs, datetimes, generics. `--dry-run` resolves inputs and prints without executing. `--print-inputs` shows what actually got passed. |
| `ops batch <recipe>` | Run N ops in one transaction from a JSON recipe. Steps are threaded by Mustache-style interpolation: `{{step_name.path.into.result}}`. A failed step with `on_failure: "halt"` rolls back the entire atomic block. |
| `ops repl` | Interactive shell with `$last`, `$N`, and `$name` variable bindings. Tab-completion via `prompt_toolkit`. The REPL caches discovery across the session, so `list` is fast. |

### Address syntax
`<app_label>:<module.path>.<func_name>` — e.g. `accounts:users.create_user`, `requests:requests.create_request`. Shorthand `<app>:<func>` accepted when unambiguous.

### Output shape (uniform across all subcommands)
```json
{"ok": true, "op": "accounts:users.update_user", "took_ms": 42, "result": {...}, "warnings": []}
```
Failures: `{"ok": false, "error": {"type": "IntegrityError", "message": "...", "traceback": "..."}}`. `FailedXResult` dataclasses return `ok: true` — business errors are in the result body. Exit codes: 0 (success), 1 (usage), 2 (op raised), 3 (import failure).

### The output selector
Every subcommand supports `--output <dotted-path>` — e.g. `--output .result.user.pk`. Scalars emit raw (shell-pipeline friendly). This means you can do:
```bash
pk=$(task ops run accounts:users.create_user --kw email=x@y.com --kw password=abc \
     --output .result.user.pk)
task ops run requests:requests.create_request --kw reporter=$pk --kw title="Hello"
```

### Batch recipe example (`seed_minimal_team.json`)
```json
{
  "atomic": true,
  "allow_sensitive": true,
  "steps": [
    {"name": "owner_account", "op": "accounts:users.create_user", "input": {...}},
    {"name": "team", "op": "accounts:accounts.create_team_account", "input": {"name": "Seed Team"}},
    {"name": "owner_membership", "op": "accounts:memberships.create_membership", "input": {
      "account": "{{team.pk}}",
      "user": "{{owner_account.user.pk}}",
      "role": "owner"
    }},
    {"name": "first_request", "op": "requests:requests.create_request", "input": {
      "account": "{{team.pk}}",
      "reporter": "{{owner_account.user.pk}}",
      "title": "Welcome"
    }},
    {"name": "welcome_doc", "op": "docs:docs.create_doc", "input": {
      "account": "{{team.pk}}",
      "author": "{{owner_account.user.pk}}",
      "title": "Welcome"
    }}
  ]
}
```
Five steps, one atomic transaction, PKs threaded automatically. If any step fails, the whole thing rolls back.

### Sensitive variable handling
Ops decorated with `@sensitive_variables(...)` are blocked unless you pass `--allow-sensitive`. Named sensitive params are always redacted in `resolved_inputs` — never leaks into logs.

### Extensibility
- `OPS_RUNNER_APPS` — restrict discovery to certain app labels
- `OPS_RUNNER_COERCERS` — plug in custom type coercers for your domain types
- `@not_an_op` — exclude a public function from CLI discovery

---

## The Query CLI (`python manage.py query`)

**Big idea:** The ops layer is for writes; the query CLI is for reads. Same JSON-first, selector-friendly surface, reusing ops infrastructure under the hood.

### Five subcommands

| Subcommand | What it does |
|---|---|
| `query models` | List every queryable model: address, verbose name, field count. The agent "what can I read?" surface. |
| `query fields <app.model>` | Describe a model's fields: name, Django type, required, relation flag, and whether it's blocklisted. |
| `query list <app.model>` | Enumerate rows. Supports `--where` (DjangoQL) or `--filter` (ORM `__` lookups), `--fields`, `--order-by`, `--limit`, `--deep`. |
| `query count <app.model>` | Cheap `COUNT(*)` — no row serialization. Ideal for agent state audits. |
| `query get <app.model> <pk>` | Single row. Exits 1 with a structured error if the row doesn't exist. |

### `--where` vs `--filter`

| | `--where` | `--filter` |
|---|---|---|
| Syntax | DjangoQL expression (same language as Django admin) | `key__lookup=JSON-value` flags |
| Best for | Ad-hoc human debugging, complex conditions | Scripts, agents, programmatic flows |
| Mutual exclusion | Yes — can't use both at once | Yes |

Example: `query list requests.request --where "status = 'triage' and account.name = 'Acme'" --output .rows[0].pk`

### Sensitive field blocklist
Default patterns: `password`, `secret`, `token`, `hash`. Applied at both projection and serialization. Per-model overrides via `QUERY_COMMAND_BLOCKLIST`. Per-invocation escape with `--allow-field <name>`. Every redaction appears in `warnings`.

### Composability with ops
The docs explicitly show this pattern:
```bash
acct=$(task query list accounts.account --filter account_type=team \
       --output '.rows[0].pk' --limit 1)
task ops run requests:requests.create_request \
  --kw account=$acct --kw reporter=7 --kw title="Onboard"
```
Query reads state → scalar sliced out → piped into an ops write. No intermediate parsing.

---

## What's Most Interesting for Engram Tasks

Given where the `bb-ai-task-platform` project is (MVP scoped, deciding which phase to build first), here's where the CLI becomes directly useful:

**1. Agent introspection loop.** An Engram harness tool could wrap `ops list --emit-schema` and `query fields` to let the agent prime its context before deciding what to call — no hardcoded op lists needed. The CLI is the discovery surface.

**2. Batch recipes as agent-authored scripts.** The batch system (JSON recipe + interpolation) is essentially a tiny typed scripting language the agent can emit. An agent session that needs to create a task + attach memory metadata + log an activity could produce and run a recipe atomically, rather than issuing three separate round-trips.

**3. `ops repl` for interactive debugging.** When building the new `backend.tasks` app, the REPL is immediately useful for manual smoke tests without opening Django shell. `$last` bindings make sequential op testing fast.

**4. Query CLI for agent state audits.** Mid-session, an Engram agent can call `query count tasks.taskactivity --filter session_id=<X>` or `query list tasks.taskagentcomment --filter task_id=<Y>` to audit what it previously wrote. Clean structured JSON, no shell_plus dance.

**5. The blocklist is the right model for Engram proxy safety.** When the engram_proxy writes knowledge file paths to Postgres, `QUERY_COMMAND_BLOCKLIST` lets you redact sensitive fields (API keys in metadata, etc.) from any CLI query — same pattern Engram uses for sensitive_variables in ops.

---

What do you want to dig into? The batch recipe system for multi-step Engram ops, how to wire a harness tool that calls these CLIs, or something about the actual `backend.tasks` app structure?

## Tool usage

- `work_status`: 1
- `memory_context`: 1
- `work_project_status`: 1
- `memory_recall`: 1
- `spawn_subagent`: 1
- `spawn_subagents`: 1

## Subagent runs

- **subagent-001** (14 turns, 41 tool calls, $2.0474):
  Task: 'Survey the Better Base codebase for CLI-related code — specifically the Ops Runner CLI and Query CLI. The repo is at C:\\Users\\Owner\\code\\personal\\better-base (or similar path). Search the workspace fo'
  Tools: read_file(27), list_files(6), glob_files(6), grep_workspace(2)
- **subagent-002** (4 turns, 5 tool calls, 2 errors, $0.1226):
  Task: 'Read the file at `backend/base/ops_runner/batch.py` in the Better Base repo at C:\\Users\\Owner\\code\\personal\\better-base. Also read `backend/base/ops_runner/recipes/seed_minimal_team.json`. Return the'
  Tools: read_file(4), list_files(1)
- **subagent-003** (11 turns, 35 tool calls, 7 errors, $0.8743):
  Task: 'Find and read the agent docs/notes for the Better Base CLI. Look in: `docs/agent-notes/topics/ops-runner-cli.md` and `docs/agent-notes/topics/query-cli.md` inside C:\\Users\\Owner\\code\\personal\\better-b'
  Tools: read_file(23), list_files(5), glob_files(4), path_stat(3)

## Memory recall

- memory/activity/2026/04/27/act-005/summary.md ← 'Better Base ops CLI query CLI agent integration' (trust=medium score=29.440)
- memory/activity/2026/04/28/act-001/summary.md ← 'Better Base ops CLI query CLI agent integration' (trust=medium score=22.013)
- memory/activity/2026/04/28/act-002/summary.md ← 'Better Base ops CLI query CLI agent integration' (trust=medium score=18.768)
- memory/activity/2026/04/27/act-004/summary.md ← 'Better Base ops CLI query CLI agent integration' (trust=medium score=16.884)
- memory/activity/2026/05/04/act-001/summary.md ← 'Better Base ops CLI query CLI agent integration' (trust=medium score=15.591)