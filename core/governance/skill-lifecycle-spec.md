# Skill Lifecycle Specification

**Change tier:** Protected — modifications require explicit user approval.

This document specifies the decomposed skill lifecycle tools that handle creation, discovery, removal, and synchronization of skills. These tools form a single-responsibility suite complementing the existing `memory_update_skill`, which remains the primary interface for fine-grained section edits and approval workflows.

---

## Design principles

### Single responsibility

Each tool has a focused purpose:
- **`memory_skill_list`** — Read-only discovery and catalog queries.
- **`memory_skill_add`** — Create new skills from templates or sources.
- **`memory_skill_remove`** — Archive skills safely with manifest cleanup.
- **`memory_skill_sync`** — Detect and repair manifest/filesystem mismatches.

### Composability

Tools are designed to work together without mutual blocking:
- `memory_skill_add` automatically updates manifests; no separate registration step needed.
- `memory_skill_sync` acts as a repair utility, not a replacement for individual tools.
- `memory_skill_list` provides the discovery layer for all other operations.

### Backward compatibility with memory_update_skill

The existing `memory_update_skill` tool remains the primary interface for:
- **Section-level edits** — upsert, append, replace modes within a specific section.
- **Frontmatter updates** — modifying metadata without touching content.
- **Fine-grained approval workflows** — governed preview-then-apply patterns for sensitive changes.

New tools handle higher-level operations that involve directory structure, manifest registration, and inter-file consistency. They do not supersede `memory_update_skill` — they augment it.

### Governance model

All skill-lifecycle tools inherit the protected-change tier from `core/memory/skills/`. This tier ensures manifest and skill-directory changes remain auditable and reversible. Specific governance rules per tool are documented below.

---

## Tool specifications

### 1. memory_skill_list

**Purpose:** Query and catalog installed skills with metadata, trust levels, lock status, and enabled state. Read-only discovery interface.

**Governance tier:** Read-only (no approval needed).

#### Parameters

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `trust_level` | enum | no | (none) | Filter by trust: `high`, `medium`, `low`, or omit for all levels. |
| `source_type` | enum | no | (none) | Filter by source: `local`, `github`, `git`, `path`, or omit for all sources. |
| `enabled` | boolean | no | (none) | Filter by enabled state (`true`, `false`), or omit to include all. |
| `archived` | boolean | no | false | Include archived skills from `core/memory/skills/_archive/`. |
| `include_lock_info` | boolean | no | true | Include content hash, lock date, and freshness status for each skill. |
| `max_results` | integer | no | 100 | Maximum results to return (0 = unlimited). |

#### Return format

```json
{
  "skills": [
    {
      "slug": "session-start",
      "title": "Session Opener",
      "description": "Session opener for returning users.",
      "source": "local",
      "trust": "high",
      "enabled": true,
      "archived": false,
      "created": "2025-11-15",
      "last_verified": "2026-04-08",
      "file_count": 1,
      "total_bytes": 4820,
      "lock_info": {
        "locked_at": "2026-04-08T15:00:00Z",
        "content_hash": "sha256:a1b2c3d4e5f6...",
        "hash_fresh": true,
        "resolved_ref": null
      }
    }
  ],
  "total_count": 1,
  "filters_applied": {
    "trust_level": null,
    "source_type": null,
    "enabled": null,
    "archived": false
  }
}
```

#### Interaction with manifests

- Reads `SKILLS.yaml` to enumerate enabled skills (filters out `enabled: false` by default).
- Reads `SKILLS.lock` to populate `lock_info` when `include_lock_info=true`.
- Computes lock freshness by comparing `content_hash` in lock entry against current directory state.
- Populates trust and enabled state from manifest; falls back to SKILL.md frontmatter if manifest entry is missing (detection of orphan skills).

#### Error handling

- **No manifest file:** Returns all skills found on disk, marked with `lock_info.hash_fresh=false`.
- **Missing skill directory:** Listed in manifest but directory absent; returned with empty metadata and `lock_info: null`.
- **Hash mismatch:** Returned with `lock_info.hash_fresh=false` (local edits detected).

---

### 2. memory_skill_add

**Purpose:** Create a new skill from a template, remote source, or local path. Registers it in the manifest and updates skill indexes.

