# Skill Manifest Specification

This document defines the schema and semantics for `SKILLS.yaml` (the declarative skill manifest) and `SKILLS.lock` (the integrity lockfile). Together they make skill dependencies explicit, reproducible, and verifiable.

**Change tier:** Protected — modifications require explicit user approval.

## Design principles

The manifest system is modeled after package manager conventions (dotagents `agents.toml`, npm `package.json`, pip `requirements.txt`) adapted to Engram's governance model:

- **Declarative over discovery.** The manifest is the authoritative list of active skills. Convention-based directory scanning (`generate_skill_catalog.py`) becomes a secondary validation check, not the source of truth.
- **Trust-aware defaults.** Source type and trust level influence default behaviors (deployment mode, verification frequency).
- **Backward compatible.** Existing vaults without a manifest continue to work — the catalog generator remains functional. The manifest is an additive layer.

## SKILLS.yaml schema

Location: `core/memory/skills/SKILLS.yaml`

```yaml
# Skill Manifest — Engram vault skill dependencies
# Schema version tracks breaking changes to this format.
schema_version: 1

# Default settings applied to all skills unless overridden per-entry.
defaults:
  # Optional repo-wide override. Omit deployment_mode to use trust-aware fallback:
  # high -> checked, medium -> checked, low -> gitignored.
  deployment_mode: checked        # checked | gitignored
  targets: [engram]               # distribution targets (engram | generic | claude | cursor | codex)

# Skill declarations. Each key is the skill slug (kebab-case, matches directory name).
skills:
  session-start:
    source: local                 # see "Source formats" below
    trust: high                   # high | medium | low — must match SKILL.md frontmatter
    description: >-
      Session opener for returning users.

  codebase-survey:
    source: local
    trust: medium
    description: >-
      Systematic host-repo exploration for worktree-backed memory stores.

  # Example: skill from a remote git repository
  # django-patterns:
  #   source: github:alexrfreeman/engram-skills
  #   ref: v1.2.0
  #   trust: medium
  #   deployment_mode: gitignored
  #   description: >-
  #     Django-specific development patterns and procedures.
```

### Top-level fields

| Field | Type | Required | Description |
|---|---|---|---|
| `schema_version` | integer | yes | Schema version. Current: `1`. Validators reject unknown versions. |
| `defaults` | mapping | no | Default values applied to all skill entries. Per-skill fields override. |
| `skills` | mapping | yes | Skill declarations keyed by slug. |

### Defaults block

| Field | Type | Default | Description |
|---|---|---|---|
| `deployment_mode` | enum | trust-aware | Optional repo-wide override. If omitted, the effective default is derived from trust: `high -> checked`, `medium -> checked`, `low -> gitignored`. `source: local` entries still resolve to `checked` because they must clone with the repo. |
| `targets` | list[string] | `[engram]` | Distribution targets. See `core/governance/skill-distribution-spec.md` for target identifiers and adapter rules. Use `[]` to disable external projections by default. |

### Per-skill fields

| Field | Type | Required | Description |
|---|---|---|---|
| `source` | string | yes | Source format string. See "Source formats" below. |
| `ref` | string | no | Version pin: git tag, branch, or commit SHA. Ignored for `local` source. |
| `trust` | enum | yes | `high`, `medium`, or `low`. Must match SKILL.md frontmatter `trust` field. |
| `description` | string | yes | One-line description for catalog display. Should match SKILL.md frontmatter. |
| `deployment_mode` | enum | no | Override for this skill. If omitted, inherits from `defaults.deployment_mode` when present, otherwise falls back to the trust-aware default. |
| `targets` | list[string] | no | Override distribution targets for this skill. Inherits from `defaults.targets` if omitted. Use `[]` to disable external projections for one skill. |
| `enabled` | boolean | no | Default `true`. Set `false` to disable without removing the entry. |
| `trigger` | string or mapping | no | Lifecycle trigger binding. Reserved for hook-trigger-metadata plan. |

### Source formats

Sources tell the resolver where to find a skill's content. Four formats are supported:

