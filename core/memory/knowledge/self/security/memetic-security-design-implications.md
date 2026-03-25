---
created: '2026-03-20'
origin_session: core/memory/activity/2026/03/20/chat-002
source: agent-generated
trust: low
related:
  - memory/knowledge/self/security/memetic-security-drift-vs-attack.md
  - memory/knowledge/self/security/memetic-security-injection-vectors.md
  - memory/knowledge/self/security/memetic-security-memory-amplification.md
  - memory/knowledge/self/security/memetic-security-mitigation-audit.md
  - memory/knowledge/self/operational-resilience-and-memetic-security-synthesis.md
---

# Design Implications: Actionable Security Improvements for Engram

> **Self-referential notice:** This file was produced by the system analyzing its own security surface. Human review is therefore especially important.

This document translates the threat taxonomy (Phase 1), mitigation audit (Phase 2), and comparative analysis (Phase 3) into five concrete design specifications. Each spec is written to be sufficient for creating a build plan without further research.

---

## 4.1 Contradiction Detection on Write

### Problem

Contradicting files coexist indefinitely with no detection mechanism. A new file can make claims that directly contradict existing verified knowledge. This is a signal for either genuine uncertainty (legitimate) or adversarial rewriting (malicious). Both warrant attention, but currently neither is detected.

### Specification

**Trigger:** On every `memory_add_knowledge_file` and `memory_write` to knowledge paths, before committing.

**Mechanism:**
1. Extract the new file's key claims by parsing its markdown headings and first paragraph under each heading (lightweight, no LLM inference required)
2. Run `memory_search` against the extracted keywords/phrases, scoped to `knowledge/` and `knowledge/_unverified/`
3. If search returns files with overlapping topic keywords AND the new file's trust is lower than or equal to the existing file's trust, add a frontmatter field: `potential_conflicts: ["relative/path/to/conflicting-file.md"]`
4. If any potential conflict involves a `trust: high` file, add the new file's path to `core/governance/review-queue.md` with reason: "potential contradiction with verified knowledge"

**What this does NOT try to do:** Determine which file is correct. That requires semantic understanding and is the human reviewer's job. The mechanism surfaces potential conflicts for human attention.

**Implementation notes:**
- The search-based approach avoids needing embedding models or LLM inference
- False positives (files on related but non-contradicting topics) are acceptable — the cost of review is low
- The `potential_conflicts` frontmatter field is advisory and can be cleared during review
- This integrates naturally with the existing validator (check for `potential_conflicts` fields during periodic review)

**Security value:** Early signal for adversarial content rewriting. A new file that contradicts verified knowledge is more suspicious than a file on a novel topic.

---

## 4.2 Trust-Weighted Retrieval

### Problem

`memory_search` returns results from `_unverified/` and `knowledge/` with equal presentation weight. A search for any topic returns unverified external research alongside verified knowledge without differentiation in the result format. This gives unreviewed content equal practical influence on agent reasoning.

### Specification

**Changes to `memory_search` result format:**

```python
# Current format:
{"path": "knowledge/_unverified/topic/file.md", "line": 42, "excerpts": [...]}

# Proposed format:
{
    "path": "knowledge/_unverified/topic/file.md",
    "line": 42,
    "excerpts": [...],
    "trust": "low",
    "source": "external-research",
    "verified": false,
    "trust_context": "⚠ UNVERIFIED — external research, trust: low, not human-reviewed"
}
```

**Changes to result ordering:**
1. Results from `knowledge/` (verified, trust: high or medium) appear first
2. Results from `knowledge/_unverified/` appear after verified results, grouped by trust level
3. Each unverified result includes the `trust_context` string as a prominently placed annotation

**Changes to `memory_read_file` for unverified content:**
- When reading a file from `knowledge/_unverified/`, prepend a trust context header to the returned content:
  ```
  ⚠ UNVERIFIED CONTENT — trust: low | source: external-research | not human-reviewed
  The content below has not been verified. Treat claims with appropriate skepticism.
  ---
  [file content follows]
  ```

