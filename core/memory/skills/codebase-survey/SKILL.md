---
name: codebase-survey
description: >-
  Systematic host-repo exploration for a new worktree-backed memory store.
  Use when projects/codebase-survey/SUMMARY.md is active or when codebase
  knowledge files still contain template stubs. Supports both initial survey
  and ongoing deepening rounds.
compatibility: Requires agent-memory MCP server for plan management and knowledge search

source: agent-generated
origin_session: manual
created: 2026-03-20
last_verified: 2026-03-30
trust: medium
---

# Codebase Survey

## When to use this skill

Use this skill when a worktree-backed memory store has just been initialized for a host repository, when `projects/codebase-survey/SUMMARY.md` is **active**, or when the files under `knowledge/codebase/` still contain template placeholders.

Also use it for **ongoing deepening**: after the initial `plans/survey-plan.yaml` phases are complete, the same project can run **further agent-driven review rounds** — knowledge should become **more detailed and specialized** over time, not freeze at the first pass.

### First session after onboarding

When onboarding has just completed and this is the agent's second session, the codebase survey is the natural first project. Load the survey plan and start from phase 1 (entry-point-mapping). The onboarding forward bridge should have previewed this.

### After the initial survey is complete

When all plan phases are marked complete, **do not treat the project as closed** unless the user explicitly archives it. Continue from:

- `projects/codebase-survey/IN/knowledge-roadmap.md` (phased deepening guide), and/or
- `projects/codebase-survey/questions.md` (open questions tagged by roadmap phase).

Prefer **one narrow theme per session** (e.g. Celery inventory, or permissions model) so notes gain depth without turning into undifferentiated blobs.

## Steps

### 1. Start from the survey plan

- Read `projects/codebase-survey/plans/survey-plan.yaml` and identify the first pending phase.
- When MCP is available, use `memory_plan_briefing` to get the assembled context for the current phase — this includes sources, failure history, and approval state in a single call.
- Confirm which knowledge file that item should update.
- Keep the current pass narrow: finish one survey item before broadening scope.

**If every phase is already complete:** skip to **step 8 (Reflective loop)** for this session's anchor (roadmap step + open questions) instead of re-running completed YAML phases unless the user asks for a full re-survey.

### 2. Audit the existing knowledge base

Before exploring the host repo, scan the knowledge base for content that already applies to this project's stack.

- Read `knowledge/SUMMARY.md` and list every non-codebase knowledge folder (e.g. `software-engineering/`, `ai/`, `mathematics/`).
- For each folder, read its `SUMMARY.md` and identify files whose topics overlap with the host repo's stack or domain (e.g. `django-production-stack.md` for a Django project, `react-19-overview.md` for a React frontend).
- Record the **most relevant files** as a short list in `projects/codebase-survey/IN/relevant-knowledge.md` with one line per file: path and a phrase explaining the relevance to this specific host repo.
- Record the **most relevant gaps** in the same file: topics the host repo depends on that have no existing knowledge coverage (e.g. "GraphQL — no knowledge files, but the host API uses Apollo").
- During later survey steps, cross-reference codebase findings against relevant knowledge files and link them via `related` frontmatter when a codebase note depends on or extends a general knowledge file.

On **deepening rounds**, revisit `IN/relevant-knowledge.md` and update it: new knowledge files may have been added since the last round, and completed survey phases may reveal new gap areas.

### 3. Explore the host repo in dependency order

- Use the `sources` declared in the current plan phase as starting exploration targets.
- Start at entry points, boot files, or top-level routes.
- Follow imports, registrations, or wiring code outward from those entry points.
- Prefer structural understanding first: boundaries, responsibilities, data flow, operational commands.

For deepening rounds, use the **sources** implied by `IN/knowledge-roadmap.md` for the chosen phase (e.g. grep for `@shared_task`, read `dc.stage.yml` / `dc.prod.yml`).

### 4. Write durable notes, not transcripts

- Update the target `knowledge/codebase/*.md` file directly, replacing template placeholders with verified findings.
- Keep temporary uncertainty, partial hypotheses, or oversized source dumps in the project's `IN/` directory or `scratchpad/` until verified.
- Replace template placeholders with concise, factual notes tied to concrete source paths.

As knowledge **specializes**, it is acceptable to add **subsections, tables, or short bullet registries** (e.g. task names, env var names, permission classes) — still summarized, not pasted source.

