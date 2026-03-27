---
source: agent-generated
origin_session: manual
created: 2026-03-23
last_verified: 2026-03-26
trust: medium
related:
  - core/governance/update-guidelines.md
  - core/governance/curation-policy.md
  - core/tools/agent_memory_mcp/frontmatter_utils.py
  - core/tools/agent_memory_mcp/models.py
  - core/tools/agent_memory_mcp/preview_contract.py
  - core/tools/agent_memory_mcp/errors.py
  - core/tools/agent_memory_mcp/git_repo.py
---

# Data Model — Engram

## Core entities

### Memory file (Markdown + YAML frontmatter)

The atomic unit of the system. Every governed file under `core/memory/` is a Markdown document with a YAML frontmatter header. Required fields:

```yaml
---
source: user-stated | agent-inferred | agent-generated | external-research | skill-discovery | template | unknown
origin_session: core/memory/activity/YYYY/MM/DD/chat-NNN | setup | manual | unknown
created: YYYY-MM-DD
trust: high | medium | low
last_verified: YYYY-MM-DD  # omitted until human confirms; created serves as fallback
---
```

Additional fields vary by namespace (`type`, `status`, `cognitive_mode`, `related`, etc.). The `related` field is a list of repo-relative paths for cross-referencing.

### Trust levels

| Source | Initial trust | Promotion path |
|---|---|---|
| `user-stated` | `high` | Already highest |
| `agent-inferred` | `medium` | → `high` on explicit user confirmation |
| `agent-generated` | `medium` | → `high` on user endorsement |
| `external-research` | `low` | → `medium` after user review → `high` after accuracy confirmation |
| `template` | `medium` | → `high` after user confirmation during onboarding |

Trust can be **demoted** if inaccuracies are found. Only explicit affirmation counts — silence, topic changes, and passive non-objection do not.

### ACCESS.jsonl (access tracking)

Each access-tracked namespace (`memory/users/`, `memory/knowledge/`, `memory/skills/`, `memory/activity/`, `memory/working/projects/`) has an `ACCESS.jsonl` file. Each line is:

```json
{"file": "relative/path.md", "date": "YYYY-MM-DD", "task": "...", "helpfulness": 0.0, "note": "...", "session_id": "memory/activity/2026/03/16/chat-001"}
```

`helpfulness` is 0.0–1.0. Aggregation triggers when entry count reaches a configurable threshold (default 15). Low-signal entries may be routed to `ACCESS_SCANS.jsonl` instead.

### Plans (YAML)

Plans live in `memory/working/projects/{project}/plans/`. Structure:

```yaml
id: plan-id
project: project-slug
status: active | completed | abandoned
work:
  phases:
    - id: phase-id
      title: ...
      status: pending | done | blocked
      changes:
        - path: ...
          action: update | create | delete
          description: ...
```

### SUMMARY.md files

Each namespace directory has a `SUMMARY.md` that serves as a compact navigator. Targets: 200–800 words (restructure if exceeding 1000).

### MemoryWriteResult (API return type)

Every write tool returns `MemoryWriteResult` (defined in `models.py`):

```
files_changed: list[str]      # Repo-relative paths
commit_sha: str | None         # None for Tier 2 staged-only
commit_message: str | None
new_state: dict                # Operation-specific (next_action, trust, version_token, etc.)
warnings: list[str]
publication: dict | None       # Commit metadata for committed operations
preview: dict | None           # Governed preview envelope
```

### Governed preview envelope

Semantic (Tier 1) tools use `preview_contract.py` to build structured previews before committing:

```
mode: preview | commit
change_class: knowledge | plan | project | ...
summary: human-readable
reasoning: why this change
target_files: [{path, change, from_path?, details?}]
invariant_effects: [side-effect descriptions]
commit_suggestion: {message: ...}
warnings: [...]
resulting_state: {operation-specific}
```

## Persistence

All persistence is **file-on-disk + git**:

- Files are Markdown or YAML under `core/`.
- Versioning is git, driven by `GitRepo` (subprocess wrapper for `git` CLI).
- Write locking uses `agent-memory-write.lock` with 5-second timeout.
- No database, queue, cache, or external store.
- Browser views access the same files via File System Access API or GitHub API (read-only).

Commit messages use a vocabulary of 10 known prefixes: `[knowledge]`, `[plan]`, `[project]`, `[skill]`, `[user]`, `[chat]`, `[curation]`, `[working]`, `[system]`, `[access]`.

## APIs and contracts

### MCP tool tiers

| Tier | Access model | Commit behavior |
|---|---|---|
| Tier 0 | Read-only | No mutations |
| Tier 1 | Semantic (governed) | Auto-commits with structured commit messages |
| Tier 2 | Raw write (fallback) | Stages only; caller must call `memory_commit` |

### Path policy

Protected roots (`memory/users`, `governance`, `memory/activity`, `memory/skills`) reject Tier 2 mutations — must use Tier 1 semantic tools. Raw mutation is allowed in `memory/knowledge` and `memory/working`.

### Version tokens (optimistic locking)

`memory_read_file` returns a `version_token` (hash). Write tools accept it and raise `ConflictError` if the file changed since the read.

### Error hierarchy

All errors inherit from `AgentMemoryError`:
- `ConflictError` — version token mismatch (includes `current_token` for re-read)
- `NotFoundError` — file or plan item does not exist
- `ValidationError` — frontmatter schema violation or malformed content
- `AlreadyDoneError` — operation already in target state (idempotency)
- `StagingError` — git operation failed (includes `stderr`)
- `MemoryPermissionError` — path in a protected directory

### Content size constraints

| File type | Target size |
|---|---|
| SUMMARY.md | 200–800 words (restructure > 1000) |
| Knowledge files | 500–2000 words (split beyond) |
| Skill files | 300–1000 words |
| Chat summaries | 100–400 words per session |
| Max file size | 512 KB default (`MEMORY_MAX_FILE_BYTES`) |

## Open questions

- What are the exact aggregation algorithm steps? (deferred to decisions.md or on-demand `curation-algorithms.md` review)
