# Backend AGENTS

This file adds backend-specific guidance on top of root `AGENTS.md`.

## Read First

- `AGENTS.md`
- `docs/engineering/style-guide.md`
- `docs/engineering/code-review-checklist.md`

## Django and Python

- Activate the project virtual environment before Python tooling commands.
- Use `snake_case` for Python identifiers and backend payload/query keys.
- Do not handwrite Django migration files; run `python manage.py makemigrations`.
- Do not manually edit generated migration files; regenerate from model changes.
- Use existing `structlog` patterns when logging is required.
- Prefer stdlib UUIDv7 for new UUID generation when compatible.

## Code Quality

- Keep imports at module scope unless there is a concrete performance or cycle reason.
- Prefer explicit assignment in ops/serializers over Django model `default=...` for
  business-significant fields.
- For optional fields/relations, use `blank=True`/`null=True` without `default=None`
  unless that default is intentionally required.
- Add regression tests when fixing bugs and behavior tests when adding features.
- Avoid broad refactors in feature PRs unless explicitly requested.

## Validation

- Run targeted tests first, then broader checks for touched areas.
- At minimum for backend-heavy changes:
  - `source .venv/bin/activate`
  - `pytest <args>`
  - `mypy <args>`

## Multi-Agent Compatibility

When adding or updating guidance, keep it portable across Codex, Cursor, Claude Code,
OpenCode, and Pi.
