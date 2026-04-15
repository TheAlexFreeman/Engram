# Skill Distribution Specification

**Change tier:** Protected — modifications require explicit user approval.

This document defines how the canonical Engram skill store is projected into other agent surfaces and how distribution interacts with deployment modes.

---

## Design principles

### Canonical store first

`core/memory/skills/` remains the single source of truth for skill content. Distribution creates projections of that canonical store; it does not create an alternative authoring surface.

### Projection, not authorship

Target-specific outputs are derived artifacts. The authoritative edit path stays inside the canonical Engram skill directory and manifest.

### Adapter-based extensibility

The manifest should name a stable set of target identifiers, but the implementation must remain extensible through target adapters rather than hard-coded one-off branches.

### Deployment-aware materialization

Distribution works from locally installed skill directories. `deployment_mode` determines whether that local directory is expected to exist immediately after clone or must be installed on demand before distribution runs.

## Target identifiers

The `targets` field in `SKILLS.yaml` uses logical target identifiers. This spec reserves the following built-in identifiers:

| Target | Root | Output model | Notes |
|---|---|---|---|
| `engram` | `core/memory/skills/` | Canonical directory | Always refers to the native Engram store. Not a generated output. |
| `generic` | `.agents/skills/` | Lowest-common-denominator exported view | Use when a tool has no dedicated adapter but can consume exported Markdown skills. |
| `claude` | `.claude/skills/` | Target adapter output | Adapter decides whether the target gets symlinks, copies, or rendered Markdown. |
| `cursor` | `.cursor/skills/` | Target adapter output | Adapter is responsible for any metadata stripping or layout changes Cursor requires. |
| `codex` | `.codex/skills/` | Target adapter output | Adapter is responsible for any metadata stripping or layout changes Codex requires. |

This spec fixes the identifier set and root directories. Exact per-target file layout is adapter-defined so implementations can evolve without changing the manifest schema.

## Adapter contract

Each target adapter must declare:

- the target identifier it implements
- the root directory or directories it owns
- whether the target can consume symlinks, requires copies, or requires rendered/adapted output
- the frontmatter policy: preserve, strip, or translate Engram-specific fields
- the deterministic output path for a given skill slug
- a verification method used by sync tooling to detect broken or stale distributed artifacts
- a platform fallback when symlinks are preferred but unavailable

Unknown target names are validation errors unless an adapter with that identifier is registered.

## Targets field semantics

- `defaults.targets` sets the repo-wide target set. If omitted, the effective default is `[engram]`.
- `skills.{slug}.targets` overrides the repo-wide value for that skill.
- Omitting `engram` from a per-skill `targets` list does not relocate the canonical skill directory; it only controls external distribution behavior.
- A skill may target external agent surfaces without changing its trust, source, or canonical storage location.

## Deployment mode interaction

Distribution always operates on the local installed copy of a skill.

### Checked skills

- `checked` skills are expected to exist immediately after clone.
- Distribution tools may generate or verify external targets without an install preflight.
- Missing local content for a `checked` skill is an error state.

### Gitignored skills

- `gitignored` skills may still declare external targets.
- Before generating target outputs, tooling must ensure the canonical local skill directory has been installed from manifest and lock state.
- If the local install is missing, the distributor must report `missing_local_install` and skip target updates rather than creating broken symlinks or empty files.
- A gitignored canonical skill does not become `checked` merely because a target adapter generates an external projection.

Changing `deployment_mode` never changes the target set; it only changes how the canonical local directory arrives in the workspace.

## Transport policy

- Prefer symlinks when the target can consume the canonical Engram format and the host platform supports symlinks reliably.
- Fall back to copies or rendered projections when symlinks are unavailable or the target requires format adaptation.
- Distribution must be idempotent: running the same distribution step twice without source changes produces no semantic diff.

## Fresh clone behavior

| Deployment mode | Clone expectation | Distribution expectation |
|---|---|---|
| `checked` | Skill content is already present locally. | Target outputs can be generated or verified immediately. |
| `gitignored` | Manifest and lock entries are present, but skill content may be absent locally. | Install or sync must materialize the local skill before target outputs are generated. |

## Relation to future work

This specification is the contract for the `multi-agent-distribution` workstream. Implementations may add more targets later through the adapter interface without changing the manifest field structure or the meaning of existing target identifiers.
