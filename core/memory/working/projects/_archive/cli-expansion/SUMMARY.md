---
active_plans: 0
cognitive_mode: execution
created: 2026-04-02
current_focus: The v4 diff inspection slice is complete; the remaining CLI
  roadmap is complete.
last_activity: '2026-04-03'
open_questions: 0
origin_session: memory/activity/2026/04/02/chat-001
plans: 10
source: agent-generated
status: completed
trust: medium
type: project
---

# Project: CLI Expansion

## Description
Expand the `engram` CLI so humans, shell-based agents, and automation can
query, inspect, and maintain the memory system outside the MCP protocol. The
v0 foundation is now implemented; the remaining roadmap is split into focused
follow-on plans instead of one monolithic backlog item.

## Cognitive mode
Execution mode: the full planned CLI roadmap is now complete: `cli-v0`, the v1
read/write surfaces, the v2 maintenance and lifecycle roadmaps, the v3 schema
foundations, the v3 plan-command roadmap, the v3 approval/trace roadmap, and
the v4 diff and portability roadmaps all shipped as verified slices.

## Plan inventory (2026-04-03)

| Version | Plan file | Status | Budget | Primary dependency |
|---|---|---|---|---|
| v0 | `cli-v0.yaml` | completed | 8 sessions / 2026-05-01 | Shipped foundation |
| v1 | `cli-v1-read-surfaces.yaml` | completed | 6 sessions / 2026-06-15 | Accurate v0 baseline |
| v1 | `cli-v1-write-ingestion.yaml` | completed | 6 sessions / 2026-06-30 | Accurate v0 baseline |
| v2 | `cli-v2-maintenance-dry-run.yaml` | completed | 7 sessions / 2026-08-01 | v1 read/write helpers |
| v2 | `cli-v2-knowledge-lifecycle.yaml` | completed | 7 sessions / 2026-08-15 | v1 ingestion + v2 dry-run previews |
| v3 | `cli-v3-schema-foundations.yaml` | completed | 5 sessions / 2026-07-15 | Accurate v0 baseline |
| v3 | `cli-v3-plan-commands.yaml` | completed | 8 sessions / 2026-10-01 | v3 schema foundations |
| v3 | `cli-v3-approval-trace.yaml` | completed | 6 sessions / 2026-09-15 | v3 schema foundations |
| v4 | `cli-v4-portability.yaml` | completed | 7 sessions / 2026-11-15 | Stable v3 command contracts |
| v4 | `cli-v4-diff.yaml` | completed | 4 sessions / 2026-11-01 | Stable read-side CLI foundations |

## Motivation
Engram already ships infrastructure CLIs (`engram-mcp`, `engram-proxy`,
`engram-sidecar`), but everyday memory work still benefits from a dedicated
terminal surface:
- `search` for ad-hoc retrieval outside chat
- `status` for memory health and maintenance checks
- `validate` for CI and setup verification
- future read/write/governance commands for shell-native agents and scripts

## Resolved v0 baseline
- Plain `argparse` shipped successfully and matched the existing proxy/sidecar
  CLIs without introducing new dependencies.
- Search auto-detects semantic support when optional search dependencies are
  installed and falls back cleanly to keyword mode otherwise.
- Repo-root discovery follows the same chain as the MCP server, with cwd-walk
  support for `agent-bootstrap.toml`.

## Artifact flow
- IN/: roadmap notes, schema audits, CLI ergonomics notes
- notes/: long-form design references that explain why plans are split the way
  they are
- plans/: one completed v0 foundation plan plus nine follow-on roadmap plans
- OUT contributions: `engram` command modules, tests, docs, and command-surface
  capability updates

## Notes
Keep `notes/cli-roadmap.md` as the design overview. The plan files own the
detailed phase contracts, blockers, budgets, and verification surfaces.