### 5. Cross-reference aggressively

- Add `related` frontmatter once a knowledge file is anchored to real host-repo files.
- Link architecture, data-model, operations, and decisions notes to each other when one depends on another.
- If the current survey item changes the next best action, update the plan before ending the session.

### 6. Verify postconditions before completing a phase

- Each phase declares `postconditions` in the plan. Review them before marking the phase complete.
- When MCP is available, use `memory_plan_verify` or pass `verify=true` to `memory_plan_execute` to check postconditions automatically.
- If a postcondition is not satisfied, continue working on the phase rather than advancing.

**Reflective-loop rounds** use the roadmap's "done when" criteria as informal postconditions even though they are not in the YAML plan.

### 7. Manage trust deliberately

- Leave a file at `trust: low` while it is mostly scaffold or partially verified.
- Promote to `trust: medium` only once the note reflects the current code and is grounded in source files.
- If a source file changes materially after verification, surface that via `memory_check_knowledge_freshness` and revisit the note.

### 8. Reflective loop — open-ended deepening

Each **review round** should close a loop, not only append text. After exploring and promoting findings:

1. **Integrate** — Merge new facts into the right `knowledge/codebase/*.md` file(s); extend `related` paths; bump `last_verified` when the note matches the repo **today**.
2. **Specialize** — Prefer **deeper detail on a slice** (one subsystem, one risk surface) over shallow edits everywhere. If a section exceeds ~400–600 words of dense fact, consider splitting a topic into a linked note under `knowledge/codebase/` and keep `SUMMARY.md` as the index.
3. **Reflect** — In `projects/codebase-survey/questions.md`: move answered items to **Resolved Questions** with date + pointer to the knowledge file and section. **Add** new open questions discovered during the round (deeper "why," edge cases, integration points). Update `next_question_id` if you add net-new numbered items.
4. **Steer** — Update `IN/knowledge-roadmap.md` if priorities shift (reorder phases, add a step, mark a row satisfied). Update `projects/codebase-survey/SUMMARY.md` (`current_focus`, `open_questions` count, `last_activity`).
5. **Stop with a handoff** — End the session with one explicit **next round** suggestion: the single roadmap phase or question cluster that yields the best depth-per-token next time.

When MCP is available, use `memory_search` / `memory_semantic_search` at the start of a round to see what is **already claimed** in memory before duplicating shallow summaries.

## Quality criteria

- The next agent can understand the host repo faster from the note than from re-reading the same files.
- Each survey session clearly advances one plan item and one durable knowledge surface.
- Each completed phase satisfies its declared postconditions.
- Notes distinguish verified facts, open questions, and operational assumptions.

**Deepening-specific:**

- Each reflective round **reduces** ambiguity in at least one **named** area (e.g. "Celery periodic tasks," "membership invite rules") or **documents** that ambiguity explicitly as an open question with a source to read next.
- Knowledge **density** increases over rounds: later passes add **interfaces, invariants, failure modes, and pointers** — not paraphrases of the first pass.
- The question file and roadmap stay **honest inventories** of what is still unknown or stale.

## Example

**First pass (YAML plan):** The session maps app entry points, updates `knowledge/codebase/architecture.md` with the boot sequence and major modules, adds `related` source paths, verifies the phase postcondition, and leaves deeper subsystem questions in the project's `IN/` directory for the next pass.

**Second pass (reflective loop):** The session picks roadmap **Phase A** (Celery): inventories tasks and beat configuration, adds a subsection to `data-model.md` or `operations.md`, resolves questions 1–2 in `questions.md` with pointers, adds question 18 about a specific task's retry policy discovered while reading code, bumps `last_verified` on touched notes, and sets `SUMMARY.md` `current_focus` to Phase B for next time.

## Anti-patterns

- Do not read the whole codebase before writing anything down.
- Do not paste long code excerpts into knowledge files when a short structural summary would do.
- Do not promote placeholder text to higher trust just because the file exists.
- Do not skip plan updates after replacing a template stub with verified knowledge.
- Do not mark a phase complete without checking its postconditions.
- Do not treat **survey-plan.yaml** "complete" as permission to **stop maintaining** codebase knowledge unless the user archives the project.
- Do not run a deepening round on **every** topic at once — breadth without depth violates the reflective loop.
- Do not delete open questions just to shrink the list; **resolve** them into knowledge or **refine** them into sharper follow-ups.
