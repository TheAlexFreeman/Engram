# Update Guidelines

This document defines how changes to the memory system are proposed, evaluated, and applied. It distinguishes between changes to _content_ (what the system knows) and changes to _governance_ (how the system operates).

## Provenance metadata

Every content file in `core/memory/users/`, `core/memory/knowledge/`, `core/memory/skills/`, and project plans under `core/memory/working/projects/` must include YAML frontmatter tracking its origin and trust level. Files in `core/governance/` and `core/memory/activity/` are exempt — governance docs are protected by change-control tiers, and chat transcripts are read-only archives.

### Required frontmatter schema

```yaml
---
source: user-stated | agent-inferred | agent-generated | external-research | skill-discovery | template | unknown
origin_session: core/memory/activity/YYYY/MM/DD/chat-NNN | setup | manual | unknown
created: YYYY-MM-DD
last_verified: YYYY-MM-DD # optional until a human confirms the content
trust: high | medium | low
superseded_by: memory/knowledge/path/to/successor.md # optional — marks this file as replaced
expires: YYYY-MM-DD # optional — declarative auto-expiration date
---
```

`last_verified` is omitted until a human explicitly reviews or confirms the content. When it is absent, `created` is the effective verification date for decay and freshness calculations.

`superseded_by` marks a file as replaced by a newer version at the given repo-relative path. Superseded files are deprioritized in retrieval but not auto-archived — they remain searchable for historical context. When present, trust-based decay calculations still apply but the file is surfaced as "superseded" in audit results. The path must point to an existing file within the memory tree.

`expires` declares an explicit expiration date. When the current date passes this value, the file is treated as expired regardless of its trust level. This is especially useful for `_unverified/` content, time-bound project context, and any fact with a known shelf life. Expired files are flagged for review or archival during the next audit. Unlike trust-based decay (which is threshold-relative), `expires` is an absolute deadline.

### Field definitions

- **source** — How this information entered the system.
  - `user-stated`: The user directly provided or dictated this content.
  - `agent-inferred`: The agent synthesized this from patterns across interactions.
  - `agent-generated`: The agent deliberately authored this artifact, such as a plan or roadmap.
  - `external-research`: Content from web searches, uploaded documents, or any source outside direct user conversation.
  - `skill-discovery`: A procedural pattern the agent identified from user corrections or repeated workflows.
  - `unknown`: Reserved for legacy backfill or genuinely unrecoverable origin. Do not use for new content when a concrete source can be identified.
  - `template`: Content pre-populated from a starter profile template installed by `setup.sh --profile`. Replaced with a concrete source (typically `user-stated`) after onboarding confirmation.
- **origin_session** — The canonical session path (e.g. `core/memory/activity/YYYY/MM/DD/chat-NNN`), or `setup` for starter templates, or `manual` for hand-authored content, or `unknown` for files predating this schema.
- **created** — Date the file was first written.
- **last_verified** — Optional date a human last reviewed or confirmed the content. Omit it for newly created content that has not yet been human-verified.
- **Plans special case.** For project plan files under `core/memory/working/projects/`, `last_verified` is the date the plan state was last reviewed or advanced in-session. It is a freshness marker for plan state, not a claim that every sentence in the plan has been externally verified.
- **trust** — The current trust classification (see `core/governance/content-boundaries.md` for retrieval behavior at each level).
- **superseded_by** — Optional. Repo-relative path to the file that replaces this one (e.g. `memory/knowledge/react/hooks-v2.md`). Set when a newer, more complete, or corrected version of the same knowledge is created. The superseded file is not deleted — it remains in git and in the folder tree — but retrieval should prefer the successor. Remove this field if the successor is itself retired or the supersession is reversed.
- **expires** — Optional. ISO date (`YYYY-MM-DD`) after which the content should be treated as expired. Use for time-bound facts (e.g. sprint goals, temporary workarounds, event-specific context). Expiration is independent of trust decay — a `trust: high` file can still expire. When `expires` is reached, the file enters the review/archive lifecycle as if its trust-based threshold had been exceeded.

### Trust assignment rules