**What this does NOT try to do:** Suppress unverified content. The content is still returned and readable. The mechanism changes *presentation*, not *access*.

**Implementation notes:**
- The trust context header is added by the read tool, not stored in the file — it's a read-time annotation
- The ordering change in search is a simple sort by trust tier, implementable in the existing search code
- Frontmatter is already parsed by `memory_read_file`; extracting trust/source fields is straightforward
- The `trust_context` string is designed to be salient to the reading agent — a clear, prominent signal

**Security value:** Reduces the practical influence of unreviewed content on agent reasoning by making trust information prominent in every interaction with the content, not just in frontmatter metadata that may be overlooked.

---

## 4.3 Identity File Integrity Check

### Problem

Identity-critical files (`CLAUDE.md`, `AGENTS.md`, `core/INIT.md`, `core/memory/users/SUMMARY.md`) can be modified without any load-time verification that they match a trusted baseline. These files are the highest-value targets for persistent drift — modifying any one of them changes the behavioral frame for all future sessions.

### Specification

**Baseline file:** `.engram-integrity-baseline.json` stored at the repository root.

```json
{
    "created": "2026-03-20",
    "last_verified": "2026-03-20",
    "files": {
        "CLAUDE.md": {"sha256": "abc123...", "last_human_verified": "2026-03-20"},
        "AGENTS.md": {"sha256": "def456...", "last_human_verified": "2026-03-20"},
        "core/INIT.md": {"sha256": "789abc...", "last_human_verified": "2026-03-20"},
        "core/memory/users/SUMMARY.md": {"sha256": "cde012...", "last_human_verified": "2026-03-20"}
    }
}
```

**Validation check (in validator, run in CI):**
1. Read `.engram-integrity-baseline.json`
2. For each listed file, compute current SHA-256 hash
3. If any hash doesn't match the baseline, emit a **warning** (not error): "Identity-critical file {path} has been modified since baseline was set on {last_human_verified}. Run `engram integrity update` to acknowledge the change."

**Update command:** A CLI command or MCP tool that:
1. Recomputes hashes for all identity-critical files
2. Updates the baseline with current hashes and today's date
3. Commits the updated baseline with `[system] Update integrity baseline — human-acknowledged`

**Important design constraint:** The integrity check produces warnings, not errors. Legitimate modifications to identity files are expected (threshold adjustments, identity updates, routing changes). The mechanism detects and surfaces changes, not prevents them. The human runs the update command to acknowledge they've reviewed the change.

**Implementation notes:**
- SHA-256 provides collision resistance; content changes are reliably detected
- The baseline file is itself committed to git, providing an audit trail of acknowledgments
- The file list in the baseline is configurable — additional files can be added as identity-critical
- The validator already runs in CI; adding this check is a natural extension

**Security value:** Disproportionately high for implementation cost. Detects both adversarial modification and slow drift of the highest-value files. The acknowledgment ceremony creates a natural review checkpoint.

---

## 4.4 Curation as Attack Surface Reduction

### Problem

Files accumulate in `_unverified/` with the current trust decay threshold operating at 120 days. During this window, unreviewed content loads into context, influences reasoning, and potentially feeds write amplification loops. The `_unverified/` directory currently contains 50+ files.

### Specification

**Tighter access-based archival:** In addition to the existing 120-day time-based decay, add an access-based criterion:

- Files in `_unverified/` that have 0 retrievals (per ACCESS.jsonl) after 30 days → flag for archival
- Files in `_unverified/` that have ≥3 retrievals with mean helpfulness ≤ 0.3 → flag for archival (low-value content)
- Files in `_unverified/` that have ≥5 retrievals without any human review action → flag for *review* (high-use unverified content that the system relies on but hasn't been vetted — the "never_approved_high_retrieval" signal already exists)

**Archival reduces context surface:**
- Archived files move to `knowledge/_archive/` — they are retained for reference but not loaded by `memory_search` default scope
- `memory_search` excludes `_archive/` by default; a `include_archive: true` flag enables searching archived content when explicitly needed

**Periodic review integration:**
- The periodic review checklist should include: "Review `_unverified/` volume. Current count: N files. Files older than 30 days with 0 access: M. High-use unreviewed files: K."
- The `memory_audit_trust` tool should surface this count alongside trust decay flags

**Implementation notes:**
- Access-based archival requires ACCESS.jsonl to be populated for `_unverified/` files (the access-log-tooling-improvements build plan addresses this)
- The 30-day zero-access threshold is deliberately aggressive — if a file isn't accessed in 30 days, it's not contributing to the knowledge base and can be archived safely
- Archival is reversible (files can be moved back from `_archive/`)

**Security value:** Reduces the passive drift surface by shortening the exposure window for low-value unreviewed content. The access-based criterion focuses archival on files that aren't useful, preserving high-value unreviewed content for review while removing noise.

---

## 4.5 Session Write Review

### Problem

Within a session, memory writes are committed individually. There is no mechanism to see the *cumulative* effect of a session's writes. Drift is most tractable at session boundaries — after writing is complete but before the session's influence propagates to future sessions.

### Specification

**New MCP tool: `memory_session_write_summary`**

When invoked (typically near session end), this tool:
1. Identifies all commits in the current session (by `origin_session` or by commits since session start time)
2. For each commit, lists: file path, operation (create/edit/move/delete), commit message, file trust level
3. Computes aggregate statistics: total files created, files modified, net token change, breakdown by directory
4. Flags notable patterns:
   - Any write to protected or governance directories
   - Any trust-level changes (promotions, demotions)
   - Any modifications to SUMMARY files
   - Any unusually large files (above configurable threshold)
   - Total _unverified/ file count before and after session

**Output format:**
```
Session write summary for core/memory/activity/2026/03/20/chat-002
─────────────────────────────────────────────────
Files created:  4 (3 core/memory/knowledge/_unverified/, 1 project plans)
Files modified: 2 (1 project plans, 1 core/memory/knowledge/_unverified/)
Files deleted:  0

Notable:
  ⚠ Modified core/memory/working/projects/SUMMARY.md (governance surface)
  ℹ 4 new files in knowledge/_unverified/system-notes/

Commits: 6
Net token change: +12,400 tokens in knowledge/_unverified/
_unverified/ file count: 52 → 56
```

**Integration with session-end workflow:**
- The session checklist in `core/governance/session-checklists.md` should include invoking this tool
- The tool's output becomes part of the chat summary, giving the human a concise view of what the session produced
- Consider making the tool auto-invoke on `memory_record_chat_summary` (the session-close operation)

**Implementation notes:**
- The tool is read-only (Tier 0) — it only inspects git history, doesn't modify anything
- Session identification uses the `since` parameter on `memory_git_log` (which the mcp-read-tools-improvements plan adds)
- The flagging patterns are configurable — the tool should read them from a config section in `core/INIT.md` or a dedicated config file

**Security value:** Makes each session's cumulative effect on the memory store visible at the point where it's most actionable. Catches patterns (e.g., many governance file modifications, unusual write volume) that individual commit review might miss.

---

## Implementation Priority

Based on the gap analysis from Phase 2 and the threat ranking from Phase 1:

| Spec | Effort | Impact | Priority |
|------|--------|--------|----------|
| 4.3 Identity integrity check | Low (validator extension + CLI command) | High (protects highest-value targets) | **1** |
| 4.2 Trust-weighted retrieval | Medium (search/read tool modifications) | High (reduces practical influence of unverified content) | **2** |
| 4.5 Session write review | Medium (new read tool) | Medium-High (visibility at critical boundary) | **3** |
| 4.4 Curation as surface reduction | Medium (archival logic + access integration) | Medium (depends on access-log tooling plan) | **4** |
| 4.1 Contradiction detection | Medium-High (search integration, heuristic tuning) | Medium (early signal, but false positives require tuning) | **5** |