**Governance tier:** Protected (requires preview-then-apply approval).

#### Parameters

| Parameter | Type | Required | Description |
|---|---|---|---|
| `slug` | string | yes | Kebab-case skill identifier (validated against `^[a-z0-9]+(?:-[a-z0-9]+)*$`). Must not already exist in manifest or on disk. |
| `title` | string | yes | Short human-readable title (used in SKILL.md frontmatter and catalog). |
| `description` | string | yes | One-line description (used in manifest and SUMMARY.md). |
| `source` | enum | yes | Where the skill comes from: `template`, `github:{owner}/{repo}`, `git:{url}`, `path:{relative-path}`. See skill-manifest-spec.md for validation rules. |
| `ref` | string | no | Version pin for remote sources (git tag, branch, or commit SHA). Required when `source` is `github:` or `git:`. |
| `trust` | enum | yes | Initial trust level: `high`, `medium`, or `low`. Must match value provided in SKILL.md frontmatter created from template. |
| `source_metadata` | object | no | Extra metadata attached to manifest entry (reserved for future use, e.g., `ci_trigger`, `owner_email`). |
| `enabled` | boolean | no | Default `true`. Set `false` to register but not activate. |
| `preview` | boolean | no | Default `false`. When `true`, return preview without creating files. |

#### Return format

```json
{
  "slug": "django-patterns",
  "status": "created",
  "location": "core/memory/skills/django-patterns/",
  "manifest_entry": {
    "source": "github:alexrfreeman/engram-skills",
    "ref": "v1.2.0",
    "trust": "medium",
    "enabled": true,
    "description": "Django-specific development patterns and procedures."
  },
  "lock_entry": {
    "source": "github:alexrfreeman/engram-skills",
    "resolved_ref": "abc1234def5678...",
    "resolved_path": "core/memory/skills/django-patterns/",
    "content_hash": "sha256:f6e5d4c3b2a1...",
    "file_count": 3,
    "total_bytes": 12400
  },
  "artifacts_updated": [
    "core/memory/skills/SKILLS.yaml",
    "core/memory/skills/SKILLS.lock",
    "core/memory/skills/SKILL_TREE.md",
    "core/memory/skills/SUMMARY.md"
  ]
}
```

#### Interaction with manifests

- **Manifest (`SKILLS.yaml`):** Adds a new skill entry with source, trust, description, and enabled state. Validates that slug is unique and kebab-case. Fails if entry already exists.
- **Lock (`SKILLS.lock`):** Generates a new lock entry with resolved path, content hash, resolved ref (for remote sources), file count, and timestamp.
- **SKILL_TREE.md:** Regenerates the skill tree index to include the new skill.
- **SUMMARY.md:** Appends a new entry under the appropriate section (or creates the section if missing).

#### Workflow: Template vs. remote source

**Template path (`source: template`):**
1. Creates directory structure: `core/memory/skills/{slug}/`
2. Generates SKILL.md with frontmatter (trust, source, created date, blank content).
3. Creates blank sections (Procedure, Examples, Related, Triggers, etc.) based on skill type hints.
4. Registers in manifest with `source: local`.

**Remote source (`source: github:` | `git:` | `path:`):**
1. Clones or copies skill from source.
2. Validates that fetched skill contains a valid SKILL.md with matching trust level.
3. Registers in manifest with the source spec and resolved ref (for git sources).
4. Creates or updates lock entry with resolved path and content hash.

#### Error handling

- **Slug already exists:** Return error, no files created. Suggest `memory_skill_remove` to clear first.
- **Invalid slug format:** Return validation error immediately (no approval phase).
- **Remote fetch fails:** Return error during approval preview; no files written.
- **Trust mismatch:** If remote SKILL.md has different trust than supplied `trust` parameter, return error and suggest resolution.
- **Preview mode:** Return the same response as normal mode, but mark files as "would be created" (no side effects).

---

### 3. memory_skill_remove

**Purpose:** Archive a skill safely: move to `_archive/` directory, remove manifest entry, and update indexes.

**Governance tier:** Protected (requires approval).

#### Parameters

