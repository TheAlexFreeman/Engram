# Session Init

**Read after `README.md` for live routing, active thresholds, and maintenance triggers. If a platform opens this file first, continue here before applying thresholds or curation rules.**

The single authoritative source for live operational parameters. Thresholds elsewhere are reference-only.

---

## Session routing

Use this file as the live operational router once you reach it:

1. If you started in `README.md`, continue here for live routing and active parameters.
2. If this is a fresh instantiation on a blank or template-backed repo, continue to `core/governance/first-run.md`.
3. If this is a fresh instantiation on a returning system, or you need the full governance stack (after governance changes, system updates, or user-requested review), follow the **Full bootstrap** manifest below.
4. If this is a scheduled or recurring automation run (no interactive user), use the **Automation** manifest below.
5. Otherwise, use the **Compact returning** manifest below and keep additional loads task-driven.

**MCP preference:** When local agent-memory MCP tools are available, prefer them for memory reads, search, and governed writes; fall back to direct file access only when the MCP surface is unavailable or lacks the needed operation. If the host exposes Engram under a project-prefixed name, use the identifier shown in the available-server list. When `memory_semantic_search` is available, prefer it for knowledge retrieval queries over structural navigation.

**Retrieval discipline:** When asked about prior conversations, decisions, or stored knowledge, query the relevant SUMMARY files, ACCESS.jsonl, or `memory_search` before answering from loaded context alone. Do not claim to remember something that is not in the loaded or searched files.

---

## Context loading manifest

Load files in the listed order. Skip files marked _(skip if empty)_ when they contain only placeholder text. `agent-bootstrap.toml` expresses the same loading rules in machine-readable form for programmatic consumers — keep both in sync when the contract changes.

| Session type | Files to load | MCP shortcut |
|---|---|---|
| **First run** | this file → `core/governance/first-run.md` (which directs: `CHANGELOG.md`, `core/governance/update-guidelines.md` §§ Change categories + Read-only operation, `core/memory/skills/SUMMARY.md`, `core/memory/skills/onboarding/SKILL.md`) | — |
| **Compact returning** | this file → `core/memory/HOME.md` _(skip if empty or still placeholder; then load `core/memory/users/SUMMARY.md`, `core/memory/activity/SUMMARY.md`, `core/memory/working/USER.md`, and `core/memory/working/CURRENT.md`; load task-relevant `core/memory/working/projects/SUMMARY.md` and/or `core/memory/knowledge/SUMMARY.md` and/or `core/memory/skills/SUMMARY.md` only as needed)_ | `memory_context_home` |
| **Full bootstrap** | this file → Compact returning files + `CHANGELOG.md`, `core/governance/curation-policy.md`, `core/governance/update-guidelines.md` | — |
| **Periodic review** | Full bootstrap files + `core/governance/system-maturity.md`, `core/governance/belief-diff-log.md`, `core/governance/review-queue.md`, `core/governance/session-checklists.md` § "Periodic integrity audit", `core/governance/security-signals.md` | `memory_prepare_periodic_review` |
| **Automation** | this file → `core/memory/HOME.md` _(load only project and scratchpad sections)_ | `memory_context_project` |
| **ACCESS aggregation** | This file + `core/governance/curation-algorithms.md` (load only when aggregation threshold is reached) | `memory_run_aggregation` |
| **Stage transition** | Periodic review files + `core/governance/curation-algorithms.md` | — |

**Do not load** `HUMANS/docs/*` (human reference) or `core/governance/curation-algorithms.md` (on-demand). `core/governance/session-checklists.md`, `core/governance/scratchpad-guidelines.md`, and `core/governance/content-boundaries.md` are also on-demand.

**Do not load** `FIATLUX.md` in normal sessions — the operational documents are self-sufficient. Consult it only when a decision touches foundational principles and no operational document resolves it.

### Worktree mode

- In worktree mode, use `host_repo_root` from `agent-bootstrap.toml` for host-code git operations; use the worktree path for memory files.

### Governance notes

**No access tracking:** `governance/` has no `ACCESS.jsonl` files.

- Run metadata-first maintenance probes before loading extra governance files.
- Load `core/governance/review-queue.md` only when it has real entries or the user asks.
- Count non-empty lines in `ACCESS.jsonl` files in `memory/` before loading governance docs.
- Treat `core/memory/working/projects/SUMMARY.md`, `core/memory/knowledge/SUMMARY.md`, and `core/memory/skills/SUMMARY.md` as task-driven drill-down context, not unconditional startup reads.

---

## Compact bootstrap contract

Compact startup files are live-state surfaces, not archives. They should answer only: what is active now, what should happen next, and where to drill down when the compact view is insufficient.

**Startup strategy:** Whole-file compact mode. Keep the startup-loaded files themselves compact; do not rely on hidden startup-safe subsections inside larger narrative files.

