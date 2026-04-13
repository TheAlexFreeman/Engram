# Engram Sidecar Guide

This document covers `engram-sidecar`, the optional observer process that watches supported local transcript stores and routes session-management writes back through `engram-mcp`.

- If you want the fast setup path, read [QUICKSTART.md](QUICKSTART.md).
- If you want the live proxy path, read [PROXY.md](PROXY.md).
- If you want the MCP server contract, read [MCP.md](MCP.md).
- If you want worktree deployment guidance, read [WORKTREE.md](WORKTREE.md).
- If something breaks, read [HELP.md](HELP.md).

---

## What the sidecar does

`engram-sidecar` is a passive observer. It does not inject prompts, proxy requests, or change the live conversation. Instead, it watches transcript files after the fact and feeds the governed memory surfaces that Engram already exposes.

In the current implementation, the sidecar:

- discovers supported transcript files on disk,
- parses user turns, assistant turns, and MCP tool calls (including timestamps and platform metadata when present),
- appends `tool_call` spans to each session's `TRACES.jsonl` (with deduplication and `metadata.source: sidecar`),
- writes compressed `dialogue.jsonl` rows when a session is recorded (no full message bodies),
- logs ACCESS entries through `memory_log_access_batch`,
- checks aggregation triggers after each ACCESS batch,
- records completed sessions through `memory_record_session` with activity metrics in SUMMARY frontmatter,
- persists local replay state so reruns stay idempotent and `chat-NNN` assignment remains stable.

The sidecar only attributes direct `memory_read_file` retrievals right now. Discovery tools such as `memory_search` and `memory_list_folder` remain outside automatic ACCESS attribution until they have stronger per-file result contracts.

## Current scope

| Platform mode | Status | Notes |
| --- | --- | --- |
| `auto` | Supported | Currently resolves to the Claude Code parser because that is the only implemented transcript backend. |
| `claude-code` | Supported | Reads JSONL transcripts from `~/.claude/projects/` by default. |

Transport support is intentionally narrow in Phase 6: `engram-sidecar` talks to `engram-mcp` over stdio only.

## Quick setup

### 1. Install the server runtime

The sidecar reuses the same runtime dependencies as `engram-mcp`.

```bash
python -m pip install -e ".[server]"
```

### 2. Confirm the repo root

By default the sidecar resolves the memory repo root in this order:

1. `--repo-root`
2. `MEMORY_REPO_ROOT`
3. `AGENT_MEMORY_ROOT`
4. file-relative detection from the installed package

If your Engram checkout is not the current working tree, set `MEMORY_REPO_ROOT` or pass `--repo-root` explicitly.

### 3. Run a one-shot backfill

```bash
engram-sidecar --once --platform claude-code
```

`--once` processes matching transcripts and exits. It is the safest first smoke test because it does not keep a watch loop alive.

### 4. Start watch mode if you want continuous observation

```bash
engram-sidecar --platform claude-code
```

Watch mode polls for transcript changes on a fixed interval and closes inactive sessions automatically.

### 5. Verify the outputs

After a successful run, inspect:

- `core/memory/activity/YYYY/MM/DD/chat-NNN/` for recorded sessions, optional `dialogue.jsonl`, and sibling `chat-NNN.traces.jsonl`,
- `core/memory/knowledge/ACCESS.jsonl`, `core/memory/users/ACCESS.jsonl`, and related namespace logs for sidecar-generated ACCESS entries.

The sidecar writes through MCP tools rather than editing these files directly, so the normal policy checks and repo validation still apply.

## Claude Code transcript discovery

The Claude parser looks for `*.jsonl` transcripts under:

- `CLAUDE_CODE_PROJECTS_DIR`, if set,
- otherwise `~/.claude/projects/`.

Only transcripts modified on or after the configured `since` timestamp are considered. If you omit `--since`, the sidecar defaults to a 24-hour lookback window.

## Configuration reference

### CLI flags

| Flag | Purpose | Default |
| --- | --- | --- |
| `--once` | Process matching transcripts and exit. | Off |
| `--platform` | Select transcript parser backend. | `auto` |
| `--since` | Ignore transcripts older than an ISO date or datetime. | 24 hours before startup |
| `--poll-interval` | Watch-mode polling interval in seconds. | `30` |
| `--mcp-url` | MCP transport selector. Phase 6 accepts only stdio forms. | `stdio://engram-mcp` |
| `--repo-root` | Memory repo root override. | Auto-detected |
| `--state-file` | Override the local sidecar state path. | `~/.engram/sidecar/<repo-hash>.json` |

Accepted stdio transport spellings are `stdio://engram-mcp`, `stdio`, `stdio://`, and `engram-mcp`.

