---
source: agent-generated
trust: medium
created: 2026-03-26
origin_session: memory/activity/2026/03/26/chat-002
title: "Phase 4 Design: External Tool Registry"
---

# Phase 4 Design: External Tool Registry

## Motivation

The harness report recommends treating tools as an API product: "clear schemas, compact outputs, namespacing." Engram has 73 well-designed MCP tools for memory operations, but agents also use external tools — shell commands, APIs, code execution — that Engram knows nothing about. This means:

- No way to express tool policies (which tools require approval, cost caps, rate limits) in a machine-readable form.
- Plan phases reference tools implicitly through postconditions (`test` type) or changes (descriptions mentioning APIs), but there's no formal registry.
- The harness can't advise agents on tool constraints because it doesn't know what tools are available.

This phase adds a **policy storage layer** for external tools. Engram does not execute these tools — it stores their definitions and policies so agents and orchestrators can query constraints before acting.

---

## Extension 1: ToolDefinition schema

### Problem

There's no structured way to describe an external tool — its inputs, approval requirements, cost, or limitations.

### Design

```python
@dataclass(slots=True)
class ToolDefinition:
    """Metadata and policy for an external tool."""
    name: str                     # Unique tool identifier (slug format)
    description: str              # What the tool does
    provider: str                 # Grouping key: "shell", "api", "mcp-external", etc.
    schema: dict | None = None    # JSON Schema for tool inputs (optional)
    approval_required: bool = False
    cost_tier: str = "free"       # free | low | medium | high
    rate_limit: str | None = None # Human-readable rate limit ("10/min", "100/day")
    timeout_seconds: int = 30     # Default timeout for execution
    tags: list[str] = field(default_factory=list)
    notes: str | None = None      # Usage notes, gotchas, warnings
```

### Cost tiers

| Tier | Meaning | Examples |
|---|---|---|
| `free` | No cost per invocation | File reads, local shell commands, memory tools |
| `low` | Negligible cost (< $0.01) | Simple API calls with free tier |
| `medium` | Non-trivial cost ($0.01–$1.00) | LLM API calls, paid API endpoints |
| `high` | Significant cost (> $1.00) | Large model calls, batch processing, cloud compute |

### Validation rules

- `name` must be a valid slug (alphanumeric + hyphens).
- `cost_tier` must be one of `{free, low, medium, high}`.
- `timeout_seconds` must be >= 1.
- `tags` are optional, validated as non-empty strings.
- `schema` is optional; when present, must be a valid JSON object (not validated as JSON Schema — that's the consumer's responsibility).

---

## Extension 2: Registry storage

### Problem

Where should tool definitions live in the memory structure?

### Design

New directory: `core/memory/skills/tool-registry/`

```
core/memory/skills/tool-registry/
├── SUMMARY.md              # Registry navigator (auto-generated)
├── shell.yaml              # Shell commands (pre-commit, pytest, ruff, etc.)
├── mcp-external.yaml       # External MCP servers (if any)
└── api.yaml                # API endpoints (if any)
```

Each file contains a list of tool definitions grouped by provider:

```yaml
# shell.yaml
provider: shell
tools:
  - name: pre-commit-run
    description: Run pre-commit hooks on all files
    approval_required: false
    cost_tier: free
    timeout_seconds: 60
    tags: [lint, format, validate]

  - name: pytest-run
    description: Run pytest test suite
    approval_required: false
    cost_tier: free
    timeout_seconds: 120
    tags: [test, validate]
    schema:
      type: object
      properties:
        args:
          type: string
          description: Additional pytest arguments
```

### Why `skills/tool-registry/` and not `tools/registry/`?

- `core/tools/` contains Python implementation code. Tool definitions are data, not code.
- `core/memory/skills/` is the designated location for capability documentation — tool definitions are a natural extension.
- This location is access-tracked via `skills/ACCESS.jsonl`, giving us usage data for free.
- Consistent with Engram's principle: memory stores facts about the world; code implements operations on those facts.

---

## Extension 3: `memory_register_tool` — Tool registration

### Problem

Agents need a way to register tools they discover or use.

### Design

New MCP tool: `memory_register_tool`

```
Parameters:
  name: str              — tool identifier (slug)
  description: str       — what the tool does
  provider: str          — grouping key
  schema: dict | null    — JSON Schema for inputs
  approval_required: bool = false
  cost_tier: str = "free"
  rate_limit: str | null
  timeout_seconds: int = 30
  tags: list[str] = []
  notes: str | null

Returns: MemoryWriteResult with new_state containing:
  tool_name: str
  registry_file: str     — path to the provider's registry file
  action: str            — "created" | "updated"
```