| Source              | Initial trust | Promotion path                                                      |
| ------------------- | ------------- | ------------------------------------------------------------------- |
| `user-stated`       | `high`        | Already at highest level                                            |
| `agent-inferred`    | `medium`      | → `high` when user explicitly confirms                              |
| `agent-generated`   | `medium`      | → `high` when user explicitly endorses the plan or artifact         |
| `skill-discovery`   | `medium`      | → `high` after user approval + successful use                       |
| `external-research` | `low`         | → `medium` after user review; → `high` after user confirms accuracy |
| `template`          | `medium`      | → `high` after user confirms during onboarding                      |
| `unknown`           | `medium`      | Replace with a concrete source if later recovered                   |

Trust may also be demoted: if a `high`-trust file is found to contain inaccuracies or the user expresses doubt, downgrade to `medium` and update `last_verified`.

For new unverified files, omit `last_verified` rather than filling it with the creation date. Human confirmation during onboarding, review, or correction is what sets it.

### Operational confirmation signals

Multiple rules reference "user explicitly confirms" or "when user validates." These are the concrete signals that count as explicit confirmation:

- **Explicit affirmation.** User says "yes," "that's right," "confirmed," or equivalent in response to a direct question about the content.
- **Active correction that confirms the rest.** User corrects one detail but accepts the remainder — the uncorrected portions are confirmed.

The following is an **implicit** signal only — it does not count as explicit confirmation and cannot by itself be used to update `last_verified` or promote trust. Treat it as a prompt to seek explicit confirmation instead:

- **Incorporation without objection.** User builds on the content in their own workflow (e.g., references the information in a follow-up request) without challenging it.

These signals do **not** count as confirmation:

- **Silence or topic change.** The user simply moves on without acknowledging the content.
- **Passive non-objection.** The content was loaded but never surfaced to or acknowledged by the user.
- **Automated retrieval.** The file was retrieved by the agent but never discussed.

When confirmation occurs, update `last_verified` to the current date and promote the trust level per the trust assignment rules above.

### Retroactive application

Files that predate this schema should have frontmatter added during the next periodic review, using `source: unknown` and `trust: medium`. If the reviewer actually reads and verifies the content during backfill, set `last_verified` to the review date. If the backfill is mechanical (adding metadata without verifying content), omit `last_verified` and let `created` serve as the effective verification date — this prevents conflating "I added metadata" with "I verified this content." If the original creation date cannot be determined, use the backfill date as `created`.

## Architectural standard for system changes

When the agent is reviewing or modifying the memory system itself — governance docs, routing manifests, bootstrap/setup flows, validation rules, or other protected architecture — the proposal must address the three architectural guardrails defined in `README.md` § "Architectural guardrails for system changes": **consistency**, **user-friendliness**, and **context efficiency**.

For system-level changes, the change summary is incomplete unless it explains the expected effect on all three dimensions, including any tradeoffs or follow-up alignment work.

## Preferred memory tool surface

MCP preference rule: see `core/INIT.md` § "MCP preference."

This preference affects the interface, not the authority chain:

- `core/INIT.md`, `README.md`, and the folder summaries still govern what to load and why.
- MCP preference does not bypass trust-weighted retrieval, instruction containment, or protected-change approvals.
- Raw file edits remain the fallback for operations the MCP surface does not yet cover.

## Change categories

### Automatic changes (no approval needed)

- Appending entries to ACCESS.jsonl files.
- Writing chat transcripts and chat-level summaries to `core/memory/activity/`.
- Writing external-research results to `core/memory/knowledge/_unverified/` (never directly to `core/memory/knowledge/`).
- Updating "Usage patterns" sections in SUMMARY.md files based on access aggregation.
- Routine progress updates in project plans: `status`, `next_action`, progress text, `last_verified`, and `core/memory/working/projects/SUMMARY.md` coverage refreshes.
- Updating `core/governance/task-groups.md` during ACCESS.jsonl aggregation (Calibration stage and beyond).
- Routine summary refreshes at any level.

### Proposed changes (require user awareness)

- Adding new knowledge files to `core/memory/knowledge/` (i.e., outside `_unverified/`).
- Creating meta-knowledge files (emergent abstractions) — propose to user, do not create silently.
- Adding, modifying, or removing files in `core/memory/users/`.
- Creating a new plan in `core/memory/working/projects/`.
- Archiving, retiring, or materially changing the scope of a plan in `core/memory/working/projects/`.
- Promoting files from `core/memory/knowledge/_unverified/` to `core/memory/knowledge/`.
- Restructuring folders (renaming, splitting, merging).
- Retiring or archiving memory files.
- Modifying any SUMMARY.md in ways that change meaning rather than just updating coverage.

