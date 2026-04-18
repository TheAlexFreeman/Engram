# Skill Distribution Specification

**Change tier:** Protected — modifications require explicit user approval.

This document defines how the canonical Engram skill store is projected into other agent surfaces, which built-in targets are reserved, how Engram metadata maps into each target's output format, and the adapter interface used to add new targets.

---

## Design principles

### Canonical store first

`core/memory/skills/` remains the single source of truth for skill content. Distribution creates projections of that canonical store; it does not create an alternative authoring surface.

### Projection, not authorship

Target-specific outputs are derived artifacts. The authoritative edit path stays inside the canonical Engram skill directory and manifest.

### Adapter-based extensibility

The manifest names stable logical target identifiers, but the implementation resolves them through target adapters rather than hard-coded one-off branches.

### Deployment-aware materialization

Distribution works from locally installed skill directories. `deployment_mode` determines whether that local directory is expected to exist immediately after clone or must be installed on demand before distribution runs.

### Instruction/provenance separation

External targets should receive the skill's usable instructions. Engram governance metadata should remain metadata unless a target profile explicitly chooses to preserve it.

### Deterministic output

Target outputs are a pure function of the canonical skill directory, normalized metadata, target identifier, and adapter profile version. Running the same distribution step twice without source changes must produce the same artifact set.

## Distribution profiles

Built-in targets are grouped into three reusable output profiles:

### `canonical-bundle`

- Preserve the canonical directory layout.
- Preserve `SKILL.md` byte-for-byte, including YAML frontmatter.
- Prefer symlink-like transport when supported; otherwise copy the directory tree.
- Preserve relative links and auxiliary files.

### `flat-markdown`

- Emit one Markdown file per skill slug.
- Strip raw YAML frontmatter from visible output.
- Render selected metadata into a short header section above the canonical body.
- Do not silently ship broken relative links. If auxiliary files are required and the adapter cannot copy/rewrite them, fail with `unsupported_auxiliary_files`.

### `prompt-bundle`

- Emit a directory per skill slug containing a prompt-facing Markdown file plus machine-readable sidecar metadata.
- Strip raw YAML frontmatter from the prompt-facing file.
- Keep governance and provenance metadata in the sidecar rather than the visible prompt text.
- Use when the target wants a terse prompt surface but sync tooling still needs structured verification data.

## Built-in target registry

The `targets` field in `SKILLS.yaml` uses logical target identifiers. This spec reserves the following built-in identifiers:

| Target | Root | Profile | Preferred transport | Visible metadata policy | Verification strategy | Notes |
|---|---|---|---|---|---|---|
| `engram` | `core/memory/skills/` | `canonical-bundle` | canonical only | Preserve all canonical metadata and files | Canonical content hash only | Always refers to the native Engram store. Not a generated output. |
| `generic` | `.agents/skills/` | `flat-markdown` | render/copy | Render name, description, and compatibility; keep governance metadata out of prompt text | Root index + rendered file hash | Lowest-common-denominator exported view for tools without a dedicated adapter. |
| `claude` | `.claude/skills/` | `canonical-bundle` | symlink -> copy | Preserve full frontmatter and body verbatim | Symlink target or copied directory hash | Highest-fidelity built-in adapter. Mirrors the canonical skill bundle. |
| `cursor` | `.cursor/skills/` | `flat-markdown` | render/copy | Render name, description, and compatibility; hide governance metadata from prompt text | Root index + rendered file hash | Optimized for single-file Markdown consumption without raw YAML preambles. |
| `codex` | `.codex/skills/` | `prompt-bundle` | render/copy | Prompt file gets name, description, compatibility, and body; governance metadata goes to sidecar | Prompt hash + sidecar hash | Optimized for terse shell-agent prompt surfaces plus machine-readable verification metadata. |

The identifier set and root directories are stable. Format details are versioned through adapter profiles rather than manifest schema changes.

## Target-specific requirements

### `engram`

- No generated projection. The canonical slug directory remains authoritative.
- Distribution tooling must treat `engram` as reserved and always available whether or not it appears in `targets`.

### `generic`

- Output path: `.agents/skills/{slug}.md`
- Artifact model: single rendered Markdown file.
- Render order:
	1. `# {name or slug}`
	2. one-paragraph description
	3. `Compatibility` block when present
	4. canonical body sections in original order
