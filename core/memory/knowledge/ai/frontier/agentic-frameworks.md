---
created: 2026-03-20
domain: ai/frontier
last_verified: '2026-03-21'
origin_session: core/memory/activity/2026/03/20/chat-001
related: knowledge/ai/frontier/multi-agent/multi-agent-coordination.md, ../../software-engineering/ai-engineering/ai-assisted-development-workflows.md
source: external-research
tags:
- agentic-ai
- frameworks
- langgraph
- crewai
- autogen
- llamaindex
- orchestration
- multi-agent
trust: medium
type: knowledge
---

# Agentic Frameworks: Architecture, Tradeoffs, and Production Realities

The agentic framework landscape crystallized in 2024-2025 around a small set of
dominant abstractions, each encoding different assumptions about how agents should
be structured, how state should flow, and who (if anyone) should be in the loop.
Choosing a framework is effectively choosing a theory of agent architecture —
and the right choice depends entirely on which failure modes you most want to avoid.

---

## The core abstraction families

The current generation of agentic frameworks divides along two axes: **how
control flows** (graph-structured vs. conversational vs. role-based) and **how
state is managed** (explicit vs. emergent vs. shared memory). Most frameworks
combine one approach from each axis.

### LangGraph — graph-structured control, explicit state

LangGraph (LangChain's orchestration layer, v1.0 late 2025) represents agent
workflows as directed graphs: nodes are actions or LLM calls, edges are control
flow (including conditional routing). State is a typed object passed through
the graph; each node receives it and returns a modified version.

**What this buys you:** Traceability. Every execution path through the graph is
inspectable. State changes are explicit and logged. You can serialize mid-execution
state and resume after failures. Human-in-the-loop (HITL) is a first-class
operation — you interrupt at any node, inspect the state object, modify it, and
resume. This makes LangGraph the framework of choice for production systems where
correctness and debuggability matter more than development speed.

**What it costs:** Verbosity. Complex branching logic requires explicit graph
construction, which is more work than describing a task in natural language.
LangGraph rewards teams with clear execution requirements; it punishes
exploratory prototyping with boilerplate.

**Architecture note:** LangGraph became the default runtime for all LangChain
agents in late 2025. It integrates with LangSmith for tracing and is the
most production-deployed of the options. `47M+ PyPI downloads` as of early 2026.

### CrewAI — role-based coordination, shared memory

CrewAI models agent systems as *crews*: collections of named agents with defined
roles, backstories, and tool access, coordinated by a crew-level task assignment
system. Agents communicate via structured outputs; the crew orchestrator routes
tasks and aggregates results.

**What this buys you:** Legibility. A crew specification reads like an org chart.
Non-engineers can understand and modify crew definitions. For workflows with stable
role specialization — customer support escalation, content pipeline (researcher →
writer → editor), code review (generator → reviewer → approver) — CrewAI
dramatically reduces coordination boilerplate.

**What it costs:** Token overhead. CrewAI's coordination layer is verbose;
benchmarks show ~3× the token consumption of LangGraph for equivalent tasks,
with ~3× the latency. This is the cost of the managerial abstraction. CrewAI
also has limited support for truly dynamic workflows where task structure isn't
known at crew-definition time.

**Architecture note:** CrewAI has grown fastest in the multi-agent enterprise
segment and offers a paid control plane with observability. Best suited for
workflows with clear role specialization.

### AutoGen — conversational coordination, event-driven state

Microsoft Research's AutoGen frames everything as asynchronous message-passing
between specialized agents. Each agent is a participant in a conversation; the
orchestrator is just another participant that routes messages. State is carried
implicitly in the conversation history rather than in an explicit typed object.

**What this buys you:** Flexibility and concurrency. Because agents communicate
asynchronously, long-running tasks don't block the system. The `UserProxyAgent`
pattern makes HITL feel natural — the human is literally a conversation participant.
Dynamic task decomposition is easy because there's no graph to predeclare.

**What it costs:** Observability. Emergent state from conversation history is
harder to inspect than an explicit state object. Reproducing a specific execution
requires replaying the full message history. Production debugging is more
demanding than with LangGraph.

**Architecture note:** AutoGen v0.4 (late 2024) shifted to a fully async,
event-driven model. It is now "AutoGen Core" with layered APIs. Best for:
research agents, coding assistants, and workflows where agents need to wait on
external events without blocking.

### OpenAI Agents SDK — native integration, minimal abstraction

Released in March 2025, the OpenAI Agents SDK provides the lowest-friction path
to production agents using OpenAI models. Core abstractions: `Agent` (role +
tools + instructions), `Handoffs` (agent-to-agent delegation), `Guardrails`
(input/output validation). The SDK manages the agent loop internally.

**What this buys you:** The easiest onboarding and tightest integration with
OpenAI's platform — Responses API, function calling, vector stores, file search.
For teams already on OpenAI infrastructure, it is the lowest-complexity option.

**What it costs:** Provider lock-in. The SDK is designed around OpenAI's tool
calling format and is not easily adapted to other model providers. The
abstraction level is also lower than LangGraph or CrewAI — you get a runtime,
not an orchestration framework.

### LlamaIndex — retrieval-first, RAG-native agents

LlamaIndex occupies a distinct niche: it is primarily a data framework (indexing,
retrieval, query pipelines) with an agent layer on top. Its `QueryEngineTool`
pattern wraps retrieval systems as agent-accessible tools. Most useful when
the dominant agent action is querying structured or unstructured data rather than
executing code or managing multi-step workflows.

**What this buys you:** The richest RAG integration of any framework. Chunking
strategies, hybrid retrieval, re-ranking, and metadata filtering are all
first-class concerns.

**What it costs:** The agent orchestration story is weaker than LangGraph or
AutoGen. For pure retrieval workflows it is excellent; for complex multi-step
agents it is typically used as a tool provider to a LangGraph orchestrator.

---

## Architectural patterns across frameworks

### The orchestrator/subagent pattern

The most common production architecture pairs LangGraph (or the OpenAI SDK)
as an orchestrator with domain-specific agents — sometimes CrewAI crews,
sometimes AutoGen conversations — handling subtasks. The orchestrator maintains
the typed state graph and makes routing decisions; subagents are invoked as
nodes and return typed outputs.

This composition leverages each framework's strengths: LangGraph's traceability
for overall system state, CrewAI's role legibility for domain-specific pipelines.

### State persistence and resumability

LangGraph's typed state object is serializable, enabling workflow checkpoint/
resume across process restarts. This is the key production advantage: a
multi-hour research agent can checkpoint after each major action and resume
without starting over if the process is interrupted. Neither AutoGen (conversation
history as state) nor CrewAI (memory modules) achieves this as cleanly.

### HITL design across frameworks

| Framework | HITL mechanism | State inspectability |
|---|---|---|
| LangGraph | Interrupt node; inspect/modify state; resume | High — typed state object |
| CrewAI | Task-level human review before proceeding | Medium — structured output |
| AutoGen | UserProxyAgent joins conversation | Low — conversation history |
| OpenAI SDK | Guardrails + manual intervention | Low — runtime-managed |

The MCP `elicitation` primitive is framework-agnostic and can layer HITL into
any framework that supports tool calls.

---

## Production considerations

### Observability

All frameworks integrate with OpenTelemetry / Langfuse for tracing. LangGraph
has the most mature native observability via LangSmith. Without tracing, agentic
systems are nearly impossible to debug in production — tool calls, LLM turns,
state mutations, and branching decisions all need to be captured.

### Latency profiles

Empirical benchmarks (2025) for equivalent tasks:
- LangGraph: lowest latency baseline
- LangChain (without LangGraph): highest latency and token usage
- CrewAI: ~3× token consumption, ~3× latency vs. LangGraph
- AutoGen: variable (async model makes benchmarking harder)

For latency-sensitive applications, CrewAI's coordination overhead is a real
cost. For correctness-sensitive applications, that overhead may be worth it.

### The token economy of coordination

A persistent finding across framework comparisons: coordination overhead is
non-trivial. Agents spend significant tokens describing their state to each other,
confirming task handoffs, and formatting outputs for the next agent. At scale,
this is an economic concern as much as a latency concern. Framework choice
should account for the expected token cost of the coordination layer, not just
the task execution cost.

---

## Where the landscape is heading (2026)

**Standardization pressure:** MCP is becoming the default tool-calling interface,
decoupling agent frameworks from specific tool implementations. Frameworks that
natively support MCP tool discovery are gaining adoption.

**Model-native agents:** OpenAI's move toward native agent capabilities
(Assistants API, then Agents SDK) puts pressure on framework-layer abstractions.
If the model handles state, memory, and tool-calling natively, the framework
layer thins. Counter-argument: frameworks add observability, testability, and
deployment management that model APIs don't provide.

**Evaluation infrastructure:** Frameworks are competing on eval tooling as much
as orchestration capability. LangSmith, CrewAI's control plane, and Langfuse
reflect a recognition that the bottleneck in production agents is not capability
but predictability — knowing when the agent will do the right thing.

---

## Relevance to Engram

The Engram/agent-memory-seed system is itself an example of the orchestrator/
subagent pattern: the MCP server is a stateful subagent (providing memory read/
write), and the host agent (Cowork, Claude Code, etc.) is the orchestrator.
The design choices in `core/tools/` — typed state via frontmatter, git-backed
durability, explicit read/write governance — parallel LangGraph's design
philosophy: prefer explicit, inspectable state over emergent conversational state.

The PWR protocol (brainstorm-pwr-protocol.md) would add something none of the
current frameworks provide natively: cross-session interaction logging as a
first-class primitive, enabling the self-optimization loop described there.

---

## Key sources

- [Langfuse: Comparing Open-Source AI Agent Frameworks (2025)](https://langfuse.com/blog/2025-03-19-ai-agent-comparison)
- [DataCamp: CrewAI vs LangGraph vs AutoGen](https://www.datacamp.com/tutorial/crewai-vs-langgraph-vs-autogen)
- [Latenode: Complete Framework Comparison 2025](https://latenode.com/blog/platform-comparisons-alternatives/automation-platform-comparisons/langgraph-vs-autogen-vs-crewai-complete-ai-agent-framework-comparison-architecture-analysis-2025)
- [Python in Plain English: Production Engineer's Comparison](https://python.plainenglish.io/autogen-vs-langgraph-vs-crewai-a-production-engineers-honest-comparison-d557b3b9262c)
- [Galileo AI: Mastering Agents — LangGraph vs AutoGen vs Crew AI](https://galileo.ai/blog/mastering-agents-langgraph-vs-autogen-vs-crew)
