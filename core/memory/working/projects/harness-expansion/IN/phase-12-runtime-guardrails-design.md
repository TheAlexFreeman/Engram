---
source: agent-generated
trust: medium
origin_session: memory/activity/2026/03/27/chat-003
created: 2026-03-27
title: "Phase 12: Runtime Guardrails Design — Guard Pipeline Architecture"
---

# Phase 12: Runtime Guardrails Design

## Motivation

The deep research report calls for guardrails as a "parallel control plane" — cheap checks that run before expensive operations, validating inputs/outputs and routing based on policy. Currently, Engram's guardrails are:

- **path_policy.py** — directory-level write protection (protected roots, raw mutation roots)
- **Prose governance** — content-boundaries.md defines trust rules, but these aren't enforced in code
- **frontmatter_utils.py** — can parse frontmatter but doesn't validate schema on writes

This design centralizes validation into a `GuardPipeline` with pluggable guards.

## Design Constraints

1. **Synchronous in write path.** Guards run inline before writes, not as async hooks. Immediate feedback is more valuable than post-hoc detection.
2. **Short-circuit on block.** When any guard blocks, the pipeline stops — no point running further checks.
3. **Additive to existing behavior.** PathGuard wraps existing path_policy.py logic. No behavioral regressions.
4. **Extensible.** New guards are added by subclassing Guard and registering in the pipeline. No core write path changes needed.

## Guard Interface

```python
class GuardResult:
    status: str       # "pass" | "warn" | "block" | "require_approval"
    guard_name: str
    message: str
    metadata: dict[str, Any]

class Guard(ABC):
    name: str
    def check(self, context: GuardContext) -> GuardResult

class GuardContext:
    path: str           # repo-relative target path
    content: str | None  # file content being written (None for deletes/moves)
    operation: str      # "write" | "delete" | "move"
    root: Path          # content root
    session_id: str | None
    metadata: dict[str, Any]  # additional context (frontmatter, etc.)
```

## GuardPipeline

```python
class GuardPipeline:
    guards: list[Guard]

    def run(self, context: GuardContext) -> PipelineResult:
        """Execute all guards in order. Short-circuit on block."""

class PipelineResult:
    allowed: bool
    results: list[GuardResult]
    warnings: list[str]
    blocked_by: str | None
    duration_ms: int
```

### Execution order

1. **PathGuard** — fast, rejects obviously invalid paths
2. **ContentSizeGuard** — fast, rejects oversized content
3. **FrontmatterGuard** — schema validation for markdown files
4. **TrustBoundaryGuard** — trust policy enforcement

Order is cheapest-first for efficiency.

## Guard Inventory

### PathGuard

Wraps existing `path_policy.py` validation. Translates `MemoryPermissionError` and `ValidationError` into `GuardResult(status="block")`.

### ContentSizeGuard

Blocks writes where content exceeds a configurable threshold.

- **Default threshold:** 100 KB per file (`ENGRAM_MAX_FILE_SIZE` env var override)
- **Applies to:** write operations with non-None content
- **Skips:** deletes, moves

### FrontmatterGuard

Validates YAML frontmatter on markdown file writes.

- **Required fields** (when frontmatter present): `source`, `created`
- **Validated enums:** `source` must be one of: `user-stated`, `agent-inferred`, `agent-generated`, `external-research`, `template`, `skill-discovery`; `trust` must be one of: `high`, `medium`, `low`
- **Skips:** non-markdown files, files without frontmatter block
- **Result:** `warn` on missing recommended fields, `block` on invalid enum values

### TrustBoundaryGuard

Enforces trust assignment rules from content-boundaries.md.

- **Blocks:** `trust: high` assignment when `source` is not `user-stated` — returns `require_approval`
- **Passes:** `trust: high` with `source: user-stated`, any other trust level, files without frontmatter
- **Skips:** non-markdown files

## Trace Integration

Every `GuardPipeline.run()` call emits a `guardrail_check` trace span:

```json
{
  "span_type": "guardrail_check",
  "name": "guard_pipeline",
  "status": "ok" | "denied",
  "duration_ms": 5,
  "metadata": {
    "path": "memory/knowledge/topic.md",
    "operation": "write",
    "guards_run": 4,
    "blocked_by": null,
    "warnings": ["FrontmatterGuard: missing recommended field 'last_verified'"]
  }
}
```

## Integration Points

The pipeline is available as a standalone module (`guard_pipeline.py`). Write tools can create a `GuardContext` and call `pipeline.run()` before executing writes. The pipeline does NOT modify the write tools' control flow — callers inspect `PipelineResult.allowed` and decide whether to proceed.

## Open Questions (Resolved)

**Q: Synchronous or pre-commit hook?** → Synchronous. Immediate feedback in the tool response is more useful than a post-hoc hook that fails after the agent has moved on.

**Q: Content size threshold?** → 100 KB per file, configurable via `ENGRAM_MAX_FILE_SIZE`. This prevents bloat while accommodating legitimate large files like research reports.

**Q: trust:high approval or warning?** → `require_approval` when agent-assigned. This matches the governance rule that trust:high is the highest privilege level and should only come from user statements or explicit confirmation.

**Q: Guard failures and plan execution?** → Guard failures produce `block` results that callers translate into errors. For plan execution, a guard block during verification manifests as a postcondition failure.
