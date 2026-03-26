---
source: agent-generated
origin_session: codebase-survey-phase-1
created: 2026-03-23
last_verified: 2026-03-26
trust: medium
related:
  - pyproject.toml
  - core/tools/agent_memory_mcp/server.py
  - core/tools/agent_memory_mcp/server_main.py
  - core/tools/memory_mcp.py
  - HUMANS/views/engram-utils.js
  - HUMANS/views/setup.html
  - HUMANS/views/dashboard.html
  - README.md
---

# Architecture — Engram

Engram is a persistent, version-controlled AI memory system with two consumer surfaces — an **MCP server** for agent-facing tool access and **browser views** for human-facing read/browse — that both operate on the same on-disk memory tree under `core/`.

## Entry points

### MCP server (agent surface)

1. **Installed CLI:** `engram-mcp` → `engram_mcp.agent_memory_mcp.server_main:main()` (registered in `pyproject.toml` under `[project.scripts]`).
2. **Module invocation:** `python -m engram_mcp.agent_memory_mcp.server_main`.
3. **Repo-local fallback:** `core/tools/memory_mcp.py` — a compatibility wrapper that bootstraps `sys.path` so `engram_mcp.*` imports work even without a pip install, then delegates to the same `server.mcp.run()`.

All three converge on `core/tools/agent_memory_mcp/server.py` → `create_mcp()`, which:
- Resolves the repo root from an explicit argument, `MEMORY_REPO_ROOT`, `AGENT_MEMORY_ROOT`, or file-relative fallback.
- Instantiates `GitRepo` (thin `subprocess` wrapper around `git`).
- Creates a `FastMCP("agent_memory_mcp")` instance.
- Registers tools in tier order: Tier 0 (read) → optional Tier 2 (raw write, gated by `MEMORY_ENABLE_RAW_WRITE_TOOLS`) → Tier 1 (semantic).
- Module-level call `mcp, TOOLS, REPO_ROOT, GIT_REPO = create_mcp()` runs at import time.

### Browser views (human surface)

- 7 standalone HTML pages under `HUMANS/views/` (dashboard, knowledge, projects, skills, users, docs, setup).
- No build step. Each page loads shared CSS (`engram-shared.css`) and shared JS (`engram-utils.js`).
- File access uses the **File System Access API** (browser-native `showDirectoryPicker`) or a **GitHub API** fallback, both surfaced through `engram-utils.js` helpers (`readFile`, `listDir`, `writeFile`).
- `HUMANS/views/index.html` redirects to `setup.html`; top-level `index.html` and `setup.html` are compatibility wrappers that redirect into `HUMANS/views/`.
- Views are read-only dashboards for humans; they parse the same frontmatter/Markdown files the MCP server manages.

### Agent bootstrap (context loading)

- Platform adapter files (`AGENTS.md`, `CLAUDE.md`, `.cursorrules`) point agents to `README.md` → `core/INIT.md`.
- `agent-bootstrap.toml` provides machine-readable session-type detection, step-by-step loading sequences, and per-step token cost estimates.
- `core/INIT.md` is the live operational router: it classifies the session type (first-run, returning, full bootstrap, automation, etc.) and specifies a context-loading manifest.

## Module map

### Python package: `engram_mcp` (mapped to `core/tools/` via `pyproject.toml`)

