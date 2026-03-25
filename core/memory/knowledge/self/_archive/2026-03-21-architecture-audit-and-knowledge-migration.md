---
title: Architecture Audit and Knowledge Base Migration (2026-03-21)
category: knowledge
tags: [self-knowledge, architecture, migration, audit, session-note]
source: agent-generated
trust: medium
origin_session: manual
created: 2026-03-21
related:
  - memory/knowledge/self/_archive/session-2026-03-20.md
  - memory/knowledge/self/_archive/session-2026-03-20-cowork-review.md
  - memory/knowledge/self/_archive/2026-03-22-plan-schema-and-activity-logging-design.md
  - memory/knowledge/self/engram-system-overview.md
  - memory/knowledge/self/engram-governance-model.md
---

# Architecture Audit and Knowledge Base Migration

Session date: 2026-03-21. This note documents a major maintenance session that brought the knowledge base into alignment with the current system architecture and performed a comprehensive soundness audit in preparation for the Engram product launch.

---

## What happened

### Knowledge base path migration

The entire knowledge base (~420 files) was accumulated under an earlier directory structure where top-level directories like `meta/`, `identity/`, `chats/`, `plans/`, `scratchpad/`, `skills/`, and `engram_mcp/` lived at the repo root. The system was subsequently reorganized under `core/`, but the knowledge files still referenced the old layout.

This session performed a comprehensive audit and migration:

1. **Frontmatter update (319 files).** All `origin_session` fields updated from `chats/YYYY/MM/DD/chat-NNN` to `core/memory/activity/YYYY/MM/DD/chat-NNN`.

2. **Self-knowledge rewrites (5 files).** `engram-system-overview.md` received a near-complete structural rewrite: new directory tree, updated MCP tool catalog (reflecting the semantic tools split), corrected bootstrap paths, and current development state. `engram-governance-model.md`, `validation-as-adaptive-health.md`, `environment-capability-asymmetry.md`, and `protocol-design-considerations.md` received targeted path fixes.

3. **Security analysis updates (7 files).** All files under `self/security/` updated with correct directory references for protected roots, validator expectations, and governance paths.

4. **Topic file updates (~50 files).** Academic files across cognitive-science, ai, mathematics, philosophy, social-science, software-engineering, and rationalist-community that included "Implications for Engram" sections or system path references were corrected. Stale `plans/` links to old flat plan files were converted to historical references.

5. **Archive preservation.** Files under `self/_archive/` were deliberately left unmodified — they document historical events and their path references reflect the system state at the time.

### Comprehensive architecture audit

A four-layer audit was performed covering governance/routing, MCP tooling, memory content, and launch infrastructure. Key findings organized by severity:

**Critical (broken functionality):**
- `core/INIT.md` referenced `core/memory/working/HOME.md` — actual file is at `core/memory/HOME.md`
- `core/memory/knowledge/SUMMARY.md` was missing (created this session)
- `core/memory/users/SUMMARY.md` drill-down links pointed to wrong paths
- ACCESS.jsonl files missing from all access-tracked namespaces
- `HUMANS/setup/initial-commit-paths.txt` referenced non-existent files

**High (incorrect for launch):**
- QUICKSTART ChatGPT/Generic instructions used bare paths without `core/` prefix
- Package naming inconsistency: `agent-memory-mcp` (project name) vs `engram_mcp` (import namespace) vs `engram-mcp` (CLI)
- CHANGELOG had no entries
- Capability manifest `shared_result.fields` included `preview` but the resolver didn't accept it

**What was confirmed sound:**
- Routing is acyclic (no circular loading in the bootstrap manifest)
- Governance files are internally consistent (thresholds, stages, policies all agree)
- Bootstrap TOML matches INIT.md routing
- MCP server is correctly wired (all tool registrations resolve, imports work)
- Path policy enforces the documented protected roots
- Platform adapters (CLAUDE.md, AGENTS.md, .cursorrules) are consistent
- CI runs validator and tests on both Ubuntu and Windows
- Trust tier system is correctly implemented in both code and documentation

---

## What this means for future sessions

- Knowledge files now reference the correct `core/` directory structure. An agent loading any knowledge file will receive architecturally accurate information about where things live.
- The `knowledge/SUMMARY.md` created this session provides a compact index of 419 files across 9 domains with entry points and thematic threads. It serves as the task-driven drill-down surface referenced in INIT.md and HOME.md.
- The self-knowledge files (`engram-system-overview.md` especially) are now authoritative about the current architecture. Cross-check against `README.md` and `core/INIT.md` for operational details.
- Several critical and high-priority issues were identified but not all were resolved in this session. The user addressed some directly (ACCESS.jsonl creation, INIT.md HOME.md path fix). Remaining items (QUICKSTART paths, package naming, CHANGELOG, resolver mismatch) are tracked for the launch preparation.