| Parameter | Type | Required | Description |
|---|---|---|---|
| `slug` | string | yes | Kebab-case skill identifier to remove. Must exist in manifest or on disk. |
| `archive_reason` | string | no | Optional note on why the skill is being archived (stored in archive metadata). |
| `preview` | boolean | no | Default `false`. When `true`, return preview without modifying files. |

#### Return format

```json
{
  "slug": "old-pattern",
  "status": "archived",
  "previous_location": "core/memory/skills/old-pattern/",
  "archive_location": "core/memory/skills/_archive/old-pattern/",
  "archive_reason": "Superseded by new-pattern v2.0",
  "manifest_entry_removed": {
    "source": "local",
    "trust": "high"
  },
  "artifacts_updated": [
    "core/memory/skills/SKILLS.yaml",
    "core/memory/skills/SKILLS.lock",
    "core/memory/skills/SKILL_TREE.md",
    "core/memory/skills/SUMMARY.md",
    "core/memory/skills/_archive/ARCHIVE_INDEX.md"
  ]
}
```

#### Interaction with manifests

- **Manifest (`SKILLS.yaml`):** Removes the skill entry entirely. Fails if entry doesn't exist and skill is not found on disk (catches typos).
- **Lock (`SKILLS.lock`):** Removes the lock entry for the skill (preserves historical information if lock was committed to git).
- **SKILL_TREE.md:** Regenerates index, removing the skill from the active tree.
- **SUMMARY.md:** Removes the skill entry from the skills summary.
- **Archive index:** Updates `core/memory/skills/_archive/ARCHIVE_INDEX.md` with the archived skill, timestamp, and reason.

#### Archival vs. deletion

Skills are **never permanently deleted**. Instead:
1. Directory moved to `core/memory/skills/_archive/{slug}/`.
2. Manifest and lock entries removed (no longer active).
3. Archive entry created with timestamp and reason for later retrieval if needed.

This preserves history and allows recovery if an archival was mistaken.

#### Error handling

- **Skill not found:** Return error if slug is not in manifest or on disk.
- **Manifest/filesystem mismatch:** If manifest entry exists but no directory found, remove manifest entry anyway (cleanup orphan). If directory exists but no manifest entry, move directory to archive and note inconsistency.
- **Preview mode:** Return the same response as normal mode, but mark files as "would be moved" (no side effects).

---

### 4. memory_skill_sync

**Purpose:** Detect and repair inconsistencies between SKILLS.yaml manifest and the filesystem. Regenerate lock entries, indexes, and symlinks.

**Governance tier:** Standard (auto-fix in non-preview, requires approval for destructive changes like orphan deletion).

#### Parameters

| Parameter | Type | Required | Description |
|---|---|---|---|
| `check_only` | boolean | no | Default `false`. When `true`, report inconsistencies without fixing (dry-run). |
| `fix_stale_locks` | boolean | no | Default `true`. Regenerate lock entries where content hash is stale. |
| `archive_orphans` | boolean | no | Default `false`. Move skill directories found on disk but missing from manifest to `_archive/`. Requires approval if `true`. |
| `remove_missing_entries` | boolean | no | Default `false`. Remove manifest entries for skills with no directory. Requires approval if `true`. |
| `verify_symlinks` | boolean | no | Default `true`. Check and repair distribution symlinks (future). |
| `regenerate_indexes` | boolean | no | Default `true`. Regenerate SKILL_TREE.md and SUMMARY.md. |

#### Return format

```json
{
  "sync_status": "healthy",
  "timestamp": "2026-04-08T15:00:00Z",
  "issues_found": {
    "stale_locks": 2,
    "orphaned_skills": 1,
    "missing_directories": 0,
    "symlink_errors": 0
  },
  "actions_taken": {
    "locks_refreshed": 2,
    "orphans_archived": 0,
    "missing_entries_removed": 0,
    "symlinks_repaired": 0,
    "indexes_regenerated": true
  },
  "details": [
    {
      "type": "stale_lock",
      "slug": "session-start",
      "issue": "content hash mismatch",
      "action_taken": "lock regenerated"
    },
    {
      "type": "orphaned_skill",
      "slug": "experimental-tool",
      "location": "core/memory/skills/experimental-tool/",
      "action_taken": "flagged for review (set archive_orphans=true to fix)"
    }
  ],
  "approval_required": false,
  "artifacts_updated": [
    "core/memory/skills/SKILLS.lock",
    "core/memory/skills/SKILL_TREE.md",
    "core/memory/skills/SUMMARY.md"
  ]
}
```