```
core/tools/                         ← engram_mcp namespace root
├── __init__.py                     ← Namespace bootstrap
├── memory_mcp.py                   ← Repo-local compatibility entrypoint
└── agent_memory_mcp/               ← Main package
    ├── __init__.py                 ← Lazy exports (GIT_REPO, REPO_ROOT, TOOLS, mcp)
    ├── server.py                   ← create_mcp(): repo resolution, tool registration
    ├── server_main.py              ← CLI entry (main → mcp.run())
    ├── git_repo.py                 ← GitRepo: subprocess git wrapper, write locking
    ├── models.py                   ← MemoryWriteResult dataclass
    ├── path_policy.py              ← Path validation, protected roots, commit prefixes
    ├── errors.py                   ← Error hierarchy (StagingError, ValidationError, etc.)
    ├── frontmatter_utils.py        ← YAML frontmatter parsing/serialization
    ├── preview_contract.py         ← Preview/commit workflow support
    ├── plan_utils.py               ← Plan YAML helpers
    ├── core/                       ← Portable format layer (importable without MCP runtime)
    │   └── __init__.py             ← Re-exports: errors, frontmatter_utils, git_repo, models, path_policy
    └── tools/                      ← Tool registration packages
        ├── read_tools.py           ← Tier 0: 15+ read/analysis tools
        ├── write_tools.py          ← Tier 2: raw write tools (staged, no auto-commit)
        ├── name_index.py           ← NAMES.md generation
        ├── reference_extractor.py  ← Link/reference graph analysis
        ├── graph_analysis.py       ← Connectivity graph utilities
        └── semantic/               ← Tier 1 semantic tools
            ├── __init__.py         ← register() aggregates all sub-modules
            ├── _session.py         ← In-memory session state
            ├── plan_tools.py       ← Plan lifecycle tools
            ├── knowledge_tools.py  ← Knowledge promotion/demotion tools
            ├── user_tools.py       ← User profile tools
            ├── skill_tools.py      ← Skill management tools
            ├── session_tools.py    ← Session lifecycle tools
            └── graph_tools.py      ← Graph analysis tools
```

### Content tree: `core/` (memory repo root)

```
core/
├── INIT.md              ← Live operational router
├── governance/          ← Self-update rules (curation, trust, security, maturity)
├── memory/
│   ├── HOME.md          ← Session entry, top-of-mind
│   ├── users/           ← User identity and preferences
│   ├── knowledge/       ← Topical knowledge (with _unverified/ quarantine)
│   ├── skills/          ← Agent workflow definitions
│   ├── activity/        ← Episodic memory (YYYY/MM/DD/chat-NNN)
│   └── working/         ← Scratchpad, projects, session state
└── tools/               ← MCP server (never loaded by agents as memory content)
```

### Human-facing tree: `HUMANS/`

```
HUMANS/
├── docs/     ← Reference docs (QUICKSTART, CORE, DESIGN, MCP, WORKTREE, etc.)
├── setup/    ← Shell-based setup scripts and templates
├── views/    ← 7 standalone browser dashboards
└── tooling/  ← Capabilities manifests, validators, test suites
```

## Key dependencies

| Dependency | Role | Install extra |
|---|---|---|
| `mcp` (≥1.0) | FastMCP server framework | `[server]` |
| `python-frontmatter` (≥1.1) | YAML frontmatter parsing | `[core]` or `[server]` |
| `PyYAML` (≥6.0) | YAML parsing for plans and config | `[core]` or `[server]` |
| `git` (CLI) | All versioning via `subprocess.run` in `GitRepo` | system |
| `setuptools` (≥68) | Build backend | build-time |
| Browser File System Access API | Local file access for browser views | browser-native |

Python ≥ 3.10 required. Base install has zero dependencies (format layer only); `[server]` adds MCP runtime.

## Open questions

- How does `preview_contract.py` interact with the staged-write workflow? (deferred to Phase 3: data-model-and-apis)

## Tool surface inventory (92 tools, 4 resources, 4 prompts)

### Tier 0 — Read-only (42 tools, registered in `read_tools.py`)

| Category | Tools |
|---|---|
| Governance & policy | `memory_get_capabilities`, `memory_get_tool_profiles`, `memory_get_policy_state`, `memory_route_intent` |
| File & folder navigation | `memory_read_file`, `memory_list_folder`, `memory_extract_file` |
| Content search & reference | `memory_search`, `memory_resolve_link`, `memory_find_references`, `memory_review_unverified` |
| Link & structure health | `memory_scan_frontmatter_health`, `memory_validate_links`, `memory_check_cross_references`, `memory_reorganize_preview`, `memory_suggest_structure` |
| Knowledge graph analysis | `memory_suggest_links`, `memory_score_existing_links`, `memory_score_links_by_access`, `memory_cross_domain_links`, `memory_surface_unlinked`, `memory_link_delta` |
| Summary & index generation | `memory_generate_summary`, `memory_generate_names_index` |
| Data analytics & audit | `memory_access_analytics`, `memory_check_knowledge_freshness`, `memory_check_aggregation_triggers`, `memory_aggregate_access`, `memory_diff_branch`, `memory_git_log`, `memory_audit_trust` |
| Session & workflow bundles | `memory_session_health_check`, `memory_session_bootstrap`, `memory_prepare_unverified_review`, `memory_prepare_promotion_batch`, `memory_prepare_periodic_review`, `memory_run_periodic_review` |
| Git & provenance | `memory_get_file_provenance`, `memory_inspect_commit`, `memory_diff` |
| System health | `memory_validate`, `memory_get_maturity_signals` |

