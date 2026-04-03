---
source: agent-generated
origin_session: memory/activity/2026/04/02/chat-001
created: 2026-04-02
trust: medium
type: design-note
---

# MCP Tool Schema Discoverability Audit

## Remediation status (April 2026)

Follow-up from the internal MCP tools review:

| Area | What changed |
| --- | --- |
| **`memory_tool_schema` scope** | Documented in [`HUMANS/docs/MCP.md`](../../../../../../HUMANS/docs/MCP.md) (JSON Schema registry section) and [`core/tools/agent_memory_mcp/tools/read_tools/_capability.py`](../../../../../../core/tools/agent_memory_mcp/tools/read_tools/_capability.py). Registry file: [`tool_schemas.py`](../../../../../../core/tools/agent_memory_mcp/tool_schemas.py) (`TOOL_INPUT_SCHEMAS`). |
| **Registry expansion** | Tier 2: `memory_write`, `memory_edit`, `memory_delete`, `memory_move`, `memory_commit`. Tier 0: `memory_read_file`, `memory_extract_file`, `memory_search`, `memory_context_home`, `memory_context_project`. |
| **`memory_plan_execute` docs** | MCP tool docstring and `execute_plan_action_result` document actions vs `blocked` state and conditional fields ([`plan_tools.py`](../../../../../../core/tools/agent_memory_mcp/tools/semantic/plan_tools.py)). |
| **`memory_log_access_batch`** | Docstring + batch validation with `aggregate_validation_errors` ([`session_tools.py`](../../../../../../core/tools/agent_memory_mcp/tools/semantic/session_tools.py)). |
| **Manifest / runtime drift** | [`test_memory_mcp.py`](../../../../../../core/tools/tests/test_memory_mcp.py) checks `declared_not_in_runtime` (manifest tools missing from MCP registration), treating `raw_fallback` as optional when `MEMORY_ENABLE_RAW_WRITE_TOOLS` is unset. |
| **`memory_plan_create` aggregation** | `build_plan_document_from_create_input` and `_coerce_phases` already collect errors across top-level fields and phases; regression: `test_build_plan_document_aggregates_errors_across_multiple_phases` in [`test_plan_validation.py`](../../../../../../core/tools/tests/test_plan_validation.py). |
| **Semantic search extras** | MCP.md clarifies tools are always registered; `pip install -e ".[search]"` (or `agent-memory-mcp[search]`) needed for full behavior. |

The sections below are the original audit snapshot (some line references and metrics may be stale).

## Context

The plan-tool-ux-improvements note identified schema discoverability as the root cause of the `memory_plan_create` retry loop. This audit examines the full Engram MCP tool surface to determine how widespread the problem is. Findings inform both the CLI expansion (which will expose these same operations) and a potential cross-cutting improvement to tool descriptions.

---

## Methodology

Audited every `@mcp.tool()` registration in:
- `tools/semantic/plan_tools.py` (plans, traces)
- `tools/semantic/session_tools.py` (access logging, sessions, checkpoints)
- `tools/semantic/knowledge_tools.py` (knowledge lifecycle, reviews)
- `tools/semantic/graph_tools.py` (link management)
- `tools/semantic/user_tools.py` (user traits)
- `tools/semantic/skill_tools.py` (skill updates)
- `tools/read_tools/*.py` (Tier 0 read tools)
- `tools/write_tools.py` (Tier 2 raw writes)

For each tool, checked: (1) whether enum constraints are documented in the docstring, (2) whether conditional required fields are documented, (3) whether `dict[str, Any]` parameters have their inner structure documented, and (4) whether validation is fail-fast or accumulating.

---

## Findings by Severity

### Critical: Missing or incomplete docstrings

**`memory_log_access_batch`** (session_tools.py:1631) — has **no docstring at all**. Accepts `access_entries: list[dict[str, object]]` with completely undocumented inner structure. An agent calling this tool has no way to know what fields to include. The single-entry sibling `memory_log_access` defines the schema via its function signature (file, task, helpfulness, note, plus optional session_id, category, mode, task_id, estimator, min_helpfulness), but the batch version erases all of that into an opaque dict list.