| File | Keep in compact path | Move to drill-down files | Target budget |
|---|---|---|---|
| `core/INIT.md` | Routing authority, active thresholds, compact contract, decision triggers | Long rationale, runbooks, full algorithms | ~2,600 tokens |
| `core/memory/HOME.md` | Context loading order, top-of-mind items, maintenance probes | Detailed rationale, full namespace rules | ~500 tokens |
| `core/memory/users/SUMMARY.md` | User portrait, working style, active durable goal | Detailed profile evidence | ~450 tokens |
| `core/memory/activity/SUMMARY.md` | Live themes, recent continuity, retrieval guidance | Chat-by-chat narrative | ~750 tokens |
| `core/memory/working/USER.md` | User-authored current constraints | Historical notes that no longer affect current work | ~400 tokens |
| `core/memory/working/CURRENT.md` | Active threads, immediate next actions, open questions, drill-down refs | Extended analysis and large tables | ~650 tokens |

These targets leave reserve headroom inside the 7k returning-session ceiling. If a file exceeds its target, move depth into a plan, scratchpad, or chat summary and link from the compact surface.

## Compact file success criteria

See compact contract table above for per-file targets and what belongs in each file vs. drill-down reads.

## Current active stage: Exploration

_Last assessed: 2026-03-19 — Exploration retained (all signals within bounds)_

**Exploration defaults apply** — use the threshold values in the Active thresholds table below until a periodic review triggers a stage transition.

## Last periodic review

**Date:** 2026-03-19

## Active thresholds

| Parameter | Active value | Stage |
|---|---|---|
| Low-trust retirement threshold | 120 days | Exploration |
| Medium-trust flagging threshold | 180 days | Exploration |
| Staleness trigger (no access) | 120 days | Exploration |
| Aggregation trigger | 15 entries | Exploration |
| Identity churn alarm | 5 traits/session | Exploration |
| Knowledge flooding alarm | 5 files/day | Exploration |
| Task similarity method | Session co-occurrence | Exploration |
| Cluster co-retrieval threshold | 3 sessions | Exploration |

---

## Active task similarity method

**Method:** Session co-occurrence

**Grouping precedence:** Group ACCESS entries by `session_id` when present. If an entry predates `session_id`, fall back to `date` for backward compatibility.

**Default before first assessment:** Treat as Exploration; use values in this file.

**Full algorithm:** See `core/governance/curation-algorithms.md` (load only for aggregation or stage transition).

---

## Decision guide: trust decay

Trust sets the decay threshold; freshness comes from the effective date (`last_verified` if present, else `created`).

- `trust: low` — older than **120 days** without re-verification: archive to `core/memory/knowledge/_archive/` and remove from SUMMARY.md.
- `trust: medium` — older than **180 days** without re-verification: flag in `core/governance/review-queue.md` for review or demotion.
- `trust: high` — older than **365 days**: mention during periodic review for a freshness check only.
- Files without frontmatter are treated as `trust: medium` until fixed.

See `core/governance/security-signals.md` for freshness-vs-confidence rationale and retroactive-frontmatter guidance.

## Decision guide: anomaly detection

| Signal | Trigger | Action |
|---|---|---|
| Identity traits changed in one session | > **5** traits | Flag in `core/governance/review-queue.md` |
| Knowledge files on same topic from `external-research`, same session or day | > **5** files | Flag in `core/governance/review-queue.md` |
| File dormant for **120 days**, then retrieved 3+ times in one session | Spike after dormancy | Flag in `core/governance/review-queue.md` |
| File retrieved 5+ times total but never explicitly approved by user | 5 retrievals | Flag in `core/governance/review-queue.md` |

## Decision guide: ACCESS.jsonl aggregation

Aggregate when entries accumulated since the last aggregation reach **15**.

1. Refresh the relevant SUMMARY.md usage patterns.
2. Enrich high-value files (5+ retrievals, mean helpfulness ≥ 0.7).
3. Review low-value files (3+ retrievals, mean helpfulness ≤ 0.3).
4. Scan for cross-folder co-retrieval clusters using the active task similarity method.
5. Archive processed entries to `ACCESS.archive.jsonl` and reset the live `ACCESS.jsonl`.

Entry counting: count entries in current `ACCESS.jsonl`, not the archive. For full procedure, load `core/governance/curation-algorithms.md`.

## How to update this file

After periodic review:

1. Update the active stage and last-assessed line.
2. Update the last periodic review date.
3. Copy the chosen stage values from `core/governance/system-maturity.md` into the Active thresholds table.
4. Keep the compact bootstrap contract and decision triggers aligned with validator rules.
5. Log the change in `CHANGELOG.md`.

---

## Context budget guideline

| Session mode | Typical token cost |
|---|---|
| First-run onboarding bootstrap | ~15,000–20,000 |
| Returning compact session | ~3,000–7,000 |
| Full bootstrap / periodic review | ~18,000–25,000 |
