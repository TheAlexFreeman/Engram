---
source: agent-generated
origin_session: memory/activity/2026/04/02/chat-001
created: 2026-04-02
trust: medium
type: design-note
---

# Plan Tool UX Improvements for Agent Callers

## Context

During the creation of the `cli-v0` plan, `memory_plan_create` rejected four consecutive calls before accepting the fifth. Each rejection surfaced a single validation error, requiring a blind guess-and-retry loop. This note catalogs the specific failure modes, traces them to the validation architecture, and proposes improvements that would benefit both the plan tool and the broader MCP surface.

These recommendations apply to any Engram MCP tool that accepts complex nested input — `memory_plan_create` is just the most complex current example.

---

## Failure Transcript

| Attempt | Error | Root cause |
|---|---|---|
| 1 | `source type must be one of ['external', 'internal', 'mcp']: 'code'` | Agent guessed `"code"` for source type; valid values not in tool description |
| 2 | `postcondition type must be one of ['check', 'grep', 'manual', 'test']: 'file_check'` | Agent guessed `"file_check"`; valid values not in tool description |
| 3 | `postcondition type 'test' requires a non-empty target` | Conditional required field not documented; only discovered after fixing type |
| 4 | `change action must be one of ['create', 'delete', 'rename', 'rewrite', 'update']: 'modify'` | Agent guessed `"modify"` (a common synonym of `"update"`); valid values not in tool description |
| 5 | Success | All constraints satisfied by trial and error |

Total round-trips wasted: 4 (each involving full JSON serialization of the plan).
Token cost of retries: ~12,000 tokens of repeated payload across the failed attempts.

---

## Root Cause Analysis

### 1. Tool description does not surface nested enum constraints

The `memory_plan_create` docstring mentions that phases may include sources, postconditions, and changes, and gives a hint at their shape:

```
Phases may include sources (list of {path, type, intent, uri?}),
postconditions (list of strings or {description, type?, target?}),
and requires_approval (bool).
```

But it does not enumerate the valid values for:
- `source.type` → `internal | external | mcp`
- `postcondition.type` → `check | grep | test | manual`
- `change.action` → `create | rewrite | update | delete | rename`

Nor does it document conditional requirements:
- `postcondition.target` is required when `type != "manual"`
- `source.uri` is required when `type == "external"`
- `source.mcp_server` and `source.mcp_tool` are required when `type == "mcp"`

The agent can see the top-level parameter types via the MCP JSON Schema (auto-generated from Python type hints), but `phases: list[dict[str, Any]]` erases all inner structure. The nested schema lives entirely in the dataclass validators in `plan_utils.py`, invisible to the caller.

### 2. Validation is fail-fast, not fail-complete

Each dataclass validates in `__post_init__` and raises `ValidationError` on the first bad field. The coercion pipeline (`_coerce_phases` → `_coerce_source_specs` → `SourceSpec.__post_init__`) short-circuits on the first invalid nested object. This means:

- If phase 1 has a bad source type AND phase 3 has a bad change action, you only learn about the source type.
- After fixing it, you re-submit the entire payload and learn about the change action.
- Each retry re-validates everything from scratch, including the parts that already passed.

### 3. Preview mode is not a soft validator

