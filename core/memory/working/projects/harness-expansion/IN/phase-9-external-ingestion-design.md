---
source: agent-generated
trust: medium
created: 2026-03-27
origin_session: memory/activity/2026/03/27/chat-001
title: "Phase 9 Design: External Ingestion Affordances"
---

# Phase 9 Design: External Ingestion Affordances

## Motivation

The governance plumbing for external content already existed before Phase 9. Engram already had:

- `source: external-research` frontmatter for provenance
- `trust: low` as the default stance for unreviewed external material
- project-local `IN/` folders and knowledge-promotion flows for later distillation

What was missing was a governed intake surface. Agents had to write files manually, hand-build frontmatter, and decide their own deduplication behavior. That created provenance drift and made external intake inconsistent across sessions.

Phase 9 closes that gap with three concrete affordances:

1. `memory_stage_external` stages externally fetched text into a project inbox with enforced frontmatter and per-project SHA-256 deduplication.
2. `phase_payload()` now emits `fetch_directives` and `mcp_calls` for missing external or MCP-backed sources so the intake work is explicit before execution starts.
3. `memory_scan_drop_zone` bulk-stages files from configured watch folders without allowing the scanner to recurse into the Engram repository itself.

## Implemented Surface

### `memory_stage_external`

`stage_external_file()` is the underlying helper and `memory_stage_external` is the MCP entrypoint. The tool accepts `project`, `filename`, `content`, `source_url`, `fetched_date`, `source_label`, and optional `dry_run` / `session_id` plumbing.

Staged files are written to `core/memory/working/projects/{project}/IN/{filename}` and the helper always builds this frontmatter preview first:

```yaml
---
source: external-research
trust: low
origin_url: <sanitized_url>
fetched_date: <fetched_date>
source_label: <source_label>
created: <today>
origin_session: <session_id or "unknown">
staged_by: memory_stage_external
---
```

The returned envelope contains:

```json
{
  "action": "stage_external",
  "project": "harness-expansion",
  "target_path": "memory/working/projects/harness-expansion/IN/example.md",
  "frontmatter_preview": {"source": "external-research", "trust": "low"},
  "content_chars": 4821,
  "content_hash": "sha256:abc123...",
  "duplicate": false,
  "staged": true
}
```

When `dry_run=true`, the same envelope is returned with `staged: false` and no file is written. This is a direct project-inbox write, not an auto-commit operation.

### SHA-256 deduplication

Each project keeps a local registry at `core/memory/working/projects/{project}/.staged-hashes.jsonl`.

Each line records:

```json
{"hash": "sha256:...", "filename": "example.md", "staged_at": "2026-03-27"}
```

Before writing, the helper computes a SHA-256 digest over the staged content. If the digest already exists in the registry, `DuplicateContentError` is raised with the matching hash and previously staged filename.

### `fetch_directives` and `mcp_calls`

`phase_payload()` now inspects `phase.sources` after resolving the source path against the repo. Missing sources produce structured intake hints:

- `fetch_directives` entries for `type: external` sources
- `mcp_calls` entries for `type: mcp` sources that include `mcp_server` and `mcp_tool`

Each directive includes the source index, the source path, a suggested filename derived from the path basename, the target project, and the source intent. `fetch_directives` also carry the original `source_uri`; `mcp_calls` echo `server`, `tool`, and `arguments` so the client can invoke the right external MCP before staging the result.

Both lists are emitted only when the referenced source file is still absent on disk.

### `memory_scan_drop_zone`

`scan_drop_zone()` reads `[[watch_folders]]` from `agent-bootstrap.toml` and stages matching files into the configured target project inbox.

Supported keys per watch-folder entry are:

```toml
[[watch_folders]]
path = "C:/Users/example/research-inbox"
target_project = "harness-expansion"
source_label = "local-research-inbox"
extensions = [".md", ".txt", ".pdf"]
recursive = false
```

Behavior details:

- Relative watch-folder paths resolve from the repo root.
- Watch folders that resolve inside the Engram repository are rejected.
- `.md` and `.txt` files are read as text with replacement for decode errors.
- `.pdf` files are extracted with `pypdf` first and `pdfminer.six` second.
- If PDF extraction is unavailable or fails, the tool records a per-file error and continues.

The scan report returns:

```json
{
  "folders_scanned": 1,
  "files_found": 5,
  "staged_count": 3,
  "duplicate_count": 1,
  "error_count": 1,
  "items": [
    {
      "filename": "paper.pdf",
      "target_project": "harness-expansion",
      "outcome": "staged",
      "hash": "sha256:...",
      "error_message": null
    }
  ]
}
```

## Security and Constraints

### URL sanitization

`origin_url` is normalized by parsing the URL and dropping the query string and fragment before persistence. Example:

- `https://arxiv.org/abs/2404.01234?utm_source=feed#section` becomes `https://arxiv.org/abs/2404.01234`

This prevents tracking tokens and prompt-injection payloads from being copied into durable frontmatter.

### Content size cap

`memory_stage_external` rejects content larger than 500,000 characters. The cap exists to prevent accidental binary intake and oversized repo-local blobs.

### Filename normalization

Staged filenames are basenames only. Path separators, traversal segments, and empty names are rejected before writing.

### Repo-bound output

All staged output is forced under `working/projects/{project}/IN/`. Watch-folder inputs may come from outside the repo, but they cannot point back into the Engram tree.

## Resolved Decisions

1. SHA-256 scope is per-project, not global.
2. PDF extraction is a soft optional feature; missing libraries become per-file scan errors.
3. `fetch_directives` and `mcp_calls` are emitted only when the target source file does not already exist.
4. External intake stages to `projects/{project}/IN/`, not `_unverified/`.
5. `memory_stage_external` stages immediately by default, with `dry_run=true` as the preview-only path.

The result is intentionally narrow. Phase 9 standardizes intake, but it does not bypass later review, summarization, or promotion into durable knowledge domains.
