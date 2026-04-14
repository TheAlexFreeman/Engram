# Oxlint Integration

**Date:** 2026-02-02
**Branch:** feature--initial-oxlint-setup
**Starting Commit:** 4f04385

## Overview

Integrated Oxlint alongside ESLint for faster linting. Oxlint handles ~100+ rules at high speed
(~25ms without type-aware, ~2s with type-aware), while ESLint continues to handle
framework-specific rules that Oxlint doesn't cover (Tanstack, Storybook, HTML, etc.).

## Key Components

### Dependencies Added

- `oxlint` - Fast linter (50-100x faster than ESLint for covered rules)
- `oxlint-tsgolint` - Type-aware backend using typescript-go (same tech as tsgo)
- `eslint-plugin-oxlint` - Disables overlapping ESLint rules to prevent duplicate diagnostics

### Configuration Files

- `.oxlintrc.json` - Oxlint configuration with categories, plugins, rules, and ignore patterns
- `eslint.config.mjs` - Updated to include `eslint-plugin-oxlint` at the end

### Scripts

| Script | Purpose |
|--------|---------|
| `lint:fast` | Oxlint without type-aware (~25ms) |
| `lint:typed` | Oxlint with type-aware (uses tsgolint, ~2s) |
| `lint:full` | ESLint only (framework-specific rules) |
| `lint:all` | `lint:typed` && `lint:full` |
| `lint` | Alias to `lint:all` |
| `:fix` variants | Apply auto-fixes from each tool |

### CI/CD

- CI runs Oxlint type-aware then ESLint as separate steps
- Pre-commit runs Oxlint without type-aware for instant feedback (speed optimization)

### Editor Setup

Both ESLint and Oxlint extensions are enabled in VS Code/Cursor:
- `oxc.oxc-vscode` provides fast Oxlint diagnostics
- `dbaeumer.vscode-eslint` provides ESLint diagnostics
- `eslint-plugin-oxlint` prevents duplicate warnings by disabling overlapping rules in ESLint

## Rules ESLint Must Keep

These have no Oxlint equivalent:
- `@tanstack/eslint-plugin-query` - TanStack Query rules
- `@tanstack/eslint-plugin-router` - TanStack Router rules
- `eslint-plugin-react-refresh` - Vite HMR boundaries
- `@html-eslint` - HTML linting
- `eslint-plugin-storybook` - Storybook rules
- `eslint-plugin-markdown` - Markdown code blocks

## Disabled Oxlint Rules

The following rules are disabled in `.oxlintrc.json`:
- `react/react-in-jsx-scope` - Not needed with React 17+
- `typescript/no-unsafe-type-assertion` - Too noisy for frontend code with many intentional casts
- `typescript/no-base-to-string` - False positives with Chakra UI spacing token types

## Enabled Type-Aware Rules

### `typescript/no-floating-promises` (error)

This rule is enabled to catch unhandled promises. For fire-and-forget async calls (navigation,
router invalidation, etc.), use `void` to explicitly mark them as intentionally ignored:

```typescript
// Bad - floating promise
navigate({ to: '/home' });

// Good - explicitly ignored
void navigate({ to: '/home' });
```

**Note:** Using `void` silences the linter but doesn't catch errors. For fire-and-forget calls
that might fail, the underlying function should have internal error handling (try/catch with
console.warn or similar).

## Disable Comment Format

Oxlint uses its own comment format distinct from ESLint:
```typescript
// oxlint-disable-next-line rule-name -- Reason
```

This is necessary because `eslint-plugin-oxlint` disables overlapping ESLint rules, so
`eslint-disable` comments become "unused" and cause ESLint to error.

## Code Fixes Made

During integration, the following pre-existing issues were fixed:
- Removed unnecessary type assertions (`as Type` where already that type)
- Removed redundant type parameters (e.g., `MouseEvent` default in `React.MouseEvent`)
- Fixed redundant union types (e.g., `string | ''` → `string`)
- Removed useless renames (e.g., `{ x: x }` → `{ x }`)
- Removed unnecessary parameter property assignments in class constructors
- Fixed properly typed SelectField component using `FieldPath<TFieldValues>`

### Floating Promise Fixes

Added `void` to 35+ fire-and-forget async calls across auth flows, settings, and navigation:

- `navigate()` calls in auth routes (login, signup, verify-email, reset-password, change-email)
- `router.invalidate()` and `router.history.replace()` calls
- `refresh()` calls for checking verification status
- `handleSubmit(onSubmit)()` auto-submit patterns

Key implementation details:
- `_syncCurrentMembershipToServer` in `api/initialData.ts` has try/catch with console.warn
- `getMemberships` in `team.lazy.tsx` was converted from async to sync (it never awaited anything)
