# Governance Maturity Roadmap

**Created:** 2026-03-22
**Last revised:** 2026-03-22
**Context:** The governance layer was consolidated from 12 files to 11 through three phases of structural work (integration fixes, small-file absorption, concern-based splitting). This roadmap tracks forward-looking improvements that become relevant as the system matures through its Exploration → Calibration → Consolidation lifecycle.

---

## Current state: 12 files (11 policy documents + this roadmap)

| File | Role | Load pattern |
|---|---|---|
| `curation-policy.md` | Memory lifecycle, access-driven curation, emergent categorization | Full bootstrap + periodic review |
| `content-boundaries.md` | Trust-weighted retrieval, instruction containment | On-demand (retrieval boundary checks) |
| `security-signals.md` | Temporal decay, anomaly detection, drift, governance feedback, review orchestration | Periodic review |
| `update-guidelines.md` | Provenance, change-control tiers, approval workflow, periodic review procedure | Full bootstrap + periodic review |
| `curation-algorithms.md` | Task similarity phases, cluster detection, aggregation runbook | On-demand (aggregation or stage transition) |
| `system-maturity.md` | Stage definitions, parameter tables, transition rules, assessment log | Periodic review |
| `scratchpad-guidelines.md` | Scratchpad lifecycle, promotion path, three-session rule | On-demand (writing to scratchpad) |
| `review-queue.md` | Queue format, triage timing, lifecycle rules | On-demand (when it has entries) |
| `first-run.md` | Streamlined first-session bootstrap | First run only |
| `session-checklists.md` | Session runbooks + periodic integrity audit | On-demand |
| `belief-diff-log.md` | Drift audit entry format and log | Periodic review |

---

## Observation items (next periodic review)

These are observation-driven evaluations, not predetermined changes. Log findings in the periodic review assessment notes.

### Governance/skills boundary

**Question:** `session-checklists.md` summarizes three skill files (`session-start.md`, `session-sync.md`, `session-wrapup.md`). Changes to session workflows require updating both layers. During the next periodic review, compare ACCESS patterns: do agents load the governance summary, the skill files, or both? If one layer is consistently bypassed, consider collapsing the redundancy.

### Anomaly signal calibration

**Question:** `security-signals.md` defines four anomaly signals and four drift signals. Before the first Calibration assessment, review whether any signals have fired. If none have, the thresholds may be too lenient; if many have with high false-positive rates, the thresholds need tightening. This is the feedback loop described in `security-signals.md` § "Governance evaluation protocol" point (2).

---

## Phase 1: Governance file versioning

**Trigger:** First Calibration stage transition (see `system-maturity.md` § Stage 2 signals).

**Problem:** By Calibration, governance files will have been through multiple revision cycles. Without revision dates, periodic reviews cannot quickly identify stale governance — files that haven't been touched since early Exploration may contain rules that no longer reflect actual system behavior.

**Changes:** Add a `<!-- last_revised: YYYY-MM-DD -->` HTML comment to the first line of each governance file (after the heading). Governance files are exempt from YAML frontmatter, but an HTML comment is invisible to agents during normal reads while remaining greppable during audits.

**Periodic review integration:** Step 4 of the governance evaluation protocol in `security-signals.md` (consistency check) should include: "Flag any governance file whose `last_revised` date is more than two stage-transitions old."

**Process:** Low-risk. Can be done as a single commit across all 12 files. No cross-reference updates needed.

---

## Phase 2: Governance doc token budgets

**Trigger:** 3+ periodic reviews completed (enough data to measure actual load patterns).

**Problem:** The compact bootstrap contract in `core/INIT.md` sets token targets for memory summaries, but governance files loaded during full bootstrap and periodic review have no target budgets. As files grow through amendments, context efficiency degrades without a measurable signal.

**Changes:**

1. Measure actual token costs of each governance file at the time this phase triggers.
2. Add a second budget table to `core/INIT.md` § "Compact bootstrap contract" for governance files loaded in full bootstrap and periodic review modes:

| File | Target budget | Notes |
|---|---|---|
| `curation-policy.md` | TBD | Full bootstrap |
| `update-guidelines.md` | TBD | Full bootstrap |
| `security-signals.md` | TBD | Periodic review |
| `system-maturity.md` | TBD | Periodic review |
| `session-checklists.md` | TBD | Periodic review (integrity audit) |

3. Update the validator to check governance file token budgets, mirroring the existing compact-file budget checks.

**Process:** Protected-tier. Token targets should be set from measurement, not prediction — hence the 3-review trigger.

---

## Phase 3: Machine-readable governance extraction

**Trigger:** MCP server evolves to enforce governance rules programmatically, or validator coverage expands beyond structural checks into behavioral policy.

**Problem:** `agent-bootstrap.toml` already expresses loading rules in machine-readable form. Other governance rules (folder behavioral contracts from `content-boundaries.md`, change-control tiers from `update-guidelines.md`, trust assignment rules) exist only as prose. If the MCP server or validators need to enforce these rules, they must parse Markdown — fragile and drift-prone.

**Proposed approach:**

- Extract folder contracts (the table in `content-boundaries.md` § "Folder behavioral contracts") into a TOML section in `agent-bootstrap.toml`.
- Extract change-control tier definitions into a parallel TOML section.
- Keep the Markdown governance files as the human-readable authority; the TOML becomes a machine-consumable mirror validated against the prose by the test suite.

**Prerequisite:** This is a "when the need arises" item. Do not build machine-readable governance speculatively. The trigger is a concrete MCP server or validator feature that requires structured policy data.

---

## Phase 4: Consolidation-stage governance review

**Trigger:** Consolidation stage transition (see `system-maturity.md` § Stage 3 signals: >80 sessions, >200 ACCESS entries, file coverage >60%, confirmation ratio >0.6).

**Problem:** Governance rules written during Exploration assume the system is young and uncertain. A mature system may need:

- **Tighter anomaly thresholds.** `security-signals.md` drift signals should be recalibrated against accumulated baseline data rather than theoretical defaults.
- **Richer cluster detection.** `curation-algorithms.md` Phase 3 (controlled category vocabulary) activates at Consolidation. The governance layer should document the new taxonomy management responsibilities that come with explicit categories.
- **Archival policy for governance artifacts.** `belief-diff-log.md` and `review-queue.md` resolved entries accumulate indefinitely. Define a retention policy — e.g., archive resolved queue entries older than 6 months, keep only the last 12 belief diffs in the active file with older entries in git history.
- **Multi-user considerations.** If the system supports multiple user profiles by Consolidation, `content-boundaries.md` folder contracts may need per-user scoping.

**Process:** This is a substantial governance revision, not a file-structure change. Evaluate each item during the first Consolidation periodic review and create individual `review-queue.md` proposals for any changes.

---

## Completed work

The following consolidation phases were completed to reach the current 11-file state:

| Phase | Changes | Date |
|---|---|---|
| Integration fixes | HOME.md references, skip-header cleanup, guardrails deduplication | 2026-03-22 |
| Small-file absorption | Retired `quick-reference.md`, absorbed `integrity-checklist.md` into `session-checklists.md`, absorbed `deferred-action-template.md` into `update-guidelines.md` | 2026-03-22 |
| Concern-based split | Split `curation-policy.md` → `curation-policy.md` + `content-boundaries.md` + `security-signals.md`; added periodic review orchestration to `security-signals.md` | 2026-03-22 |