For proposed changes: describe the change and reasoning to the user. If approved, apply and log in CHANGELOG.md. If the user is unavailable, add to `core/governance/review-queue.md`.

### Approval workflow

**For proposed changes:**

1. Present a 2–3 sentence summary of the change and your reasoning.
2. Wait for an explicit response (approval or rejection). Do not infer approval from silence or topic changes.
3. If approved → apply the change and log in CHANGELOG.md.
4. If rejected → acknowledge and do not proceed. Note the rejection context for future reference.
5. If the user doesn't respond and the session continues on other topics → add to `core/governance/review-queue.md` as `type: proposed`.

**For protected changes:**

Same workflow, but with elevated formality: state explicitly that the change requires approval because it modifies a protected file (`core/memory/skills/`, `core/governance/`, `README.md`). For system-level changes, include the expected impact on consistency, user-friendliness, and context efficiency. Use phrasing like: "This requires your explicit approval because it modifies [target]. Shall I proceed?"

**What counts as approval:** An explicit affirmative response — "yes," "go ahead," "approved," "do it," or equivalent. Lack of objection, moving on to another topic, or ambiguous responses ("maybe," "I guess") are not approval. When in doubt, ask again clearly.

### Protected changes (require explicit approval)

- Creating, modifying, or removing files in `core/memory/skills/`.
- Any modification to files in `core/governance/` (including this file), **with the exception of machine-generated state files** listed below.
- Any modification to `README.md`.
- Any modification to `CHANGELOG.md` beyond appending new entries.
- Bulk operations (retiring multiple files, restructuring multiple folders).

**Machine-generated state files in `core/governance/` (exempt from protected-change requirement):**

| File                      | Generated by                                  | Why exempt                                                                                                    |
| ------------------------- | --------------------------------------------- | ------------------------------------------------------------------------------------------------------------- |
| `core/governance/task-groups.md`     | ACCESS.jsonl aggregation (Calibration stage+) | Auto-generated data file, not a governance document                                                           |
| `core/governance/task-categories.md` | Calibration → Consolidation transition        | Distilled from task-groups.md; initial creation requires protected approval, routine maintenance is automatic |

Protected changes must never be applied silently. Always present them to the user with full reasoning and wait for explicit confirmation.

**Why `core/memory/skills/` is protected:** Skill files contain procedures the agent will execute. They are the highest-value target for memory injection — a poisoned skill file directly controls agent behavior.

## Commit conventions

When the agent has write access to the repository, commits should follow this format:

```
[category] brief description

Longer explanation if needed. Include reasoning for non-obvious changes.
```

Categories and their change-control tiers:

| Prefix | Typical paths | Change tier |
|---|---|---|
| `[access]` | `ACCESS.jsonl` files | Automatic |
| `[chat]` | `core/memory/activity/` | Automatic |
| `[curation]` | `core/memory/knowledge/_unverified/` promotions, SUMMARY refreshes | Automatic or Proposed |
| `[identity]` | `core/memory/users/` | Proposed |
| `[knowledge]` | `core/memory/knowledge/` | Automatic (`_unverified/`) or Proposed (verified) |
| `[plan]` | `core/memory/working/projects/` | Automatic (progress) or Proposed (create/archive/scope) |
| `[scratchpad]` | `core/memory/working/` (USER.md, CURRENT.md) and `core/memory/working/notes/` | Automatic |
| `[skill]` | `core/memory/skills/` | Protected |
| `[system]` | `core/governance/`, `README.md`, `CHANGELOG.md` | Protected |

### Publication semantics

When the MCP has write access, governed publication uses a porcelain-first, plumbing-fallback model:

- **Single-writer rule:** only one writer may publish commits for a worktree at a time. If a write lock is already held, the agent should wait briefly and then fail clearly rather than racing another publisher.
- **Preferred publication path:** use standard git porcelain (`git commit`, `git revert`) whenever the index is available.
- **Degraded publication path:** if porcelain fails because the index cannot be locked, the agent may publish through git plumbing by replaying the staged object IDs into an alternate index, writing a tree, creating the commit with `commit-tree`, and advancing the branch ref with `update-ref` guarded by the expected parent SHA.
- **No silent scope widening:** degraded publication must preserve the governed staged snapshot only. It must not pull in unrelated staged files or unstaged working-tree edits.
- **Visibility:** tool outputs should surface publication metadata and warnings so callers can distinguish normal publication from degraded publication.

