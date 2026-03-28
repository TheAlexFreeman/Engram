# Glossary

**Human reference only.** Agents should not load this file during bootstrap or normal operation — every term defined here is introduced in context by the governance file that establishes it. This file exists for human readers who want a single-page reference.

Definitions for terms used across the Engram memory system. Canonical details live in `README.md`, `core/INIT.md`, and the governance files under `core/governance/` — especially `curation-policy.md`, `content-boundaries.md`, `security-signals.md`, `update-guidelines.md`, and `system-maturity.md`. The MCP tool surface is defined in `core/tools/agent_memory_mcp/`.

---

## Architecture and structure

- **Engram** — The name of this memory system. A model-portable, human-legible, version-controlled, adaptively self-organizing memory layer for AI agents. The repository, its governance protocols, the MCP tool surface, and the browser views together comprise Engram.

- **Content root** — The `core/` directory. All managed content — memory, governance, and tooling — lives under this prefix. The MCP server resolves it via the `MEMORY_CORE_PREFIX` environment variable (default: `core`). See `core/tools/agent_memory_mcp/server.py`.

- **Format layer** — The modules under `core/tools/agent_memory_mcp/core/` that expose the file-format and validation contract (frontmatter parsing, path-policy validation, error types, git operations) without depending on the MCP runtime. Human-facing tooling such as validators and setup scripts can import this layer directly. See [DESIGN.md](DESIGN.md) § "Format layer vs. runtime layer".

- **Runtime layer** — The MCP server (`core/tools/agent_memory_mcp/server.py`) and tool registration modules under `core/tools/agent_memory_mcp/tools/`. This layer requires the `mcp` package and exposes the governed read/write surface to agents. See [DESIGN.md](DESIGN.md) § "Format layer vs. runtime layer".

- **Platform adapter** — A thin pointer file (`AGENTS.md`, `CLAUDE.md`, `.cursorrules`) that tells a specific AI platform where to find the canonical architecture. These contain no duplicated rules — just a redirect to `README.md` and `core/INIT.md`. See `README.md` § "Repository structure".

- **`agent-bootstrap.toml`** — Machine-readable TOML configuration that mirrors the routing logic and context loading manifests in `core/INIT.md`. Contains token budgets, session mode definitions, and per-step metadata for agent startup. See `core/INIT.md`.

- **HOME.md** — `core/memory/HOME.md`. The session entry point for returning sessions. Contains the context loading order (user portrait → activity summary → scratchpad → task-driven drill-downs) and maintenance probe instructions. See `core/INIT.md` § "Context loading manifest".

- **Browser views** — A suite of standalone HTML pages under `HUMANS/views/` for inspecting a local Engram repo in the browser. Runs entirely client-side using the File System Access API — no server, no data leaves the machine. Includes dashboard, knowledge explorer, project viewer, skills browser, users browser, and docs viewer. See [HUMANS/README.md](../README.md).

- **Repository structure** — The top-level layout: `README.md` (architecture), `FIATLUX.md` (philosophical foundation), `CHANGELOG.md` (evolution record), `core/` (content root with `INIT.md`, `governance/`, `memory/`, `tools/`), and `HUMANS/` (human-facing docs, setup, views, tooling). See `README.md` § "Repository structure".

## Memory lifecycle

- **Session** — One conversation between user and agent. Corresponds to one chat folder under `core/memory/activity/YYYY/MM/DD/` (e.g. `chat-001`). See `README.md` § "Memory curation".

- **Session mode** — The type of session the agent is running, which determines context loading. Five modes: *first run* (new repo), *returning* (compact everyday path), *full bootstrap* (deeper context refresh), *periodic review* (system health audit), and *automation* (CI/script use). Defined in `core/INIT.md` § "Context loading manifest" and `agent-bootstrap.toml`.