#### Workflow

1. **Enumerate manifest entries** from SKILLS.yaml.
2. **Check each entry:**
   - Does the directory exist? If no → add to `missing_directories`.
   - Does the lock entry match the current content hash? If no → add to `stale_locks`.
3. **Scan filesystem** for skill directories not in the manifest.
   - Add to `orphaned_skills` for later review or archival.
4. **Perform repairs:**
   - Regenerate stale lock entries (if `fix_stale_locks=true`).
   - Archive orphaned skills (if `archive_orphans=true` and approval granted).
   - Remove missing entries (if `remove_missing_entries=true` and approval granted).
   - Regenerate SKILL_TREE.md and SUMMARY.md (if `regenerate_indexes=true`).

#### Interaction with manifests

- **Manifest (`SKILLS.yaml`):** Reads to enumerate active skills. Modifies only if `remove_missing_entries=true` (removes entries with no directory).
- **Lock (`SKILLS.lock`):** Regenerates entries where hashes are stale. Adds missing lock entries for skills newly detected on disk.
- **SKILL_TREE.md:** Regenerated based on current manifest and archive state.
- **SUMMARY.md:** Regenerated to reflect current skill catalog.

#### Approval gates

Destructive operations require explicit user approval:
- **`archive_orphans=true`:** Moves skills from disk to archive; user should review what's being archived.
- **`remove_missing_entries=true`:** Removes manifest entries; user should confirm they don't want to keep metadata for missing skills.

Non-destructive operations (lock refresh, index regeneration) proceed automatically.

#### Error handling

- **Manifest file missing:** Return error — cannot proceed without manifest. Suggest creating a manifest with `memory_skill_sync --initialize` (future tool).
- **Corrupted manifest:** Return parse error and suggest manual review.
- **Corrupted lock:** Treat as stale and regenerate (non-destructive).
- **Permission errors:** Return error with file path and permission level required.

---

## Relationship to memory_update_skill

`memory_update_skill` and the new decomposed tools serve different scopes:

| Operation | Tool | Responsibility |
|---|---|---|
| **Create a new skill** | `memory_skill_add` | Directory structure, manifest registration, initial SKILL.md. |
| **Edit skill content (sections)** | `memory_update_skill` | Upsert, append, replace within a specific section. |
| **Update skill frontmatter** | `memory_update_skill` | Modify trust, source, origin_session metadata. |
| **Governed approval flow** | `memory_update_skill` | Preview-then-apply for sensitive edits. |
| **List and discover skills** | `memory_skill_list` | Catalog query, filtering, lock status inspection. |
| **Remove a skill** | `memory_skill_remove` | Archive skill and cleanup manifest/lock entries. |
| **Detect inconsistencies** | `memory_skill_sync` | Manifest/filesystem mismatch detection and repair. |

**When to use which tool:**

- **Adding a brand new skill:** Use `memory_skill_add` to create structure and register. Then use `memory_update_skill` for content development.
- **Editing an existing skill:** Use `memory_update_skill` for section edits and metadata updates.
- **Discovering available skills:** Use `memory_skill_list` with filters.
- **Removing a skill:** Use `memory_skill_remove` (higher-level than `memory_update_skill delete`).
- **Repairing manifest/filesystem mismatch:** Use `memory_skill_sync` when you suspect inconsistencies.

---

## Error handling matrix

### Common scenarios

| Scenario | Tool | Expected behavior |
|---|---|---|
| Skill slug already exists | `memory_skill_add` | Reject with error. Suggest `memory_skill_remove` first. |
| Source URL is invalid | `memory_skill_add` | Reject during preview. Validate URL format before approval. |
| Remote fetch fails (network) | `memory_skill_add` | Reject during preview with network error details. |
| Trust mismatch (manifest vs. SKILL.md) | `memory_skill_add` | Reject with both trust values; ask user to correct one. |
| Slug doesn't exist | `memory_skill_remove` | Reject with error. Suggest using `memory_skill_list` to find correct slug. |
| Manifest is missing | `memory_skill_sync` | Refuse to proceed. Suggest initializing with `memory_skill_add`. |
| Content hash mismatch | `memory_skill_sync` | Mark as stale, regenerate on next sync (non-destructive). |
| Orphaned skill on disk | `memory_skill_sync` | Flag in report. Require explicit approval to archive. |
| Missing directory (manifest entry only) | `memory_skill_sync` | Flag in report. Require explicit approval to remove entry. |

