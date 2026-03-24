---
source: agent-generated
origin_session: unknown
created: 2026-03-24
trust: medium
type: knowledge
domain: software-engineering
tags: [agent-config, mcp, copilot, cursor, instructions, customization, tools]
related:
  - ai-assisted-development-workflows.md
  - ../../ai/tools/mcp/mcp-server-design-patterns.md
  - ../../ai/tools/ai-tools-landscape-2026.md
  - ../../ai/frontier/agentic-frameworks.md
---

# Agent Configuration and Tooling

How to configure AI coding agents for maximum effectiveness — instruction files, MCP servers, custom tools, and multi-agent patterns.

## 1. VS Code Copilot Configuration

VS Code Copilot supports layered customization:

**Instruction files** (`.instructions.md`): Markdown files with YAML frontmatter that provide persistent context to the agent. Placed anywhere in the workspace.
```yaml
---
applyTo: "**/*.py"
---
Use Django 6.0 patterns. Prefer class-based views.
Always include type annotations.
```

**Custom agents** (`.agent.md`): Define specialized agent modes with specific tool access, instructions, and descriptions. Used for recurring workflows — "tester" agent that only runs tests, "reviewer" agent that reads but doesn't edit.

**Skills** (`SKILL.md`): Reusable knowledge packages that agents load when relevant. Include domain expertise, workflow instructions, and quality criteria. Skills are activated based on task matching.

**Prompt files** (`.prompt.md`): Reusable prompt templates for common tasks. Can include variable placeholders filled at invocation time.

**Layering**: Instructions stack — global `copilot-instructions.md` applies everywhere, folder-level `.instructions.md` adds specificity, and skill files add domain knowledge. More specific overrides less specific.

## 2. MCP Server Setup

Model Context Protocol servers extend agent capabilities with custom tools:

**Common development MCP servers**:
- **File system**: Read/write/search files in the workspace and beyond
- **Git**: Commit, diff, branch, log operations
- **Database**: Query databases, inspect schemas
- **Memory**: Persistent knowledge across sessions (this repository is one such system)
- **Web**: Fetch documentation, API references

**Configuration** (VS Code `settings.json`):
```json
{
  "mcp": {
    "servers": {
      "memory": {
        "command": "python",
        "args": ["-m", "agent_memory_mcp"],
        "env": { "MEMORY_ROOT": "/path/to/engram" }
      }
    }
  }
}
```

**Transport options**: stdio (local, simple, default), SSE/HTTP (remote, shared), streamable-HTTP (newer, more capable). For development use, stdio is simplest.

**Security**: MCP servers run with the user's permissions. Audit what tools you expose — a file-write tool with no path restrictions is equivalent to giving the agent full system access. Use path policies and allowlists.

## 3. Cursor/Windsurf/CLI Agent Configuration

**Cursor rules** (`.cursorrules`): Plain text file in project root with coding conventions, architecture notes, and style preferences. Similar to Copilot's instruction files but simpler format.

**Windsurf cascade**: Uses `.windsurfrules` files. Supports knowledge graphs and workspace indexing for context retrieval.

**Claude CLI / Codex CLI**: Terminal-based agents configured via `CLAUDE.md` or similar files in the project root. These agents excel at multi-step tasks: read code → run tests → fix failures → verify.

**Cross-tool strategy**: Use a single source of truth for coding conventions (e.g., an `AGENTS.md` or `CONVENTIONS.md` file) and reference it from each tool's config file. This prevents drift between tools.

## 4. Custom Tool Design

When to build an MCP tool vs. use existing ones:

**Build a custom tool when**:
- You have a repetitive workflow that involves multiple steps (deploy, check status, rollback)
- You need domain-specific context the model can't get from general tools (internal API docs, proprietary schema)
- You want to enforce guardrails (read-only database access, path-restricted file access)

**Use existing tools when**:
- Standard file/git/terminal operations suffice
- The task is a common pattern already covered by community MCP servers

**Tool design principles**:
- **Single responsibility**: One tool does one thing well. `read_file` and `write_file`, not `manage_file`.
- **Clear input schemas**: Define exact parameter types, descriptions, and constraints. The model uses these to decide when and how to call tools.
- **Useful error messages**: When a tool fails, return enough information for the model to self-correct. "File not found: /path/to/file.py" is better than "Error."
- **Idempotent when possible**: Tools that can be safely retried reduce error recovery complexity.

## 5. Agent Memory and Persistence

Effective agents need knowledge that persists across sessions:

**Session context**: What's been discussed, decided, and modified in the current conversation. Most agents maintain this automatically via conversation history.

**Project knowledge**: Architecture decisions, coding conventions, common patterns, known gotchas. Stored in instruction files, documentation, or dedicated memory systems.

**Cross-session learning**: Agents that remember past interactions, user preferences, and common mistakes. Implementations range from simple note files to structured knowledge bases (like this Engram system) to vector-store RAG.

**Memory hierarchy** (from most to least persistent):
1. Repository documentation (README, architecture docs) — permanent
2. Instruction/rules files — semi-permanent, version-controlled
3. Memory system knowledge files — curated, evolving
4. Session notes — conversation-scoped
5. Conversation context — ephemeral

The most effective setup feeds all relevant layers to the agent at the right time.

## 6. Multi-Agent Workflows

Multiple agents can collaborate on complex tasks:

**Orchestrator-subagent**: A primary agent decomposes the task and delegates subtasks to specialized subagents. The orchestrator maintains overall coherence while subagents handle isolated, bounded work. Example: main agent plans a feature, spawns "Explore" subagents for codebase research, then implements.

**Parallel exploration**: Launch multiple read-only agents simultaneously to gather information from different parts of the codebase. Merge their findings before proceeding with implementation. Safe because read-only operations can't conflict.

**Handoff protocols**: When one agent completes its portion, it returns a structured summary that becomes context for the next agent. Clean handoffs prevent context loss at boundaries.

**When not to use multi-agent**: Simple tasks, short conversations, tasks where maintaining a single coherent mental model matters more than parallelism. Multi-agent adds coordination overhead.
