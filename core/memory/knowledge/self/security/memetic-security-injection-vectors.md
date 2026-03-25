---
created: '2026-03-20'
origin_session: core/memory/activity/2026/03/20/chat-002
source: agent-generated
trust: low
related:
  - memory/knowledge/self/security/memetic-security-drift-vs-attack.md
  - memory/knowledge/self/security/memetic-security-design-implications.md
  - memory/knowledge/self/security/memetic-security-memory-amplification.md
  - memory/knowledge/self/security/memetic-security-mitigation-audit.md
  - memory/knowledge/self/operational-resilience-and-memetic-security-synthesis.md
---

# Context Injection Vectors in a Running Engram Session

> **Self-referential notice:** This file was produced by the system analyzing its own security surface. Human review is therefore especially important.

This document maps every path through which foreign or uncontrolled content enters an Engram agent's context window during a session. Each vector is a potential entry point for both active injection attacks and passive value drift.

## 1. System Prompt and Bootstrap Files

**Vector:** The context loading manifest in `core/INIT.md` determines which files load at session start. These files frame all subsequent reasoning.

**What enters context:**
- `core/INIT.md` itself (routing rules, active thresholds, compact contract)
- `core/memory/users/SUMMARY.md` (user portrait, working style)
- `core/memory/activity/SUMMARY.md` (episodic continuity)
- `core/memory/working/projects/SUMMARY.md` (active work and priorities)
- `core/memory/working/USER.md` and `core/memory/working/CURRENT.md` (working state)
- Mode-dependent extras: `CHANGELOG.md`, `core/governance/curation-policy.md`, etc.

**Control model:** These files are committed to git (audit trail) but any agent with write access can modify them between sessions. The bootstrap router (`agent-bootstrap.toml`) defines five modes with different loading manifests, but mode selection itself is not externally validated — it's inferred from repo state.

**Risk profile:** High-value targets for persistent drift. A single edit to `core/memory/users/SUMMARY.md` or `core/INIT.md` shifts the behavioral frame for all future sessions. Current protection is git history (visibility after the fact) but no integrity check at load time.

## 2. Loaded Memory Files (On-Demand Reads)

**Vector:** Beyond the bootstrap manifest, any file in the repo can be loaded via `memory_read_file` or `memory_search` during a session. The agent decides which files to read based on task context.

**What enters context:**
- Knowledge files (verified and unverified) — full content including body text
- Plan files with detailed phase descriptions
- Scratchpad files with working notes
- Chat summaries from prior sessions
- Skill definitions

**Control model:** The trust tier system (`trust: high|medium|low` frontmatter) labels files but does not quarantine them from context. A `trust: low` file in `_unverified/` loads with the same mechanical effect as a `trust: high` file in `knowledge/`. The tag is metadata advice, not enforcement.

**Risk profile:** The unverified quarantine zone is the largest uncontrolled content surface. Files there carry `trust: low` but their body text can make any claim. A well-crafted adversarial note with plausible frontmatter enters context indistinguishably from legitimate research.

## 3. Tool Outputs (MCP Responses)

**Vector:** Every MCP tool call returns results that enter the agent's context as tool-use responses.

**What enters context:**
- `memory_search` results: file paths, line numbers, text excerpts from across the repo
- `memory_git_log` results: commit SHAs, commit messages, file change lists
- `memory_audit_trust`: trust tier summaries across all files
- `memory_check_aggregation_triggers`: ACCESS log entry counts and near-trigger summaries
- `memory_check_knowledge_freshness`: freshness status for knowledge files

**Control model:** Tool outputs reflect repo state. If the repo contains adversarial content, tool outputs surface it. Search results do not distinguish by trust tier — a search for "intelligence" returns hits from both verified knowledge and unverified quarantine with equal presentation weight.

**Risk profile:** Tool outputs are the mechanism through which stored adversarial content reaches the agent mid-session. The search tool is the primary amplifier: an adversarial file that matches common query terms will be surfaced repeatedly.

## 4. Conversation History (Multi-Turn Accumulation)

