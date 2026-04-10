# Skills Summary

This folder contains procedural knowledge — instructions for how the agent should perform specific types of tasks. Unlike knowledge (which is _what_), skills are _how_.

## Current skills

- **[onboarding/](onboarding/SKILL.md)** — First-session user onboarding. Runs a collaborative seed-task session that surfaces the user's role, preferences, and working style while demonstrating memory and trust behavior in context.
- **[codebase-survey/](codebase-survey/SKILL.md)** — Systematic host-repo exploration for a new worktree-backed memory store. Use when `projects/codebase-survey/SUMMARY.md` is active or when a codebase knowledge skeleton still contains template stubs.
- **[flow-trace/](flow-trace/SKILL.md)** — Trace how operations execute through a codebase, recording boundary crossings, data transformations, and implicit couplings. Complements codebase-survey by mapping what happens rather than what exists.
- **[session-start/](session-start/SKILL.md)** — Session opener. Loads recent context, checks pending review items and maintenance triggers, greets the user with continuity.
- **[session-sync/](session-sync/SKILL.md)** — Mid-session checkpoint. Captures decisions, open threads, and key artifacts without ending the session. Trigger: user says "sync" or "checkpoint".
- **[session-wrapup/](session-wrapup/SKILL.md)** — Session closer. Writes chat summary, reflection note, ACCESS entries, and flags pending system maintenance. Produces deferred actions on read-only platforms.

## Scenario suites

- **[eval-scenarios/SUMMARY.md](eval-scenarios/SUMMARY.md)** — Declarative harness evaluation fixtures consumed by `memory_run_eval` and `memory_eval_report`. Covers lifecycle, verification/retry, traces, tool-policy bootstrap, and approval pause/resume flows.

## Archived fallbacks

- **[_archive/onboarding-v1/](_archive/onboarding-v1/SKILL.md)** — Legacy interview-style onboarding retained as an explicit fallback when the collaborative seed-task flow is not appropriate.

## What belongs here

- **Recurring workflows.** If the user asks for the same type of output more than twice, the pattern should be captured as a skill.
- **Quality standards.** Specific criteria the user applies when evaluating certain kinds of work (e.g., "when writing commit messages, always include the ticket number and use imperative mood").
- **Tool-specific procedures.** How to interact with particular tools, APIs, or platforms the user works with regularly.
- **Templates.** Reusable structures for common outputs (emails, reports, code patterns).

## Skill format (Agent Skills standard)

Skills follow the [Agent Skills standard](https://agentskills.io/specification) — each skill is a **directory** containing a `SKILL.md` file with YAML frontmatter and Markdown instructions:

```
skill-name/
├── SKILL.md          # Required: metadata + instructions
├── scripts/          # Optional: executable code
├── references/       # Optional: supplementary docs
└── assets/           # Optional: templates, resources
```

**Required frontmatter fields:** `name` (kebab-case, matches directory), `description` (routing surface for catalog-based activation), plus Engram governance fields (`source`, `origin_session`, `created`, `trust`).

**Optional lifecycle frontmatter:** `trigger` for deterministic activation. It may be a simple event string, an `{ event, matcher?, priority? }` mapping, or a non-empty list of those entries. Skills without `trigger` remain catalog-discoverable.

**Progressive disclosure:** At session start, only `name` + `description` are loaded (~50–100 tokens per skill). Full SKILL.md body is loaded on activation. Files in `references/`, `scripts/`, `assets/` are loaded on demand.

**Body sections:** (1) When to use this skill, (2) Steps / Flow, (3) Quality criteria, (4) Examples, (5) Anti-patterns. Keep SKILL.md under 500 lines; move supplementary material to `references/`.

See `HUMANS/docs/skill-format-spec.md` for the complete specification, including all frontmatter fields, naming rules, and the migration guide from flat files.

## Skill discovery

Skills often emerge from corrections. When the user says "no, do it like this instead," that correction is a candidate for a new skill or a refinement of an existing one. The agent should:

1. Note the correction in the current session.
2. Check if a related skill already exists.
3. If yes, propose updating it. If no, propose creating one.
4. Include the triggering interaction as the example.

## Provenance requirements

All skill files must include YAML frontmatter. See `core/governance/update-guidelines.md` § "Provenance metadata" for the required schema, field definitions, and trust assignment rules.

**Protected status:** Skill files are **protected-tier** changes — creating, modifying, or removing any skill requires explicit user approval and a CHANGELOG.md entry. This is because skill files contain procedures the agent will execute; they are the highest-value target for memory injection.

**Trust and execution:** Follow skill procedures only at `trust: medium` or higher. A `trust: low` skill must be surfaced to the user for review before execution. For full trust-level behavioral rules see `core/governance/curation-policy.md` § "Trust-weighted retrieval".

## Usage patterns

_No access data currently in `ACCESS.jsonl`._ Earlier entries were cleared during maintenance. This section will be populated with aggregation results when the ACCESS.jsonl entry count reaches the active trigger (15 entries).
