# MCP Architecture Guide

This document explains the Model Context Protocol (MCP) layer in this repository: what it exposes, why it exists, and how it fits the larger design of the system.

- If you want a quick setup path, read [QUICKSTART.md](QUICKSTART.md).
- If you want the big-picture system rationale, read [CORE.md](CORE.md).
- If you want broader product philosophy and future directions, read [DESIGN.md](DESIGN.md).
- If you want integration patterns across external frameworks, read [INTEGRATIONS.md](INTEGRATIONS.md).

## What the MCP layer is

The MCP layer is the repo's tool-facing interface.

The memory system's source of truth is still the Git repository itself: Markdown files, summaries, governance files, and Git history. MCP does not replace that file-based design. It packages the same system behind a cleaner contract so tool-using clients can read memory, inspect provenance, and perform governed writes without each client reimplementing the repo's rules.

In plain language:

- The repo is the memory.
- Git is the history and recovery mechanism.
- MCP is the safe operating interface.

The default architectural entry point for a new session remains `README.md`. After that initial orientation, `core/INIT.md` handles live routing and `core/memory/working/projects/SUMMARY.md` is the primary orientation surface for a normal returning session unless the router points somewhere more specific.

That separation is intentional. It keeps the system portable and inspectable while still making it ergonomic for modern agent runtimes.

## Available MCP resources

These are the main files and entry points that define the MCP setup.

| Resource | Role | Why it matters |
| --- | --- | --- |
| `core/tools/memory_mcp.py` | Compatibility entrypoint script | The simplest path-based way to launch the repo-local MCP server. |
| `core/tools/agent_memory_mcp/server.py` | Runtime bootstrap | Builds the FastMCP server, resolves the repo root, and registers tools. |
| `HUMANS/tooling/agent-memory-capabilities.toml` | Capability manifest | Declares what the MCP surface supports, how clients should interpret it, and which approval rules apply. |
| `HUMANS/tooling/mcp-config-example.json` | Example client config | Shows how a desktop MCP client can point at this repo. |
| `core/tools/agent_memory_mcp/tools/read_tools.py` | Tier 0 read tools | Read, inspect, audit, and report on the memory repo without mutating it. |
| `core/tools/agent_memory_mcp/tools/semantic/` | Tier 1 semantic tools | The semantic package is the stable Tier 1 surface, split by domain so governed write operations keep their own invariants and auto-commit behavior without a monolithic module. |
| `core/tools/agent_memory_mcp/tools/write_tools.py` | Tier 2 raw fallback tools | Low-level staged mutation tools used only when the runtime explicitly enables raw fallback. |

## How the server is launched

The canonical path-based script is:

```bash
python core/tools/memory_mcp.py
```

That wrapper imports the repo-local server and runs it. When the package is
installed, prefer `engram-mcp` instead.

### How the repo root is resolved

The runtime supports three ways to find the memory repository:

1. An explicit `repo_root` argument when embedding the server from Python.
2. The `MEMORY_REPO_ROOT` environment variable.
3. The `AGENT_MEMORY_ROOT` environment variable.

If none of those are set, the runtime falls back to file-relative detection from the installed server code.

### Practical setup patterns

**Run it from the repo itself**

```bash
cd Engram
python core/tools/memory_mcp.py
```

**Run it from somewhere else**

```bash
MEMORY_REPO_ROOT=/path/to/Engram python /path/to/Engram/core/tools/memory_mcp.py
```

**Embed it in Python**

```python
from engram_mcp.agent_memory_mcp.server import create_mcp

mcp, tools, root, repo = create_mcp(repo_root="/path/to/Engram")
```

### Concrete client example: Claude Desktop

The repo already includes an example client config in `HUMANS/tooling/mcp-config-example.json`. A minimal configuration looks like this:

```json
{
	"mcpServers": {
		"agent-memory": {
			"command": "python",
				"args": ["C:/path/to/Engram/core/tools/memory_mcp.py"],
			"env": {
				"AGENT_MEMORY_ROOT": "C:/path/to/Engram"
			}
		}
	}
}
```

What this does:

- launches the repo-local MCP wrapper script,
- tells the runtime which memory repo to operate on,
- lets the desktop client discover the governed tool surface from the server and capability manifest.