**`memory_plan_execute`** (plan_tools.py:440) — docstring mentions actions "inspect, start, block, complete, or record failure" but `"block"` is **not a valid action value**. The actual enum is `{"inspect", "start", "complete", "record_failure"}`. Blocked is an automatic state transition, not a user-selectable action. This is actively misleading. Additionally:
- The `review` parameter is mentioned nowhere in the docstring but is conditionally used when completing a plan
- The `verification_results` parameter structure is undocumented
- `session_id` is required for start/complete/record_failure but optional for inspect — not documented

**`memory_record_session`** (session_tools.py:1682) — accepts `access_entries: list[dict[str, object]] | None` with minimal documentation. References ACCESS entries but doesn't specify the expected fields.

### High: Undocumented enum constraints

| Tool | Parameter | Valid values | Documented? |
|---|---|---|---|
| `memory_plan_create` | `phases[*].sources[*].type` | `internal`, `external`, `mcp` | No |
| `memory_plan_create` | `phases[*].postconditions[*].type` | `check`, `grep`, `test`, `manual` | No |
| `memory_plan_create` | `phases[*].changes[*].action` | `create`, `rewrite`, `update`, `delete`, `rename` | No |
| `memory_plan_execute` | `action` | `inspect`, `start`, `complete`, `record_failure` | Incorrect |
| `memory_promote_knowledge_batch` | `trust_level` | `medium`, `high` | No |
| `memory_mark_reviewed` | `verdict` | `approve`, `reject`, `defer` | No |
| `memory_resolve_approval` | `resolution` | `approve`, `reject` | No |
| `memory_flag_for_review` | `priority` | `normal`, `urgent` | No |
| `memory_update_user_trait` | `mode` | `upsert`, `append`, `replace` | No |
| `memory_update_skill` | `mode` | `upsert`, `append`, `replace` | No |

### Medium: Undocumented conditional requirements

| Tool | Condition | Required field |
|---|---|---|
| `memory_plan_create` | `source.type == "external"` | `source.uri` |
| `memory_plan_create` | `source.type == "mcp"` | `source.mcp_server` + `source.mcp_tool` |
| `memory_plan_create` | `postcondition.type != "manual"` | `postcondition.target` |
| `memory_plan_execute` | `action in {start, complete, record_failure}` | `session_id` |
| `memory_plan_execute` | `action == "record_failure"` | `reason` |

### Positive: Well-documented tools (models to follow)

**`memory_record_trace`** (plan_tools.py:1433) — docstring clearly lists `span_type` values (`tool_call`, `plan_action`, `retrieval`, `verification`, `guardrail_check`) and `status` values (`ok`, `error`, `denied`). This is what good looks like.

**`memory_prune_weak_links`** (graph_tools.py:181) — docstring documents the `signal` parameter values (`structural`, `access`, `combined`).

**`memory_update_frontmatter_bulk`** (write_tools.py:533) — docstring clearly documents the entry structure (path, fields, version_token). Also the **only tool that accumulates validation errors** instead of failing fast — it collects all bad entries before raising a single error. This is the model for batch operations.

---

## Validation Pattern Analysis

### Current state

| Pattern | Tools using it | Example |
|---|---|---|
| Fail-fast (raise on first error) | ~15 tools | `memory_plan_create`, `memory_plan_execute`, `memory_mark_reviewed` |
| Error accumulation (collect all errors) | 1 tool | `memory_update_frontmatter_bulk` |
| No validation (pass-through) | ~3 tools | Some read-only tools with simple params |

The overwhelming pattern is fail-fast. `memory_update_frontmatter_bulk` is the lone exception, and it's notably the one that feels best to call with batch input — you learn about all problems at once.

### Impact

