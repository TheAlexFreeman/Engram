---
type: summary
domain: software-engineering
scope: ai-engineering
---

# AI Engineering

Practitioner-focused knowledge on working with AI coding agents — prompt patterns, workflows, quality assurance, tool configuration, and trajectory. Theory and research on AI architectures, history, and frontier models lives in `knowledge/ai/`; these files cover the practical software-engineering angle.

## Files

### Workflow & Patterns

| File | Coverage |
|------|----------|
| [prompt-engineering-for-code.md](prompt-engineering-for-code.md) | Structured prompting (zero/few-shot, CoT), system prompt design, code-specific patterns, context loading, anti-patterns, model-specific tips |
| [ai-assisted-development-workflows.md](ai-assisted-development-workflows.md) | When to delegate vs. hand-code, workflow patterns (generate-then-edit, spec-first, test-driven AI), pair programming, IDE integration, task decomposition |
| [context-window-management.md](context-window-management.md) | Context window limits, loading strategies, RAG for codebases, cost/latency tradeoffs, token budgets, MCP tool-based context |

### Quality & Verification

| File | Coverage |
|------|----------|
| [ai-code-review-and-quality.md](ai-code-review-and-quality.md) | Failure modes of AI code, review checklist, testing strategies (property-based, mutation), hallucination detection, trust calibration, CI/CD gates |

### Tooling & Configuration

| File | Coverage |
|------|----------|
| [agent-configuration-and-tooling.md](agent-configuration-and-tooling.md) | VS Code Copilot config, MCP server setup, Cursor/Windsurf/CLI agents, custom tool design, agent memory, multi-agent workflows |

### Trajectory

| File | Coverage |
|------|----------|
| [ai-engineering-trajectory.md](ai-engineering-trajectory.md) | Capability growth curve, 2026–2028 trajectory, agent reliability, emerging patterns, risks (skill atrophy, monoculture), what to invest in |

## Cross-References

These files link to and are referenced by:
- `ai/tools/ai-tools-landscape-2026.md` — Industry tools survey (Cursor, Copilot, Windsurf, CLI agents)
- `ai/tools/mcp/mcp-server-design-patterns.md` — MCP protocol design patterns
- `ai/tools/mcp/mcp-protocol-overview.md` — MCP architecture and primitives
- `ai/frontier/agentic-frameworks.md` — LangGraph, CrewAI, AutoGen theory
- `ai/frontier/multi-agent/agent-architecture-patterns.md` — ReAct, Plan-and-execute, Reflexion
- `ai/frontier/retrieval-memory/rag-architecture.md` — RAG design patterns
- `ai/frontier/inference-time-compute.md` — Test-time compute scaling
- `ai/tools/agent-memory-in-ai-ecosystem.md` — Memory system positioning
- `testing/behavioral-testing-and-red-teaming.md` — Prompt injection testing, adversarial methods
- `testing/ml-evaluation-methodology.md` — LLM evaluation, benchmark contamination