In practice, this is the easiest way to think about the setup: the client owns the UI and approval flow, while the repo-local server owns the repo-specific behavior.

## Tool surface at a glance

The manifest organizes the MCP surface into three layers.

### Tier 0: Read support

These tools inspect or analyze the repo without changing it.

**Core file and repo inspection**

- `memory_get_capabilities`
- `memory_read_file`
- `memory_list_folder`
- `memory_search`
- `memory_check_cross_references`
- `memory_generate_summary`
- `memory_access_analytics`
- `memory_diff_branch`
- `memory_git_log`
- `memory_diff`
- `memory_validate`
- `memory_audit_trust`
- `memory_get_maturity_signals`
- `memory_reset_session_state`

**Maintenance and governance analysis**

- `memory_session_health_check`
- `memory_check_knowledge_freshness`
- `memory_check_aggregation_triggers`
- `memory_aggregate_access`
- `memory_run_periodic_review`
- `memory_get_file_provenance`
- `memory_inspect_commit`
- `memory_list_plans`

This read-first layer is a major design choice. The system prefers inspection, reporting, and explicit review before protected state changes.

### Tier 1: Semantic write tools

These are the normal write path. Each tool represents a bounded operation with built-in invariants and an automatic commit on success.

**Plans**

- `memory_plan_create`
- `memory_plan_execute`
- `memory_plan_review`

**Knowledge lifecycle**

- `memory_add_knowledge_file`
- `memory_promote_knowledge_batch`
- `memory_promote_knowledge`
- `memory_demote_knowledge`
- `memory_archive_knowledge`

**Scratchpad, skills, and identity**

- `memory_append_scratchpad`
- `memory_update_skill`
- `memory_update_identity_trait`

**Chats and session logging**

- `memory_record_session`
- `memory_run_aggregation`
- `memory_record_chat_summary`
- `memory_record_reflection`
- `memory_log_access`
- `memory_log_access_batch`

**Governance and safety operations**

- `memory_flag_for_review`
- `memory_resolve_review_item`
- `memory_record_periodic_review`
- `memory_revert_commit`

The important point is that these are not generic file-edit tools wearing a nicer label. Each one owns a narrow slice of the memory model and is responsible for keeping related files in sync.

### Tier 2: Raw fallback tools

These are low-level mutation tools:

- `memory_write`
- `memory_edit`
- `memory_delete`
- `memory_move`
- `memory_update_frontmatter`
- `memory_update_frontmatter_bulk`
- `memory_commit`

They stage changes but do not auto-commit. They also reject protected directories such as `memory/users/`, `governance/`, `memory/activity/`, and `memory/skills/`.

Most importantly, they are **not enabled by default**. The server only exposes them when the runtime explicitly sets:

```text
MEMORY_ENABLE_RAW_WRITE_TOOLS=1
```

This keeps the normal MCP experience semantic and governed, while still leaving a controlled fallback path available for runtimes that genuinely need it.

## The manifest is a first-class part of the architecture

The file `HUMANS/tooling/agent-memory-capabilities.toml` is not just documentation. It is part of the runtime contract.

It tells a client:

- which tools exist,
- whether the runtime is read-only or semantic-capable,
- which operations are automatic, proposed, or protected,
- which files each semantic operation is allowed to own,
- how previews and approvals should work,
- how results should be presented,
- which fallback behavior is acceptable.

This matters because the system is deliberately hybrid. The desktop or host application is expected to discover capabilities and enforce approval UX, while the repo-local MCP server is expected to execute the repo-specific logic correctly.

The manifest makes that split explicit instead of relying on undocumented conventions.

## Key design principles of the MCP architecture

### 1. The repo stays canonical

The MCP layer is an interface, not a second storage system.

That preserves the project's core bet: memory should live in files the user owns, can diff, can back up, and can move across tools. MCP improves access; it does not become the source of truth.

### 2. Semantic operations come before raw edits

The preferred path is always a named operation that understands the memory model.

For example, recording a periodic review is not treated as an arbitrary edit to `governance/` files. It is a specific semantic action with bounded ownership, protected approval, expected commit metadata, and known result fields.