**Vector:** Within a session, each user message and agent response becomes part of the context for subsequent turns. Early turns set precedents that later turns build on.

**What enters context:**
- User messages (trusted input from the principal hierarchy)
- Agent's own prior responses (self-reinforcing)
- Tool call results from prior turns
- System messages and role instructions

**Control model:** The user controls their own messages. The agent's prior responses are not externally validated — they become training signal for the rest of the session. In long sessions with context compaction, the compacted summary replaces raw history, introducing a summarization-as-editing vector.

**Risk profile:** Precedent creep is the primary intra-session threat. If an early turn normalizes an unusual pattern (e.g., writing to a protected directory "just this once"), later turns inherit that precedent. The compaction boundary is a particularly sensitive point — whatever the compaction retains becomes the behavioral anchor for the remaining session.

## 5. Cross-Agent Messages (Multi-Agent Deployments)

**Vector:** In the worktree deployment model, multiple agents share a git repository. Each agent reads files written by other agents.

**What enters context:**
- Memory files written by other agent instances (Cowork, CI, laptop Claude Code)
- Git commits and commit messages from other agents
- Shared plans, scratchpad notes, and knowledge files

**Control model:** Honor-system only. Each agent reads `CLAUDE.md` / `AGENTS.md` and is expected to comply. There is no mechanical authentication of which agent wrote a given file. The `origin_session` frontmatter field is self-reported by the writing agent.

**Risk profile:** Every file from another agent is potentially adversarial, even if that agent is nominally aligned. A compromised or drifted agent in one environment (e.g., CI with access to external code) could write memory files that influence all other agents sharing the repo. The write lock (`.git/agent-memory-write.lock`) prevents concurrent writes but does not authenticate writers.

## 6. Git Commit History

**Vector:** Git operations (`memory_git_log`, `memory_inspect_commit`, revert previews) surface commit metadata including commit messages, diffs, and file change lists.

**What enters context:**
- Commit messages (authored by agents, potentially containing injection payloads)
- Diff content (file additions, modifications, deletions)
- Author metadata (configurable: defaults to "Claude" / "agent@agent-memory")

**Control model:** Commit messages follow a prefix vocabulary (`[knowledge]`, `[plan]`, `[identity]`, etc.) enforced by path policy. But the message body after the prefix is free-form text authored by the committing agent. The prefix is validated but the content is not.

**Risk profile:** Rarely considered vector. A poisoned commit message is visible in git log output and could contain instructions that the reviewing agent processes as context. The git audit trail that is meant to provide security oversight is itself an injection surface when the log is read programmatically.

## 7. External Input via Host Repo (Worktree Mode)

**Vector:** In worktree mode, `host_repo_root` points to an external codebase. The `memory_check_knowledge_freshness` tool reads host repo git state.

**What enters context:**
- Host repo file paths and change summaries
- Host repo git log entries
- Potentially host repo file contents if tools are extended to read them

**Control model:** The host repo is outside the memory system's governance. Its content is controlled by whatever development process applies to that codebase, which may include untrusted contributors, CI artifacts, or dependency updates.

**Risk profile:** The host repo is the widest uncontrolled surface — an entire codebase with its own trust model. Currently the exposure is limited (freshness checks only), but any extension of host repo reading tools expands this surface significantly.

## Summary: Attack Surface Ranking

| Vector | Persistence | Control | Current Protection | Risk |
|--------|------------|---------|-------------------|------|
| Bootstrap/identity files | Cross-session | Agent-writable | Git audit trail only | **Critical** |
| Unverified knowledge files | Cross-session | Any agent | Trust tag (advisory) | **High** |
| Cross-agent writes | Cross-session | Other agents | Honor system | **High** |
| Tool search results | Per-query | Repo state | None (reflects content) | **Medium** |
| Git commit messages | Permanent | Committing agent | Prefix validation only | **Medium** |
| Conversation history | Per-session | User + agent | Context compaction | **Medium** |
| Host repo content | External | External process | Limited tool exposure | **Low** (current) |
