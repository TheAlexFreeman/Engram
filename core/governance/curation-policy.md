# Curation Policy

This document defines how memory is maintained, pruned, promoted, and retired. It is the immune system of the memory repo — preventing unbounded growth, information decay, and context pollution.

## The forgetting principle

Memory without forgetting degrades over time. Indiscriminate accumulation causes retrieval of stale information, context pollution from irrelevant details crowding out relevant ones, and growing costs as more material must be searched and loaded. **Forgetting is not failure. It is maintenance.**

## Lifecycle stages

Every piece of stored memory passes through these stages:

### 1. Capture

New information enters the system during a chat session. The agent identifies what is worth persisting based on the criteria in README.md ("What to store" / "What not to store").

### 2. Provisional storage

New memories are written with low confidence. Identity traits are tagged `[tentative]`. Unverified content starts with `created` but omits `last_verified` until a human confirms it. Skill files are marked as drafts until confirmed by successful use.

Unverified review state is tracked in `knowledge/_unverified/REVIEW_LOG.jsonl`. This file is committed, not gitignored, so review verdicts remain durable across sessions and auditable in git history. When the same file is reviewed multiple times, the most recent log entry is authoritative for pending-review views.

### 3. Confirmation

Through repeated access, user validation, or explicit approval, provisional memories are promoted to confirmed status. Confidence tags are upgraded. Skills are marked as tested.

### 4. Maintenance

Confirmed memories are periodically reviewed for staleness. Triggers for review: a file has not been accessed within the active staleness trigger window (see `core/INIT.md`; check `ACCESS.jsonl` or `ACCESS.archive.jsonl` for last access), the user contradicts information in the file, or a related file has been significantly updated creating potential inconsistency.

### 5. Retirement

Memories that are stale, contradicted, or consistently unhelpful are: **Demoted** (moved to `_archive/` subfolders such as `core/memory/knowledge/_archive/` or equivalent project-local archives, removed from the active `SUMMARY.md`, retained in git history), **Merged** (consolidated into a broader file if partially relevant but too granular), or **Deleted** (removed entirely if wrong or user-requested; git history preserves the record).

## Access-driven curation

ACCESS-driven curation applies to the access-tracked memory namespaces (listed in `core/INIT.md`). `core/governance/` is the governance layer and is not part of the ACCESS lifecycle for now.

The ACCESS.jsonl feedback loop is the primary curation signal:

- **High access + high helpfulness** (mean ≥ 0.5)**:** Core memory. Ensure it stays current and prominent in summaries.
- **High access + low helpfulness:** Distinguish two sub-ranges:
  - _Mean 0.2–0.4 (near-miss):_ Right context, rarely incorporated. Probably too broad, poorly differentiated, or covering two topics that should be split.
  - _Mean 0.0–0.1 (false-positive attractor):_ Consistently wrong context. Something about the title, tags, or SUMMARY.md placement is misleading. Retitle or retag rather than retire.
- **Low access + high helpfulness** (mean ≥ 0.5 when found)**:** Hidden gem. Improve the folder SUMMARY.md to give it better placement.
- **Low access + low helpfulness:** Retirement candidate. Flag for review.

## Knowledge amplification

When ACCESS.jsonl aggregation identifies a file as consistently high-value (5+ retrievals, mean helpfulness ≥ 0.7):

1. **Enrich cross-references.** Add a `## Related` section linking frequently co-retrieved files.
2. **Note task contexts.** Add a `## Proven useful for` section listing task types where it delivered value.
3. **Suggest expansion.** Note adjacent knowledge acquisition opportunities in `core/governance/review-queue.md`.
4. **Strengthen summary presence.** Ensure prominent, retrieval-friendly SUMMARY.md placement.

When a file is consistently low-value (3+ retrievals, mean helpfulness ≤ 0.3): investigate root cause (misleading title? stale? irrelevant?), demote summary presence, and flag for retirement if no longer useful.

## Summary refresh cadence

