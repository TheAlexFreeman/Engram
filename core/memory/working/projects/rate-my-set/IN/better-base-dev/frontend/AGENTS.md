# Frontend AGENTS

This file adds frontend-specific guidance on top of root `AGENTS.md`.

## Read First

- `AGENTS.md`
- `docs/engineering/style-guide.md`
- `docs/engineering/code-review-checklist.md`

## Design and Theming

- Use Chakra UI v3 patterns and existing theme tokens in `frontend/theme/*`.
- Avoid hard-coded color values when a semantic token exists.
- Read `.cursor/rules/chakra-ui-rules.mdc` before substantial component changes.
- Read `.cursor/rules/design-system-rules.mdc` for visual and layout work.

## Router and Data

- Prefer TanStack CLI docs/discovery output for Router and Query behavior. Start with
  `bunx @tanstack/cli --help`, then use `doc`/`search-docs` as needed.
- Route files should only export `Route` at runtime for code splitting.
- For intentional fire-and-forget async calls, use `void`.
- Keep frontend code in `camelCase`, including API request/query object keys.
- Apply this camelCase rule to object/dictionary keys, not to value literals.
- Do not pre-convert request/query keys to `snake_case`; rely on API-boundary
  conversion.
- Preserve `snake_case` only for protocol-defined literal string values or explicit
  non-camelized endpoints.

## Validation

- Run targeted checks while iterating.
- Before finishing frontend-heavy changes, run at least:
  - `bun run tscheck`
  - `bun run lint`
  - any relevant local UI validation steps

## Multi-Agent Compatibility

When adding or updating guidance, keep it portable across Codex, Cursor, Claude Code,
OpenCode, and Pi.