### Trust/approval patterns

| Operation | Preview required? | Approval required? | Reason |
|---|---|---|---|
| `memory_skill_list` | No | No | Read-only, no system changes. |
| `memory_skill_add` | Yes | Yes | Creates new skill directory and updates manifest (protected). |
| `memory_skill_remove` | Yes | Yes | Archives skill and removes manifest entry (destructive, protected). |
| `memory_skill_sync` (lock refresh) | Yes | No | Non-destructive, automatic lock refresh. |
| `memory_skill_sync` (archive orphans) | Yes | Yes | Destructive, requires approval. |
| `memory_skill_sync` (remove missing) | Yes | Yes | Manifest cleanup, requires approval. |

---

## Interaction matrix

This matrix shows how each tool interacts with the key system files:

### File state transitions

```
SKILLS.yaml (manifest)
├── memory_skill_add: Add entry
├── memory_skill_list: Read entries (enumerate skills)
├── memory_skill_remove: Delete entry
└── memory_skill_sync: Check and optionally remove missing entries

SKILLS.lock (lockfile)
├── memory_skill_add: Create lock entry (resolve source, compute hash)
├── memory_skill_list: Read lock entries (report freshness)
├── memory_skill_remove: Delete lock entry
└── memory_skill_sync: Regenerate stale entries, compute missing hashes

SKILL_TREE.md (catalog index)
├── memory_skill_add: Regenerate with new entry
├── memory_skill_list: (no direct interaction)
├── memory_skill_remove: Regenerate (remove entry)
└── memory_skill_sync: Regenerate (sync with manifest)

SUMMARY.md (skill summary)
├── memory_skill_add: Append new skill entry
├── memory_skill_list: (no direct interaction)
├── memory_skill_remove: Remove skill entry
└── memory_skill_sync: Regenerate to match manifest

core/memory/skills/{slug}/ (skill directory)
├── memory_skill_add: Create directory + SKILL.md
├── memory_skill_list: Read to verify existence, compute hash
├── memory_skill_remove: Move to _archive/
└── memory_skill_sync: Verify exists (per manifest), detect orphans

core/memory/skills/_archive/ (archive directory)
├── memory_skill_add: (no interaction)
├── memory_skill_list: Read if archived=true parameter set
├── memory_skill_remove: Move skill directory here + update index
└── memory_skill_sync: Optionally move orphans here
```

### Concurrency notes

- All tools treat SKILLS.yaml and SKILLS.lock as protected files (write operations require approval).
- `memory_skill_sync` is safe to run concurrently with `memory_skill_list` (read-only query).
- `memory_skill_add` and `memory_skill_remove` block other write operations on the same slug (prevent race conditions).
- Lock entry regeneration during `memory_skill_sync` is atomic per entry.

---

## Future extensions

These tools are designed with forward compatibility in mind:

- **Skill publishing:** Extend `memory_skill_add` to support `publish` mode that generates distribution packages.
- **Hook triggers:** Reserve `trigger` field in SKILLS.yaml for lifecycle hooks (e.g., run-on-session-start).
- **Multi-platform targets:** Support `targets: [engram, claude, cursor]` distribution in manifest; `memory_skill_sync --deploy` would generate platform-specific packages.
- **Skill versioning:** Extend lock schema to support multiple versions of the same skill coexisting.
- **Dependency graph:** Add skill dependencies to manifest; `memory_skill_sync` would detect and report missing dependencies.

---

## See also

- `core/governance/skill-manifest-spec.md` — Full schema and semantics for SKILLS.yaml and SKILLS.lock.
- `core/governance/update-guidelines.md` — Change-control tiers and approval workflows.
- `README.md` — Architectural guardrails for system changes.