- YAML frontmatter must not appear in visible output.
- Governance metadata must not appear in visible prompt text.
- If the canonical skill depends on auxiliary files and the adapter cannot rewrite/copy them safely, fail with `unsupported_auxiliary_files` rather than generating broken links.

### `claude`

- Output path: `.claude/skills/{slug}/`
- Artifact model: mirrored canonical bundle.
- `SKILL.md` is preserved verbatim, including YAML frontmatter.
- Auxiliary files are mirrored at the same relative paths so canonical links remain valid.
- Preferred transport is a directory symlink when supported. If the host platform cannot create reliable symlinks, the adapter falls back to copying the bundle.
- Because the profile is canonical-preserving, no metadata translation occurs.

### `cursor`

- Output path: `.cursor/skills/{slug}.md`
- Artifact model: single rendered Markdown file.
- Render order:
	1. `# {name or slug}`
	2. description paragraph
	3. `Compatibility` block when present
	4. remaining body sections in canonical order
- YAML frontmatter must be stripped from the visible file.
- Governance metadata must stay out of visible prompt text and live only in the distribution index.
- Relative links to local assets are invalid unless the adapter copied those assets and rewrote the links. Otherwise fail with `unsupported_auxiliary_files`.

### `codex`

- Output path: `.codex/skills/{slug}/SKILL.md` plus `.codex/skills/{slug}/metadata.json`
- Artifact model: prompt bundle.
- `SKILL.md` is prompt-facing and intentionally terse:
	1. `# {name or slug}`
	2. short `Purpose`/description line
	3. `Compatibility` block when present
	4. canonical body sections in original order
- `metadata.json` stores the canonical slug, source path, target id, adapter version, verification hashes, and preserved governance/provenance metadata.
- Raw YAML frontmatter must not appear in the prompt-facing file.
- Auxiliary files may be bundled only if the adapter declares support for them; otherwise fail closed.

## Metadata mapping

The canonical `SKILL.md` contains both instructional and governance metadata. Distribution targets must handle them explicitly rather than accidentally leaking governance fields into prompt text.

### Visible instruction mapping

| Canonical element | `engram` | `claude` | `cursor` | `codex` | `generic` |
|---|---|---|---|---|---|
| `name` | Preserve canonical frontmatter and authored title | Preserve canonical frontmatter and authored title | Render as top-level H1 | Render as top-level H1 in `SKILL.md` | Render as top-level H1 |
| `description` | Preserve canonical frontmatter | Preserve canonical frontmatter | Render as opening paragraph | Render as `Purpose` line | Render as opening paragraph |
| `compatibility` | Preserve canonical frontmatter | Preserve canonical frontmatter | Render as visible `Compatibility` block | Render as visible `Compatibility` block | Render as visible `Compatibility` block |
| Body headings and prose | Preserve verbatim | Preserve verbatim | Preserve section order after rendered header | Preserve section order after terse preamble | Preserve section order after rendered header |
| Auxiliary files | Preserve canonical tree | Preserve canonical tree | Copy and rewrite links or fail | Bundle only when adapter supports it; otherwise fail | Copy and rewrite links or fail |

### Governance and provenance mapping

| Canonical field | `engram` | `claude` | `cursor` | `codex` | `generic` |
|---|---|---|---|---|---|
| `source` | Preserve frontmatter | Preserve frontmatter | Distribution index only | `metadata.json` only | Distribution index only |
| `origin_session` | Preserve frontmatter | Preserve frontmatter | Distribution index only | `metadata.json` only | Distribution index only |
| `created` | Preserve frontmatter | Preserve frontmatter | Distribution index only | `metadata.json` only | Distribution index only |
| `last_verified` | Preserve frontmatter | Preserve frontmatter | Distribution index only | `metadata.json` only | Distribution index only |
| `trust` | Preserve frontmatter | Preserve frontmatter | Distribution index only | `metadata.json` only | Distribution index only |
| `trigger` | Preserve frontmatter for Engram use only | Preserve frontmatter for provenance only; not executed by the distributor | Omit from prompt text; store only in distribution index | Omit from prompt text; store only in `metadata.json` | Omit from prompt text; store only in distribution index |

External targets must never treat `trigger` as executable automation by default. Trigger routing remains an Engram concern unless a future target-specific integration explicitly opts in.

