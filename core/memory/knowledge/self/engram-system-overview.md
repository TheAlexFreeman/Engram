---
title: Engram System — Architecture and Design Overview
category: knowledge
tags: [engram, architecture, self-knowledge, mcp, memory-system]
source: agent-generated
trust: medium
origin_session: core/memory/activity/2026/03/20/chat-001
created: 2026-03-20
last_verified: 2026-03-20
related:
  - memory/knowledge/self/engram-governance-model.md
  - memory/knowledge/self/protocol-design-considerations.md
  - memory/knowledge/self/validation-as-adaptive-health.md
  - memory/knowledge/self/environment-capability-asymmetry.md
  - memory/knowledge/self/operational-resilience-and-memetic-security-synthesis.md
  - memory/knowledge/self/comprehensive-self-knowledge-summary.md
---

# Engram System — Architecture and Design Overview

This file is self-knowledge: a description of this system by the system itself, written for
use by future sessions of this agent. It should be treated as authoritative about intent and
design philosophy, and cross-checked against `README.md` and `core/INIT.md` for
operational details. Human review is recommended before relying on it for architectural decisions.

---

## What Engram Is

Engram is a **git-backed persistent AI memory system** designed to give a language model agent
durable memory across sessions. The model itself is stateless and ephemeral — each session starts
from a clean context window. Engram provides continuity by maintaining a structured repository of
knowledge, plans, and session history that the agent loads at session start and updates during the
session.

The core design bet: *structured Markdown files under git version control are a better long-term
memory substrate than embeddings databases or opaque blob stores*, because they are:
- **Human-readable and editable** — the user can inspect, correct, or override any memory directly
- **Auditable** — git history is a tamper-evident record of everything the system has written
- **Version-controlled** — rollback to any prior state is always possible
- **Composable** — files can link to each other, be organized into taxonomies, and be queried both
  semantically and structurally

The tradeoff: Markdown + git is slower, more verbose, and requires more curation discipline than
a vector store. The bet is that for a long-running personal memory system, those costs are worth
paying for the transparency and recoverability guarantees.

---

## Repository Structure

```
agent-memory-seed/
├── CLAUDE.md                    # Session adapter — Claude Code entry point
├── AGENTS.md                    # Session adapter — general agent entry point
├── .cursorrules                 # Session adapter — Cursor IDE entry point
├── agent-bootstrap.toml         # Structured bootstrap configuration
├── README.md                    # Full architectural reference
│
├── core/                        # All system internals live under core/
│   ├── INIT.md                  # IDENTITY-CRITICAL: live router, active thresholds, bootstrap
│   │
│   ├── governance/              # Governance and operational parameters
│   │   ├── curation-policy.md   # Trust decay and archiving policy
│   │   ├── update-guidelines.md # How to change the system
│   │   ├── system-maturity.md   # Stage definitions and transition criteria
│   │   ├── curation-algorithms.md # Full aggregation and cluster algorithms
│   │   ├── review-queue.md      # Flagged items awaiting human review
│   │   ├── belief-diff-log.md   # Tracking belief changes over time
│   │   ├── integrity-checklist.md # Periodic review checklist
│   │   └── ...                  # first-run.md, session-checklists.md, etc.
│   │
│   ├── memory/                  # Retrievable memory content
│   │   ├── users/               # Who the user is; persistent user profile
│   │   │   ├── SUMMARY.md       # User portrait, working style, goals
│   │   │   └── Alex/            # User-specific subfolders (profile, traits)
│   │   │
│   │   ├── knowledge/           # Topic knowledge
│   │   │   ├── ai/              # AI history, frontier, tools
│   │   │   ├── cognitive-science/ # Memory, attention, concepts, metacognition
│   │   │   ├── mathematics/     # Logic, complexity, causal inference, game theory
│   │   │   ├── philosophy/      # History, ethics, personal identity, phenomenology
│   │   │   ├── software-engineering/ # Django, React, devops, testing, systems-architecture
│   │   │   ├── social-science/  # Behavioral economics, cultural evolution
│   │   │   ├── rationalist-community/ # Origins, AI discourse, institutions
│   │   │   ├── literature/      # Literary knowledge
│   │   │   ├── self/            # This folder — system self-knowledge
│   │   │   └── _archive/        # Retired knowledge; preserved but not loaded
│   │   │
│   │   ├── skills/              # Reusable procedure files for the agent
│   │   │
│   │   ├── activity/            # Episodic memory — session history
│   │   │   └── YYYY/MM/DD/chat-NNN/
│   │   │       ├── transcript.md, SUMMARY.md, reflection.md
│   │   │       └── artifacts/
│   │   │
│   │   └── working/
│   │       ├── projects/        # Active multi-session work tracking
│   │       │   ├── SUMMARY.md   # IDENTITY-CRITICAL: priority stack, next actions
│   │       │   └── project-id/  # Per-project: plans/, SUMMARY.md
│   │       └── scratchpad/
│   │           ├── USER.md      # User-authored constraints and preferences
│   │           └── CURRENT.md   # Agent working notes, active session threads
│   │
│   └── tools/                   # MCP server implementation
│       └── agent_memory_mcp/    # Python FastMCP package
│           ├── server.py        # FastMCP server definition
│           ├── server_main.py   # CLI entrypoint
│           ├── core/            # Shared internals (git_repo, path_policy, models)
│           ├── tools/
│           │   ├── read_tools.py     # Read, search, git log, analytics tools
│           │   ├── write_tools.py    # Write, edit, delete, move, frontmatter tools
│           │   └── semantic/         # Domain-aware tools (split by concern)
│           │       ├── session_tools.py   # Session lifecycle, access logging, aggregation
│           │       ├── knowledge_tools.py # Promote, demote, archive, reorganize knowledge
│           │       ├── plan_tools.py      # Plan CRUD, status tracking
│           │       ├── user_tools.py      # User trait management
│           │       └── skill_tools.py     # Skill updates
│           └── tests/           # Unit tests (in core/tools/tests/)
│
└── HUMANS/                      # Human-facing documentation and tooling
    ├── docs/                    # QUICKSTART, CORE, DESIGN, MCP, INTEGRATIONS
    └── tooling/
        ├── scripts/             # validate_memory_repo.py, inspect_compact_budget.py, etc.
        └── tests/               # test_validate_memory_repo.py and full test suite
```