### Environment variables

| Variable | Purpose |
| --- | --- |
| `MEMORY_REPO_ROOT` | Primary repo-root override shared with `engram-mcp`. |
| `AGENT_MEMORY_ROOT` | Alternate repo-root override. |
| `MEMORY_CORE_PREFIX` | Content root override when the managed tree lives under `core/`. |
| `SIDECAR_PLATFORM` | Default platform when `--platform` is omitted. |
| `SIDECAR_POLL_INTERVAL` | Default watch interval in seconds. |
| `SIDECAR_MCP_URL` | Default transport selector. Phase 6 supports stdio only. |
| `CLAUDE_CODE_PROJECTS_DIR` | Override Claude Code transcript discovery root. |

## Local state file

The sidecar keeps a small local JSON state file outside the repo by default:

```text
~/.engram/sidecar/<repo-hash>.json
```

It stores two things:

- transcript watermarks, so unchanged transcript files are skipped on later runs,
- observed-session to canonical `memory/activity/YYYY/MM/DD/chat-NNN` mappings, so reruns keep the same Engram session ID.

Deleting the state file is safe if you intentionally want to rebuild the sidecar's local view, but it also removes replay suppression. Do that only when you expect the sidecar to reprocess old transcripts.

## How it feeds curation

The sidecar is the first automation layer in the session-management roadmap. It exists to bootstrap the feedback signals that Engram's retrieval and curation features already know how to use.

- ACCESS entries are written with `estimator: "sidecar"` so downstream tooling can distinguish them from agent-authored logs.
- Helpfulness is estimated from transcript evidence rather than trusted as ground truth.
- Aggregation triggers still run after ACCESS batches, so normal maintenance thresholds continue to apply.
- Session recording uses the same governed semantic write surface as direct agent workflows, including replay checks.

This keeps the automation conservative: the sidecar enriches the existing system rather than bypassing it.

## Adding a new platform parser

1. Implement the `TranscriptParser` contract in `core/tools/agent_memory_mcp/sidecar/parser.py`: `platform_name()`, `detect_platform()`, `find_transcripts()`, `extract_tool_calls()`, and `parse_session()` returning a `ParsedSession` (populate `dialogue_turns` in transcript order when possible).
2. Add a module under `core/tools/agent_memory_mcp/sidecar/parsers/` and register the parser class in `PARSER_REGISTRY` with a stable CLI key (for example `my-platform`). Keep `PARSER_PRIORITY` ordered so auto mode tries parsers in the intended order.
3. Extend `load_config` / `build_parsers_from_registry` consumers only through the registry: new platforms should not require edits to `lifecycle.py` or trace/dialogue capture logic.
4. Run the sidecar with `--platform <key>` or rely on `auto` once the parser is registered and discovery paths are correct.

## Troubleshooting

### No transcripts are discovered

Check that Claude Code is writing transcripts under `~/.claude/projects/` or set `CLAUDE_CODE_PROJECTS_DIR` to the correct directory. If you are backfilling older sessions, widen the time window with `--since YYYY-MM-DD`.

### The sidecar says the transport is unsupported

Phase 6 only supports stdio transport to the repo-local MCP server. Use the default `SIDECAR_MCP_URL` or one of the accepted stdio aliases.

### The sidecar cannot find the memory repo

Pass `--repo-root /path/to/Engram` or export `MEMORY_REPO_ROOT`. In worktree deployments, point the sidecar at the memory worktree, not the host repository.

### Sessions are skipped unexpectedly

Inspect the local state file. A transcript whose modified time is older than the stored watermark is considered already processed. If you intentionally want to replay historical transcripts, remove the state file or point `--state-file` at a fresh path.

### Duplicate session writes appear after a rerun

The normal path is replay-safe, so duplicates usually mean the local state file was reset or the transcript was materially rewritten. Check whether the observed transcript now represents a different session boundary or content payload than the earlier run.

### Nothing seems to happen in watch mode

Watch mode is mostly quiet when healthy. Use `--once` first to confirm discovery and writing. Then leave watch mode running in a dedicated terminal while Claude Code is active.

## Relationship to the proxy roadmap

The sidecar is Phase 1 of the session-management roadmap. The planned proxy layer is a later, separate capability.

- The sidecar is passive: it watches transcripts and writes memory after the fact.
- The proxy will be active: it can mediate requests, inject context, and enforce compaction-flush behavior before or during a live interaction.

That separation is intentional. You can adopt the sidecar today to bootstrap ACCESS and session data without committing to a proxy architecture.

When you are ready for the active layer, use [PROXY.md](PROXY.md) for the sidecar-only to sidecar+proxy upgrade path.
