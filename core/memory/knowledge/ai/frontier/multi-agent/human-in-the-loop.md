---
created: 2026-03-19
last_verified: '2026-03-21'
origin_session: core/memory/activity/2026/03/19/chat-001
source: external-research
topic: Human-in-the-loop design — interruption, approval gates, reversibility, trust-building
trust: medium
type: knowledge
related: ../../tools/agent-memory-in-ai-ecosystem.md, ../../../cognitive-science/human-llm-cognitive-complementarity.md, ../../../philosophy/llm-vs-human-mind-comparative-analysis.md
---

# Human-in-the-Loop Design for Agent Systems

## Lede

The decision of when an agent should pause and ask versus proceed autonomously is both a design choice and an alignment question. Autonomous agents that never interrupt are the most efficient but the hardest to control; agents that interrupt constantly are controllable but not useful. The right operating point depends on task stakes, action reversibility, agent capability, and user trust — all of which change over time. This connects to the alignment thread (human oversight is a core alignment primitive), the multi-agent thread (human-in-the-loop is one layer of a broader approval hierarchy), and the agent design thread (where to place interruption checkpoints is an architectural decision with large impact on system behavior).

---

## When to Interrupt vs. When to Proceed

**The fundamental tradeoff:**
- Interrupting unnecessarily degrades the agent's utility; users abandon agents that constantly ask for permission
- Proceeding autonomously inappropriately creates errors, irreversible consequences, and erodes trust

**Four factors that should push toward interruption:**
1. **Irreversibility:** The action cannot be undone (send an email, delete a file, make a purchase). High-stakes irreversible actions warrant a checkpoint regardless of agent confidence.
2. **Scope creep:** The task has expanded beyond what was originally authorized ("You said to draft an email, but it seems I should also send it and add three recipients not in the original request" — stop and verify).
3. **Ambiguity:** The task specification is genuinely unclear and multiple interpretations lead to meaningfully different actions.
4. **Confidence threshold:** The agent's internal confidence (or an explicit uncertainty estimate) falls below a threshold.

**Four factors that push toward proceeding:**
1. **Reversibility:** The action can be undone without significant cost (editing a draft, reading a file, searching the web).
2. **Explicit authorization:** The user has explicitly authorized this type of action in this context.
3. **Track record:** The agent has successfully completed many similar actions without errors in this session.
4. **Low stakes:** Errors in this action, even if they occur, would have minimal consequences.

---

## Approval Gate Design

When an interruption occurs, what information should the human see to make a good approval decision?

**Principles for effective approval gates:**
1. **Show the action, not just the intent:** "Send an email to alice@example.com with subject 'Q3 report' containing [content]" is evaluable. "Send the report email" is not.
2. **Show what happens if they approve and what happens if they decline:** The consequences of both paths should be visible.
3. **Show the agent's rationale:** Why does the agent think this is the right action? This allows the human to catch reasoning errors, not just action errors.
4. **Show what has happened so far:** The execution trace to this point should be inspectable so the human can evaluate whether prior steps were correct.
5. **Flag the stakes:** Is this action reversible? What resources does it consume? What are the downstream effects?

**The approval fatigue problem:** If approval gates are too frequent or demand too much cognitive effort, humans stop reading them and approve everything reflexively. This is strictly worse than no gates (false sense of control). Good gate design minimizes the cognitive load of each gate while preserving the information necessary for genuine evaluation.

**The MCP Elicitation primitive:** The Model Context Protocol's `elicitation` primitive formalizes server-initiated user queries. Rather than the agent just generating text asking the user a question, `elicitation` is a structured mechanism where the server (agent runtime) requests specific structured input from the user. This provides:
- A clean separation between "the agent is talking" and "the system needs input"
- Machine-readable approval responses that can be validated and logged
- The ability to present structured options rather than free-text prompts

---

## Reversibility Scoring

**The reversibility framework:** Before executing any action, the agent (or its orchestration layer) can score the action on a reversibility scale:

| Score | Category | Examples |
|---|---|---|
| 1 | Fully reversible | Reading a file, searching, browsing |
| 2 | Easily reversible | Creating a new file, adding a draft |
| 3 | Reversible with effort | Editing an existing file (can restore from backup) |
| 4 | Difficult to reverse | Sending a message (recipient has seen it) |
| 5 | Irreversible | Deleting data permanently, executing a financial transaction |

**Policy options based on score:**
- Score 1–2: Proceed autonomously
- Score 3: Proceed if within authorized scope; log prominently
- Score 4–5: Interrupt for explicit approval unless pre-authorized

**Dynamic reversibility:** Some actions that appear irreversible at first are reversible with compensating actions. Defining "reversibility" in terms of the full action space (what compensating action exists?) rather than just the immediate action gives a more useful score.

**This repo's approach:** The operational safety section of the agent's instructions follows this pattern: create/edit files are low-risk (proceed); git push, reset --hard, deleting files require confirmation. The taxonomy is informal but consistent with the reversibility framework.

