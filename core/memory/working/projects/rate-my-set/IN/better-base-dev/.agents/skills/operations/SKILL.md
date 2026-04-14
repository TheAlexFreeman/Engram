---
name: operations
description: Apply the Django Operations layer pattern for business logic in this repository. Use when editing or reviewing `backend/**/ops.py` and `backend/**/ops/**/*.py`, or when asked about "ops", "operations", or `validate_can_*` workflows.
---

Use this skill for backend operations-layer implementation and code review.

## Automatic Trigger Context

Load this skill whenever work touches either of these paths:

- `backend/**/ops.py`
- `backend/**/ops/**/*.py`

This includes feature implementation, refactors, and code review comments for those
paths.

## Invocation

Use any of these trigger forms:

- `operations`
- `[skill:operations]`
- `operations pattern`
- `ops review`

## Required Context

1. Read `AGENTS.md` and `backend/AGENTS.md`.
2. Read `docs/engineering/operations-pattern.md`.
3. Read `references/operations-pattern-whitepaper.md`.
4. Read `references/repo-ops-inventory.md`.

## Definition

An operation is an action-oriented unit of business logic that lives in either:

- an `ops.py` file, or
- an `ops/` module path.

Public operations should not start with `_`. Private operation helpers should start with
`_`.

Data-only structures (for example result dataclasses or typed dicts) are not operations.

## Core Rules

1. Keep operation entrypoints discoverable and action-oriented.
2. Keep views/tasks/commands thin: they should orchestrate and call operations.
3. Keep model methods focused on model state, integrity, and derived behavior.
4. Use `validate_can_<action>` style checks for permission/state gating where helpful.
5. Keep side effects explicit (DB writes, email, session mutation, cache, external I/O).
6. Prefer explicit result objects for non-trivial outcomes.
7. Use underscored helpers for internal-only operation dependencies.

## Review Checklist For Ops Files

When reviewing files in ops paths, verify:

- Entry points call operations rather than embedding business logic.
- Operation names describe business actions (`create_*`, `attempt_*`, `send_*`, etc.).
- Preconditions and validation are explicit and readable.
- Multi-model workflows are transactionally safe where required.
- Error/result contracts are explicit and testable.
- Public vs private (`_`) boundaries are clear.
- Tests exist for success, failure, and critical edge flows.

## Output Expectations

Report:

- Operation entrypoints added/changed.
- Validation gates (`validate_can_*`) added/changed.
- Side effects touched.
- Transactions/error semantics.
- Tests run and skipped.
