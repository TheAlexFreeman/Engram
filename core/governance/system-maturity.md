# System Maturity

This document tracks the memory system's developmental stage and defines candidate parameter sets for each stage. The core insight: a young system should bias toward exploration (capturing aggressively, retiring slowly), while a mature system should bias toward order (capturing selectively, retiring confidently). This file is a reference for maturity assessment and parameter selection during periodic review; `core/INIT.md` is the live runtime source for active thresholds.

## Maturity signals

The system's developmental stage is assessed from quantitative signals, not calendar time:

| Signal | How to measure | What it indicates |
|--------|---------------|-------------------|
| **Total sessions** | Count of chat folders in `core/memory/activity/` | Volume of interaction |
| **ACCESS density** | Total ACCESS.jsonl entries across all folders | Depth of retrieval history |
| **File coverage** | Percentage of content files accessed at least once | How much of the memory has proven relevant |
| **Confirmation ratio** | Ratio of `trust: high` files to total content files | How much of the memory has been validated |
| **Identity stability** | Sessions since last identity trait change | Whether the user portrait has converged |
| **Retrieval success rate** | Mean helpfulness score across recent ACCESS entries | Whether the system is serving useful memory |

## Maturity stages

### Stage 1: Exploration (young system)

**Typical signals:** < 20 sessions, < 50 ACCESS entries, file coverage < 30%, confirmation ratio < 0.3

**Bias:** Toward chaos. The system doesn't yet know what matters.

| Parameter | Exploration setting | Rationale |
|-----------|-------------------|-----------|
| Low-trust retirement threshold | 120 days | Keep unverified content longer — it might prove useful |
| Medium-trust flagging threshold | 180 days | Don't rush to flag content for re-verification |
| Staleness trigger (no access) | 120 days | Tolerate dormant files — usage patterns haven't stabilized |
| Aggregation trigger | 15 entries | Aggregate sooner to build retrieval patterns faster |
| Identity churn alarm | 5 traits/session | Allow more identity exploration before flagging |
| Knowledge flooding alarm | 5 files/day | Allow more aggressive knowledge capture |
| Task similarity method | Session co-occurrence | Coarse proxy; insufficient data for finer-grained detection |
| Cluster co-retrieval threshold | 3 sessions | Low bar appropriate for small dataset |

### Stage 2: Calibration (adolescent system)

**Typical signals:** 20–80 sessions, 50–200 ACCESS entries, file coverage 30–60%, confirmation ratio 0.3–0.6

**Bias:** Balanced. The system has patterns but they're still evolving.

| Parameter | Calibration setting | Rationale |
|-----------|-------------------|-----------|
| Low-trust retirement threshold | 60 days | Start applying pressure on unverified content |
| Medium-trust flagging threshold | 120 days | Moderate verification expectations |
| Staleness trigger (no access) | 90 days | Standard maintenance cadence |
| Aggregation trigger | 20 entries | Standard aggregation frequency |
| Identity churn alarm | 3 traits/session | Standard drift detection |
| Knowledge flooding alarm | 3 files/day | Standard flooding detection |
| Task similarity method | Task-string normalization | Finer-grained; retroactively normalizes Phase 1 data. See `core/governance/curation-algorithms.md` § Phase 2 |
| Cluster co-retrieval threshold | 3 sessions | Same threshold; task-group scoping reduces false positives |

### Stage 3: Consolidation (mature system)

**Typical signals:** > 80 sessions, > 200 ACCESS entries, file coverage > 60%, confirmation ratio > 0.6

**Bias:** Toward order. The system knows what matters and should be selective.

| Parameter | Consolidation setting | Rationale |
|-----------|----------------------|-----------|
| Low-trust retirement threshold | 45 days | Aggressive cleanup — enough signal to judge value quickly |
| Medium-trust flagging threshold | 90 days | Expect timely verification |
| Staleness trigger (no access) | 60 days | Unused memory in a mature system is likely irrelevant |
| Aggregation trigger | 25 entries | Larger batches for more statistically meaningful patterns |
| Identity churn alarm | 2 traits/session | Mature identity should be stable |
| Knowledge flooding alarm | 2 files/day | Past bulk knowledge acquisition |
| Task similarity method | Controlled category vocabulary | Machine-readable, stable across sessions. See `core/governance/curation-algorithms.md` § Phase 3 |
| Cluster co-retrieval threshold | 4 sessions | Higher bar for cleaner category-based signal |

## Current stage assessment

First assessed 2026-03-19 during periodic review. Record each assessment below with the date and signal values.

### Assessment log

## [2026-03-19] Stage assessment

**Stage:** Exploration
**Signals:**
- Total sessions: < 5
- ACCESS density: < 50 entries
- File coverage: < 30%
- Confirmation ratio: < 0.3
- Identity stability: insufficient data
- Retrieval success rate: insufficient data

**Active parameter set:** Exploration
**Notes:** All measurable signals remain well within Exploration bounds. System is young with limited session history and access data. Exploration retained — no transition warranted.

---


## Stage transitions

Transitions are not hard boundaries. The agent should:

1. **Assess maturity** during each periodic review (see `core/governance/update-guidelines.md`).
2. **Advance only on a clear majority** — 4 or more of the 6 signals must agree on the later stage before advancing. A 3-3 split is not sufficient to move forward.
3. **Tiebreaker: stay put, or prefer the earlier stage.** If signals are evenly split (3-3) between two adjacent stages, remain in the current stage. If there is no prior assessment (first evaluation ever), default to Exploration regardless of the split.
4. **Regress only on sustained signal drop.** Do not revert to an earlier stage based on a single signal crossing back. If 4 or more signals drop back to an earlier stage's range, flag for re-assessment in `core/governance/review-queue.md` rather than auto-reverting — regression should be a deliberate decision, not a reflexive one.
5. **Log all transitions and close calls** in both this file's assessment log and in `CHANGELOG.md`. A "close call" (3-3 split that was resolved by tiebreaker) is worth noting so future assessments can see the trend.

The system can also regress: if a user's focus shifts dramatically (new job, new domain), many existing files may become irrelevant, file coverage drops, and the system should temporarily revert toward exploration parameters for the new domain while maintaining consolidation parameters for stable areas. This is a judgment call for the agent, documented in the assessment log.

When a stage transition occurs, load `core/governance/curation-algorithms.md` for the full algorithmic specifications of the new stage's task similarity method.
