# AGENTS.md

## Instruction Map

Start here, then read the most specific files for the area you are touching.

- Root operational guidance: `AGENTS.md` (this file).
- Cross-cutting coding conventions: `docs/engineering/style-guide.md`.
- Code review expectations: `docs/engineering/code-review-checklist.md`.
- Instruction system governance: `docs/engineering/agent-instruction-governance.md`.
- Sync workflow guidance: `docs/engineering/sync-best-practices.md`.
- Sync reference examples: `docs/engineering/sync-reference-patterns.md`.
- API client guidance: `docs/engineering/api-client-best-practices.md`.
- API client reference examples: `docs/engineering/api-client-reference-patterns.md`.
- Third-party mocking guidance: `docs/engineering/third-party-mocking-best-practices.md`.
- Third-party mocking reference examples:
  `docs/engineering/third-party-mocking-reference-patterns.md`.
- Frontend-specific additions: `frontend/AGENTS.md`.
- Backend-specific additions: `backend/AGENTS.md`.

## Project Context

Better Base is a reusable Django + React scaffold. It is meant to stay broadly useful as
an opinionated base for derived projects, not to accumulate child-project-specific
assumptions by accident.

When porting improvements back from derived projects:

- Keep the change if it improves the shared base.
- Remove or rewrite project-specific branding, product assumptions, and private context.
- Prefer guidance that remains valid across future derived projects unless the user asks
  for something more specialized here.

For context on this port, reference:

- `docs/agent-notes/2026-03-06 Better Base Dotagents and Guidance Port.md`

## Primary Agent Targets

The primary coding agents for this repo are:

1. Codex
2. Cursor
3. Claude Code
4. OpenCode
5. Pi

Implementation notes:

- Dotagents manages cross-agent skill + MCP config for Claude, Cursor, Codex, and
  OpenCode from `agents.toml`.
- Pi reads `.agents/skills/` natively and does not require a dedicated `agents` target.

## Skill Invocation Conventions

Use named skill triggers so behavior is consistent across local sessions and PR comments.

- Canonical skill name: `update-eng-style-guide`
- Explicit marker form: `[skill:update-eng-style-guide]`
- Supported phrase triggers:
  - `update style guide`
  - `update eng style guide`
  - `update engineering style guide`
- Alias skill names:
  - `update-style-guide`
  - `update-engineering-style-guide`
- Session-closeout skill:
  - `consolidate-session-learnings`
  - `[skill:consolidate-session-learnings]`
  - phrase: `consolidate session learnings`
- Dependency update skill:
  - `update-deps`
  - `[skill:update-deps]`
  - phrases: `update deps`, `dependency update`, `/update-deps`
- Operations skill:
  - `operations`
  - `[skill:operations]`
  - phrases: `operations pattern`, `ops review`
  - apply by default when touched paths include:
    - `backend/**/ops.py`
    - `backend/**/ops/**/*.py`

When a prompt or PR comment includes one of these triggers, agents should load and apply
that skill if available.

## Instruction Maintenance Policy

When the user gives broad feedback about coding style, review expectations, workflow, or
agent behavior, agents should proactively update instruction docs in the same change
unless the user asks not to.

- Keep `AGENTS.md` concise and map-like; avoid turning it into a large policy dump.
- Put durable style guidance in `docs/engineering/style-guide.md`.
- Put review process guidance in `docs/engineering/code-review-checklist.md`.
- Put area-specific guidance in path-scoped files (`frontend/AGENTS.md`,
  `backend/AGENTS.md`).
- If behavior changes, update the relevant docs immediately and add a concise note to
  `docs/agent-notes/` for future agents and engineers.

## Environment

### UV

This project heavily uses `uv`, so you can rely on it.

- Main `uv` docs: https://docs.astral.sh/uv/

### Python Virtual Environment

To activate Python, run `source .venv/bin/activate` to use this virtual environment. If
you're on Windows, you might need to do `.venv\\Scripts\\activate.bat`, but prefer the
Linux/Mac first and fall back to Windows if you know you're on Windows or the other one
doesn't work.

### Taskfile

We use `Taskfile.yml` from https://taskfile.dev/ for commands to run.

- Main `task` (`go-task`) docs: https://taskfile.dev/docs/guide

You can read the `Taskfile.yml` to see some common commands. If you're unsure how to do
something within this project that's a great spot to check before asking.

### Tests

Run tests by activating the virtual environment and then running `pytest $args` as
needed.

### Type checker

Run the type checker by activating the virtual environment and then running `mypy $args`
as needed.

## MCP (Model Context Protocol) Servers

This project uses MCP servers to provide AI assistants with access to documentation and
external services. MCP declarations are managed in `agents.toml` via dotagents and
generated into agent-specific config files (for example `.cursor/mcp.json`,
`.codex/config.toml`, and `opencode.json`). Under dotagents v1, `agents.lock` is
local managed state and should not be committed.

