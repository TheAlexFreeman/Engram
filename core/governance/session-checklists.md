# Session checklists

Quick-reference runbooks for session start and end. **Load on demand** when you want more structure than the compact manifest in `core/INIT.md`. For full detail, quality criteria, and edge cases, see the skill files: `core/memory/skills/session-start/SKILL.md`, `core/memory/skills/session-sync/SKILL.md`, `core/memory/skills/session-wrapup/SKILL.md`.

> **Authority:** Subordinate to `core/INIT.md` for routing and thresholds. When these runbooks and `core/INIT.md` conflict, `core/INIT.md` governs.

## First session

Follow `core/governance/first-run.md` instead.

## Session start (returning)

1. Follow `core/INIT.md` → `core/memory/HOME.md` for the context loading order.
2. Check write access. If read-only, note for deferred actions at session end.
3. Run metadata-first maintenance checks (review-queue entries, ACCESS.jsonl aggregation triggers).
4. Weave `core/memory/working/USER.md` content into greeting naturally.
5. Greet with continuity — reference what the user was working on. 2–3 sentences, then let the user speak.

Detail: `core/memory/skills/session-start/SKILL.md`

## Mid-session sync

Use `memory_checkpoint` for lightweight in-progress saves after decisions, discoveries, and major task completions. Reserve `checkpoint.md` in the chat folder for user-requested or heavier mid-session syncs. Don't checkpoint trivially.

If context pressure is detected (>75% of effective context window consumed, or platform signals compaction), trigger an automatic checkpoint per the context-pressure flush protocol. See `core/memory/skills/session-sync/SKILL.md` § "Context-pressure flush".

Detail: `core/memory/skills/session-sync/SKILL.md`

## Session end

1. **Chat summary** — `SUMMARY.md` in the chat folder (10–30 lines).
2. **Reflection** — `reflection.md` in the chat folder.
3. **Scratchpad review** — Promote confirmed entries, clear stale ones.
4. **ACCESS.jsonl** — Log every content file retrieved. Include `session_id`. Skip governance, SUMMARY.md, and scratchpad files.
5. **Aggregation check** — If any ACCESS.jsonl hit the trigger, run aggregation.
6. **Summary updates** — Update relevant SUMMARY.md files if the session produced significant changes.
7. **Deferred actions** (read-only only) — Produce a deferred-action summary per `core/governance/update-guidelines.md` § "How to communicate deferred actions".
8. **Sign off** — Brief, warm, specific to the session.

Detail: `core/memory/skills/session-wrapup/SKILL.md`

## Periodic integrity audit

Advisory checklist for periodic review (see `core/governance/update-guidelines.md` § "Periodic review"). The memory system does not enforce these automatically — they are a read-only audit aid.

1. **Provenance and frontmatter** — Every content file in `core/memory/users/`, `core/memory/knowledge/`, `core/memory/skills/`, and project plans under `core/memory/working/projects/` has the required YAML frontmatter: `source`, `origin_session`, `created`, and `trust`, plus `last_verified` when appropriate for that folder's contract. See `core/governance/update-guidelines.md` § "Provenance metadata". Flag any file missing required fields, any quarantine file in `core/memory/knowledge/_unverified/` that sets `last_verified`, or any invalid `last_verified` value. **Call `memory_validate` first** — it automates checks 1 and 2 and reports errors and warnings; then use `memory_search` for the instruction-containment grep below.

2. **Instruction containment** — No imperative or instructional patterns in `core/memory/knowledge/` or `core/memory/users/` files. Project plans may contain task-local sequencing for the specific plan, but not general standing behavior. Procedural content outside those limits belongs in `core/memory/skills/` or `core/governance/`. Use the boundary-violation test in `core/governance/content-boundaries.md` § "Instruction containment" (e.g. "Would this content be appropriate in `core/memory/skills/`?"). Flag any file that prescribes agent behavior, recommends courses of action, or establishes norms the agent enforces beyond its allowed folder contract. Explicit imperative patterns (e.g. "always do X", "you must", "when asked about Y respond with...") are strong signals.

3. **Commit signatures (optional)** — Run `git log --show-signature` on protected paths (`core/governance/`, `core/memory/skills/`, `README.md`). Flag unsigned commits on these paths as a security concern; record in `core/governance/review-queue.md` if the protocol in `core/governance/update-guidelines.md` § "Commit integrity" is adopted.

4. **System-change architecture fit** — For recent edits to `core/governance/`, `README.md`, `core/memory/skills/`, setup flows, or validator contracts, confirm the operating contract is still consistent across docs and tooling, the user-facing workflow remains understandable and low-friction, and the compact returning path plus context-budget guidance have not regressed. Flag duplicated rules, confusing approval flows, or new mandatory reads without clear benefit.

5. **HUMANS/docs alignment** — Verify that `HUMANS/docs/CORE.md`, `HUMANS/docs/DESIGN.md`, and other human-facing documentation still reflect the current governance rules, directory layout, and operational contracts. Flag any descriptions that have drifted from the live system.

6. **HOME.md alignment** — Verify that `core/memory/HOME.md` context loading order matches `core/INIT.md` § Context loading manifest and `agent-bootstrap.toml` step lists. Flag any divergence.

This checklist is advisory. The repository owner decides whether and how often to run it; the agent may run it as part of periodic review and report findings without automatically applying changes.
