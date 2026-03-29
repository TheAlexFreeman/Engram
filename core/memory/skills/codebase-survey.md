---
source: agent-generated
origin_session: manual
created: 2026-03-20
last_verified: 2026-03-20
trust: medium
---

# Codebase Survey

## When to use this skill

Use this skill when a worktree-backed memory store has just been initialized for a host repository, when `projects/codebase-survey/SUMMARY.md` is active, or when the files under `knowledge/codebase/` still contain template placeholders.

### First session after onboarding

When onboarding has just completed and this is the agent's second session, the codebase survey is the natural first project. Load the survey plan and start from phase 1 (entry-point-mapping). The onboarding forward bridge should have previewed this.

## Steps

### 1. Start from the survey plan

- Read `projects/codebase-survey/plans/survey-plan.yaml` and identify the first pending phase.
- When MCP is available, use `memory_plan_briefing` to get the assembled context for the current phase — this includes sources, failure history, and approval state in a single call.
- Confirm which knowledge file that item should update.
- Keep the current pass narrow: finish one survey item before broadening scope.

### 2. Explore the host repo in dependency order

- Use the `sources` declared in the current plan phase as starting exploration targets.
- Start at entry points, boot files, or top-level routes.
- Follow imports, registrations, or wiring code outward from those entry points.
- Prefer structural understanding first: boundaries, responsibilities, data flow, operational commands.

### 3. Write durable notes, not transcripts

- Update the target `knowledge/codebase/*.md` file directly, replacing template placeholders with verified findings.
- Keep temporary uncertainty, partial hypotheses, or oversized source dumps in the project's `IN/` directory or `scratchpad/` until verified.
- Replace template placeholders with concise, factual notes tied to concrete source paths.

### 4. Cross-reference aggressively

- Add `related` frontmatter once a knowledge file is anchored to real host-repo files.
- Link architecture, data-model, operations, and decisions notes to each other when one depends on another.
- If the current survey item changes the next best action, update the plan before ending the session.

### 5. Verify postconditions before completing a phase

- Each phase declares `postconditions` in the plan. Review them before marking the phase complete.
- When MCP is available, use `memory_plan_verify` or pass `verify=true` to `memory_plan_execute` to check postconditions automatically.
- If a postcondition is not satisfied, continue working on the phase rather than advancing.

### 6. Manage trust deliberately

- Leave a file at `trust: low` while it is mostly scaffold or partially verified.
- Promote to `trust: medium` only once the note reflects the current code and is grounded in source files.
- If a source file changes materially after verification, surface that via `memory_check_knowledge_freshness` and revisit the note.

## Quality criteria

- The next agent can understand the host repo faster from the note than from re-reading the same files.
- Each survey session clearly advances one plan item and one durable knowledge surface.
- Each completed phase satisfies its declared postconditions.
- Notes distinguish verified facts, open questions, and operational assumptions.

## Example

Good result: the survey session maps the app entry points, updates `knowledge/codebase/architecture.md` with the boot sequence and major modules, adds `related` source paths, verifies the phase postcondition, and leaves deeper subsystem questions in the project's `IN/` directory for the next pass.

## Anti-patterns

- Do not read the whole codebase before writing anything down.
- Do not paste long code excerpts into knowledge files when a short structural summary would do.
- Do not promote placeholder text to higher trust just because the file exists.
- Do not skip plan updates after replacing a template stub with verified knowledge.
- Do not mark a phase complete without checking its postconditions.