### Tier 2 — Raw write (7 tools, registered in `write_tools.py`, gated by `MEMORY_ENABLE_RAW_WRITE_TOOLS`)

`memory_write`, `memory_edit`, `memory_delete`, `memory_move`, `memory_update_frontmatter`, `memory_update_frontmatter_bulk`, `memory_commit`. All stage changes without auto-commit; caller must call `memory_commit` to seal. Protected roots (`memory/users`, `governance`, `memory/activity`, `memory/skills`) are rejected — use Tier 1 semantic tools instead.

### Tier 1 — Semantic write (43 tools across 6 modules in `tools/semantic/`)

| Module | Tools |
|---|---|
| `plan_tools.py` | `memory_plan_create`, `memory_plan_execute`, `memory_plan_review`, `memory_list_plans` |
| `knowledge_tools.py` | `memory_promote_knowledge`, `memory_promote_knowledge_batch`, `memory_promote_knowledge_subtree`, `memory_demote_knowledge`, `memory_archive_knowledge`, `memory_reorganize_path`, `memory_update_names_index`, `memory_add_knowledge_file`, `memory_mark_reviewed`, `memory_list_pending_reviews` |
| `user_tools.py` | `memory_update_user_trait` |
| `skill_tools.py` | `memory_update_skill` |
| `session_tools.py` | `memory_append_scratchpad`, `memory_record_chat_summary`, `memory_flag_for_review`, `memory_resolve_review_item`, `memory_log_access`, `memory_log_access_batch`, `memory_record_session`, `memory_run_aggregation`, `memory_record_reflection`, `memory_record_periodic_review`, `memory_revert_commit` |
| `graph_tools.py` | `memory_analyze_graph`, `memory_prune_redundant_links`, `memory_audit_link_density`, `memory_prune_weak_links` |

### MCP Resources (4)

`memory://capabilities/summary`, `memory://policy/summary`, `memory://session/health`, `memory://plans/active`

### MCP Prompts (4)

`memory_prepare_unverified_review_prompt`, `memory_governed_promotion_preview_prompt`, `memory_prepare_periodic_review_prompt`, `memory_session_wrap_up_prompt`

### Utility modules (not tool-registered)

- `reference_extractor.py` — link analysis, graph building, suggestion heuristics (consumed by `read_tools.py` and `graph_tools.py`).
- `graph_analysis.py` — connectivity graph and co-access scoring (consumed by `graph_tools.py`).
- `name_index.py` — NAMES.md generation (consumed by `read_tools.py` and `knowledge_tools.py`).

### Format layer (`core/` sub-package, importable without MCP)

- `git_repo.py` — `GitRepo` class: subprocess git wrapper, write-lock with `agent-memory-write.lock`, fallback author identity. All paths accepted as repo-relative strings.
- `models.py` — `MemoryWriteResult` dataclass returned by every write tool (files_changed, commit_sha, commit_message, new_state, warnings, publication, preview).
- `path_policy.py` — Path validation, protected-root enforcement, commit-prefix vocabulary (10 known prefixes: `[knowledge]`, `[plan]`, `[project]`, `[skill]`, `[user]`, `[chat]`, `[curation]`, `[working]`, `[system]`, `[access]`).
- `errors.py` — Error hierarchy (`StagingError`, `ValidationError`, `MemoryPermissionError`).
- `frontmatter_utils.py` — YAML frontmatter parsing/serialization.
- `preview_contract.py` — Preview/commit workflow helpers.
