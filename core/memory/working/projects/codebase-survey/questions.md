---
source: agent-generated
origin_session: manual
created: 2026-03-23
trust: medium
type: questions
next_question_id: 4
---

# Open Questions

_All questions resolved._

---

# Resolved Questions

## q-001: What are the essential entry points and boot sequence for Engram?
**Asked:** 2026-03-23 | **Resolved:** 2026-03-26 | **Context:** The MCP server has a Python entry point and the browser views have a separate File System Access API flow. Mapping both is the first survey phase.
**Resolution:** Documented in `IN/knowledge/codebase/architecture.md`. Three MCP entry points (CLI, module, repo-local) converge on `server.py:create_mcp()`. Browser views are 7 standalone HTML pages using `engram-utils.js` for file access. Agent bootstrap uses platform adapters → `README.md` → `core/INIT.md`.

## q-002: How do the MCP tool layer and the browser views relate architecturally?
**Asked:** 2026-03-23 | **Resolved:** 2026-03-26 | **Context:** Both consume the same on-disk `core/` tree.
**Resolution:** Documented across architecture.md and data-model.md. MCP tools provide full governed read/write via `GitRepo` subprocess calls. Browser views are read-only dashboards using File System Access API or GitHub API fallback via `engram-utils.js`. Both parse the same frontmatter/Markdown files. The shared data contract (frontmatter schema, directory layout, trust levels) is in data-model.md.

## q-003: Which governance and curation rules constrain what the survey can write?
**Asked:** 2026-03-23 | **Resolved:** 2026-03-26 | **Context:** The `core/governance/` directory defines trust levels, size limits, and promotion rules.
**Resolution:** Documented in `IN/knowledge/codebase/decisions.md` under active constraints. Three-tier change control, instruction containment, path protection policy, content size ceilings, and compact startup contract.
