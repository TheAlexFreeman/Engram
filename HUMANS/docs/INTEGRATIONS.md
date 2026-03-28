# Third-Party Integrations

Ecosystem tools that complement the Engram memory system — what role each fills, and how you would wire them in.

- If you want worktree deployment and CI/tooling setup, read [WORKTREE.md](WORKTREE.md).
- If you want the MCP tool surface explained, read [MCP.md](MCP.md).
- If you want standalone setup, read [QUICKSTART.md](QUICKSTART.md).
- If something breaks, read [HELP.md](HELP.md).

Engram's file-first, Markdown-native design makes it straightforward to layer additional tools on top of the memory store. The categories below outline ecosystem tools that complement the system, what role each fills, and how you would wire them in.

## Semantic retrieval — vector search

Engram currently relies on keyword search and git-backed file reads. Adding a vector index lets agents perform similarity search over knowledge files, activity logs, and session summaries.

| Tool | Why it fits | Integration sketch |
|---|---|---|
| **LanceDB** | Embedded, zero-server vector store; stores on disk alongside the repo. | Index Markdown files into a Lance table at commit time or via a post-write hook. Query with cosine similarity from a thin MCP tool wrapper. |
| **ChromaDB** | Lightweight embedded vector DB with built-in sentence-transformer support. | Run as a sidecar or in-process. Sync `core/memory/knowledge/` into a Chroma collection; expose a `memory_semantic_search` MCP tool. |
| **Qdrant** | Production-grade vector search with filtering, sparse vectors, and multi-tenancy. | Deploy as a local Docker container or use Qdrant Cloud. Point a sync job at the knowledge tree; query via the Qdrant REST or gRPC client. |
| **Turbopuffer** | Serverless vector DB with automatic scaling and low cold-start latency. | Good fit if you want managed infrastructure. Use the HTTP API for upserts on commit and queries from MCP. |

**Embedding models.** Any of these vector stores pairs well with a local embedding model. Ollama can serve `nomic-embed-text` or `mxbai-embed-large` for fully offline embeddings. Alternatively, `sentence-transformers` provides a Python-native option (`all-MiniLM-L6-v2` is a good default).

## Knowledge graphs

Graph databases capture relationships between entities that flat files lose. They are valuable when the knowledge base grows beyond what sequential Markdown links can convey.

| Tool | Why it fits | Integration sketch |
|---|---|---|
| **Neo4j** | Mature graph DB with Cypher query language; strong ecosystem. | Model knowledge topics, users, plans, and relationships as nodes and edges. Populate on commit or via periodic sync. Expose a `memory_graph_query` MCP tool for Cypher queries. |
| **FalkorDB** | Redis-compatible graph DB optimized for low-latency graph traversal. | Lightweight alternative to Neo4j for smaller deployments or when Redis is already in the stack. |
| **Microsoft GraphRAG** | Builds a hierarchical community-summary graph from unstructured text, then answers questions over the graph. | Run the GraphRAG indexer on `core/memory/knowledge/` to produce community summaries. Query the graph for high-level synthesis ("What are the main themes across all knowledge files?"). |

## Observability and evaluation

As agents interact with the memory system, you want visibility into what tools they call, how long operations take, what knowledge they retrieve, and whether the governed-write pipeline is working correctly.

| Tool | Why it fits | Integration sketch |
|---|---|---|
| **LangFuse** | Open-source LLM observability: traces, cost tracking, prompt versioning, evaluation datasets. Self-hostable. | Instrument MCP tool calls as LangFuse spans. Tag each span with the tool name, maturity tier, and success/failure. Use the dashboard to spot expensive or failing patterns. |
| **LangSmith** | Managed observability from LangChain. Similar trace/eval surface, tighter LangChain integration. | Same instrumentation approach. Better fit if you already use LangChain or LangGraph for orchestration. |
| **Weights & Biases Weave** | Trace-based evaluation with built-in leaderboard and dataset management. | Wrap MCP tool dispatch in Weave `@op` decorators. Compare tool-call quality across model versions. |

## Agent orchestration and scheduling

If you run multi-agent workflows or need periodic maintenance tasks (aggregation, freshness checks, promotion sweeps), a scheduler or orchestrator can drive those cycles.

| Tool | Why it fits | Integration sketch |
|---|---|---|
| **Temporal** | Durable workflow engine: retries, timeouts, versioning, visibility. | Define workflows for periodic review, knowledge promotion, and aggregation. Activities call MCP tools. Temporal handles retry and scheduling. |
| **Inngest** | Event-driven step functions with built-in cron triggers. | Similar to Temporal but lower operational overhead. Define a cron function for `memory_run_periodic_review` and `memory_check_knowledge_freshness`. |
| **n8n** | Visual workflow automation with 400+ integrations. Self-hostable. | Build a workflow that triggers on git push to the memory branch, runs freshness checks, and posts results to Slack or a dashboard. |
| **Activepieces** | Open-source alternative to n8n with a code-first option. | Same pattern: event-driven or cron-triggered workflows that call MCP tools via HTTP or subprocess. |

