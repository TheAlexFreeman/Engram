---
source: agent-generated
origin_session: unknown
created: 2026-03-24
trust: medium
type: knowledge
domain: software-engineering
tags: [context-window, tokens, rag, chunking, retrieval, cost, performance]
related:
  - prompt-engineering-for-code.md
  - ../../ai/frontier/retrieval-memory/rag-architecture.md
  - ../../ai/tools/mcp/mcp-protocol-overview.md
---

# Context Window Management

How to get the right information into the model's context — strategies for loading, prioritizing, and budgeting tokens for code tasks.

## 1. Context Windows in Practice

Model context windows as of 2026:

| Model | Window | Practical sweet spot |
|-------|--------|---------------------|
| Claude Opus/Sonnet | 200K tokens | 30–80K for best quality |
| GPT-4o / o3 | 128K tokens | 20–60K for best quality |
| Gemini 2.5 | 1M tokens | 50–200K for best quality |
| Open-weight (Llama, Qwen) | 32–128K | 8–32K for best quality |

**The practical limit is always lower than the technical limit.** Quality degrades with context length — the model pays less attention to information in the middle of very long contexts ("lost in the middle" effect). For code tasks, aim for the minimum context that contains all relevant information.

A typical Python function is ~20–50 tokens. A 500-line file is ~2,000–4,000 tokens. A complex prompt with 10 relevant files and instructions can easily hit 30K tokens.

## 2. Context Loading Strategies

### Full File
Include the entire file being modified. Best for small-to-medium files (<500 lines) where the model needs to understand the full structure. For larger files, extract the relevant section plus imports and class signatures.

### Function-Level
Include only the function being modified plus its type signatures, docstring, and the imports it uses. Best for targeted edits in large files. Include the calling function if the change affects the interface.

### Dependency-Aware
Include the target code plus the interfaces it depends on — type definitions, abstract base classes, related model definitions, API schemas. This is the sweet spot for most code generation tasks: enough context to be correct, little enough to stay focused.

### Semantic Search
Use embeddings to find the most relevant code chunks across the entire codebase. Best for questions like "how do we handle authentication?" where the relevant code could be anywhere. Quality depends heavily on chunking strategy and embedding model.

### Progressive Disclosure
Start with minimal context. If the model asks questions or produces incorrect output, add more. This is the default behavior of most IDE-integrated agents — they read files as needed rather than pre-loading everything.

## 3. RAG for Codebases

Retrieval-augmented generation applies to code, but code has different properties than documents:

**Chunking strategies for code**:
- **Function/class level**: Parse the AST and chunk at function or class boundaries. Preserves semantic units. Better than sliding-window for code.
- **File level with overlap**: Include the full file as a chunk, with cross-references to imported modules. Simple but works well for small-to-medium codebases.
- **Dependency-graph chunking**: Chunk a function plus everything it directly imports. Expensive to compute but produces self-contained chunks.

**Embedding models**: Code-specific models (CodeBERT, StarCoder embeddings) outperform general-purpose models for code similarity. However, general models (text-embedding-3-large, Cohere v3) work acceptably for most tasks.

**Retrieval quality matters more than retrieval quantity**. Returning 20 irrelevant chunks degrades output more than returning 3 relevant ones. Use reranking and filter by file path, language, and recency.

## 4. Cost/Latency/Quality Tradeoffs

**Model selection by task**:
- Quick completions, boilerplate: smaller/faster model (Sonnet, GPT-4o-mini, Haiku)
- Complex reasoning, architecture: larger model (Opus, o3)
- Repetitive batch processing: cheapest model that maintains quality

**Caching**: If multiple prompts share the same system prompt or codebase context, use prompt caching (Claude's cache_control, OpenAI prompt caching). Reduces cost by 75–90% on repeated prefixes.

**Batching**: For bulk operations (adding logging to 50 functions), batch requests rather than sending 50 sequential prompts. Some APIs support batch endpoints with lower cost.

**Token budgets by use case**:
- Inline completion: 1–4K tokens total (fast, cheap)
- Chat question: 10–30K tokens (context + response)
- Agent task: 30–100K tokens over the task lifetime (tool calls accumulate)
- Complex refactor: 50–200K tokens (multi-file context + planning + execution)

## 5. Token Budget Management

When context is limited, prioritize what you include:

1. **High priority**: The code being modified, its direct dependencies, error messages, test output
2. **Medium priority**: Related code (similar functions, nearby modules), architecture overview, coding standards
3. **Low priority**: Full codebase tree, distant dependencies, historical context, documentation prose

**Summarization**: For large files, include a summary (function signatures + docstrings) rather than the full implementation. The model can request the full code if needed.

**Progressive context**: Start with the minimum context. If the output is wrong, add more targeted context rather than dumping everything. This is more efficient than front-loading a massive context.

**Conversation pruning**: In long conversations, summarize completed work and start fresh when the context window fills up. Don't let old context crowd out new, relevant information.

## 6. MCP and Tool-Based Context

MCP (Model Context Protocol) tools let the model pull context on demand rather than requiring everything upfront:

**Pre-loaded context** (include in prompt):
- The specific file being modified
- Error messages and test output
- Key type definitions and interfaces

**Tool-based context** (let the model fetch as needed):
- File contents it might need (via read_file tool)
- Search results across the codebase (via grep/semantic search tools)
- Documentation lookups
- Terminal command output

**When to pre-load vs. tool-fetch**: Pre-load when you know exactly what the model needs. Use tools when the model needs to explore — debugging, investigating unfamiliar code, or tasks where the relevant files aren't obvious upfront.

The overhead of a tool call is ~100–500 tokens for the call + response framing. For context you'll definitely need, pre-loading is more token-efficient. For context you might need, tools avoid waste.
