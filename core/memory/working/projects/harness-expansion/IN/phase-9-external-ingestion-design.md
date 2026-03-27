---
source: agent-generated
trust: medium
created: 2026-03-27
origin_session: memory/activity/2026/03/27/chat-001
title: "Phase 9 Design: External Ingestion Affordances"
---

# Phase 9 Design: External Ingestion Affordances

## Motivation

The governance plumbing for external content already exists. Engram has:

- `source: external-research` frontmatter type for provenance tracking
- `trust: low` initial assignment for untrusted external sources
- `core/memory/knowledge/_unverified/` quarantine directory for pre-promotion staging
- A promotion pipeline (`memory_promote_knowledge`, `memory_review_unverified`) for escalating trust after human review

What is missing is the **tool surface**: agents must currently use raw Tier 2 write tools, hand-craft frontmatter, and manually enforce trust assignment rules. This bypasses governance, creates provenance drift, and makes ingestion behavior agent-specific rather than system-defined.

Phase 9 closes this gap with three affordances:

1. **`memory_stage_external`** — agent-called MCP tool to stage web-fetched or synthesized content into a project inbox with auto-generated trust frontmatter and SHA-256 deduplication
2. **`fetch_directive` / `mcp_call`** — structured hints surfaced in `phase_payload()` to guide agent fetching behavior for phases that have `type: external` or `type: mcp` sources
3. **`memory_scan_drop_zone`** — bulk ingestion tool that reads configured local watch-folders, hashes file contents, stages new files, and emits a scan report

---

## Gap Analysis: Current vs. Proposed

| Concern | Current State | Proposed |
|---|---|---|
| External content staging | Raw file write + manual frontmatter | `memory_stage_external` with auto-frontmatter |
| Trust assignment | Agent-defined (inconsistent) | System-enforced (`source: external-research`, `trust: low`) |
| Deduplication | None | SHA-256 content hash registry per project |
| Fetch guidance for plans | None | `fetch_directive` in `phase_payload()` response |
| Local folder ingestion | None | `memory_scan_drop_zone` + `watch_folders` config |
| Preview before write | None | Preview envelope matching Phase 5 HITL pattern |

---

## Extension 1: `memory_stage_external` MCP Tool

### Problem

When an agent fetches a web page, synthesizes a research note, or receives content from an external MCP, it has no governed path to write that content into a project's inbox. The governance system assumes files in `_unverified/` or `IN/` already have correct frontmatter — but no tool creates that frontmatter automatically.

### Staging Target Decision

**Decision: stage to `projects/{project}/IN/`** (not `_unverified/`).

Rationale:
- `IN/` is project-scoped and visible to the active implementation agent without KB-wide knowledge
- `_unverified/` is a KB-wide quarantine optimized for the promotion pipeline — mixing externally-fetched project research with KB promotion candidates creates confusion
- Agents can always manually move content from `IN/` to `_unverified/` if KB-wide promotion is the goal
- This matches the existing Phase 5 pattern where approval documents live in project-local `working/approvals/`

### API Design

```python
def stage_external_file(
    project: str,
    filename: str,
    content: str,
    source_url: str,
    fetched_date: str,  # ISO-8601 date string, e.g. "2026-03-27"
    source_label: str,  # human-readable label, e.g. "arxiv-2404.01234"
    *,
    root: Path,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Stage a file in projects/{project}/IN/ with governed frontmatter.

    Returns a preview envelope (always) before writing (if not dry_run).
    Raises DuplicateContentError if SHA-256 hash matches an already-staged file.
    """
```

### Frontmatter Schema

Auto-generated frontmatter for staged files:

```yaml
---
source: external-research
trust: low
origin_url: <sanitized_url>          # query strings stripped (see Security section)
fetched_date: <fetched_date>
source_label: <source_label>
created: <today>
origin_session: <session_id or "unknown">
staged_by: memory_stage_external
---
```