### Setup

Use dotagents as the source of truth:

```bash
bunx dotagents install
```

### Available MCP Servers

The following MCP servers are configured in `agents.toml`:

1. **Chakra UI MCP** (`@chakra-ui/react-mcp`)
   - Provides access to Chakra UI component documentation.
   - Use this when working with UI components, styling, or theming.

2. **Figma MCP** (`https://mcp.figma.com/mcp`)
   - HTTP-based MCP server for Figma integration.
   - Provides access to Figma designs, variables, design tokens, components, and more.
   - Useful for design-to-code workflows, extracting styles, and implementing designs
     accurately.

### Notes

- `agents.toml` is the canonical MCP declaration file for this repo.
- Use `bunx dotagents install` after skill or package changes.
- Use `bunx dotagents sync` when you need to reconcile gitignore, symlinks, or generated
  agent config state.
- `agents.lock` should remain untracked in this repo under dotagents v1.
- Local MCP servers use `bunx` for execution (consistent with the project's use of Bun).
- If an MCP server is not connecting or authenticating properly, check the respective
  documentation links above for troubleshooting.

## Code Style

### Comments

For code comments, please try and use full sentences unless it's like a one or two
(e.g.) summary type of comment block, or the scenario really merits not using a full
sentence.

Also, for code comments, please, if referencing or commenting on variables, enclose them
with backticks, e.g. Set `some_var` to the result of, ..., etc.

Please follow the same commenting guidelines for, e.g., Python docstrings and module
comments as well, along with related things in other languages.

### Printing and Logging

See how `import structlog`, `logger = structlog.stdlib.get_logger()`,
`logger.bind(...)`, `logger.info`, `logger.warning`, and `logger.error` are used. That's
how to do logging in this project. But, only log if it feels really necessary to. I
don't like unecessary logging.

### Imports

Avoid nested imports if possible. If they're necessary, put in an underscored
`@class_cachedproperty` (preferred) or `@cached_property` (if could change per-instance)
if only used within a class. Otherwise, put in an underscored function at the end of the
file decorated with `@lru_cache(1)`.

### Cross-Layer Naming

Use `camelCase` in frontend TypeScript code, including API request/query object keys.
Apply this to object/dictionary keys, not to value literals.

Use `snake_case` in backend Python/Django code, serializers, and persistence-facing keys.

Rely on the existing automatic camel/snake conversion at the API boundary. Rare
exceptions are allowed for protocol literal values (for example enum string values) or
endpoints that explicitly disable camelization.

### Explicit Defaults

Prefer explicit assignment of business-significant values in operations/serializers over
model-level `default=...` values.

Use model defaults only when the value is a deliberate invariant fallback and should not
be required from callers.

For optional Django relations/fields, prefer `blank=True`/`null=True` without
`default=None` unless `None` as a default is an intentional invariant.

### UUIDs

Prefer Python stdlib UUIDv7 when generating new UUID values (for example,
`from uuid import uuid7` and `uuid7()`) when possible. Only use UUIDv4 when there is a
specific compatibility reason.

## Django Specific

### Django Model Migrations

Do not ever handwrite a Django migration file. Activate the virtual environment and then
run `python manage.py makemigrations` instead.

Do not manually edit generated migration files either. If a migration needs to change,
update model code and regenerate it with `makemigrations`.

## Frontend Specific

### Bun

- We use `bun` and `bunx` instead of `npm` and `npx` for this project.
- Use `bun run tscheck` to run the type checker (uses `tsgo` - TypeScript Native).

### Frontend Formatting (oxfmt)

- Use `bun run fmt` to format code (uses `oxfmt` - Rust-based formatter).
- Use `bun run fmt:check` to check formatting without modifying files.
- Use `bun run fmt:toml` to format TOML files (uses `taplo`).

### Frontend Linting (Oxlint + ESLint)

This project uses **two linters** that work together:

1. **Oxlint** - Fast Rust-based linter (~25ms without type-aware, ~2s with type-aware).
   Handles most common rules at high speed.
2. **ESLint** - Handles framework-specific rules that Oxlint doesn't cover (TanStack,
   Storybook, react-refresh, HTML, Markdown).

The `eslint-plugin-oxlint` package disables overlapping ESLint rules to prevent
duplicate diagnostics.

| Command              | What it runs                  | Use case                              |
| -------------------- | ----------------------------- | ------------------------------------- |
| `bun run lint:fast`  | Oxlint without type-aware     | Quick feedback (~25ms)                |
| `bun run lint:typed` | Oxlint with type-aware        | Catches floating promises, etc. (~2s) |
| `bun run lint:full`  | ESLint only                   | Framework-specific rules              |
| `bun run lint:all`   | `lint:typed` then `lint:full` | Full linting                          |
| `bun run lint`       | Alias for `lint:all`          | **Default - use this**                |