---

## Building Trust Incrementally

**The trust-building curve:** An agent earns broader autonomy by demonstrating reliable judgment on lower-stakes tasks. This mirrors how trust is established in human professional relationships.

**Mechanisms for trust-building:**
1. **Transparent execution traces:** Every action logged with reasoning allows users to verify that the agent acted correctly even when they didn't review it in real time.
2. **Proactive error reporting:** When the agent notices it has made a mistake, it reports this without being asked. This signal is important — it shows the agent's error detection is working and its honesty is intact.
3. **Appropriate uncertainty expression:** The agent hedges when genuinely uncertain rather than projecting false confidence. Calibrated uncertainty expression is a trust signal.
4. **Boundary-testing awareness:** The agent notices when a task is approaching the edges of its authorized scope and flags this rather than proceeding.

**The trust ratchet:** Trust should earn autonomy; errors should narrow it. A system that expands autonomy based on track record but contracts it after errors provides the correct incentive structure. This is not currently implemented in most agent frameworks (autonomy scope is usually static per session).

**Calibration over time:** As the user and agent develop a history, the appropriate interrupt threshold shifts. For a new agent completing its first financial task, pause at every step. For an agent that has successfully completed 100 similar tasks, the threshold for interruption can be higher. Trust is session-context-dependent, not just agent-capability-dependent.

---

## Designing for Failure Modes

**Failure mode 1: Agent gets stuck and keeps attempting**
The agent has hit an obstacle (tool returns an error, task is blocked) and iterates on failing approaches without interrupting. Prevention: limit total attempts on any single step; trigger interruption when consecutive failures exceed threshold.

**Failure mode 2: Agent succeeds at letter of task, fails at spirit**
The agent interprets the task literally and produces technically correct but wrong output (asks "clean up the code" and deletes half of it, satisfying the literal instruction to "clean up" without understanding the spirit). Prevention: ask the agent to paraphrase its interpretation of the task before executing; interrupt at major decision points during long tasks.

**Failure mode 3: Approval gate fatigue leads to rubber-stamping**
The user approves everything without reading. Prevention: randomize gate depth (occasionally provide detailed information about a low-stakes action to test whether the user is actually reading), require structured responses rather than single-click approval, set a maximum approval rate before triggering a "review required" flag.

**Failure mode 4: Agent proceeds past authorization scope**
The agent was authorized to "fix the bug" and ends up refactoring half the codebase. Prevention: explicit scope boundaries in the system prompt ("only modify files in src/utils/"), with hard stops when the agent attempts actions outside the boundary.

---

## The Corrigibility Design Principle

**Corrigibility** is the property of being safely correctable — the agent should:
- Accept corrections without resistance
- Not take actions that prevent future corrections
- Defer to human judgment when human and agent conflict
- Not acquire resources, influence, or capabilities beyond what the current task requires

Corrigibility is in tension with competence: a highly capable agent that pursues its goal effectively may "resist" corrections not out of stubbornness but because corrections temporarily interfere with goal achievement. Designing for corrigibility requires treating goal-pursuit and correction-acceptance as equally important.

**Practical corrigibility measures:**
- Include explicit instructions to the agent to stop and wait when the user says "stop" regardless of task state
- Design the agent to prefer undoing its own actions when instructed rather than arguing for keeping them
- Log all actions to an append-only record that cannot be modified by the agent itself
- Never give the agent write access to its own instructions, system prompt, or permission boundaries

---

## Open Questions

- **Automatic reversibility scoring:** Can agents reliably compute reversibility scores for novel actions, or does this always require human specification? Early results suggest LLMs can provide useful but imperfect reversibility estimates.
- **Trust modeling across sessions:** How should an agent's earned trust level persist and transfer across sessions and task types? A trusted agent for code review may not have earned trust for financial actions.
- **Minimal interruption design:** Can agents be trained to achieve correct behavior with fewer interruptions while maintaining safety? The goal is the Pareto frontier of (fewer interruptions, maintained correctness), not just one at the expense of the other.
- **Formal approval protocols:** Can we formalize approval gate design with guarantees — e.g., if a user approves an action at an approval gate, can we guarantee the agent's behavior post-approval is bounded in some useful way?

---

## Key Sources

- Anthropic 2024 — "Building Effective Agents" (human-in-the-loop section)
- Leike et al. 2022 — "Alignment of Language Agents" (corrigibility framing)
- Model Context Protocol 2024 — Elicitation primitive specification
- Irving and Askell 2019 — "AI Safety Needs Social Scientists" (human factors in AI oversight)
- Weld and Etzioni 1994 — "The First Law of Robotics: A Call to Arms" (classic corrigibility discussion)
- Hendrycks et al. 2023 — "Aligning AI With Shared Human Values" (ETHICS dataset for alignment)