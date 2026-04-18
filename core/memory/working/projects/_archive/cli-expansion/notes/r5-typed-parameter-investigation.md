---
source: agent-generated
origin_session: memory/activity/2026/04/02/chat-001
created: 2026-04-02
trust: medium
type: design-note
---

# R5 Investigation: Typed MCP Parameters in FastMCP

## Summary

Typed nested parameters are viable in the current FastMCP stack, but they are not a drop-in replacement for the explicit `plan_create_input_schema()` helper yet.

In this environment:

- `mcp` version is `1.26.0`
- FastMCP already builds tool schemas through Pydantic-backed models in `mcp.server.fastmcp.utilities.func_metadata`
- nested `TypedDict` and `BaseModel` inputs produce nested JSON Schema automatically, including `$defs` references and enum values
- runtime validators do **not** become conditional JSON Schema automatically
- conditional requirements can still be expressed, but only by adding explicit `json_schema_extra` metadata to the typed models

## Evidence

### 1. FastMCP already supports nested typed inputs

`Tool.from_function()` builds its parameter schema from `func_metadata(...).arg_model.model_json_schema(...)`.

The implementation in `mcp.server.fastmcp.utilities.func_metadata` explicitly handles:

- `BaseModel` subclasses directly
- `TypedDict` via `_create_model_from_typeddict()`
- nested generic containers like `list[...]` and `dict[...]`

Prototype result from this session:

- nested `TypedDict` fields generated `$defs` entries for `SourceSpec`, `ChangeSpec`, and `PhaseSpec`
- `Literal[...]` fields became JSON Schema `enum` values automatically
- nested `BaseModel` fields were also emitted correctly inside the argument schema

This means the original R5 premise was correct: typed inputs can surface the nested structure that `list[dict[str, Any]]` currently erases.

### 2. Conditional validators do not show up in schema automatically

A prototype `BaseModel` with:

- `type: Literal["internal", "external", "mcp"]`
- `uri: str | None = None`
- a `@model_validator(mode="after")` enforcing `uri` for `external`

did validate correctly at runtime, but the generated JSON Schema only contained ordinary field definitions and required keys. It did **not** emit the `if/then` conditional requirement.

This matters because the current explicit schema helper encodes conditions like:

- `uri` required when `type = external`
- `mcp_server` and `mcp_tool` required when `type = mcp`
- `target` required when `postcondition.type != manual`

If we migrated to typed parameters alone, callers would regain nested enums and field structure, but they would lose some of the machine-visible conditional guidance unless we added manual schema extras.

### 3. Manual schema extras can restore those conditions

Adding `ConfigDict(json_schema_extra={...})` to a `BaseModel` successfully injected custom `allOf` / `if` / `then` JSON Schema clauses into the generated output.

So typed parameters plus explicit schema extras can reach parity with the current helper in principle.

## Compatibility assessment

### What looks safe

- Callers already send JSON objects; Pydantic-backed typed inputs still accept dict-shaped payloads.
- Nested enums and field descriptions become visible to MCP clients automatically.
- A phased migration could keep top-level behavior mostly stable while replacing `dict[str, Any]` signatures with typed objects.

### What would still need care

- **Aliases.** The current UX hardening normalizes caller guesses like `modify -> update`, `code -> internal`, and `file_check -> check`. Typed models do not provide those semantics automatically.
- **Conditional schema.** Runtime validation is not enough if the goal is discoverable MCP JSON Schema; conditional rules still need explicit schema extras.
- **Error text.** Pydantic/FastMCP error formatting will not match the current aggregated Engram-specific messages unless we keep custom coercion and aggregation logic in front of the typed models or adapt the error layer.
- **Unknown keys.** BaseModel defaults can ignore extras, but if we tighten models later the behavior could become stricter than today's permissive dict ingestion.
- **Migration blast radius.** Swapping function signatures changes the MCP-generated schema directly and could affect tests, tool consumers, and any host-side expectations built around current parameter shapes.

## Recommendation

Do **not** replace `plan_create_input_schema()` with typed FastMCP parameters in the next batch.

Instead:

1. Keep the explicit schema helper as the authoritative contract for `memory_plan_create` in the near term.
2. Treat typed parameters as a **schema-generation and validation simplification opportunity**, not as a full replacement for the helper.
3. If migration becomes worthwhile, use a phased approach:

   - define internal typed input models first
   - prove schema parity against `plan_create_input_schema()` with tests
   - preserve alias normalization and aggregated Engram-style error reporting
   - add `json_schema_extra` only where conditional requirements must stay visible
   - switch the public tool signature only after the schema and error surface are demonstrably equivalent enough

## Bottom line

R5 is technically viable, but only as a **coexistence strategy** at first.

Typed parameters can recover nested structure and enums automatically in FastMCP 1.26.0. They do **not** eliminate the need for explicit schema enrichment, alias handling, or Engram-specific aggregated validation. The right next step is a small prototype migration behind equivalence tests, not a direct replacement of the current explicit schema helper.