The `preview: bool = False` parameter suggests a dry-run capability, but preview mode runs the same strict validation pipeline — it just skips the git commit at the end. A plan with validation errors cannot generate a preview. This is architecturally correct (you shouldn't preview an invalid plan), but it means there is no "tell me everything that's wrong" mode.

---

## Recommendations

### R1: Enrich the tool description with nested schemas (high leverage, low risk)

Expand the `memory_plan_create` docstring to include the full enum values and conditional requirements. This is the single highest-impact change because agents read tool descriptions before calling them. A compact format works fine:

```
sources: list of {path, type, intent, uri?, mcp_server?, mcp_tool?, mcp_arguments?}
  type: "internal" | "external" | "mcp"
  uri: required when type="external"
  mcp_server + mcp_tool: required when type="mcp"

postconditions: list of strings (shorthand → manual) or {description, type?, target?}
  type: "check" | "grep" | "test" | "manual" (default "manual")
  target: required when type != "manual"

changes: list of {path, action, description}
  action: "create" | "rewrite" | "update" | "delete" | "rename"
```

This adds ~15 lines to the docstring. Every agent that calls this tool will benefit immediately.

**Applies broadly:** Any MCP tool that accepts `dict[str, Any]` with internal structure should document that structure in its description. This is a general Engram convention worth establishing.

### R2: Collect all validation errors before raising (medium leverage, medium risk)

Change the validation pipeline to accumulate errors instead of failing on the first one. Two approaches:

**Option A: Accumulator pattern in coercion functions.** Modify `_coerce_phases`, `_coerce_source_specs`, etc. to catch `ValidationError` per item, collect them, and raise a single `ValidationError` with all messages at the end:

```python
def _coerce_phases(raw_phases: list[dict]) -> list[PlanPhase]:
    errors: list[str] = []
    phases: list[PlanPhase] = []
    for i, raw in enumerate(raw_phases):
        try:
            phases.append(_coerce_single_phase(raw))
        except ValidationError as e:
            errors.append(f"phase[{i}] ({raw.get('id', '?')}): {e}")
    if errors:
        raise ValidationError(
            f"{len(errors)} validation error(s):\n" + "\n".join(f"  - {e}" for e in errors)
        )
    return phases
```

**Option B: Separate `validate()` pass.** Add a `PlanDocument.validate() -> list[str]` class method that walks the entire structure and returns a list of error strings without raising. The coercion pipeline calls `validate()` after construction and raises if the list is non-empty.

Option A is simpler and more local. Option B is cleaner but requires restructuring the dataclass `__post_init__` logic.

**Risk:** This changes error message format, which could affect tests that assert on specific error strings. Grep for `ValidationError` assertions in the test suite and update them.

### R3: Add a schema introspection tool (medium leverage, low risk)

Register a new Tier 0 read-only tool:

```python
@mcp.tool(name="memory_plan_schema")
async def memory_plan_schema() -> str:
    """Return the full JSON Schema for plan creation input, including
    all nested object schemas, enum constraints, and conditional
    requirements. Use this before calling memory_plan_create to
    understand the expected input shape."""
```

This tool would return a static JSON Schema document derived from the dataclass definitions. It's zero-risk (read-only, no side effects) and lets agents self-serve the schema on demand rather than discovering it through errors.

**Broader pattern:** This could generalize to `memory_tool_schema(tool_name)` that returns the full input schema for any Engram MCP tool, including nested structures that `dict[str, Any]` type hints erase.

### R4: Make preview mode a soft validator (low leverage, low risk)

When `preview=True`, catch validation errors and include them in the preview response instead of raising:

```python
if preview:
    try:
        plan = PlanDocument(...)
    except ValidationError as e:
        return {"preview": True, "valid": False, "errors": str(e).split("\n")}
    return {"preview": True, "valid": True, "plan": plan.to_dict(), ...}
```

This turns preview into a "tell me what's wrong" mode. The non-preview path stays strict.

**Why lower leverage than R1–R3:** If the description is good (R1) and agents can introspect the schema (R3), they shouldn't need to validate by trial and error. But this is still a nice safety net.

### R5: Use typed parameters instead of `dict[str, Any]` where MCP supports it (high leverage, higher risk, longer term)

The root cause of the schema invisibility is that `phases: list[dict[str, Any]]` erases all type information at the MCP JSON Schema level. If MCP's JSON Schema generation supports nested object schemas (via TypedDict, Pydantic models, or inline JSON Schema annotations), switching to typed parameters would make the full schema visible in the tool's auto-generated JSON Schema — no docstring maintenance needed.

This is the most architecturally clean solution but requires:
- Verifying that the MCP library (FastMCP) can generate nested JSON Schema from Python type structures
- Migrating from `dict[str, Any]` to typed input models
- Ensuring backward compatibility (agents currently pass raw dicts)

Worth investigating but not a quick fix.

### R6: Standardize natural-language-friendly enum values (low leverage, low risk)

Some enum values are surprising when you don't have the list in front of you:
- `"rewrite"` vs `"update"` — both sound like "modify" to an agent guessing. Consider adding `"modify"` as an alias for `"update"` in the coercion layer.
- `"check"` for postconditions is ambiguous (check what?). It maps to a shell command check, but `"command"` or `"shell"` would be more discoverable.

This is a minor polish, but every eliminated synonym guess saves a round-trip. Aliases can be handled in the coercion functions without changing the canonical stored values.

---

## Broader Applicability

These patterns aren't specific to `memory_plan_create`. Any MCP tool that accepts structured nested input faces the same discoverability problem. Recommendations R1 (rich descriptions), R2 (error accumulation), and R3 (schema introspection) should be treated as conventions for the entire Engram MCP surface:

- **R1 convention:** Every tool that accepts `dict[str, Any]` must document the inner schema in its docstring, including enum values and conditional requirements.
- **R2 convention:** Validation of list inputs should accumulate errors across items rather than failing on the first.
- **R3 convention:** Complex tools should have a companion `_schema` introspection tool, or a single `memory_tool_schema(tool_name)` tool should exist for the whole surface.

---

## Implementation Priority

| Recommendation | Impact | Effort | Risk | Priority |
|---|---|---|---|---|
| R1: Enrich tool descriptions | High | Low (docstring edits) | None | **Do first** |
| R2: Accumulate validation errors | Medium | Medium (coercion refactor) | Low (test updates) | Second |
| R3: Schema introspection tool | Medium | Low (new read-only tool) | None | Third |
| R4: Soft preview validation | Low | Low | None | Nice-to-have |
| R5: Typed MCP parameters | High | High (migration) | Medium | Investigate |
| R6: Enum aliases | Low | Low | None | Nice-to-have |

R1 alone would have prevented 3 of the 4 failures in this session. R1 + R2 together would have reduced 4 retries to at most 1.

---

## Relevance to CLI Expansion

The `engram plan create` CLI command (v3 roadmap) will face this same problem in a different form: how do you let a user or script author a valid plan from the terminal? The CLI will need either a guided interactive mode or excellent `--help` output that documents the full schema. The improvements above (especially R1 and R3) directly inform the CLI's design — the schema introspection tool could power `engram plan create --help` dynamically.
