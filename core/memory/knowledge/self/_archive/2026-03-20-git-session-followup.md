---
source: agent-generated
type: session-note
domain: system-operations
created: 2026-03-20
trust: low
tags: [git, session-hygiene, multi-agent, engram_mcp, architecture, incident-followup]
origin_session: core/memory/activity/2026/03/20/chat-001
related: 2026-03-19-tmp-data-loss-incident.md, session-2026-03-20.md, session-2026-03-20-cowork-review.md, 2026-03-21-architecture-audit-and-knowledge-migration.md, 2026-03-22-plan-schema-and-activity-logging-design.md
---

# Git Session Follow-up: 2026-03-20

Follow-up to `2026-03-19-tmp-data-loss-incident.md`. Documents resolution
confirmation, multi-agent dynamics, and architectural observations from the
next session.

---

## Recovery validation

The recovery commit (`b242c11`) produced during the 2026-03-19 session was
confirmed correct by an independent signal: when the 2026-03-20 session
performed a `git pull --rebase`, git dropped `b242c11` with the message:

> *dropping b242c11 — patch contents already upstream*

This means the user (or a laptop agent) independently pushed an equivalent
recovery commit (`6b03351: "Files recovered from git mishap"`) that contained
the same diffs. Git's deduplication confirmed byte-level parity between the
two independent reconstructions of the lost content — a strong signal that the
in-context reconstruction was accurate.

**Implication for the workspace-first norm**: The files we copied directly into
the workspace folder at the end of the 2026-03-19 session were redundant in
this case (upstream already had them), but the copy was still the right call.
Had the upstream recovery not existed, the workspace-folder write would have
been the only copy. The norm "write durable output to the workspace folder
immediately, treat git commit as secondary" remains correct regardless of
upstream state.

---

## Multi-agent dynamics observed

This session exposed an important operational pattern: **two agents working
concurrently on the same branch**.

- **Cowork agent** (this session): operates via FUSE-mounted workspace folder;
  cannot push to GitHub directly; uses `/tmp/work-repoN` clones for git commits;
  advises user to push.
- **Laptop agent** (user's local machine): appears to have full git credentials;
  can push directly; performed the actual recovery push (`6b03351`) and
  subsequent research (`4eb7087: "research: AI frontiers"`).

The diverged-branch state throughout the 2026-03-19 session was a symptom of
this two-agent pattern, not a mistake by either agent. The agents were working
in parallel and their commits needed periodic reconciliation via merge/rebase.

**This scenario is not yet called out in `plans/worktree-integration.md`.**
The plan addresses orphan-branch worktrees attached to project repos, but the
concurrent Cowork-agent + laptop-agent pattern on the *same* branch is a
distinct coordination problem worth designing around. See action items.

---

## engram_mcp architecture snapshot

As of 2026-03-20, the system's MCP server implementation lives at
`engram_mcp/agent_memory_mcp/`. Key facts:

| File | Lines | Role |
|---|---|---|
| `tools/read_tools.py` | 2,051 | `memory_read_file`, `memory_list_folder`, `memory_search`, `memory_git_log`, `memory_diff`, `memory_audit_trust` |
| `tools/semantic_tools.py` | 2,170 | Session state, plan tools, knowledge promotion/demotion, identity, scratchpad, access logging, reflection |
| `tools/write_tools.py` | 546 | Low-level file write/delete with git integration |
| `server.py` | — | FastMCP instance bootstrap; `MEMORY_REPO_ROOT` / `AGENT_MEMORY_ROOT` env var resolution |

The top-priority active plan (`mcp-reorganization.md`, 0/41 steps complete)
will split `semantic_tools.py` into four focused submodules
(`plan_tools.py`, `knowledge_tools.py`, `identity_tools.py`,
`session_tools.py`) and move the entrypoint into `engram_mcp/` proper.

### What the MCP server is and isn't

The `engram_mcp` server handles **memory operations**: reading files, writing
files, promoting/demoting knowledge, logging access, recording reflections,
managing plans, and running git operations against the repo. It is a governed
write layer for the memory format.

It is **not** a self-extension server. The agent cannot use `engram_mcp` tools
to install new MCP servers, modify its own tool surface, or propose new
capabilities. Self-extension at the MCP layer uses the host environment's
`search_mcp_registry` and `suggest_connectors` tools (Cowork-provided), which
surface suggestions to the user for human approval. The `engram_mcp` server
is invisible to this flow — it manages the memory substrate, not the capability
surface.

### Relationship to self-optimization loop

The `brainstorm-pwr-protocol.md` note describes a self-optimization loop where
PWR `work:` sequences cluster into skill and MCP proposals. The `engram_mcp`
server is the infrastructure that would log those PWR records (via something
like `memory_log_access` or a future `memory_log_pwr`). The `mcp-semantic-tools-improvements.md`
plan includes session recording improvements that are a step toward this, but
the full PWR logging flow does not yet exist. The current `access-log-tooling-improvements.md`
plan (batch writes, session identity) is a prerequisite.

---

## Action items

- [ ] Add concurrent Cowork-agent + laptop-agent coordination scenario to
      `plans/worktree-integration.md` (noted in the plan as a gap)
- [ ] Add a note to `meta/session-checklists.md` about the workspace-first
      durability norm (complement to the incident report's action items)
- [ ] Review `2026-03-19-tmp-data-loss-incident.md` action items for staleness
      now that the recovery is confirmed upstream
- [ ] Track PWR logging as a concrete milestone toward the self-optimization loop
      (currently blocked on `mcp-reorganization.md`)