| Format | Syntax | Example | Resolution |
|---|---|---|---|
| **Local** | `local` | `source: local` | Skill directory already exists at `core/memory/skills/{slug}/`. No remote fetch. |
| **GitHub shorthand** | `github:{owner}/{repo}` | `source: github:alexrfreeman/engram-skills` | Clones `https://github.com/{owner}/{repo}`, discovers skill by slug in `skills/` or root. |
| **Pinned git ref** | `github:{owner}/{repo}` + `ref` field | `ref: v1.2.0` or `ref: abc1234` | Same as GitHub shorthand but checks out the specified ref. |
| **Git URL** | `git:{url}` | `source: git:https://git.corp.dev/team/skills` | Clones arbitrary git URL. Supports HTTPS, SSH (`git:git@host:repo`), and local file URLs (`git:file:///tmp/shared-skills.git`). |
| **Local path** | `path:{relative-path}` | `source: path:../shared-skills/my-skill` | Copies or symlinks from a local filesystem path relative to vault root. Paths must stay relative, never absolute. |

### Source format validation

```
local            → exact literal "local"
github:{o}/{r}   → /^github:[a-zA-Z0-9_.-]+\/[a-zA-Z0-9_.-]+$/
git:{url}        → /^git:(https?:\/\/|git@|file:\/\/).+$/
path:{p}         → /^path:(?:\.\/|\.\.\/).+$/  (must be relative, must start with ./ or ../)
```

### Resolution precedence

When resolving a skill, the resolver follows this order:

1. **Local directory** — If `core/memory/skills/{slug}/SKILL.md` exists and source is `local`, use it directly.
2. **Lockfile match** — If `SKILLS.lock` has an entry for this slug with a matching source and the content hash verifies, use the locked version.
3. **Remote fetch** — Clone/fetch from the source, verify content, update lockfile.

### Validation rules

- Every `skills` key must be kebab-case and match the pattern `^[a-z0-9]+(?:-[a-z0-9]+)*$`.
- The `trust` field must match the corresponding `SKILL.md` frontmatter `trust` field. A mismatch is a sync error, not a silent override.
- `ref` is only valid when `source` is `github:` or `git:`. Setting `ref` with `source: local` is an error.
- `path:` sources must stay relative. Absolute filesystem paths are rejected so manifests remain portable across worktrees and machines.
- `source: local` cannot use `deployment_mode: gitignored`. Local skills must stay checked so fresh clones receive the skill contents; use `path:`, `git:`, or `github:` if you want on-demand install.
- `targets` entries must use known target ids from the distribution registry. Unknown target names are validation errors.
- Duplicate target names are normalized away while preserving first-seen order. An empty list is valid and disables external projections for that skill.
- `enabled: false` skills are excluded from catalog generation and distribution but retained in the manifest for version tracking.
- Unknown fields at any level produce a validation warning (not an error) to support forward-compatible extensions.

## Deployment mode semantics

`deployment_mode` controls whether the canonical skill directory is expected to be committed to git or restored on demand from the manifest and lockfile.

### Effective deployment mode

Resolve the effective mode in this order:

1. `skills.{slug}.deployment_mode`
2. `defaults.deployment_mode`
3. Trust-aware fallback from `trust`

Recoverability rule: `source: local` entries resolve to `checked` unless the per-skill entry explicitly sets `deployment_mode: gitignored`, which is invalid. Repo-wide `defaults.deployment_mode: gitignored` and the low-trust fallback do not override this rule for local skills.

| Trust | Effective default | Rationale |
|---|---|---|
| `high` | `checked` | High-trust skills are part of the durable operating surface and should be available immediately after clone. |
| `medium` | `checked` | Medium-trust skills remain shared workflow defaults unless a repo explicitly chooses a lighter local-only install model. |
| `low` | `gitignored` | Low-trust or agent-generated skills are more likely to be experimental and noisy, so on-demand install is the safer default when the source is recoverable (`path:`, `git:`, or `github:`). |

### Migration from checked-only vaults

Existing vaults that already commit all skills do not need an immediate migration. Keeping `defaults.deployment_mode: checked` preserves current behavior.

Repositories can adopt trust-aware deployment incrementally by:

- removing `defaults.deployment_mode`, so omitted entries fall back to the trust-aware mapping
- setting `deployment_mode: gitignored` only on selected skills
- later restoring an explicit repo-wide default if team policy requires uniform behavior

This preserves backward compatibility for current vaults while giving new or revised vaults a clean path to lower-noise deployment.

### Gitignore management contract

When a skill's effective deployment mode is `gitignored`:

- the canonical install location remains `core/memory/skills/{slug}/`
- the path is managed inside a delimited block in `core/memory/skills/.gitignore`
- tooling may add or remove entries only inside that managed block; user-authored rules outside the block are preserved verbatim
- switching a skill back to `checked` removes the managed ignore entry but does not delete the local directory

### Fresh clone contract