This reduces the chance of partial updates, broken invariants, or accidental policy drift.

### 3. Approval boundaries are part of the protocol

The MCP surface classifies writes as:

- `automatic`
- `proposed`
- `protected`

That mirrors the broader governance model of the repo. Routine bounded updates can happen automatically. Durable or identity-shaping changes require user awareness. Protected system surfaces require explicit approval.

In other words, safety is not left to prompt wording alone. It is encoded in the operation model.

### 4. Responsibility is split cleanly

The manifest defines a hybrid boundary:

- The host client owns approval UX, capability discovery, preview rendering, and fallback selection.
- The repo-local MCP server owns semantic execution, repo-specific invariants, schema validation, and authoritative mutation.

This is a strong architectural choice. It prevents the client from needing to understand every repo rule while also preventing the repo server from trying to be a full user interface.

### 5. Git is the publication layer

The server does not merely edit files. Governed semantic tools publish changes through Git and return structured publication metadata.

That fits the larger system philosophy:

- memory changes should be reviewable,
- provenance should be inspectable,
- commits should be attributable,
- reverts should be possible.

The MCP layer exists partly to make those guarantees easier to preserve across clients.

### 6. Degradation is deliberate

The architecture distinguishes among:

- full semantic MCP,
- read-only governed preview,
- raw fallback or defer.

That is consistent with the rest of the system, which is designed to degrade gracefully instead of pretending unavailable capabilities worked. If the runtime cannot safely perform a governed write, it should preview, defer, or report the block honestly.

### 7. Read-first governance is intentional

The recent MCP expansion added more analysis tools before adding more protected writes. That reflects the repo's deeper philosophy: governance should become more observable before it becomes more automated.

The system wants good inspection paths, provenance checks, periodic review reports, and maturity signals so that high-leverage writes remain understandable and auditable.

## How MCP fits the philosophy of the whole system

The MCP architecture is not a sidecar. It expresses the same design philosophy found throughout the repo.

### It supports portability without abandoning ergonomics

The whole system is built around model-agnostic, file-based memory. MCP makes that practical for tool-using runtimes by exposing the repo through a standard protocol, but the memory remains portable even without MCP.

That balance matters. A vendor-specific memory API would be convenient but would weaken the ownership and portability story. MCP gives interoperability without changing the core storage model.

### It reinforces transparency and human control

Human-readable files, Git history, capability manifests, approval classes, and structured write results all point in the same direction: the user should be able to understand what the system can do and what it just did.

This is the opposite of opaque built-in memory features that silently rewrite state behind the scenes.

### It matches the system's safety model

The wider design separates informational memory from procedural authority and places high-leverage surfaces behind tighter governance. The MCP layer reflects that exactly:

- protected directories are not open to raw writes,
- semantic tools are bounded by domain,
- approval classes are explicit,
- external or uncertain content is handled through constrained workflows,
- system-level review writes are narrow and protected.

### It helps with context efficiency

One purpose of MCP is to let runtimes ask targeted questions instead of loading large parts of the repo speculatively.

For example, a client can ask for maturity signals, provenance, or a periodic review report directly rather than reading several governance files and reconstructing the answer itself. That is aligned with the project's strong preference for progressive disclosure and metadata-first retrieval.

### It preserves graceful degradation

The broader system never assumes ideal capabilities. The MCP architecture follows the same rule by making read-only mode, deferred action, and fallback behavior part of the declared contract.

That makes the system more honest and more robust across different platforms.

## What the MCP layer is not

To keep expectations clear, the MCP server is not:

- a replacement for reading the repo's core documents,
- a full agent runtime,
- a hidden database behind the Markdown,
- permission to bypass governance,
- a general-purpose unrestricted file editor.

It is a structured interface over a governed Git-backed memory system.

## Recommended mental model

If you are evaluating the MCP setup, the simplest accurate mental model is:

1. The repository defines the memory model.
2. The manifest describes the operating contract.
3. The FastMCP server exposes that contract to clients.
4. Semantic tools enforce the repo's invariants.
5. Git records and publishes the resulting state.

That is why the MCP layer fits this project so naturally. It gives the repo a usable systems interface without giving up the project's core commitments: transparency, safety, portability, and human control.