### Reverting memory commits

When using the MCP revert surface, treat revert as a two-step operation rather than a single destructive action:

1. Call `memory_revert_commit` with `confirm: false` (or omit `confirm`) to preview the target commit.
2. Review the returned `target_message`, `files_changed`, `applies_cleanly`, and `policy_reasons`.
3. Call `memory_revert_commit` again with `confirm: true` and the returned `preview_token` only if the preview is still acceptable.

The preview token is tied to the current `HEAD`. If the repository moves between preview and confirm, the confirm call is rejected and the agent must preview again.

`memory_revert_commit` is intentionally scoped to memory-domain history. Confirm is rejected when any of the following are true: the target is a merge commit, the commit prefix is not one of the known memory prefixes, the revert would not apply cleanly at the current `HEAD`, the commit touches files outside the governed memory surface, or a `[system]` commit touches anything outside governance files such as `governance/`, `README.md`, `CHANGELOG.md`, `AGENTS.md`, `CLAUDE.md`, or `agent-bootstrap.toml`.

## Read-only operation

Some deployment contexts give the agent read access but not write access — sandboxed chat environments, models without tool use, or sessions where git commits are disabled. The memory system degrades gracefully.

### What still applies

All behavioral rules remain active regardless of write access: trust-weighted retrieval, instruction containment, decay awareness, and security anomaly detection.

### What to defer

| Action                            | Deferred behavior                                                     |
| --------------------------------- | --------------------------------------------------------------------- |
| Appending to ACCESS.jsonl         | Compile entries mentally; present to user as a block to copy in       |
| Writing chat summaries            | Present the summary as output; user can paste it into the repo        |
| Updating SUMMARY.md files         | Note which summaries need updating and what changes are needed        |
| Writing to `core/governance/review-queue.md` | Surface the finding verbally and describe what entry would be written |
| Logging a maturity assessment     | Run the assessment, report the result, ask the user to commit it      |
| Periodic review curation actions  | Run through the checklist, report findings; user handles the commits  |
| Writing session reflection notes  | Summarize the reflection verbally; user can paste it in               |

### How to communicate deferred actions

At the end of any session where write actions were deferred, present a concise **deferred-action summary**:

```
## Deferred actions (write access required)

### ACCESS.jsonl entries
[folder/ACCESS.jsonl]
{"file": "...", "date": "...", "task": "...", "helpfulness": 0.7, "note": "...", "session_id": "memory/activity/YYYY/MM/DD/chat-NNN"}

Optional ACCESS metadata may also include `category`, `mode`, `task_id`, and `estimator` provenance when available.

### Review-queue entries
[core/governance/review-queue.md]
- type: security, file: memory/knowledge/some-file.md, pattern: "always do X" detected

### Other
- SUMMARY.md for core/memory/knowledge/ needs "Usage patterns" updated: react-patterns.md is high-value (7 retrievals)
```

This makes the read-only session auditable and allows the user to batch-commit the deferred actions.

### Worked example (reference only)

_This example illustrates the format above. After your first read-only session, you know the pattern — skim or skip on subsequent loads._

A session where the agent retrieved three knowledge files and noticed a boundary violation:

