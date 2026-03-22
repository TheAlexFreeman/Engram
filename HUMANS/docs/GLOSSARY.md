# Glossary

**Human reference only.** Agents should not load this file during bootstrap or normal operation — every term defined here is introduced in context by the governance file that establishes it. This file exists for human readers who want a single-page reference.

Short definitions for terms used in this memory system. Canonical details are in README.md, `core/governance/curation-policy.md`, `core/governance/content-boundaries.md`, `core/governance/security-signals.md`, `core/governance/update-guidelines.md`, and `core/INIT.md`.

- **Session** — One chat folder under `core/memory/activity/YYYY/MM/DD/` (e.g. `chat-001`). One conversation corresponds to one session. See README § "Memory curation".

- **Retrieval** — Opening a specific content file (in `core/memory/users/`, `core/memory/knowledge/`, `core/memory/skills/`, `core/memory/working/projects/`, or `core/memory/activity/`) in response to a user query. Retrievals are logged in ACCESS.jsonl; SUMMARY.md and `core/governance/` reads are not. See README § "Memory curation".

- **Aggregation** — Processing an ACCESS.jsonl file when it reaches the active aggregation trigger: analyzing patterns, updating SUMMARY.md usage sections, archiving entries to ACCESS.archive.jsonl, and resetting ACCESS.jsonl. See README § "Aggregation" and `core/INIT.md` § "ACCESS.jsonl aggregation".

- **Trust level** — Classification (high / medium / low) in content frontmatter. Governs how the agent uses the file: high = use freely; medium = use with caution, surface provenance when influential; low = inform only, never instruct, always disclose provenance. See `core/governance/content-boundaries.md` § "Trust-weighted retrieval" and `core/governance/update-guidelines.md` § "Provenance metadata".

- **Maturity stage** — Developmental phase of the system: Exploration (young), Calibration (adolescent), or Consolidation (mature). `core/governance/system-maturity.md` defines the assessment criteria and candidate parameter sets; `core/INIT.md` records the active runtime thresholds and alarms.

- **Protected change** — Modifications that require explicit user approval and (where applicable) a CHANGELOG entry: `core/memory/skills/`, `core/governance/` (except machine-generated state files), README.md, CHANGELOG structure, bulk operations. See `core/governance/update-guidelines.md` § "Change categories".

- **Proposed change** — Modifications that require user awareness but not necessarily explicit approval before applying: new knowledge files, identity changes, promotion from quarantine, plan creation or scope changes, restructuring, retirement. See `core/governance/update-guidelines.md` § "Change categories".

- **Quarantine** — `core/memory/knowledge/_unverified/`. Staging area for externally sourced content; all such content lands here at `trust: low`. Promotion to `core/memory/knowledge/` requires user review. See README § "Security model" and `core/governance/curation-policy.md`.

- **Provenance** — Origin and verification metadata (source, origin_session, created, optional `last_verified`, trust) in YAML frontmatter on content files. See `core/governance/update-guidelines.md` § "Provenance metadata".

- **Plan** — Persistent multi-session roadmap stored in `core/memory/working/projects/`. Plans can contain task-local sequencing for that specific investigation, plus execution state such as `status` and `next_action`.

- **Belief diff** — Periodic summary of content changes since the last review. Recorded in `core/governance/belief-diff-log.md`. See `core/governance/update-guidelines.md` § "Belief diff".

- **Aggregation trigger** — The ACCESS.jsonl entry count that triggers aggregation processing. Active value in `core/INIT.md` § "Active thresholds".

- **Helpfulness score** — 0.0–1.0 rating in ACCESS.jsonl entries. See README § "Memory curation".

- **Instruction containment** — Structural rule: only `core/memory/skills/` and `core/governance/` may contain general procedural instructions; `core/memory/working/projects/` may contain task-local sequencing for the specific plan only. See `core/governance/content-boundaries.md` § "Instruction containment".

- **Temporal decay** — Automatic retirement or flagging based on the effective verification date: `last_verified` when present, otherwise `created`. See `core/INIT.md` § "Decision guide: trust decay".

- **Read-only operation** — Degraded mode where behavioral rules apply but writes are deferred. See `core/governance/update-guidelines.md` § "Read-only operation".

- **Deferred action** — A write action deferred due to read-only access. See `core/governance/update-guidelines.md` § "How to communicate deferred actions".

- **session_id** — Chat folder path (e.g. `core/memory/activity/2026/03/16/chat-001`) used to group ACCESS.jsonl entries by session. See README § "Memory curation".

- **Reflection note** — Meta-observation of session quality written to `reflection.md` in the chat folder. See README § "Session reflection".

- **Knowledge amplification** — Protocol for enriching high-value files identified during aggregation. See `core/governance/curation-policy.md` § "Knowledge amplification".

- **Curation algorithms** — Task similarity, cluster detection, and vocabulary emergence algorithms. See `core/governance/curation-algorithms.md` (loaded only during aggregation or stage transitions).
