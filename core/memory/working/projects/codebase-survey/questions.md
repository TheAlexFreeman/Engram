---
source: agent-generated
origin_session: manual
created: 2026-03-23
trust: medium
type: questions
next_question_id: 4
---

# Open Questions

## q-001: What are the essential entry points and boot sequence for Engram?
**Asked:** 2026-03-23 | **Last touched:** 2026-03-23 | **Context:** The MCP server has a Python entry point and the browser views have a separate File System Access API flow. Mapping both is the first survey phase.
**Resolves by:** agent-research
**Agent contribution:** Trace `pyproject.toml` entry points, `server_main.py`, and the browser view bootstrap sequence; summarize in `IN/knowledge/codebase/architecture.md`.

## q-002: How do the MCP tool layer and the browser views relate architecturally?
**Asked:** 2026-03-23 | **Last touched:** 2026-03-23 | **Context:** Engram has two consumer surfaces — agent-facing MCP tools and human-facing browser views — that read the same on-disk memory tree. Understanding the boundary matters for data-model and operations notes.
**Resolves by:** agent-research
**Agent contribution:** Map the shared data contract (frontmatter, directory layout) and document how each surface reads/writes versus read-only.

## q-003: Which governance and curation rules constrain what the survey can write?
**Asked:** 2026-03-23 | **Last touched:** 2026-03-23 | **Context:** The `core/governance/` directory defines trust levels, size limits, and promotion rules. The survey must respect these when writing knowledge files.
**Resolves by:** agent-research
**Agent contribution:** Summarize the relevant curation constraints in `IN/knowledge/codebase/decisions.md` under active constraints.

---

# Resolved Questions

_None yet._
