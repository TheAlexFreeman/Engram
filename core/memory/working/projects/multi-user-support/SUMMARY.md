---
active_plans: 4
cognitive_mode: planning
created: 2026-04-03
current_focus: `user-identity-and-namespacing` is complete. Next decision:
  choose between `frontmatter-visibility` and `concurrent-session-writes`,
  which are now both unblocked by the identity foundation.
last_activity: '2026-04-16'
open_questions: 12
origin_session: memory/activity/2026/04/03/chat-001
plans: 5
source: agent-generated
status: active
trust: medium
type: project
---

# Project: Multi-User Support

## Description
Enable multiple users to share a single Engram memory repo for team
collaboration. This requires user identity resolution, namespace isolation for
personal state, visibility controls on shared vs private content, safe
concurrent writes, team-aware activity feeds, and role-based governance.

## Cognitive mode
Planning mode: architecture reviewed, five implementation plans drafted
covering the full workstream from identity foundations through governance.

## Plan inventory (2026-04-03)

| Plan | Status | Primary dependency |
|---|---|---|
| `user-identity-and-namespacing.yaml` | completed | None (foundation) |
| `frontmatter-visibility.yaml` | active | Identity plan (env-identity) |
| `concurrent-session-writes.yaml` | active | Identity plan (env-identity) |
| `team-activity-feed.yaml` | active | Identity + Visibility plans |
| `role-based-governance.yaml` | active | Identity + Visibility plans |

## Motivation
Engram is currently single-user-per-repo by design. As the system matures
toward Consolidation stage, team use cases emerge: shared project knowledge,
cross-user context surfacing, and collaborative curation. The maturity roadmap
already identifies multi-user as a Consolidation consideration. This project
makes it concrete.

## Design principles
- **Backward compatible**: single-user repos must work unchanged (no
  MEMORY_USER_ID required)
- **Git-native**: lean into git's existing multi-author, branching, and merge
  capabilities rather than building parallel infrastructure
- **Frontmatter-driven**: extend the existing metadata system rather than
  adding a separate ACL database
- **Progressive**: teams can adopt features incrementally (start with identity,
  add visibility later)

## Artifact flow
- notes/: design references and open question discussions
- plans/: five phased implementation plans
- OUT contributions: MCP server changes, governance docs, frontmatter schema
  extensions, new test suites

## Key dependencies
- Plan 1 (identity/namespacing) is the foundation — all others depend on it
- Plans 2 and 3 can proceed in parallel after Plan 1's env-identity phase
- Plans 4 and 5 depend on both identity and visibility being in place

## Priority update (2026-04-15)

`multi-user-support` is now the top active project. `skills-expansion` has been closed out, so the next engineering priority is the identity foundation in `user-identity-and-namespacing.yaml`, starting with the `env-identity` phase.

## Progress update (2026-04-16)

`env-identity` is complete. `MEMORY_USER_ID` now resolves at MCP startup, persists on shared `SessionState`, and is written into session metadata plus ACCESS entries. The next implementation phase is `session-namespace`.

`session-namespace` is also complete. Session summaries, checkpoints, reflections, dialogue logs, and session-linked ACCESS entries now route to `memory/activity/{user_id}/...` when `MEMORY_USER_ID` is set, and the existing flat layout remains valid when it is not.

`working-namespace` is complete. USER.md, CURRENT.md, and scratchpad notes now resolve under `memory/working/{user_id}/...` when `MEMORY_USER_ID` is set, while `memory/working/projects/...` remains shared so project registries and plans stay readable across the repo.

`access-log-scoping` is complete. ACCESS writers continue to stamp `user_id`, and the read-side analytics now accept optional `user_id` filters for aggregation, curation analytics, and file provenance summaries.

`backward-compat-tests` is complete. A focused compat suite now locks in the flat single-user layout when `MEMORY_USER_ID` is unset, and the targeted multi-user plus legacy regressions for working memory, context loading, and ACCESS analytics are passing.

The `user-identity-and-namespacing` foundation plan is now complete. The next project decision is which newly unblocked plan to execute first: `frontmatter-visibility` or `concurrent-session-writes`.
