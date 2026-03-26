---
source: agent-generated
origin_session: codebase-survey-phase-6
created: 2026-03-23
last_verified: 2026-03-26
trust: medium
related:
  - core/memory/working/projects/codebase-survey/plans/survey-plan.yaml
---

# Codebase Knowledge — Engram

Survey completed 2026-03-26. All six phases of `plans/survey-plan.yaml` are done; all four knowledge files are at `trust: medium`.

## Files

| File | Coverage | Source paths grounded |
|---|---|---|
| [architecture.md](architecture.md) | Entry points (MCP server, browser views, agent bootstrap), full module map, 92-tool inventory, format layer, content tree, HUMANS tree, dependencies | `pyproject.toml`, `server.py`, `server_main.py`, `memory_mcp.py`, `engram-utils.js`, `README.md`, 12 tool module files |
| [data-model.md](data-model.md) | Frontmatter schema, trust levels, ACCESS.jsonl format, plan YAML structure, MemoryWriteResult, preview envelope, persistence model, API contracts, error hierarchy, size constraints | `update-guidelines.md`, `curation-policy.md`, `frontmatter_utils.py`, `models.py`, `preview_contract.py`, `errors.py`, `git_repo.py` |
| [operations.md](operations.md) | Install, run, setup, worktree, tests (15 test files across Python + JS), lint, validation scripts, deployment, debugging tools | `pyproject.toml`, `setup.sh`, `validate_memory_repo.py`, `agent-memory-capabilities.toml`, test directories |
| [decisions.md](decisions.md) | 12 ADRs from CORE.md, three-tier change control, instruction containment, path protection, size ceilings, compact startup contract, maturity stages, recent changelog | `CORE.md`, `update-guidelines.md`, `curation-policy.md`, `system-maturity.md`, `content-boundaries.md`, `CHANGELOG.md` |

## Re-verification cadence

- **Trigger events**: changes to `pyproject.toml` (dependencies, entry points), changes to `core/tools/agent_memory_mcp/` (tool registrations, API contracts), changes to `core/governance/` (policy or threshold updates), major CHANGELOG entries.
- **Periodic**: run `memory_check_knowledge_freshness` against these files during periodic review sessions.
- **Promotion**: once a human verifies accuracy, promote files from IN/ to `knowledge/codebase/` via OUT/ and set `trust: high`.

## Usage notes

- These files collectively replace ad-hoc codebase exploration for most architecture, data-model, operational, and design questions.
- For deeper subsystem detail (e.g., individual tool semantics, specific governance algorithm steps), drill down to the source files linked in `related` frontmatter.
- Keep entries concise — if a file exceeds 2000 words, split it.