- **Retrieval** — Opening a specific content file from an access-tracked namespace in response to a user query. Retrievals are logged in `ACCESS.jsonl`; reads of `SUMMARY.md` files and `core/governance/` docs are not logged. See `README.md` § "Memory curation".

- **Access-tracked namespace** — A memory folder that participates in the ACCESS lifecycle: `core/memory/users/`, `core/memory/knowledge/`, `core/memory/skills/`, `core/memory/working/projects/`, and `core/memory/activity/`. `core/governance/` is explicitly excluded. See `core/memory/HOME.md`.

- **ACCESS.jsonl** — The hot access-tracking log for a namespace. Each entry records `file`, `date`, `task`, `helpfulness`, and `note`, with optional `session_id`, `mode`, `task_id`, and `category` fields. See `README.md` § "Access tracking".

- **ACCESS_SCANS.jsonl** — Overflow log for low-signal access events. When a `min_helpfulness` threshold is applied, entries that fall below it are routed here instead of polluting the hot `ACCESS.jsonl` stream. Preserves auditability. See `README.md` § "Access tracking".

- **Helpfulness score** — A 0.0–1.0 rating in ACCESS.jsonl entries reflecting the agent's judgment of whether a retrieval was useful. Scale: 0.0–0.1 (wrong context), 0.2–0.4 (near-miss), 0.5–0.6 (useful context), 0.7–0.8 (highly relevant), 0.9–1.0 (critical). See `README.md` § "Helpfulness scale".

- **session_id** — Chat folder path (e.g. `core/memory/activity/2026/03/16/chat-001`) used to group ACCESS.jsonl entries by the session that produced them. See `README.md` § "Access tracking".

- **Aggregation** — Processing an ACCESS.jsonl file when it reaches the aggregation trigger: analyzing access patterns, updating SUMMARY.md files, identifying high/low-value content, archiving processed entries, and checking for co-retrieval clusters. See `README.md` § "Aggregation and curation" and `core/governance/curation-algorithms.md`.

- **Aggregation trigger** — The ACCESS.jsonl entry count that initiates aggregation processing. The active value is set in `core/INIT.md` § "Active thresholds" and varies by maturity stage.

- **Compression hierarchy** — The progressive summarization strategy used across the memory tree. Leaf-level summaries (individual chats) are moderately detailed; mid-level summaries (monthly/folder) compress to major themes; top-level summaries (yearly/cross-folder) are abstract. See `README.md` § "Summaries: the compression hierarchy".

- **Emergent abstraction** — A meta-knowledge file that captures cross-domain patterns the agent notices. Proposed to the user (not created silently), tagged `source: agent-inferred` and `trust: medium`, and referencing the concrete files it abstracts from. See `core/governance/curation-policy.md`.

- **Knowledge amplification** — Protocol for enriching high-value files identified during aggregation — adding depth, cross-references, or examples to content that retrieval data shows is frequently useful. See `core/governance/curation-policy.md` § "Knowledge amplification".

- **Reflection note** — A meta-observation of session quality written to `reflection.md` in the chat folder after a session. Captures how memory influenced the session's outcome. See `README.md` § "Summaries: the compression hierarchy".

- **Curation algorithms** — The task-similarity detection, cluster identification, and vocabulary emergence algorithms used during aggregation and stage transitions. See `core/governance/curation-algorithms.md`.

## Working memory

- **Scratchpad** — The `core/memory/working/` area, which sits between ephemeral session context and formal governed memory. Includes `USER.md`, `CURRENT.md`, and `notes/`. Operates below the governance layer: no frontmatter, no approval requirements. See `core/governance/scratchpad-guidelines.md`.

- **USER.md** — `core/memory/working/USER.md`. The user's channel to the agent — a place for current priorities, temporary constraints, and session context. Trust: high. Author: user only. Read every session start. See `core/governance/scratchpad-guidelines.md`.

