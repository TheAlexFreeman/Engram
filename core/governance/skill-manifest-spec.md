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
  deployment_mode: checked        # checked | gitignored
  targets: [engram]               # distribution targets (future: claude, cursor, codex)

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
| `deployment_mode` | enum | `checked` | `checked` (committed to git) or `gitignored` (fetched on demand). |
| `targets` | list[string] | `[engram]` | Distribution targets. Reserved for multi-agent distribution plan. |

### Per-skill fields

| Field | Type | Required | Description |
|---|---|---|---|
| `source` | string | yes | Source format string. See "Source formats" below. |
| `ref` | string | no | Version pin: git tag, branch, or commit SHA. Ignored for `local` source. |
| `trust` | enum | yes | `high`, `medium`, or `low`. Must match SKILL.md frontmatter `trust` field. |
| `description` | string | yes | One-line description for catalog display. Should match SKILL.md frontmatter. |
| `deployment_mode` | enum | no | Override for this skill. Inherits from `defaults` if omitted. |
| `targets` | list[string] | no | Override distribution targets for this skill. |
| `enabled` | boolean | no | Default `true`. Set `false` to disable without removing the entry. |
| `trigger` | string or mapping | no | Lifecycle trigger binding. Reserved for hook-trigger-metadata plan. |

### Source formats

Sources tell the resolver where to find a skill's content. Four formats are supported:

| Format | Syntax | Example | Resolution |
|---|---|---|---|
| **Local** | `local` | `source: local` | Skill directory already exists at `core/memory/skills/{slug}/`. No remote fetch. |
| **GitHub shorthand** | `github:{owner}/{repo}` | `source: github:alexrfreeman/engram-skills` | Clones `https://github.com/{owner}/{repo}`, discovers skill by slug in `skills/` or root. |
| **Pinned git ref** | `github:{owner}/{repo}` + `ref` field | `ref: v1.2.0` or `ref: abc1234` | Same as GitHub shorthand but checks out the specified ref. |
| **Git URL** | `git:{url}` | `source: git:https://git.corp.dev/team/skills` | Clones arbitrary git URL. Supports SSH (`git:git@host:repo`). |
| **Local path** | `path:{relative-path}` | `source: path:../shared-skills/my-skill` | Copies or symlinks from a local filesystem path relative to vault root. |

### Source format validation

```
local            → exact literal "local"
github:{o}/{r}   → /^github:[a-zA-Z0-9_.-]+\/[a-zA-Z0-9_.-]+$/
git:{url}        → /^git:(https?:\/\/|git@).+$/
path:{p}         → /^path:\.\/.+$/  (must be relative, must start with ./)
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
- `enabled: false` skills are excluded from catalog generation and distribution but retained in the manifest for version tracking.
- Unknown fields at any level produce a validation warning (not an error) to support forward-compatible extensions.

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
- For remote sources: `resolved_ref` matches the `ref` constraint in the manifest (or is the latest when no ref is pinned).

A lock entry is **stale** when:
- The content hash no longer matches (local edits since last lock).
- The manifest `ref` changed and no longer matches `resolved_ref`.
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
