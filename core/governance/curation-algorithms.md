# Curation Algorithms

**Load this file only when running ACCESS.jsonl aggregation or a stage transition.** It is not needed during normal sessions. For active thresholds and the current task similarity method, see `core/INIT.md`.

This document contains the full algorithmic specifications for task similarity detection, cluster identification, and category vocabulary emergence. These algorithms progress through three phases aligned with the system's maturity stages.

---

## Task similarity: Phase 1 — Session co-occurrence (Exploration)

"Similar tasks" = occurred in the same session. Use `session_id` when present in ACCESS.jsonl entries; fall back to `date` only for legacy entries that predate the `session_id` field.

### Algorithm during aggregation

1. Group all ACCESS.jsonl entries by `session_id` when present; otherwise group by `date` as a legacy fallback.
2. Within each session-group, collect the set of distinct files retrieved.
3. For each pair of files from different folders, count how many session-groups contain both.
4. Flag groups of 3+ files from 2+ folders where every pair co-occurs in 3+ session-groups as cluster candidates.

**Known weakness:** Long or multi-topic sessions create false co-occurrences. Acceptable at Exploration because there is not enough data for finer-grained detection, and false clusters will be pruned at Phase 2.

**The `task` field is not used for clustering in this phase** — but write meaningful task descriptions; they are raw material for Phase 2's normalization.

---

## Task similarity: Phase 2 — Task-string normalization (Calibration)

"Similar tasks" = entries whose `task` strings normalize to the same equivalence class. Eliminates Phase 1's false co-occurrence problem by splitting multi-topic sessions into distinct task groups.

### Normalization procedure (executed during aggregation)

1. Collect all `task` values from unarchived ACCESS.jsonl entries.
2. Normalize each string: lowercase → remove articles/prepositions/conjunctions → collapse whitespace → lemmatize to root forms (e.g., "debugging" → "debug") → sort remaining tokens alphabetically.
3. Group entries whose normalized token sets are identical. Merge entries with Jaccard similarity ≥ 0.7 into the same group if neither already belongs to a different group.
4. Name each group with a short descriptive label derived from the original task strings (e.g., "react-performance-debug").
5. Detect clusters **within** each task group: 3+ files from 2+ folders, each appearing in 3+ entries with distinct dates within that group.

### Persistent storage

Task groups are recorded in `core/governance/task-groups.md` (created automatically during the first Calibration-stage aggregation). Each group entry includes: the group name, representative task strings, normalized tokens, first-seen date, session count, and commonly co-retrieved files. This history feeds Phase 3's vocabulary emergence.

### Retroactive application

At the Exploration → Calibration transition, the agent normalizes all historical `task` strings (including archived entries) to seed the initial task groups. No schema change is needed — Phase 2 operates entirely on the existing free-text `task` field.

---

## Task similarity: Phase 3 — Controlled category vocabulary (Consolidation)

"Similar tasks" = entries sharing the same `category` value from a controlled vocabulary. Machine-readable, stable across sessions and model switches.

### Vocabulary emergence (executed once at Calibration → Consolidation transition)

1. Read `core/governance/task-groups.md`. Prune groups with fewer than 5 matched sessions (insufficient evidence).
2. Merge near-duplicate groups (80%+ token overlap AND 60%+ overlap in co-retrieved files).
3. Promote surviving groups to categories. Write the vocabulary to `core/governance/task-categories.md`.
4. Propose the ACCESS.jsonl schema addition to the user — adding `category` is a protected-tier change.

### Schema addition

Once approved, ACCESS.jsonl entries gain a `category` field:

```json
{
  "file": "...",
  "date": "...",
  "task": "...",
  "category": "react-performance",
  "helpfulness": 0.0,
  "note": "..."
}
```

> **JSONL format note:** The multi-line format above is for documentation readability only. ACCESS.jsonl requires one JSON object per line. Write each entry as a single line when appending to the file:
> `{"file": "...", "date": "...", "task": "...", "category": "react-performance", "helpfulness": 0.0, "note": "..."}`