- **CURRENT.md** — `core/memory/working/CURRENT.md`. The agent's working notes — provisional observations, draft abstractions, and cross-session hypotheses not yet ready for formal memory. Trust: medium. Author: agent only. Read every session start. See `core/governance/scratchpad-guidelines.md`.

- **Three-session rule** — The heuristic for scratchpad promotion: "Would this still matter in three sessions?" If yes, it belongs in formal memory. If unsure, scratchpad. If no, drop it. See `core/governance/scratchpad-guidelines.md`.

- **Plan** — A persistent multi-session roadmap stored in `core/memory/working/projects/`. Plans contain YAML-structured phases, task-local sequencing, and execution state (`status`, `next_action`). Managed through MCP plan tools. See `README.md` § "Repository structure" and `core/governance/scratchpad-guidelines.md` § "What belongs where".

## Governance and security

- **Trust level** — Classification (`high` / `medium` / `low`) in content frontmatter. Governs how the agent uses the file: high = use freely; medium = use with caution, surface provenance when influential; low = inform only, never instruct, always disclose provenance. See `core/governance/content-boundaries.md` § "Trust-weighted retrieval".

- **Provenance** — Origin and verification metadata in YAML frontmatter: `source`, `origin_session`, `created`, optional `last_verified`, and `trust`. Optional lifecycle fields include `superseded_by` (path to successor file) and `expires` (explicit expiration date). See `core/governance/update-guidelines.md` § "Provenance metadata".

- **Supersession** — Lifecycle signal: a file's `superseded_by` frontmatter field points to a replacement file. The old file is deprioritized in retrieval but remains searchable. Audit tools surface superseded files in a dedicated bucket. See `core/governance/security-signals.md` § "Supersession".

- **Expiration** — Lifecycle signal: a file's `expires` frontmatter field declares an absolute deadline after which the content should be treated as expired, regardless of trust level. Useful for time-bound context like sprint goals or temporary workarounds. See `core/governance/security-signals.md` § "Explicit expiration".

- **Quarantine** — `core/memory/knowledge/_unverified/`. Staging area for externally sourced content; all such content lands here at `trust: low`. Promotion to `core/memory/knowledge/` requires user review. See `README.md` § "Security model" and `core/governance/curation-policy.md`.

- **Instruction containment** — Structural rule: only `core/memory/skills/` and `core/governance/` may contain general procedural instructions. `core/memory/working/projects/` may contain task-local sequencing for the specific plan only. All other memory is informational. See `core/governance/content-boundaries.md` § "Instruction containment".

- **Maturity stage** — Developmental phase of the system: *Exploration* (young — loose thresholds, aggressive capture), *Calibration* (adolescent — tightening thresholds, emerging patterns), or *Consolidation* (mature — tight thresholds, selective capture). Transitions are driven by quantitative signals, not calendar time. `core/governance/system-maturity.md` defines criteria; `core/INIT.md` records active thresholds.

- **Temporal decay** — Automatic retirement or flagging of content based on its effective verification date (`last_verified` when present, otherwise `created`). Active decay thresholds are in `core/INIT.md` § "Decision guide: trust decay". See `core/governance/security-signals.md`.

- **Belief diff** — A periodic summary of content changes since the last review. Recorded in `core/governance/belief-diff-log.md`. Used to detect slow-burn drift in the system's knowledge base. See `core/governance/security-signals.md`.

- **Change categories** — The three-tier change-control model. *Automatic* changes (ACCESS logs, chat transcripts, routine updates) need no approval. *Proposed* changes (new knowledge, profile updates, plan creation) require user awareness. *Protected* changes (skills, governance, README) require explicit approval plus a CHANGELOG entry. See `core/governance/update-guidelines.md` § "Change categories".

- **Protected change** — A modification requiring explicit user approval and (where applicable) a CHANGELOG entry. Applies to `core/memory/skills/`, `core/governance/` (except machine-generated state), `README.md`, and bulk operations. See `core/governance/update-guidelines.md`.