### Preview Envelope

Before writing, the tool returns a preview envelope matching the Phase 5 HITL pattern:

```json
{
  "action": "stage_external",
  "target_path": "core/memory/working/projects/{project}/IN/{filename}",
  "frontmatter_preview": { ... },
  "content_chars": 4821,
  "content_hash": "sha256:abc123...",
  "duplicate": false,
  "staged": false
}
```

When `dry_run=False` (default): write the file and set `"staged": true` in the returned envelope.

### SHA-256 Deduplication

A hash registry is maintained per project at `core/memory/working/projects/{project}/.staged-hashes.jsonl`. Each line: `{"hash": "sha256:...", "filename": "...", "staged_at": "..."}`.

Before writing:
1. Compute `hashlib.sha256(content.encode()).hexdigest()`
2. Scan `.staged-hashes.jsonl` for matching hash
3. If duplicate found: raise `DuplicateContentError` with the filename of the existing staged file
4. If new: write file, append hash entry to `.staged-hashes.jsonl`

### MCP Tool Registration

```python
@mcp.tool(name="memory_stage_external", annotations=TextAnnotation(
    title="Stage external content",
    readOnlyHint=False,
    idempotentHint=False,
))
async def memory_stage_external(
    project: str,
    filename: str,
    content: str,
    source_url: str,
    fetched_date: str,
    source_label: str,
    dry_run: bool = False,
) -> str: ...
```

---

## Extension 2: `fetch_directive` and `mcp_call` in `phase_payload()`

### Problem

When `phase_payload()` returns a phase that has `type: external` or `type: mcp` sources, the agent sees the source intent but has no structured guidance on *how* to fetch the content. The agent must infer the fetching action from the `intent` field string, which is inconsistent and error-prone.

### Design

Extend `phase_payload()` to include a top-level `fetch_directives` list containing one entry per `type: external` or `type: mcp` source whose referenced file does not yet exist on disk.

```json
{
  "phase_id": "...",
  "sources": [...],
  "fetch_directives": [
    {
      "source_index": 0,
      "action": "fetch_and_stage",
      "source_path": "...",
      "suggested_filename": "...",
      "target_project": "...",
      "intent": "...",
      "reason": "Source file does not exist on disk; fetch and stage before starting phase work."
    }
  ],
  "mcp_calls": [
    {
      "source_index": 1,
      "server": "...",
      "tool": "...",
      "arguments": { ... },
      "target_project": "...",
      "suggested_filename": "..."
    }
  ]
}
```

### Emission Condition

`fetch_directive` entries are only emitted when the source file **does not yet exist on disk**. This prevents redundant fetching when a prior session already staged the file.

### `mcp_call` schema

For `type: mcp` sources that include a `mcp_server` and `mcp_tool` field in the SourceSpec YAML:

```yaml
sources:
  - path: core/memory/working/projects/my-project/IN/arxiv-result.md
    type: mcp
    intent: Fetch search results for "RAG evaluation 2025"
    mcp_server: search-mcp
    mcp_tool: search
    mcp_arguments:
      query: RAG evaluation 2025
      limit: 5
```

The `mcp_call` entry in `phase_payload()` would echo these fields with a `suggested_filename` derived from the `path` basename.

---

## Extension 3: `memory_scan_drop_zone` MCP Tool

### Problem

Users may have local folders of PDFs, markdown notes, or downloaded research that they want to bulk-ingest into a project inbox. Currently there is no tool for this — content must be staged one file at a time using raw writes or `memory_stage_external`.

### Design

Add a `watch_folders` configuration key to `agent-bootstrap.toml` that lists folders to scan:

```toml
[[watch_folders]]
path = "C:/Users/example/research-inbox"
target_project = "general-knowledge-base"
source_label = "local-research-inbox"
trust = "low"
```

The `memory_scan_drop_zone` MCP tool reads this config, scans each folder, and stages new files:

```python
def scan_drop_zone(
    *,
    root: Path,
    project_filter: str | None = None,
) -> dict[str, Any]:
    """Scan all configured watch_folders and stage new files.

    Returns a scan report:
    {
      "folders_scanned": 1,
      "files_found": 5,
      "staged_count": 3,
      "duplicate_count": 2,
      "error_count": 0,
      "items": [
        {
          "filename": "paper.md",
          "target_project": "general-knowledge-base",
          "outcome": "staged" | "duplicate" | "error",
          "hash": "sha256:...",
          "error_message": null
        }
      ]
    }
    """
```

### PDF Extraction

If a file ends in `.pdf`:
1. Check if `pdfminer.six` or `pypdf` is installed (subprocess fallback: `python -c "import pdfminer"`)
2. If available: extract plain text; stage extracted text as `.md` variant of the filename
3. If unavailable: log `outcome: error` with `error_message: "PDF extraction unavailable; install pdfminer.six or pypdf"`
4. PDF extraction is **optional** — the tool must not fail if PDF libraries are absent

### Watch Folder Config Schema

Each `[[watch_folders]]` entry in `agent-bootstrap.toml` supports:

```toml
[[watch_folders]]
path = "<absolute or relative path to folder>"
target_project = "<project name>"     # project key, must exist in working/projects/
source_label = "<human-readable label>"
trust = "low"                          # always low for external content
extensions = [".md", ".txt", ".pdf"]  # optional; defaults to [".md", ".txt", ".pdf"]
recursive = false                      # optional; defaults to false
```

---

## Security

### URL Sanitization

Before storing `origin_url` in frontmatter:
1. Parse the URL using `urllib.parse.urlparse`
2. Strip query string (`?...`) and fragment (`#...`)
3. Store only `scheme://netloc/path`
4. Example: `https://arxiv.org/abs/2404.01234?utm_source=feed` → `https://arxiv.org/abs/2404.01234`

**Rationale:** Query strings can contain tracking tokens, session IDs, or adversarial payloads. Stripping them prevents prompt-injection vectors from entering persistent storage.

### Content Size Cap

Maximum content size for `memory_stage_external`: **500,000 characters** (~100KB). Files exceeding this limit are rejected with a clear error message.

**Rationale:** Prevents accidental staging of binary content or extremely large files that would inflate the repository and degrade performance.

### Hash Algorithm

SHA-256 via Python `hashlib.sha256`. Hex digest (64 chars). Stored as `sha256:<hexdigest>` in `.staged-hashes.jsonl`.

### Path Traversal Prevention

For `watch_folders` entries:
1. Resolve the `path` to an absolute path using `Path.resolve()`
2. Ensure the absolute path does not point inside the Engram repo working tree
3. Raise `SecurityError` if the scan path would write outside `working/projects/{project}/IN/`

---

## Open Questions

1. **Should SHA-256 scope be per-project or global?**
   - Per-project (proposed): simpler isolation, prevents cross-project side-channels, allows intentional duplication across projects
   - Global: prevents any duplicate content across the entire system, but adds a single coordination file that can become a bottleneck

2. **Should PDF extraction be a hard dependency or soft optional?**
   - Soft optional (proposed): MCP server starts regardless of PDF library availability; scan just skips PDFs with an error entry
   - Hard dependency: cleaner failure mode but blocks tool availability for users without PDF libraries

3. **Should `fetch_directive` be emitted only for missing files, or always?**
   - Only when file is absent (proposed): reduces noise for phases where the work has been partially done
   - Always: gives agents a consistent signal without them needing to check file existence first

4. **Should `memory_stage_external` return the preview envelope before writing, requiring a second call to write?**
   - No — single call (proposed): the `dry_run=True` parameter exists for agents that want to preview first; default is stage-immediately to match the system's low-friction philosophy
   - Two-call: more consistent with Phase 5 HITL but adds unnecessary latency for simple staging