```
## Deferred actions (write access required)

### ACCESS.jsonl entries
[core/memory/knowledge/ACCESS.jsonl]
{"file": "memory/knowledge/react-performance-patterns.md", "date": "2026-03-17", "task": "optimize dashboard rendering", "helpfulness": 0.8, "note": "directly applicable memoization patterns", "session_id": "memory/activity/2026/03/17/chat-002"}
{"file": "memory/knowledge/browser-api-reference.md", "date": "2026-03-17", "task": "optimize dashboard rendering", "helpfulness": 0.4, "note": "opened but only tangentially relevant", "session_id": "memory/activity/2026/03/17/chat-002"}

[core/memory/users/ACCESS.jsonl]
{"file": "memory/users/communication-preferences.md", "date": "2026-03-17", "task": "calibrate response style", "helpfulness": 0.9, "note": "shaped concise code-first response format", "session_id": "memory/activity/2026/03/17/chat-002"}

[core/memory/working/projects/ACCESS.jsonl]
{"file": "memory/working/projects/performance-investigation.md", "date": "2026-03-17", "task": "resume multi-session performance investigation", "helpfulness": 0.8, "note": "provided the active checklist and next step for the session", "session_id": "memory/activity/2026/03/17/chat-002"}

### Review-queue entries
[core/governance/review-queue.md]
- type: security, trigger: boundary-violation, file: memory/knowledge/react-performance-patterns.md, pattern: "always use React.memo for list items" — imperative instruction detected; candidate for reclassification to memory/skills/

### Other
- `core/memory/knowledge/SUMMARY.md` needs "Usage patterns" updated: react-performance-patterns.md is high-value (6 retrievals, mean helpfulness 0.82)
- `core/memory/working/projects/SUMMARY.md` needs progress refreshed: performance-investigation.md advanced to Phase 2
- Chat summary and reflection note for `core/memory/activity/2026/03/17/chat-002/` need to be written
```

Key principles for deferred-action summaries: group ACCESS entries by target file (the ACCESS.jsonl they should be appended to), include all required fields (`file`, `date`, `task`, `helpfulness`, `note`, `session_id`), list review-queue entries with their type and description, and present the summary at session end so all deferred actions are captured.

### Periodic review in read-only

The agent should still run periodic reviews when the 30-day threshold is reached. Follow the same ordered checklist — but frame all findings as observations rather than actions, and present the full deferred-action summary at the end.

## Periodic review

During any session, if the agent notices it has been more than 30 days since the date in `core/INIT.md` § "Last periodic review" (or, if that date is missing or "Not yet run", since repo creation or the last `[system]` CHANGELOG entry), it should suggest a brief system review. **Follow this order** — security and integrity issues discovered early may affect or abort later steps.

1. **Security flags.** Are there any security flags (type: `security`) in `core/governance/review-queue.md`? Resolve or escalate before proceeding.
2. **Unverified content.** Files in `core/memory/knowledge/_unverified/` awaiting promotion or retirement? Check against active low-trust threshold.
3. **Conflict resolution.** Any `[CONFLICT]` tags unresolved in user-profile or knowledge files?
4. **Review queue.** Non-security entries in `core/governance/review-queue.md` awaiting approval?
5. **Unhelpful memory.** Files consistently flagged as unhelpful in ACCESS.jsonl? Cross-reference with knowledge amplification protocol.
6. **Maturity assessment.** Assess developmental stage using `core/governance/system-maturity.md`. If changed, log transition and update `core/INIT.md`.
7. **Governance evaluation.** Are curation rules producing good outcomes? For system-level governance, explicitly review consistency across authority surfaces, user-friendliness of the workflow, and context efficiency of the load path. See `core/governance/security-signals.md` § "Governance feedback".
8. **Folder structure.** Does it still make sense given actual usage?
9. **Emergent categorization.** Cross-folder retrieval clusters? See `core/governance/curation-policy.md` § "Emergent categorization." (Most expensive step — do last.)
10. **Session reflection themes.** Review recent reflection notes for recurring patterns. Address through summary updates or review-queue proposals.
11. **Update last review date** in `core/INIT.md`.

This review should be lightweight — a quick summary and any recommendations, not a full audit.

### Belief diff

As part of each periodic review, generate a **belief diff** recorded as a new dated entry in `core/governance/belief-diff-log.md` covering: new files added, files modified, files retired or archived, trust level changes, security flags triggered, and identity drift. See `core/governance/belief-diff-log.md` for the entry format.

## Commit integrity

Protected changes should use GPG-signed commits (`git commit -S`) when the environment supports it. `git log --show-signature` shows which commits are signed. Unsigned commits on protected files (`core/governance/`, `core/memory/skills/`, `README.md`) should be flagged in `core/governance/review-queue.md`. This is guidance, not enforcement.

## Model portability

When switching models: no repository changes needed, the new model starts with `core/INIT.md` and follows its routing, limitations should be noted in `core/governance/review-queue.md`, and model transitions recorded in CHANGELOG.md as system events.