- **Proposed change** — A modification requiring user awareness but not necessarily explicit prior approval. Applies to new knowledge files, identity changes, quarantine promotion, plan creation or scope changes, restructuring, and retirement. See `core/governance/update-guidelines.md`.

- **Read-only operation** — Degraded mode where behavioral rules apply but writes are deferred (e.g. on platforms without write access). See `core/governance/update-guidelines.md` § "Read-only operation".

- **Deferred action** — A write action deferred due to read-only access. The agent describes what it would do and why, so the user or a future write-capable session can apply the change. See `core/governance/update-guidelines.md` § "How to communicate deferred actions".

- **Periodic review** — A scheduled audit of system health: checking trust decay, ACCESS anomalies, belief drift, governance rule fitness, and maturity stage signals. Orchestrated by `core/governance/security-signals.md` § "Periodic review" and triggered via MCP tools or manual session.

- **Review queue** — `core/governance/review-queue.md`. A staging area for pending system modification proposals, governance suggestions, and security flags awaiting human triage. See `core/governance/review-queue.md`.

## MCP tool surface

- **MCP (Model Context Protocol)** — The standardized protocol through which AI agents interact with Engram. The MCP server exposes governed tools for reading, searching, analyzing, and writing memory without each agent client reimplementing the repo's rules. See [MCP.md](MCP.md).

- **Tool tiers** — The three-level permission model for MCP tools. *Tier 0* (read-only): analytics, search, validation, session health — 43 tools, always available. *Tier 1* (semantic operations): governed knowledge promotion, plans, session recording, aggregation — 47 tools, always available. *Tier 2* (write primitives): low-level staged file mutations — 7 tools, gated behind the `MEMORY_ENABLE_RAW_WRITE_TOOLS` environment flag. See [MCP.md](MCP.md).

- **Governed preview** — The default write workflow: the MCP server returns a preview of the proposed change (diff, affected files, commit message) before committing. Allows the agent or user to review and approve before mutation. Supported by all Tier 1 semantic tools and Tier 2 write primitives.

- **Version token** — An opaque token returned with each file read, used to detect concurrent modifications. The agent passes the token back on write to prevent stale overwrites. See `core/tools/agent_memory_mcp/models.py`.

- **Staged transaction** — The Tier 2 write model: mutations (`memory_write`, `memory_edit`, `memory_delete`, `memory_move`) are staged in git's index without committing. The agent calls `memory_commit` to seal all staged changes as a single atomic commit. See [MCP.md](MCP.md).

- **Publication metadata** — Structured information returned by write operations: `commit_sha`, `commit_message`, `files_changed`, and operation-specific `new_state` fields. Eliminates the need for read-after-write. See `core/tools/agent_memory_mcp/models.py`.

- **Identity churn tracking** — Per-session rate-limiting on user trait updates. The MCP server tracks how many times `memory_update_user_trait` has been called in a session and raises an alarm after 5 updates, preventing rapid identity thrashing. See `core/tools/agent_memory_mcp/tools/semantic/_session.py`.

- **Delete permission hook** — An optional external helper (`MEMORY_DELETE_PERMISSION_HELPER` env var) invoked before `memory_delete` removes a file. A non-zero exit status blocks the deletion. See `core/tools/agent_memory_mcp/server.py`.

- **MCP resources** — Read-only data endpoints exposed alongside tools: `memory://capabilities/summary` (governed capability manifest), `memory://policy/summary` (current policy state), `memory://session/health` (maintenance status), and `memory://plans/active` (current plan state). See `core/tools/agent_memory_mcp/tools/read_tools/`.

- **MCP prompts** — Pre-built workflow templates: unverified review, governed promotion preview, periodic review preparation, and session wrap-up. Help agents execute complex multi-step workflows consistently. See `core/tools/agent_memory_mcp/tools/read_tools.py`.