The `task` field is retained as human-readable context and raw input for vocabulary refinement. The `category` field is selected from `core/governance/task-categories.md` at write time. If no category fits (Jaccard similarity below 0.5), assign `uncategorized`.

### Cluster detection (Consolidation)

3+ files from 2+ folders, each appearing in 4+ entries (raised threshold — cleaner signal warrants a higher bar) sharing the same `category` value.

### Vocabulary maintenance (during each Consolidation-stage aggregation)

- If 5+ `uncategorized` entries cluster around a new theme, propose a new category (protected-tier).
- If a category has zero entries within the staleness trigger window, flag for retirement (proposed-tier).
- If entries within a category have very low mutual co-retrieval, the category may be too broad — propose splitting.

### Backward compatibility

At the Calibration → Consolidation transition, the agent backfills `category` values on all historical entries (including archives) by matching task strings against the new vocabulary.

---

## Cluster co-retrieval threshold by stage

| Stage         | Threshold  | Rationale                                                            |
| ------------- | ---------- | -------------------------------------------------------------------- |
| Exploration   | 3 sessions | Low bar appropriate for small dataset and coarse similarity signal   |
| Calibration   | 3 sessions | Same threshold, but finer task-group scoping reduces false positives |
| Consolidation | 4 sessions | Higher bar appropriate for cleaner category-based signal             |

The active threshold is recorded in `core/INIT.md`.

## Aggregation runbook

Concrete steps for running ACCESS.jsonl aggregation. This procedure applies at any maturity stage — the task similarity method changes by stage, but the data pipeline is the same.

### Prerequisites

- At least one `ACCESS.jsonl` file has reached the active aggregation trigger (see `core/INIT.md`).
- You have loaded this file and `core/INIT.md`.

### Procedure

1. **Collect entries.** Read all non-empty `ACCESS.jsonl` files from the access-tracked memory namespaces (`core/memory/users/`, `core/memory/knowledge/`, `core/memory/knowledge/_unverified/`, `core/memory/skills/`, `core/memory/working/projects/`, and `core/memory/activity/`).
2. **Merge into a working set.** Group entries by `session_id` when present; fall back to `date` for legacy entries without `session_id`.
3. **Run task similarity analysis** using the phase appropriate to the current maturity stage (Phase 1 / 2 / 3 above). Record any new clusters or task groups.
4. **Compute per-file statistics.** For each file appearing in the working set: total retrievals, mean helpfulness, sessions where retrieved, co-retrieved files.
5. **Identify high-value files** (5+ retrievals, mean helpfulness ≥ 0.7). Enrich per `core/governance/curation-policy.md` § "Knowledge amplification."
6. **Identify low-value files** (3+ retrievals, mean helpfulness ≤ 0.3). Investigate root cause and flag for retirement if appropriate.
7. **Update SUMMARY.md files.** Refresh the "Usage patterns" section in each folder's SUMMARY.md with: high-value files, low-value files, co-retrieval clusters, and retrieval trends since last aggregation.
8. **Update task-groups or task-categories.** At Calibration+: write or update `core/governance/task-groups.md`. At Consolidation: update `core/governance/task-categories.md`.
9. **Archive entries.** Append the current contents of each `ACCESS.jsonl` to `ACCESS.archive.jsonl` in the same folder (create the archive file if it doesn't exist).
10. **Reset ACCESS.jsonl files.** Clear each processed `ACCESS.jsonl` to empty.
11. **Commit.** Log as a `[curation]` commit with a summary of findings (e.g., "Aggregation: 15 entries, 2 high-value files, 1 cluster detected").

### Post-aggregation

- If aggregation revealed files needing retirement, add entries to `core/governance/review-queue.md`.
- If a maturity stage transition is indicated, follow the transition procedure in `core/governance/system-maturity.md` and update `core/INIT.md`.