### Behavioral contract

- If a tool with the same name already exists in the provider file, it is **updated** (not duplicated).
- If the provider file doesn't exist, it is created.
- Registration is a proposed-tier change: the agent presents the registration and waits for approval before committing.
- SUMMARY.md is regenerated after each registration.

---

## Extension 4: `memory_get_tool_policy` — Policy queries

### Problem

Before using an external tool, an agent (or orchestrator) should check its policy: does it require approval? What's the cost? What's the timeout?

### Design

New MCP tool: `memory_get_tool_policy`

```
Parameters:
  tool_name: str | null    — exact tool name (single query)
  provider: str | null     — filter by provider (bulk query)
  tags: list[str] | null   — filter by tags (any match)
  cost_tier: str | null    — filter by cost tier

Returns: dict containing:
  tools: list[dict]        — matching tool definitions
  count: int
```

At least one filter parameter is required. If `tool_name` is provided, returns at most one result. Otherwise returns all matching tools.

### Behavioral contract

- Read-only: no state changes.
- Returns empty list if no tools match (not an error).
- Cost tier and approval requirements are returned as-is — the agent/orchestrator decides whether to proceed.

---

## Extension 5: Tool policy integration with plan phases

### Problem

When a plan phase references tools (via postconditions or changes), the agent should know the relevant policies without a separate lookup.

### Design

If a phase has `test`-type postconditions, `phase_payload()` includes the tool policy for any registered tool that matches the postcondition target:

```python
def phase_payload(plan, phase, root):
    payload = {
        # ... existing fields ...
        "tool_policies": _resolve_tool_policies(phase, root),
    }
    return payload
```

The `_resolve_tool_policies` helper:
1. Scans postcondition targets for command names.
2. Looks up matching tools in the registry.
3. Returns a list of `{tool_name, approval_required, cost_tier, timeout_seconds}` dicts.

This is best-effort: unregistered tools are silently skipped. The field is empty if no matches are found.

---

---

## Finalized design decisions (2026-03-26)

**Decision 1: Storage — one file per provider (confirmed)**
`core/memory/skills/tool-registry/` with `shell.yaml`, `api.yaml`, `mcp-external.yaml`. Provider grouping rather than one-file-per-tool keeps the YAML scannable and makes bulk queries cheap (read one file to get all shell tools).

**Decision 2: Default seed tools — seed `shell.yaml` with three definitions**
Pre-populate with `pre-commit-run` (timeout 60s, tags [lint, format, validate]), `pytest-run` (timeout 120s, tags [test, validate]), `ruff-check` (timeout 30s, tags [lint, format]). All `free` tier, no approval required. Immediately useful for Phase 5 tool-policy integration.

**Decision 3: Registration writes immediately (no async approval gate)**
`memory_register_tool` writes on call and returns `action: "created" | "updated"`. The `approval_required` field in the tool definition describes invocation policy for orchestrators, not registration policy. Consistent with all other Tier 1 semantic tools.

**Decision 4: `memory/skills/` path policy — Tier 1 semantic tool bypass**
`memory/skills/` is in `_PROTECTED_ROOTS`, blocking raw Tier 2 writes. `memory_register_tool` writes directly to the filesystem as a Tier 1 semantic tool, the same pattern used by plan_tools.py and session_tools.py.

**Decision 5: `phase_payload` tool policy matching — normalized slug comparison**
For `test`-type postconditions, extract the command prefix from the target field and normalize to a slug (e.g., `"pre-commit run --all-files"` → `"pre-commit-run"`, `"pytest-run"`, `"ruff-check"`). Matching uses normalized slug comparison. Best-effort — no match yields `tool_policies: []`.

---

## What this phase does NOT include

- **Tool execution.** Engram stores tool metadata and policies. It does not execute external tools (except `test` postconditions in Phase 2).
- **Tool discovery.** The registry is populated by agents registering tools they use. There's no automated tool discovery from MCP server introspection or environment scanning.
- **Rate limit enforcement.** Rate limits are stored as human-readable strings for documentation. Enforcement is the orchestrator's responsibility.
- **Tool versioning.** Tool definitions don't track versions. If a tool's schema changes, the definition is updated in place.
- **Multi-agent tool sharing.** The registry is per-worktree. Multi-worktree sharing is out of scope.
