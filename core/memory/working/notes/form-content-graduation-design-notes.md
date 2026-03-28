---
created: 2026-03-28
source: agent-generated
trust: medium
origin_session: memory/activity/2026/03/28/chat-001
title: "Design Notes: Form/Content Graduation Pipeline"
---

# Form/Content Graduation Pipeline

Design conversation from 2026-03-28. Captures Alex's vision for how Engram content self-organizes into progressively more formal system structures.

## The graduation ladder

| Level | Expression | Flexibility | Efficiency | Example |
|---|---|---|---|---|
| **Data** | Markdown file in `activity/`, `knowledge/`, or `users/` | High — reinterpretable per context | Low — agent must find, read, reason | "Alex prefers TypeScript for new projects" |
| **Skill** | Markdown file in `skills/` | Medium — procedural but natural-language | Medium — agent follows steps but still interprets | session-wrapup.md |
| **MCP tool** | Python code in `tools/` | Low — deterministic, parameterized | High — single call, no interpretation overhead | memory_context_home |

Each transition is lossy compression: trading generality for efficiency and reliability. Maps to rate-distortion tradeoff.

## The self-organization loop

1. **Observation:** ACCESS tracking records which files are co-retrieved, which skills are invoked, which retrieval patterns recur
2. **Detection:** Curation algorithms (Phase 3 co-retrieval clusters) identify stable task clusters
3. **Proposal:** System proposes a new skill based on detected cluster (pending — skill-auto-discovery not yet built)
4. **Validation:** User reviews, edits, approves the skill (existing governance: protected-tier change)
5. **Hardening:** Frequently invoked skills with stable parameter patterns are candidates for MCP tool promotion (future — tool composition not yet built)

## Speciation and horizontal transfer

- **Speciation:** Each Engram instance develops its own skills and tools from usage patterns. Git branches enable divergence. Same base architecture, different specialized surfaces.
- **Horizontal transfer:** Skills (natural language) are portable between branches. Import via `_unverified/` at `trust: low`. Provenance and trust system = immune system for safe intake.
- **Compatibility check needed:** Does imported skill's trigger overlap existing skills? Does it reference tools/knowledge that exist locally?

## Key design tensions

- **Stability detection vs. premature hardening:** Not all recurring patterns should be formalized. Some content is valuable because it remains fluid and reinterpretable. Reconsolidation analogy: accessed memories become labile, open to reinterpretation. A tool loses that lability.
- **Graduation should be reversible:** Tools that stop being useful should be demotable back to skills, then to knowledge. Temporal decay and maturity stages may provide the machinery, but need to extend to the tool layer.
- **Meta-overhead vs. actual work:** OpenClaw's failure mode — systems that become so complex in self-management that meta-overhead dominates. Context efficiency as first-class constraint is the defense.
- **Code generation safety:** MCP tool graduation means generating or composing executable code. Composition of existing primitives (deterministic) is safer than generation (non-deterministic). Prefer: detect stable skill → compose existing tool calls → register composite tool.

## Prerequisites for the full pipeline

1. **Context injectors** (in progress) — formalize the most common routing patterns
2. **Skill auto-discovery** — the linchpin; without it, graduation is manual
3. **Tool composition framework** — register composite tools from skill patterns
4. **Reversible promotion/demotion** — extend temporal decay to tool layer

## Alex's framing

> "Allowing system 'content' to graduate into new aspects of its 'form' will allow for something like speciation across git branches but with rich potential for horizontal transfer of knowledge, skills, and even MCP tools."

Core philosophical motivation: natural language as shared knowledge substrate for human/LLM collaboration. Inspired by production agent instruction tuning and structural-functional organization of codebases. Context management as its own dedicated layer.
