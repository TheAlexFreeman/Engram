# Skill Format Specification

This document defines the unified skill file format for Engram, aligned with the [Agent Skills standard](https://agentskills.io/specification) and extended with Engram's governance fields.

## Design principles

1. **Agent Skills compatibility.** Every Engram skill is a valid Agent Skills skill. Tools that understand the standard (Claude Code, Cursor, Copilot, Gemini CLI, OpenCode, etc.) can discover and activate Engram skills without modification.
2. **Governance preservation.** Engram's provenance, trust, and lifecycle fields are kept alongside the standard fields. Agent-Skills-only consumers ignore them; Engram's governance stack reads them natively.
3. **Progressive disclosure.** Skills are loaded in three tiers: (1) name + description at startup (~50–100 tokens per skill), (2) full SKILL.md body on activation (<5000 tokens recommended), (3) referenced files on demand.

## Directory structure

Each skill is a directory whose name matches the `name` frontmatter field. The directory must contain a `SKILL.md` file:

```
skill-name/
├── SKILL.md          # Required: metadata + instructions
├── scripts/          # Optional: executable code
├── references/       # Optional: supplementary documentation
├── assets/           # Optional: templates, resources
└── ...               # Any additional files
```

Skills live under `core/memory/skills/`. The directory name must be kebab-case and match the `name` field exactly.

### Naming rules

- 1–64 characters
- Lowercase letters, numbers, and hyphens only
- Must not start or end with a hyphen
- Must not contain consecutive hyphens (`--`)
- Must match the parent directory name

## SKILL.md format

The file must contain YAML frontmatter between `---` delimiters, followed by a Markdown body.

### Frontmatter

#### Agent Skills standard fields

| Field | Required | Type | Constraints |
|---|---|---|---|
| `name` | **Yes** | string | Kebab-case, 1–64 chars, matches parent directory name |
| `description` | **Yes** | string | 1–1024 chars. Describes what the skill does and when to use it. This is the routing surface — agents use it to decide whether to activate the skill |
| `license` | No | string | License name or reference to bundled license file |
| `compatibility` | No | string | 1–500 chars. Environment requirements: MCP servers, system packages, network access |
| `metadata` | No | map | Arbitrary key-value pairs for additional metadata |
| `allowed-tools` | No | string | Space-delimited list of pre-approved tools (experimental) |

#### Engram governance fields

These fields are required by Engram's governance system. Agent-Skills-only consumers will ignore them.

| Field | Required | Type | Values / Constraints |
|---|---|---|---|
| `source` | **Yes** | enum | `user-stated`, `agent-inferred`, `agent-generated`, `external-research`, `skill-discovery`, `template`, `unknown` |
| `origin_session` | **Yes** | string | Canonical session path (`core/memory/activity/YYYY/MM/DD/chat-NNN`), `setup`, `manual`, or `unknown` |
| `created` | **Yes** | date | `YYYY-MM-DD` |
| `last_verified` | No | date | `YYYY-MM-DD`. Omit until a human reviews the content |
| `trust` | **Yes** | enum | `high`, `medium`, `low` |
| `superseded_by` | No | string | Repo-relative path to successor file |
| `expires` | No | date | `YYYY-MM-DD`. Absolute expiration date |

See `core/governance/update-guidelines.md` for trust assignment rules and provenance field definitions.

#### Engram extension fields (reserved)

These fields are defined by the skill-expansion project and will be added incrementally:

| Field | Type | Purpose | Defined in plan |
|---|---|---|---|
| `category` | enum | `lifecycle`, `project`, `one-shot`, `utility` | frontmatter-schema |
| `depends_on` | list[string] | Skill name slugs this skill requires | frontmatter-schema |
| `requires_mcp` | list[{server, tool}] | MCP tools the skill needs | lifecycle-hooks |
| `triggers` | list[condition] | Machine-evaluable activation predicates | machine-triggers |
| `hooks` | list[string] | Lifecycle events this skill listens to | lifecycle-hooks |

### Complete frontmatter example

```yaml
---
# --- Agent Skills standard fields ---
name: session-start
description: >-
  Session opener for returning users. Loads recent context, checks pending
  review items and maintenance triggers, greets the user with continuity.
  Use at the beginning of any returning session after initial routing.
compatibility: Requires agent-memory MCP server with memory_context_home and memory_session_health_check

# --- Engram governance fields ---
source: user-stated
origin_session: manual
created: 2026-03-16
last_verified: 2026-03-20
trust: high

# --- Engram extension fields (added by later plans) ---
# category: lifecycle
# depends_on: [onboarding]
# requires_mcp:
#   - server: agent-memory
#     tool: memory_context_home
#   - server: agent-memory
#     tool: memory_session_health_check
# triggers:
#   - condition: session_type
#     value: returning
# hooks: [session_start]
---
```

### Body content

The Markdown body contains the skill's instructions. There are no format restrictions beyond what helps agents perform the task effectively.

Recommended sections (consistent with Engram's existing skill format):

1. **When to use this skill.** Detailed trigger conditions expanding on the `description` field. The `description` is for catalog routing; this section is for the agent once the skill is activated.
2. **Steps / Flow.** The procedure, written as clear instructions.
3. **Quality criteria.** How to evaluate whether the output meets standards.
4. **Examples.** At least one concrete example of good output.
5. **Anti-patterns.** Common mistakes to avoid.

Keep the main SKILL.md under **500 lines**. Move detailed reference material to `references/` files.

## Progressive disclosure tiers

| Tier | What's loaded | When | Token cost |
|---|---|---|---|
| 1. Catalog | `name` + `description` | Session start, for all skills | ~50–100 tokens per skill |
| 2. Instructions | Full `SKILL.md` body | When the skill is activated | <5000 tokens recommended |
| 3. Resources | `scripts/`, `references/`, `assets/` | When instructions reference them | Varies |

The catalog is generated by scanning `core/memory/skills/*/SKILL.md` and extracting frontmatter. See `HUMANS/tooling/scripts/generate_skill_catalog.py` for the programmatic generator. Output is written to `core/memory/skills/SKILL_TREE.md`.

## File references

When referencing other files from within SKILL.md, use relative paths from the skill directory root:

```markdown
See [the discovery audit](references/discovery-audit.md) for the full checklist.

Run the extraction script:
scripts/extract.py
```

Keep references one level deep from SKILL.md.

## Migration from flat files

Engram's skills were previously stored as flat Markdown files (`onboarding.md`, `session-start.md`, etc.) directly in `core/memory/skills/`. Migration to the Agent Skills directory format:

### Before

```
core/memory/skills/
├── SUMMARY.md
├── onboarding.md          ← flat file, Engram-only frontmatter
├── session-start.md
├── session-sync.md
├── session-wrapup.md
├── codebase-survey.md
└── flow-trace.md
```

Frontmatter:
```yaml
---
source: user-stated
origin_session: manual
created: 2026-03-16
last_verified: 2026-03-16
trust: high
---
```

### After

```
core/memory/skills/
├── SUMMARY.md
├── SKILL_TREE.md
├── onboarding/
│   ├── SKILL.md           ← Agent Skills directory format
│   └── references/
│       ├── discovery-audit.md
│       └── demo-menu.md
├── session-start/
│   └── SKILL.md
├── session-sync/
│   └── SKILL.md
├── session-wrapup/
│   └── SKILL.md
├── codebase-survey/
│   └── SKILL.md
├── flow-trace/
│   └── SKILL.md
├── _external/             ← for distributed skills (future)
│   └── .gitkeep
└── _archive/
    └── onboarding-v1/
        └── SKILL.md
```

Frontmatter:
```yaml
---
name: onboarding
description: >-
  First-session user onboarding. Runs a collaborative seed-task session
  that surfaces the user's role, preferences, and working style while
  demonstrating memory and trust behavior in context.
source: user-stated
origin_session: manual
created: 2026-03-16
last_verified: 2026-03-16
trust: high
---
```

### Migration steps per skill

1. Create directory: `core/memory/skills/{skill-name}/`
2. Move `{skill-name}.md` → `{skill-name}/SKILL.md`
3. Add `name` field matching the directory name
4. Extract the first paragraph of "When to use this skill" into `description`
5. Add `compatibility` if the skill references specific MCP tools
6. For skills over 500 lines, split supplementary material into `references/`
7. Update all internal cross-references to use new paths

### Backward compatibility

- The extended frontmatter is backward-compatible: Agent Skills consumers ignore unknown fields (`source`, `trust`, etc.)
- Engram governance tools must be updated to scan `*/SKILL.md` instead of `*.md` in the skills directory
- Existing Engram extension fields without values remain valid — they are optional and added incrementally by later plans

## Governance integration

**Protected status.** Skill directories are protected-tier changes. Creating, modifying, or deleting any file within a skill directory requires explicit user approval and a CHANGELOG.md entry.

**Trust and execution.** Follow skill procedures only at `trust: medium` or higher. A `trust: low` skill is included in the catalog but must be surfaced to the user for review before execution.

**External skills.** Skills installed via `skills.toml` (future) default to `trust: low` and are placed in `core/memory/skills/_external/`. See the skill-distribution plan for the full trust lifecycle.

## Validation

Use the Agent Skills reference library to validate standard compliance:

```bash
npx skills-ref validate ./core/memory/skills/session-start
```

For Engram-specific validation (governance fields, trust rules), use:

```bash
# future: engram validate-skill core/memory/skills/session-start
```