## Multi-agent frameworks

If you run multiple agents that share the same memory store, these frameworks provide coordination primitives.

| Tool | Why it fits | Integration sketch |
|---|---|---|
| **CrewAI** | Role-based multi-agent system with task delegation. | Give each crew member an MCP tool handle. Use Engram as the shared long-term memory while CrewAI manages short-term task state. |
| **LangGraph** | Graph-based agent orchestration from LangChain. Supports cycles, persistence, and human-in-the-loop. | Model the governed-write pipeline as a LangGraph graph. Nodes call MCP tools; edges encode maturity transitions. |
| **AutoGen** | Microsoft's multi-agent conversation framework. | Register MCP tools as AutoGen functions. Use Engram for cross-session persistence; AutoGen handles intra-session message passing. |

## RAG and memory-augmented frameworks

These frameworks specialize in retrieval-augmented generation and can treat Engram as their backing store.

| Tool | Why it fits | Integration sketch |
|---|---|---|
| **LlamaIndex** | Comprehensive RAG framework with document loaders, index types, and query engines. | Use the Markdown reader to ingest `core/memory/knowledge/`. Build a vector index or knowledge-graph index. Expose as a query tool inside MCP. |
| **Letta (MemGPT)** | Adds tiered memory (core, recall, archival) to LLM agents. | Map Letta's archival memory to Engram's knowledge tree. Use Letta for conversation-window management; Engram for durable storage. |
| **Cognee** | Builds a knowledge graph from documents with automatic entity extraction and relationship mapping. | Run Cognee's pipeline on the knowledge tree to extract entities and relationships, then expose the resulting graph for agent queries. |

## External ingestion workflow

Engram now includes a governed external-intake path for research artifacts and fetched context. The workflow is intentionally simple:

1. `memory_plan_execute` and `memory_plan_briefing` can surface `fetch_directives` and `mcp_calls` when a phase references `type: external` or `type: mcp` sources that are still missing on disk.
2. An agent fetches the content externally, then calls `memory_stage_external` to place it in `memory/working/projects/{project}/IN/` with enforced `source: external-research`, `trust: low`, sanitized `origin_url`, and per-project SHA-256 deduplication.
3. For local research inboxes, `memory_scan_drop_zone` reads `[[watch_folders]]` entries from `agent-bootstrap.toml` and bulk-stages supported `.md`, `.txt`, and optional `.pdf` inputs into the same project inbox path.
4. Once staged content has been reviewed and distilled, the existing knowledge-promotion flow can move the durable result into `_unverified/` or a verified knowledge domain.

Example watch-folder configuration:

```toml
[[watch_folders]]
path = "C:/Users/example/research-inbox"
target_project = "harness-expansion"
source_label = "local-research-inbox"
extensions = [".md", ".txt", ".pdf"]
recursive = false
```

This preserves the same governance boundary as the rest of the system: external systems may fetch, index, or prepare data, but durable Markdown intake still flows through repo-owned MCP semantics rather than ad hoc file mutation.

## Developer workflow tools

| Tool | Why it fits | Integration sketch |
|---|---|---|
| **Aider** | CLI-based coding assistant that works with git. | Point Aider at the host repo while Engram runs as a worktree sidecar. Aider handles code edits; the memory agent records what was learned. |
| **Raycast AI** | macOS launcher with AI commands and clipboard history. | Build a Raycast extension that queries the MCP server for knowledge lookups, plan status, or quick session notes without leaving the keyboard. |

## Recommended starting points

If you are deciding where to begin, these four integrations offer the highest value relative to setup cost:

1. **LanceDB + Ollama embeddings.** Adds semantic search with zero external dependencies. Both run locally, store on disk, and need no API keys. Start by indexing `core/memory/knowledge/` into a Lance table and exposing a `memory_semantic_search` tool.

2. **LangFuse.** Self-host with Docker Compose, instrument MCP tool dispatch, and get immediate visibility into how agents use the memory system. Helps validate that governance rules are working.

3. **Temporal.** Ideal once you have recurring maintenance tasks like periodic reviews, promotion sweeps, or freshness checks. Handles retry, scheduling, and workflow versioning so you do not have to build those primitives from scratch.

4. **GraphRAG.** High value once the knowledge base is large enough that flat search misses cross-topic connections. The community-summary approach produces synthesis that neither keyword search nor vector search can replicate.

## General wiring pattern

Most third-party integrations follow the same shape:

1. **Sync layer.** Watch for file changes in the memory store (git hooks, file-system watcher, or periodic poll) and push updates into the external system (vector index, graph, event bus).
2. **Query layer.** Expose the external system's query capability as one or more MCP tools so agents can use it during sessions.
3. **Governance boundary.** Keep Engram as the single governed writer for Markdown files. External systems are read-only consumers of the memory store, or they write back through the MCP governed-write pipeline — never by direct file mutation.

For the full MCP tool surface available once the server is running, see [MCP.md](MCP.md).
