# Home

This is the Home file for the memory store. After `core/INIT.md` routes you here, use it to load session context and check what's top-of-mind.

---

## Context loading order

**MCP shortcut:** When `memory_context_home` is available, call it instead of this manual load sequence — it covers steps 1–4 below in a single call and returns a budget report.

Load in this order. Skip files marked _(skip if placeholder)_ when they contain only default text.

1. `core/memory/users/SUMMARY.md` — user portrait and working style
2. `core/memory/activity/SUMMARY.md` _(skip if placeholder)_ — recent session continuity
3. `core/memory/working/USER.md` _(skip if placeholder)_ — user-authored current priorities
4. `core/memory/working/CURRENT.md` _(skip if placeholder)_ — agent working notes

Then load task-driven drill-downs only when the current task makes them relevant:

- `core/memory/working/projects/SUMMARY.md` — active projects and plans
- `core/memory/knowledge/SUMMARY.md` — accumulated knowledge index
- `core/memory/skills/SUMMARY.md` — codified procedures

### Maintenance probes (before loading extra files)

- Count non-empty lines in `ACCESS.jsonl` files — if any hit the aggregation trigger (see `core/INIT.md`), note for end-of-session.
- Check `core/governance/review-queue.md` — load only when it has real entries or the user asks.

### Access-tracked namespaces

`core/memory/users/`, `core/memory/knowledge/`, `core/memory/skills/`, `core/memory/activity/`, `core/memory/working/projects/`.

Log retrievals from these folders to their `ACCESS.jsonl`. `core/governance/` is not access-tracked.

### Worktree mode

In worktree mode, use `host_repo_root` from `agent-bootstrap.toml` for host-code git operations; use the worktree path for memory files.

---

## Top of mind

- Codebase survey: promote IN/ files to `knowledge/codebase/` after user review
- Harness expansion complete (15 phases); guard pipeline now wired into write paths
- System review remediation in progress
