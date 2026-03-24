---
created: 2026-03-19
last_verified: '2026-03-21'
origin_session: core/memory/activity/2026/03/19/chat-001
source: external-research
topic: Agent architecture patterns — ReAct, Plan-and-execute, Reflexion, orchestrator-subagent
trust: medium
type: knowledge
related: multi-agent-coordination.md, ../retrieval-memory/rag-architecture.md, ../../tools/mcp/mcp-server-design-patterns.md, ../../../software-engineering/ai-engineering/ai-assisted-development-workflows.md
---

# Agent Architecture Patterns

## Lede

Practical agent design has converged on a small taxonomy of patterns, each with characteristic strengths, failure modes, and cost profiles. These patterns connect to the capability thread (agents extend single-model capabilities through composition), the alignment thread (autonomous agents create alignment risks proportional to their autonomy and capability), the memory thread (all complex agents require some form of memory to maintain state across steps), and the dynamical-systems thread (the execution trace of an agent is a trajectory through an action space, and agent design determines the geometry of that trajectory). The "Building Effective Agents" essay (Anthropic 2024) is the canonical taxonomy, though it has predecessors.

---

## Foundations: The Augmented LLM

The simplest building block: an LLM with access to tools (retrieval, code execution, API calls), memory (previous conversation, stored facts), and structured input/output formats. This is not yet an agent — it is the substrate from which agents are built.

**The tool interface:** Tools are typically presented as function schemas in the system prompt, with the model generating structured tool-call outputs that a runtime layer executes. The result is returned to the model for the next step. This is the MCP protocol's model in specific; the general pattern is universal across agent frameworks.

**Key properties of the augmented LLM:**
- The model decides when to call tools based on context (not predetermined)
- Tool results can inform subsequent decisions (closed-loop)
- The model's context window serves as working memory
- The context has a maximum length, bounding the agent's effective planning horizon

---

## ReAct: Reasoning + Acting

**ReAct (Yao et al. 2022):** The model interleaves natural language reasoning ("Thought: I need to find the current price of X") with action invocations ("Action: search[current price of X]"). The Thought-Action-Observation loop repeats until the model produces a final answer.

**How it works:**
```
Thought: I need to find out when GPT-4 was released.
Action: search[GPT-4 release date]
Observation: GPT-4 was released on March 14, 2023.
Thought: Now I have the information. I can answer the question.
Final Answer: GPT-4 was released on March 14, 2023.
```

**Why it works:** The explicit reasoning step before each action gives the model space to plan which tool to use and why. Without explicit reasoning, models tend to take actions immediately based on surface-level pattern matching.

**Strengths:**
- Simple to implement (prompt engineering, no framework required)
- The chain of reasoning is inspectable
- Handles well-structured, predictable tasks efficiently

**Failure modes:**
- ReAct tends to get "stuck" in loops if a tool returns an unexpected result (it keeps trying the same approach)
- Limited planning horizon: each step decides only the next action, not a sequence
- Expensive if the task requires many sequential steps (each step is a full forward pass)
- Sensitive to observation quality: bad tool results cascade into bad reasoning

---

## Plan-and-Execute

**Pattern:** An upfront planning LLM call generates a multi-step plan; a separate execution agent carries out each step in sequence (or in parallel where steps are independent).

**Two-agent structure:**
1. **Planner:** Given the task, generates a structured plan: [step 1, step 2, ..., step N]
2. **Executor:** For each step, calls the appropriate tools and records results
3. **Replanner (optional):** If a step fails or produces unexpected results, re-runs the planner with the updated context

**When it beats ReAct:**
- Tasks with many sequential steps where upfront planning prevents later backtracking
- Tasks where some steps are parallelizable (the planner can identify this)
- Tasks where the final step depends critically on the outputs of all earlier steps
- Cases where the user wants to review/approve a plan before execution

**When ReAct beats Plan-and-Execute:**
- Tasks where the required steps cannot be known upfront (each step reveals information needed to determine the next step)
- Short tasks (the planning overhead is not worth it)
- Rapidly changing environments where the plan will be outdated before execution completes

**Hybrid (React-in-Plan):** The planner generates a high-level plan; each plan step is executed with a local ReAct loop. This captures the benefits of both: global coordination from the planner, adaptive local execution from ReAct.

---

## Reflexion: Self-Critique and Learning from Errors

**Reflexion (Shinn et al. 2023):** After each attempt at a task, the model generates a verbal self-critique analyzing what went wrong, then uses this critique as additional context for the next attempt. The model "learns" from errors within a single session without weight updates.

**Components:**
1. **Actor:** Generates task attempts (can be ReAct or direct)
2. **Evaluator:** Scores each attempt (can be the model itself, a verifier, or human feedback)
3. **Self-reflector:** Generates short verbal summaries of what went wrong and how to improve
4. **Memory:** Stores reflections across attempts within the session