For tools with a single enum parameter (like `memory_mark_reviewed`), fail-fast is fine — there's only one thing that can be wrong. For tools with deeply nested structures (like `memory_plan_create`), fail-fast creates the retry cascade documented in plan-tool-ux-improvements.md.

**Recommendation:** Accumulation should be the default for any tool that accepts a list of items or nested structured input. Fail-fast is acceptable for tools with flat, simple parameters.

---

## The `dict[str, Any]` Problem

Nine tools accept `dict[str, Any]` or `list[dict[str, Any]]` parameters where the inner structure is invisible at the MCP JSON Schema level:

| Tool | Parameter | Inner fields |
|---|---|---|
| `memory_plan_create` | `phases` | sources, postconditions, changes, failures, blockers |
| `memory_plan_create` | `budget` | deadline, max_sessions, advisory |
| `memory_plan_execute` | `review` | Undocumented |
| `memory_plan_execute` | `verification_results` | Undocumented |
| `memory_log_access_batch` | `access_entries` | file, task, helpfulness, note, + optional fields |
| `memory_record_session` | `access_entries` | Same as above |
| `memory_update_frontmatter_bulk` | `updates` | path, fields, version_token |
| `memory_request_approval` | `context` | Appears to be freeform dict |
| Various graph tools | `options` dicts | Varies by tool |

This is the deepest structural issue. No matter how good the docstring is, agents that rely on JSON Schema auto-generation (which many MCP hosts use for tool-calling prompts) will see `"type": "object"` with no properties defined. The docstring helps, but only if the agent (or its host) actually reads and incorporates docstrings into the tool-calling prompt.

---

## Recommendations

### Tier 1: Immediate docstring fixes (< 1 session)

Fix the 10 tools with undocumented enums by adding valid values to their docstrings. This is pure text editing with zero code risk. Prioritize by usage frequency:

1. `memory_plan_create` — add full nested schema (sources, postconditions, changes)
2. `memory_plan_execute` — fix the incorrect "block" action, add conditional requirements
3. `memory_log_access_batch` — add a docstring (it has none)
4. `memory_mark_reviewed` — add verdict values
5. `memory_update_user_trait` / `memory_update_skill` — add mode values
6. `memory_promote_knowledge_batch` — add trust_level values
7. `memory_resolve_approval` — add resolution values
8. `memory_flag_for_review` — add priority values
9. `memory_record_session` — add access_entries structure

### Tier 2: Validation improvements (1–2 sessions)

Switch batch/nested tools to error accumulation:
- `memory_plan_create` (the highest-impact target — documented in plan-tool-ux-improvements.md)
- `memory_log_access_batch`
- `memory_record_session`

Follow the pattern already established by `memory_update_frontmatter_bulk`.

### Tier 3: Schema introspection (1 session)

Add `memory_tool_schema(tool_name)` — a single Tier 0 tool that returns the full nested JSON Schema for any named tool. This is a one-time investment that benefits every tool automatically, including future ones.

### Tier 4: Typed parameters (investigation)

Investigate whether FastMCP can generate nested JSON Schema from TypedDict or Pydantic models instead of `dict[str, Any]`. If so, migrate the most complex tools (plan_create, plan_execute) first. This eliminates the problem at the source — the schema becomes part of the MCP protocol, not just the docstring.

---

## Metrics

- **Tools with at least one undocumented enum:** 10 out of ~90 total tools (~11%)
- **Tools with `dict[str, Any]` hiding inner structure:** 9 tools
- **Tools with incorrect documentation:** 1 (`memory_plan_execute` lists "block" as valid action)
- **Tools with no docstring:** 1 (`memory_log_access_batch`)
- **Tools using error accumulation:** 1 out of ~15 that validate (`memory_update_frontmatter_bulk`)

The problem is concentrated in the Tier 1 semantic write tools — the tools agents call most often for real work. Tier 0 read tools and Tier 2 raw tools are generally well-documented or simple enough that documentation isn't critical.