## Targets field semantics

- `defaults.targets` sets the repo-wide target set. If omitted, the effective default is `[engram]`.
- `skills.{slug}.targets` overrides the repo-wide value for that skill.
- `targets: []` means no external projections are generated for that skill. It does not remove the canonical Engram copy.
- Omitting `engram` from a per-skill `targets` list does not relocate the canonical skill directory; it only controls external distribution behavior.
- Unknown target names are validation errors unless an adapter with that identifier is registered.
- Duplicate target names are collapsed while preserving first occurrence order.

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

## Verification model

Non-canonical targets must be verifiable without re-reading the entire canonical store from scratch. Built-in adapters therefore own a target-root index file:

- Path: `{target_root}/.engram-distribution.json`
- Purpose: record which skills were distributed, from which canonical hashes, with which adapter profile version

Minimum index shape:

```json
{
	"target": "cursor",
	"adapter_version": 1,
	"entries": {
		"session-start": {
			"canonical_path": "core/memory/skills/session-start",
			"canonical_hash": "sha256:...",
			"outputs": [".cursor/skills/session-start.md"],
			"rendered_hash": "sha256:..."
		}
	}
}
```

Verification must report one of the following stable states for each target artifact:

- `healthy`
- `missing_local_install`
- `missing_target`
- `broken_link`
- `stale_render`
- `unsupported_auxiliary_files`

`memory_skill_sync` and future distribution tooling will consume these result codes rather than target-specific freeform strings.

## Transport policy

- `canonical-bundle` targets prefer symlinks when the host platform supports them reliably.
- When symlinks are preferred but unavailable, adapters may fall back to directory junctions only if the semantics remain equivalent; otherwise they fall back to copying.
- `flat-markdown` and `prompt-bundle` targets always render/copy because their visible format differs from the canonical bundle.
- Distribution must be idempotent: running the same distribution step twice without source changes produces no semantic diff.

## Fresh clone behavior

| Deployment mode | Clone expectation | Distribution expectation |
|---|---|---|
| `checked` | Skill content is already present locally. | Target outputs can be generated or verified immediately. |
| `gitignored` | Manifest and lock entries are present, but skill content may be absent locally. | Install or sync must materialize the local skill before target outputs are generated. |

## Adapter interface

Every target adapter must implement the same logical contract even if the concrete code uses classes, protocols, or registry functions.

```python
class SkillTargetAdapter(Protocol):
		target_id: str
		root_relpath: str
		profile: Literal["canonical-bundle", "flat-markdown", "prompt-bundle"]
		adapter_version: int

		def plan(
				self,
				*,
				repo_root: Path,
				skill_slug: str,
				canonical_dir: Path,
				manifest_entry: Mapping[str, Any],
				frontmatter: Mapping[str, Any],
				body_markdown: str,
		) -> DistributionPlan: ...

		def materialize(
				self,
				plan: DistributionPlan,
				*,
				transport_capabilities: TransportCapabilities,
		) -> DistributionResult: ...

		def verify(
				self,
				*,
				repo_root: Path,
				skill_slug: str,
				canonical_hash: str,
		) -> VerificationResult: ...

		def remove(self, *, repo_root: Path, skill_slug: str) -> list[Path]: ...
```

Adapter responsibilities:

- `plan()` returns the deterministic output paths, required transport mode, and verification fingerprint inputs for one skill.
- `materialize()` creates or updates artifacts plus the target-root distribution index.
- `verify()` returns one of the stable verification states defined above.
- `remove()` deletes generated artifacts for a skill without touching the canonical Engram directory.

Registration rules:

- Built-in targets are registered under their reserved identifiers.
- New targets must supply a unique identifier, root path, profile, and verification strategy.
- Manifest validation accepts a target name only when an adapter with that identifier is registered.
- Adapter version bumps are allowed to change rendered output, but they must invalidate verification fingerprints so stale projections are detectable.

## Relation to future work

This specification is the contract for the `multi-agent-distribution` workstream.

- `distribution-engine` implements the profiles, registry, verification model, and adapter interface defined here.
- `manifest-integration` wires `targets` through `SKILLS.yaml` validation and defaults.
- `sync-integration` consumes the verification states and target-root index to report and repair stale projections.

Implementations may add more targets later through the adapter interface without changing the manifest field structure or the meaning of existing target identifiers.
