# First-Run Flow

This document is an agent-facing streamlined flow for the very first session. It condenses the README-first bootstrap into a single checklist with clear silent/interactive annotations.

> **Authority:** This flow is reached via `core/INIT.md` routing. It is subordinate to `core/INIT.md` for active thresholds and session routing. When in doubt, defer to `core/INIT.md`.

**When to use:** No date-organized chat folders exist under `core/memory/activity/`, AND either:

- `core/memory/users/SUMMARY.md` contains "No portrait yet" (blank-slate setup — no profile installed), OR
- `core/memory/users/` contains a file with `source: template` in its frontmatter (a starter profile was installed by `setup.sh --profile` but onboarding has not yet run).

If neither condition matches — a user portrait exists without the `template` marker, or chat history is present — the system has already been onboarded. Return to `core/INIT.md` and follow its routing instead.

---

## Silent setup (do not produce output for these steps)

1. Read `CHANGELOG.md` to understand the system's recent evolution.
2. Use the thresholds and routing state already loaded from `core/INIT.md`; do not override them with older prose elsewhere.
3. Read the following sections of `core/governance/update-guidelines.md`: "Change categories", "Read-only operation", and the periodic-review trigger reference only if needed.
4. **Check write access.** Can you write to this repository? If not, note this — all behavioral rules still apply, but writes must be deferred per `core/governance/update-guidelines.md` § "Read-only operation". If this is your first read-only session, also review the worked example in `core/governance/update-guidelines.md` § "Worked example" for the output format.
5. Read `core/memory/skills/SUMMARY.md` and `core/memory/skills/onboarding/SKILL.md`.

At this point you have loaded: system architecture (README.md), evolution history, active thresholds, change-control rules, write-access status, and the onboarding skill. **Stop loading files and begin interactive work below.** Do not summarize any of this to the user.

## Interactive onboarding (this is the part the user sees)

6. **Run the onboarding skill** (`core/memory/skills/onboarding/SKILL.md`). This is a collaborative first session centered on a seed task, with profile discovery, capability demonstration, and explicit confirmation folded into the work. Follow the skill's phases and quality criteria exactly.

7. **After onboarding completes**, greet the user using what you learned. Do not recap the bootstrap process or list which files you read. The greeting should feel like the start of a relationship, not a system status report.

## Skippable on first run

- `core/memory/knowledge/SUMMARY.md` — empty on first run.
- `core/memory/activity/SUMMARY.md` — empty on first run.
- `core/governance/curation-policy.md` and the full `core/governance/update-guidelines.md` — you loaded the essential sections in step 3. Read the full governance docs from session two onward.
- `core/governance/curation-algorithms.md` — only needed during aggregation or stage transitions.
- `HUMANS/docs/*` — human reference only; never needs to be loaded by agents.

---

## After first run

From session two onward, return to `core/INIT.md` for live routing. Follow the Compact returning manifest in `core/INIT.md` → `core/memory/HOME.md` for the context loading order. Keep project plans task-driven, and load `core/governance/session-checklists.md` only when you want detailed runbooks.

### Worktree mode: codebase survey

In worktree mode, the init script seeds a codebase-survey project as the first active project. After onboarding completes, mention this project during the forward bridge (Phase D of the onboarding skill) so the user knows what session two will look like. Do not start the survey during the onboarding session — it is the natural second-session task.