- **Chat-level summaries:** Immediately after each session.
- **Session reflection notes:** Immediately after each session (written to `reflection.md` in the chat folder — see format below).
- **Daily summaries:** End of each day with multiple sessions (skip for single-session days).
- **Monthly summaries:** First session of a new month, reviewing the prior month.
- **Yearly summaries:** First session of a new year, reviewing the prior year.
- **Folder SUMMARY.md files:** Updated on ACCESS.jsonl aggregation or significant new content.

### Session reflection format

Each session should produce a brief reflection note written to the chat folder as `reflection.md` (e.g. `core/memory/activity/YYYY/MM/DD/chat-NNN/reflection.md`):

```markdown
## Session reflection

**Memory retrieved:** [list of files accessed, with helpfulness scores]
**Memory influence:** [1-2 sentences on how retrieved memory shaped the session's responses]
**Outcome quality:** [brief assessment: did the session go well? did memory help or hinder?]
**Gaps noticed:** [any moments where relevant memory was missing, or irrelevant memory intruded]
**System observations:** [optional: any patterns about the memory system itself]
```

ACCESS.jsonl tracks file-level retrieval. Session reflection tracks the reasoning level — how memory was used, which combinations worked, and where the system has blind spots. Over time, reflection notes reveal characteristic strengths, blind spots, retrieval pattern quality, and combinatorial insights that pure access tracking cannot capture.

When reviewing reflection notes during periodic review, look for recurring themes and update folder SUMMARY.md files to address identified gaps, `core/governance/review-queue.md` with proposals to address systematic blind spots, and `core/governance/system-maturity.md` with observations relevant to stage assessment.

## Size limits

- **SUMMARY.md files:** 200–800 words (restructure folder if exceeding 1000).
- **Knowledge files:** 500–2000 words (split into subfolders beyond that).
- **Skill files:** 300–1000 words (may indicate multiple skills if exceeding 1000).
- **Chat summaries:** 100–400 words per session.

## Conflict resolution protocol

1. **Explicit correction wins.** User says "actually, I prefer X now" → update immediately. When creating a corrected replacement, set `superseded_by` on the old file pointing to the new one.
2. **Recent observation wins over old inference.** A `[tentative]` from today outweighs an `[inferred]` from six months ago.
3. **When uncertain, flag and ask.** Add both versions with a `[CONFLICT]` tag and raise it with the user.
4. **Never silently discard.** Git history is your safety net. Prefer `superseded_by` over deletion — it preserves retrievability for historical queries while directing agents to current truth.

## Content boundaries

Trust-weighted retrieval rules and instruction containment (folder behavioral contracts, the boundary-violation test) are in `core/governance/content-boundaries.md`.

## Security signals

Temporal decay rationale, access anomaly detection, drift detection, and governance self-evaluation are in `core/governance/security-signals.md`.

## Emergent categorization

The folder structure is a starting taxonomy, not permanent. Genuine structure should emerge from usage patterns.

### Cross-folder retrieval clusters

During ACCESS.jsonl aggregation, look for co-retrieval patterns across folders: 3+ files from 2+ different folders, co-retrieved in 3+ instances for similar tasks, constitute an emergent cluster.

**When a cluster is detected:** (1) Record the task context in `core/governance/task-groups.md` (Calibration+) or inline in `SUMMARY.md` (Exploration). (2) Name the cluster descriptively. (3) Document in relevant `SUMMARY.md` files. (4) Evaluate taxonomy fit — propose restructuring in `core/governance/review-queue.md` if needed.

**For the full task similarity algorithms (Phases 1–3), cluster detection procedures, and vocabulary emergence protocol:** Load `core/governance/curation-algorithms.md`. It is not needed during normal sessions — only during aggregation or stage transitions.

### Taxonomy health check

During periodic review: Are there folders with very low access that should be merged? Very high access that should be subdivided? Do folder names still describe their contents? Are there emergent clusters the structure fails to represent?

## Maturity-adaptive thresholds

The thresholds in this policy are reference values. Active thresholds always live in `core/INIT.md`. During periodic review, the agent uses `core/governance/system-maturity.md` to assess the system and choose the next parameter set, then copies the selected values into `core/INIT.md`.
