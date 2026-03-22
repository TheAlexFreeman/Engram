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

## Steps

### 1. Start from the survey plan

- Read `projects/codebase-survey/plans/survey-plan.yaml` and identify the first pending phase.
- Confirm which knowledge file that item should update.
- Keep the current pass narrow: finish one survey item before broadening scope.

### 2. Explore the host repo in dependency order

- Start at entry points, boot files, or top-level routes.
- Follow imports, registrations, or wiring code outward from those entry points.
- Prefer structural understanding first: boundaries, responsibilities, data flow, operational commands.

### 3. Write durable notes, not transcripts

- Promote stable findings into `knowledge/codebase/*.md`.
- Keep temporary uncertainty, partial hypotheses, or oversized source dumps in `scratchpad/` until verified.
- Replace template placeholders with concise, factual notes tied to concrete source paths.

### 4. Cross-reference aggressively

- Add `related` frontmatter once a knowledge file is anchored to real host-repo files.
- Link architecture, data-model, operations, and decisions notes to each other when one depends on another.
- If the current survey item changes the next best action, update the plan before ending the session.

### 5. Manage trust deliberately

- Leave a file at `trust: low` while it is mostly scaffold or partially verified.
- Promote to `trust: medium` only once the note reflects the current code and is grounded in source files.
- If a source file changes materially after verification, surface that via `memory_check_knowledge_freshness` and revisit the note.

## Quality criteria

- The next agent can understand the host repo faster from the note than from re-reading the same files.
- Each survey session clearly advances one plan item and one durable knowledge surface.
- Notes distinguish verified facts, open questions, and operational assumptions.

## Example

Good result: the survey session maps the Django app entry points, updates `knowledge/codebase/architecture.md` with the boot sequence and major apps, adds `related` source paths, and leaves deeper subsystem questions in `scratchpad/` for the next pass.

## Anti-patterns

- Do not read the whole codebase before writing anything down.
- Do not paste long code excerpts into knowledge files when a short structural summary would do.
- Do not promote placeholder text to higher trust just because the file exists.
- Do not skip plan updates after replacing a template stub with verified knowledge.
