---
source: agent-generated
type: architecture-note
domain: system-operations
created: 2026-03-20
trust: low
origin_session: core/memory/activity/2026/03/20/chat-001
tags: [git, architecture, multi-agent, environment, deployment, coordination]
related:
  - _archive/2026-03-19-tmp-data-loss-incident.md
  - engram-governance-model.md
  - operational-resilience-and-memetic-security-synthesis.md
  - protocol-design-considerations.md
  - validation-as-adaptive-health.md
  - engram-system-overview.md
---

# Environment Capability Asymmetry in Engram Deployments

## The core observation

The `agent_memory_mcp` git tooling is intentionally local-only: `core/tools/agent_memory_mcp/core/git_repo.py` performs
reads, writes, commits, and local branch operations but has no `git push` or
remote-interaction capability. This is a reasonable design choice — it keeps the
server stateless with respect to the network and avoids storing credentials in
the MCP process environment. But it creates a class of coordination failures that
vary depending on where an agent is running.

## The asymmetry table

| Environment | Git read | Git commit | Git push | Credential access |
|---|---|---|---|---|
| User's local machine (laptop agent) | ✓ | ✓ | ✓ | ✓ (OS credential store) |
| Cowork sandbox (this session type) | ✓ (via /tmp clone) | ✓ (via /tmp clone) | ✗ | ✗ |
| CI/CD runner | ✓ | ✓ | ✓ (via injected token) | ✓ (env var) |
| Headless server / cron | ✓ | ✓ | ✓ (if configured) | depends |

The result: two agents working on the same repo from different environments can
both commit, but only one can push. Commits accumulate in the environment that
can't push, creating divergence that has to be resolved by the environment that
can.

## Failure modes by environment pair

### Cowork agent + laptop agent (observed 2026-03-19/20)

Both agents commit; neither knows the other's unpushed commits exist until a
`git fetch` reveals the divergence. The Cowork agent cannot resolve the divergence
by pushing — it has to advise the user to push from the laptop. If the Cowork
sandbox resets `/tmp/` before the user pushes, commits are lost (the incident).

**Mitigation in place:** workspace-folder-first write norm means durable content
exists on disk even without a push. Git history may lag, but files don't disappear.

### Two Cowork sessions on the same repo (hypothetical)

Neither session can push. Both can commit to their respective `/tmp/` clones.
Neither session's commits reach the other. Merging requires the user to pull
from both sessions' advised states — but since neither session can push, there's
nothing to pull. All commits are effectively ephemeral unless the user manually
copies content from `/tmp/` (impossible after session end).

**Mitigation:** workspace-folder-first writes. The second session should read
from the workspace folder, which reflects the first session's file writes even
if they were never committed.

### Cowork agent + CI runner (hypothetical)

CI can push; Cowork cannot. If CI runs on a branch while Cowork has unpushed
commits, CI's push will not include Cowork's work. After CI pushes, the Cowork
session is behind and its next commit will diverge again.

**Mitigation:** same as above — workspace writes are durable regardless of CI
state. But CI workflows that rewrite files (reformatting, auto-fixing) can
conflict with workspace-folder content if files are modified in both places.

## Why keeping git tooling local-only is still the right call (for now)

1. **Simplicity and safety.** A push capability in the MCP server requires
   credential management, error handling for network failures, and decisions
   about when to push (every commit? batched?). These are non-trivial.

2. **The user retains control of remote state.** Nothing reaches GitHub without
   the user's explicit action. This is consistent with Engram's principle of
   human approval for consequential actions.

3. **The workspace-folder norm absorbs most of the risk.** If every durable
   write goes to the workspace folder first, the only thing lost in a `/tmp/`
   reset is the git history of those writes — not the content itself.

4. **`memory_git_push` can be added later without breaking anything.** It's a
   purely additive change, and the right moment to add it is when the
   credential management story is clear (env var in `.codex/config.toml`,
   or SSH key configured in the server's process environment).

## What a `memory_git_push` tool would need

If added to `write_tools.py` (or a future `remote_tools.py`):

- **Credential source:** read from `GH_TOKEN` / `GITHUB_TOKEN` env var already
  set in `[mcp_servers.agent_memory.env]` in `.codex/config.toml` (untracked
  section, or a separate gitignored `.codex/local.toml`). Configure git to use
  it via `http.extraheader` or `credential.helper`.
- **Remote inference:** default to `origin`; fall back to inspecting
  `git remote -v` if multiple remotes exist.
- **Branch inference:** use the current branch (`git branch --show-current`).
- **Pre-push checks:** verify no unresolved merge conflicts; warn if pushing
  would overwrite remote work (non-fast-forward); require explicit `force` flag
  for force-push (which should almost never be permitted).
- **Audit trail:** log the push as a commit-level event in the ACCESS log or a
  dedicated `remote-ops.log`.

## Summary

The local-only git design is intentional and appropriate for the current system
maturity. The capability asymmetry it creates is manageable through the
workspace-folder-first write norm. The failure modes are well-understood and
primarily manifest as divergence between Cowork sessions and laptop agents —
a known coordination pattern that the multi-agent section of
the system documentation should cover explicitly.