Add `:fix` to any command to apply auto-fixes (e.g., `bun run lint:fast:fix`).

#### Oxlint Disable Comments

Oxlint uses its own comment format (not `eslint-disable`):

```typescript
// oxlint-disable-next-line rule-name -- Reason for disabling
```

#### Floating Promises

The `typescript/no-floating-promises` rule is enabled. For intentionally
fire-and-forget async calls, use `void` to explicitly mark them as ignored:

```typescript
// Bad - floating promise warning
navigate({ to: '/home' });

// Good - explicitly ignored
void navigate({ to: '/home' });
```

### Frontend Theme and Variables

- Our project uses Chakra UI V3.
- Please read `.cursor/rules/chakra-ui-rules.mdc` if editing any frontend code.
- All frontend components should follow our themeing structure.
- Also, read @frontend/theme (`@frontend/theme/*`) in its entirety. Every file.
- Review some existing frontend components to see how we use the semantic colors (e.g.
  `primary.text.main`) and regular ones, e.g. `blue.500`.
- You **SHOULD NOT** hard code hex or rgb or other color values if possible. If you do,
  make a `FIXME: Hard coded` comment above/around it.
- **Important: If doing anything that could have style or design changes, or if making
  any visual (not just logic) frontend changes, please read
  `.cursor/rules/design-system-rules.mdc`.**
- You should have access to MCP to Chakra UI's documentation. If inserting, updating, or
  deleting any frontend code that could possibly be touching any visual styles or
  structure, you should use the Chakra UI MCP to get necessary info.

#### Tanstack Router and Query

- Our project heavily uses Tanstack Router and Tanstack Query on the frontend.
  - The routes are in `frontend/routes/**`.
  - A lot of queries (but not all) are on `frontend/queries/**`.
- Use the TanStack CLI directly for docs/discovery workflows.
- If inserting, updating, or deleting frontend code that could touch Tanstack Router,
  Tanstack (React) Query, or related tools, use TanStack CLI docs/discovery commands
  first. Start with `bunx @tanstack/cli --help` to see available commands (for example,
  `libraries`, `doc`, and `search-docs`), then use commands such as:
  - `bunx @tanstack/cli search-docs "loaders" --library router --framework react --json`
  - `bunx @tanstack/cli doc query framework/react/overview --json`
- Immediately stop and tell the user/prompter to fix TanStack CLI availability if you
  cannot run `bunx @tanstack/cli ...` successfully. Direct them to
  https://tanstack.com/cli/latest/docs/overview.
- If the user allows, you can also access Tanstack Router pretty recent documentation at
  any file matching `.cursor/rules/tanstack**.mdc`. However, you must prefer the
  TanStack CLI output for fetching Tanstack relevant documentation or documentation
  context.

#### Auto Code Splitting (Important)

This project uses TanStack Router's automatic code splitting (`autoCodeSplitting: true`
in `vite.config.ts`). For this to work correctly:

- **Only export `Route`** from route files. The `component`, `errorComponent`,
  `pendingComponent`, `notFoundComponent`, and `loader` properties are automatically
  code-split by the bundler plugin.
- **Do NOT export component functions** (e.g., don't do `export function MyPage()`).
  Components should be defined as regular functions, not exported.
- **Type/interface exports are fine** - TypeScript types are erased at compile time and
  don't affect runtime bundling. For example, exporting `FollowInvitationData` types is
  okay.
- If you export a component, it will be bundled into the main application bundle
  instead of being lazily loaded, defeating the purpose of code splitting.

Example of correct pattern:

```tsx
// Correct - only Route is exported
export const Route = createFileRoute('/my-page')({
  component: MyPageComponent,
});

function MyPageComponent() {
  return <div>My Page</div>;
}

// Type exports are fine
export interface MyPageData {
  id: string;
}
```

```tsx
// Wrong - component is exported
export const Route = createFileRoute('/my-page')({
  component: MyPageComponent,
});

export function MyPageComponent() {
  return <div>My Page</div>;
}
```

Note: TanStack Router's ESLint plugin (`@tanstack/eslint-plugin-router`) does not
currently have a rule to enforce this. It only has `create-route-property-order`. The
`react-refresh/only-export-components` rule provides partial protection but has
different semantics.

## Other Documentation to Reference and Update

**Important**: Before doing anything, read anything relevant in `docs/agent-notes/**`.

If your change is significant to add to that, make a new file (probably Markdown but you
can make more files if you want to reference additional files). Title it `YYYY-MM-DD
Some Descriptive Title.md` (or different file extension). From there, even though
redundant, put a top level section that indicates the time the change was made, what
`commit` and `branch` you were on (and worktree) when starting to make the change, what
time the change was made, and what you want to note/document. Try and keep these notes
high level and to the point, but leave enough information for future agents and human
engineers to understand what needs to be understood.