---

## The MCP Server (core/tools/agent_memory_mcp)

The MCP server exposes the memory system to any MCP-capable agent (Claude Desktop, Claude Code,
Cursor, etc.). It is implemented in Python using FastMCP. The package lives at
`core/tools/agent_memory_mcp/`.

### Tool Categories

**Read tools** (`tools/read_tools.py`):
- `memory_read_file` — read a specific file by path
- `memory_list_folder` — list files by folder or pattern
- `memory_search` — keyword/semantic search across the repo
- `memory_git_log` — structured git history for a path or the whole repo
- `memory_get_capabilities` — return the governed capability manifest
- `memory_session_bootstrap` — optimized bootstrap loader for session start
- `memory_access_analytics` — usage analytics from ACCESS.jsonl

**Semantic tools** (split into `tools/semantic/` modules by domain):
- **Session tools** (`session_tools.py`): `memory_record_session`, `memory_record_chat_summary`,
  `memory_append_scratchpad`, `memory_flag_for_review`, `memory_log_access`,
  `memory_run_aggregation`, `memory_record_reflection`, `memory_record_periodic_review`
- **Knowledge tools** (`knowledge_tools.py`): `memory_promote_knowledge`,
  `memory_promote_knowledge_batch`, `memory_promote_knowledge_subtree`,
  `memory_demote_knowledge`, `memory_archive_knowledge`, `memory_reorganize_path`,
  `memory_add_knowledge_file`, `memory_mark_reviewed`
- **Plan tools** (`plan_tools.py`): `memory_plan_create`, `memory_plan_execute`,
  `memory_plan_review`, `memory_list_plans`
- **User tools** (`user_tools.py`): `memory_update_user_trait`
- **Skill tools** (`skill_tools.py`): `memory_update_skill`

**Write tools** (`tools/write_tools.py`):
- `memory_write` — write a new file (with frontmatter validation)
- `memory_edit` — edit an existing file
- `memory_delete` — delete a file
- `memory_move` — move/rename a file
- `memory_update_frontmatter` — update frontmatter fields
- `memory_update_frontmatter_bulk` — batch frontmatter updates
- `memory_commit` — explicit commit (for batched operations)

### Key Design Constraints

- All writes are committed to git immediately (no uncommitted writes)
- The server resolves the repo root via `MEMORY_REPO_ROOT` or `AGENT_MEMORY_ROOT` env vars
- Push to remote is deliberately NOT implemented (see `environment-capability-asymmetry.md`)

---

## The Trust Tier System

Every knowledge file has a `trust` frontmatter field and lives in a path that encodes its
review status:

| Tier | Path | Meaning |
|---|---|---|
| Unverified | `core/memory/knowledge/_unverified/` | Agent-written, not yet human-reviewed |
| Promoted | `core/memory/knowledge/*/` (non-`_unverified`) | Human-reviewed, approved for full weight |
| Archived | `core/memory/knowledge/_archive/` | Retired; preserved for reference but not loaded in normal context |

The trust field (`low` / `medium` / `high`) encodes confidence about the *content*, independent
of the review status. A promoted file can still be `trust: medium` if its content is uncertain.

The system also uses `source` frontmatter (`agent-generated`, `external-research`, `manual`,
`user-authored`) to distinguish provenance.

---

## Session Bootstrap Architecture

The bootstrap is designed for minimal context cost. Two entry points:

**Compact returning** (~3,000–7,000 tokens): the default for day-to-day sessions. Loads:
`core/INIT.md` → `core/memory/users/SUMMARY.md` → `core/memory/activity/SUMMARY.md` →
`core/memory/working/projects/SUMMARY.md` → `core/memory/working/USER.md` →
`core/memory/working/CURRENT.md` (all skipped if empty or only placeholder text).

**Full bootstrap** (~18,000–25,000 tokens): for fresh instantiation on a returning system or
periodic governance reviews. Adds `README.md`, `CHANGELOG.md`, `core/governance/curation-policy.md`,
`core/governance/update-guidelines.md`.

The compact path has strict token budgets enforced by the test suite:
`core/INIT.md` ≤ ~2,600 tokens, `core/memory/working/projects/SUMMARY.md` ≤ ~1,700 tokens.

---

## Project Tracking

Projects live in `core/memory/working/projects/` and are organized as subdirectories:

- Each project has its own folder (e.g. `projects/general-knowledge-base/`)
- Projects contain `plans/` subfolder for individual plan files, plus `IN/` for intake
- `core/memory/working/projects/SUMMARY.md` is the priority stack and orientation doc
- Completed projects are moved to `core/memory/working/projects/OUT/`

---

## Current Development State

The system is in **Exploration** stage (see `core/INIT.md`).

The MCP server has been reorganized from the legacy `core/tools/` and `tools/` paths into
`core/tools/agent_memory_mcp/`. The semantic tools monolith has been split into domain-specific
modules under `tools/semantic/`.

**Test suite**: The suite is in `HUMANS/tooling/tests/`.
Running `python -m pytest` from repo root is the standard verification step before every commit.
