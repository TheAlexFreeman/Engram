# Engineering Style Guide

## Purpose

This document captures cross-cutting coding style expectations for this repository. Use
this together with `AGENTS.md` and the path-specific guidance in `frontend/AGENTS.md`
and `backend/AGENTS.md`.

## Agent Compatibility

Write guidance so it works consistently for the project's primary agents: Codex, Cursor,
Claude Code, OpenCode, and Pi.

- Keep guidance tool-agnostic when possible.
- Put tool-specific setup details in `AGENTS.md` only when needed.
- Assume Pi consumes `.agents/skills/` directly, while other agents may rely on
  generated config files.

## Hierarchy

When guidance conflicts, prefer the most specific scope:

1. Task or user request constraints.
2. Path-scoped guidance (`frontend/AGENTS.md`, `backend/AGENTS.md`).
3. Root `AGENTS.md`.
4. This style guide.

## General / Overall

- Keep changes focused. Do not batch unrelated refactors into feature work.
- Preserve existing architecture and patterns unless the task explicitly includes
  redesign.
- Prefer clear names and explicit logic over compact but opaque code.
- Keep Better Base generic enough to remain a strong base for derived projects.
- When porting improvements back from derived projects, retain the implementation value
  while stripping project-specific assumptions unless they are intentionally becoming
  part of the base.
- For sync workflows, normalize remote and local records into explicit comparison shapes
  before diffing or deciding writes. See `docs/engineering/sync-best-practices.md` and
  `docs/engineering/sync-reference-patterns.md`.
- For third-party integrations, keep one explicit client boundary and test it with
  dedicated mocks or fake SDK clients rather than relying on live services. See
  `docs/engineering/api-client-best-practices.md`,
  `docs/engineering/api-client-reference-patterns.md`,
  `docs/engineering/third-party-mocking-best-practices.md`, and
  `docs/engineering/third-party-mocking-reference-patterns.md`.
- Use full-sentence comments and docstrings when comments are needed.
- Avoid nested imports unless there is a clear reason.
- Use `structlog` patterns already used in the codebase when logging is necessary.
- Avoid noisy logs in hot paths.
- Prefer explicit, actionable error messages over generic failures.
- Fail early on invalid input, then keep happy-path control flow straightforward.
- Run the smallest relevant checks while iterating, then run broader checks before
  merge.
- Validate both functional behavior and developer ergonomics (error messages, docs,
  generated configs) when touching tooling.
- If a change affects user-facing or operator-facing behavior, update docs in the same
  change.
- Prefer deterministic ordering in config/code-like metadata files. When practical, keep
  lists/maps/blocks alphabetized (for example in root/tooling config such as ESLint,
  Ruff, oxfmt/TOML, and related repository-level config files).

## Backend

- Use `snake_case` for Python identifiers and backend-facing payload/query keys.
- Do not handwrite Django migrations. Use `python manage.py makemigrations`.
- Do not manually edit generated migration files; change model code and regenerate.
- For Django model fields, avoid `default=...` when values should be supplied
  explicitly by operations, serializers, or callers.
- Use model defaults only for deliberate invariant fallbacks.
- For optional Django fields/relations, prefer `blank=True`/`null=True` without
  `default=None` unless `None` as a default is intentional.
- For ops class constructors and factory functions, require callers to pass all
  business-significant arguments explicitly. Do not use `= None` defaults to make
  parameters optional when the caller should always make a conscious choice. Reserve
  defaults for values that are genuinely invariant or convenience-only.
- When `None` is an intentional choice, pass it explicitly at the call site.
- Keep operation responsibilities narrowly scoped.
- If an operation depends on pre-parsed or pre-normalized collaborator state, require
  that as an explicit pre-condition and fail fast. Do not silently parse/normalize
  collaborator-owned objects inside the operation.
- Prefer stdlib UUIDv7 for new UUID generation where compatible.
- Prefer `attrs` over `dataclasses` for value objects, result types, and similar
  structures. Default to `@attrs.define(frozen=True, kw_only=True, slots=True)`. Drop
  `frozen` when mutability is needed and `slots` when dynamic attributes are required.
- Prefer `.get(...)` for lookups that should be unique. Avoid `.first()`/`.last()` in
  uniqueness paths because they can mask data-integrity issues.
- Use `.first()`/`.last()` only when ordering semantics are intentional and multiple
  records are expected.
- For model `help_text` that describes persisted state, prefer declarative wording about
  what is stored (for example, "will be set to ...") instead of imperative
  instructions.
- For pytest database tests, use `@pytest.mark.django_db` by default.
- For `transaction.on_commit(...)` behavior, prefer pytest-django's built-in
  `django_capture_on_commit_callbacks` fixture instead of escalating to
  `transaction=True`.
- Use `@pytest.mark.django_db(transaction=True)` only when the test specifically needs
  transaction semantics (for example, commit/rollback behavior that cannot be validated
  with default test wrapping).
- When adding a Django model, follow this checklist.
- Add the model.
- Add the Django admin class/registration.
- If relevant, add a test factory for the model.
- Add a factory test that creates the factory 5 times to verify stable creation.
- Add an admin changelist smoke test that loads and does not crash.
- Add an admin detail-page smoke test that loads and does not crash.
- Add an admin regular-search smoke test that loads and does not crash.
- Add dedicated model tests for `repr(...)` coverage paths.
- Add dedicated model tests for `str(...)` coverage paths.
- Keep type hints and mypy clean for changed code.
- Add tests for behavior changes and regressions, not just coverage.

## Frontend

- Use Bun tooling (`bun`, `bunx`) for package and script operations.
- Use `camelCase` for TypeScript identifiers and frontend API request/query object keys.
- Apply frontend camelCase normalization to object/dictionary keys, not to value
  literals.
- Rely on automatic API boundary key conversion for backend `snake_case`; do not
  manually pre-snake-case frontend request objects.
- Keep snake_case string literals only when they are protocol-defined values (for
  example enum values) or when an endpoint explicitly disables camelization.
- Follow Chakra UI v3 and existing theme tokens; avoid hard-coded colors when possible.
- In TanStack Router route files, only export `Route` at runtime; do not export route
  component functions.
- Mark intentionally ignored async calls with `void` to satisfy floating-promise rules.

## DevOps / Infra

- Prefer reproducible workflows (`Taskfile`, pinned deps, checked-in lockfiles where
  appropriate for the toolchain).
- Keep generated config as code when used by multiple agents/tools (for example
  `agents.toml` -> generated MCP configs).
- Validate infra/tooling changes with at least one real execution path, not just static
  edits.
- Keep CI-impacting command changes documented in `README.md` or `docs/`.