**Strengths:**
- Effective when errors are consistent and diagnosable (the model makes the same mistake repeatedly, and reflection breaks the pattern)
- Requires no retraining or reward model
- Inspectable: the reflections expose the model's error diagnosis

**Failure modes:**
- If the model's self-critique is wrong (it misdiagnoses its own error), Reflexion makes things worse
- Effective reflection requires that failures have visible signals the model can observe; for tasks where failure is subtle or delayed, Reflexion doesn't help
- Context grows with each reflection, eventually hitting window limits

---

## Orchestrator-Subagent (Hierarchical Agents)

**Pattern:** A coordinator agent decomposes a complex task, delegates subtasks to specialized subagents, and integrates results into a final output.

**Structure:**
```
Orchestrator
├── Subagent A (web search specialist)
├── Subagent B (code execution specialist)
├── Subagent C (data analysis specialist)
└── Synthesis step: integrates A, B, C outputs
```

**Why specialization helps:** Specialized subagents can be prompted with different system prompts optimized for their tasks. They can use different models (cheap fast model for retrieval, expensive reasoning model for analysis). They can run in parallel where their subtasks are independent.

**Trust and information flow challenges:** Orchestrators must decide what information to pass to subagents and how much to trust subagent outputs. A subagent that receives malicious injected content via its tools could return injected results to the orchestrator.

**The Anthropic taxonomy:**
- Simple orchestrator: single coordinating model with tool-calling subagents
- Complex orchestrator: multi-hop delegation (orchestrator → subagent → sub-subagent)
- Peer networks (swarms): multiple peer agents without fixed coordinator, coordinating via shared state or message passing

---

## Evaluator-Optimizer

**Pattern:** One LLM generates candidate outputs; a second LLM (the evaluator) scores them and provides feedback; the generator revises based on feedback; repeat.

**Use cases:** Writing tasks (generate and refine), code generation (generate and test), planning (generate plan and critique it).

**Connection to RLHF:** This is inference-time RLHF without weight updates: the evaluator plays the role of the reward model, and the generator's revision plays the role of policy optimization.

**Key requirement:** The evaluator must be better at evaluating than the generator is at generating to the right quality level. If the evaluator is weaker than the generator, the feedback is noise.

---

## Autonomous Agents and the Capability/Risk Tradeoff

**Fully autonomous agents** (Devin, SWE-agent, OpenDevin) operate with minimal human interruption: given a task, they plan, execute, debug, and deliver results with no intermediate checkpoints.

**Why autonomy increases risk:**
- More steps before human review → more opportunity for error propagation
- Actions may be irreversible (producing a database write, sending an email, deploying code)
- The agent may pursue subgoals that satisfy the literal task but not the intended task (reward hacking at the agent level)
- Prompt injection via tool results can redirect the agent's goals mid-execution

**The minimal-footprint principle:** Well-designed autonomous agents should:
1. Request only necessary permissions
2. Avoid storing sensitive information beyond the immediate task
3. Prefer reversible over irreversible actions
4. Ask for clarification when uncertain, even at the cost of interrupting autonomy
5. Log all actions with enough detail to audit the execution trace

This is the engineering implementation of the alignment principle "prefer safe, reversible actions" at the agent system level.

---

## Open Questions

- **Agent evaluation:** How do you evaluate an agent's quality? Task completion on benchmarks (SWE-bench) works for code; general-purpose evaluation is unsolved. Partial credit (doing 70% of a task correctly and 30% incorrectly) is hard to measure.
- **Parallel agent coordination without a coordinator:** Swarm architectures lack a central coordinator to decompose tasks. How do independent agents divide labor without a top-down structure?
- **Trust verification between agents in a pipeline:** An orchestrator's subagent may have been compromised. How does the orchestrator verify that a subagent's result is trustworthy?
- **Long-horizon autonomy:** For tasks taking hours or days, how does an agent maintain context, recover from interruptions, and adapt to environmental changes over the execution period?

---

## Key Sources

- Yao et al. 2022 — "ReAct: Synergizing Reasoning and Acting in Language Models"
- Wang et al. 2023 — "Plan-and-Solve Prompting: Improving Zero-Shot Chain-of-Thought Reasoning"
- Shinn et al. 2023 — "Reflexion: Language Agents with Verbal Reinforcement Learning"
- Anthropic 2024 — "Building Effective Agents" (blog post — canonical taxonomy)
- Wu et al. 2023 — "AutoGen: Enabling Next-Gen LLM Applications via Multi-Agent Conversation"
- Significant-Gravitas 2023 — AutoGPT (early autonomous agent precedent)
- Wang et al. 2024 — "OpenDevin: An Open Platform for AI Software Developers as Generalist Agents"
