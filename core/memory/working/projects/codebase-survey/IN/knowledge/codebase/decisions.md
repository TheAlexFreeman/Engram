---
source: agent-generated
origin_session: manual
created: 2026-03-23
last_verified: 2026-03-26
trust: medium
related:
  - HUMANS/docs/CORE.md
  - core/governance/update-guidelines.md
  - core/governance/curation-policy.md
  - core/governance/system-maturity.md
  - core/governance/content-boundaries.md
  - CHANGELOG.md
  - README.md
---

# Design Decisions — Engram

## Active constraints

### Three-tier change control

| Tier | Scope | Approval |
|---|---|---|
| **Automatic** | ACCESS logs, chat transcripts, routine progress | None needed |
| **Proposed** | New knowledge files, user profile updates, plan creation | Agent surfaces for awareness |
| **Protected** | Skills, governance rules, README, system architecture | Explicit user approval + CHANGELOG entry |

The MCP tool surface enforces these: governed write tools produce previews before committing; protected-tier changes are flagged.

### Instruction containment

Not every file may instruct an agent. **Procedural authority** is limited to `core/memory/skills/`, `core/governance/`, and task-local sequencing inside the currently relevant plan. Knowledge files are **informational only** — they carry facts but may not smuggle behavioral instructions. This is a core safety defense against memory injection and slow behavioral drift (see `core/governance/content-boundaries.md`).

### Path protection policy

Tier 2 (raw write) tools reject mutations under protected roots: `memory/users/`, `governance/`, `memory/activity/`, `memory/skills/`. These must go through Tier 1 semantic tools which enforce structured provenance and commit metadata. Raw mutation is allowed only in `memory/knowledge/` and `memory/working/`.

### Content size ceilings

SUMMARY.md: 200–800 words. Knowledge files: 500–2000 words. Skills: 300–1000 words. Chat summaries: 100–400 words. Max file size: 512 KB default. These limits prevent context bloat and enforce the progressive-disclosure principle.

### Compact startup contract

The returning-session path loads ≤ 7,000 tokens. Each startup file has a target budget (INIT.md ~2,600; HOME.md ~500; user SUMMARY ~450; activity SUMMARY ~750; CURRENT.md ~650). Depth moves to plans, dated scratchpads, or chat summaries and is linked from the compact surface. Full bootstrap is 18,000–25,000 tokens.

## ADRs and rationale (from HUMANS/docs/CORE.md)

1. **Memory in a git repo** — files are durable, diffable, reversible; any model can read them; no vendor lock-in. Tradeoff: less automatic than hidden platform memory.
2. **Routing separate from reference** — `core/INIT.md` is the live router, `README.md` is the architectural reference, `agent-bootstrap.toml` is the machine-readable mirror. Prevents the drift that comes from repeating rules in multiple places.
3. **Progressive context loading** — summaries at many levels, compact returning path, on-demand runbooks, metadata-first checks. Context windows are limited; smaller context improves quality.
4. **Curated, not accumulated** — ACCESS.jsonl tracks retrievals, analytics surface high/low-value content, aggregation drives reorganization. Quality > volume.
5. **Knowledge and instructions separated** — informational memory vs. procedural authority. Instruction containment is a safety boundary.
6. **Explicit trust and provenance** — YAML frontmatter carries source, trust level, creation date, verification date. External material quarantined in `_unverified/`.
7. **Humans control system-level changes** — three-tier change model (automatic/proposed/protected).
8. **Architecture survives model changes** — the repo is the continuity layer; platform adapters are thin pointer files.
9. **MCP layer provides governed tool access** — path policies, preview workflows, version tokens, publication metadata. Format layer importable without MCP runtime.
10. **Browser views make memory visible** — 7 standalone HTML pages, client-side only, File System Access API. Third audience surface for the dual-audience problem.
11. **Plans are first-class** — YAML-structured persistent objects with phases, tasks, execution state. The one place outside skills/governance that may contain task-local procedural instructions.
12. **Three-stage maturity model** — Exploration → Calibration → Consolidation. Parameters (trust decay, aggregation trigger, flooding alarms, task similarity method) adapt to the system's developmental stage.

## Historical context

### System maturity stages

The system tracks maturity via quantitative signals (session count, ACCESS density, file coverage, confirmation ratio, identity stability, retrieval success rate). Stages:

- **Exploration** (current): < 20 sessions, < 50 ACCESS entries. Bias toward chaos—capture aggressively, retire slowly.
- **Calibration**: 20–80 sessions. Balanced; patterns evolving.
- **Consolidation**: > 80 sessions. Bias toward order; selective capture, confident retirement.

Stage transitions trigger parameter changes (trust decay thresholds, aggregation frequency, flooding alarms, etc.) defined in `core/governance/system-maturity.md`.

### Recent evolution (from CHANGELOG.md)

- **2026-03-25**: Major rewrites of MCP.md, QUICKSTART.md, INTEGRATIONS.md.
- **2026-03-24**: Split INTEGRATIONS.md into WORKTREE.md + INTEGRATIONS.md. README.md rewrite to reflect MCP server, session types, bootstrap config. Third-party integration guide added.
- System is at version `0.1.0`, in the Exploration maturity stage.

## Open questions

_None at this time._