- `checked` skills must be present and usable immediately after clone without an install step
- `gitignored` skills must be recoverable from `SKILLS.yaml` and `SKILLS.lock` through install or sync workflows
- `source: local` skills therefore remain `checked`; they are not reconstructible from the lockfile alone
- tools must surface missing `gitignored` skills as an explicit state, not silently treat them as absent from the manifest

See `core/governance/skill-distribution-spec.md` for how deployment mode interacts with external distribution targets.

## SKILLS.lock schema

Location: `core/memory/skills/SKILLS.lock`

The lockfile records the exact resolved state of each skill, enabling reproducible installs. It is auto-generated — never hand-edited.

```yaml
# Auto-generated by Engram skill resolver. Do not edit manually.
# Regenerate with: memory_skill_sync or generate_skill_manifest.py --lock
lock_version: 1
locked_at: "2026-04-08T15:00:00Z"

entries:
  session-start:
    source: local
    resolved_path: core/memory/skills/session-start/
    content_hash: "sha256:a1b2c3d4e5f6..."
    locked_at: "2026-04-08T15:00:00Z"
    file_count: 1
    total_bytes: 4820

  # Remote skill example:
  # django-patterns:
  #   source: "github:alexrfreeman/engram-skills"
  #   resolved_ref: "abc1234def5678..."
  #   resolved_path: core/memory/skills/django-patterns/
  #   content_hash: "sha256:f6e5d4c3b2a1..."
  #   locked_at: "2026-04-08T15:00:00Z"
  #   file_count: 3
  #   total_bytes: 12400
```

### Lock entry fields

| Field | Type | Description |
|---|---|---|
| `source` | string | The source string from the manifest at lock time. |
| `requested_ref` | string | Optional manifest `ref` value captured at lock time for remote sources. Used to detect ref changes in frozen verification. |
| `resolved_ref` | string | For remote sources: the full commit SHA that was resolved. Absent for `local`. |
| `resolved_path` | string | Repo-relative path to the installed skill directory. |
| `content_hash` | string | `sha256:{hex}` hash of the skill directory contents (deterministic tree hash). |
| `locked_at` | string | ISO 8601 timestamp of when this entry was locked. |
| `file_count` | integer | Number of files in the skill directory at lock time. |
| `total_bytes` | integer | Total byte size of skill directory at lock time. |

### Content hashing algorithm

The content hash covers the skill directory deterministically:

1. List all files in the skill directory recursively, sorted lexicographically by relative path.
2. For each file, compute `SHA-256(relative_path + "\0" + file_contents)`.
3. Concatenate all per-file hashes in order and compute the final `SHA-256` of the concatenation.

This ensures the hash changes when any file is added, removed, renamed, or modified.

### Lock freshness

A lock entry is **fresh** when:
- The `content_hash` matches the current directory state.
- For remote sources with a manifest `ref`: `requested_ref` matches the current manifest `ref` value.
- For remote sources without a manifest `ref`: `resolved_ref` still identifies the locked commit.

A lock entry is **stale** when:
- The content hash no longer matches (local edits since last lock).
- The manifest `ref` changed and no longer matches `requested_ref` recorded in the lock entry.
- The skill was removed from the manifest but the lock entry remains.

### Frozen install mode

For CI/CD reproducibility, the resolver supports frozen mode:
- Only resolves from lockfile entries — refuses to fetch from remote.
- Fails immediately on any hash mismatch or missing lock entry.
- Invoked via `memory_skill_sync --frozen` or the `skill_install_frozen.py` script.

## Interaction with existing systems

### SKILL_TREE.md and generate_skill_catalog.py

The catalog generator continues to work by scanning directories. When a manifest exists, the generator should:
1. Warn about skills present on disk but missing from the manifest (orphans).
2. Warn about manifest entries with no corresponding directory (missing).
3. Include only `enabled: true` (or omitted) skills in the catalog output.

### Trust model

The manifest `trust` field is a declaration that must match the SKILL.md frontmatter. It is not an override mechanism. Trust changes flow through `memory_update_skill` with the governed approval workflow, then the manifest is updated to match.

### Protected-change tier

Both `SKILLS.yaml` and `SKILLS.lock` live under `core/memory/skills/` and inherit its protected-change status. Creating or modifying either file requires explicit user approval per `update-guidelines.md`.

Exception: `SKILLS.lock` regeneration during `memory_skill_sync` is treated as an automatic change when the manifest itself hasn't changed and only hashes are being refreshed. This parallels how `npm install` updates `package-lock.json` without requiring manual approval.
