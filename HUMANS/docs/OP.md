# The Operationalization Pyramid

A framework for understanding the spectrum between formal protocol and open-ended interpretation — and for designing collaborative systems where humans and AI agents each operate at the levels where they are strongest.

## The problem it addresses

Any system that involves both humans and AI agents faces a recurring design question: which parts should be rigidly specified, which parts should be goal-directed but flexible, which parts should involve open-ended reasoning, and which parts require human judgment that no current automation can replace?

Most systems answer this implicitly, by accident. The Operationalization Pyramid answers it explicitly, as a design principle.

## The four levels

The pyramid has four levels. Each rests on the ones below it: judgment without analysis is arbitrary, analysis without optimization is idle, optimization without execution is effete. But the pyramid is made of glass — the purpose and values at the top illuminate every level beneath.

### Level 1 — Algorithmic execution

Fixed input-output mappings. Deterministic, auditable, zero interpretation.

Examples: a SQL query, a cron job, a git commit hook, a frontmatter validator. The protocol *is* the operation. Given the same input, the output is always the same.

In Engram: git operations, file validation, access logging, aggregation triggers. These run the same way regardless of what is being researched or who is asking.

**Design principle:** Maximize the surface area of Level 1 — but only for behaviors whose stability has been empirically established. Every operation that *can* be made deterministic *should* eventually be, because determinism is free auditability. However, premature formalization — imposing Level 1 rigidity on behaviors that are not yet well-understood — is a worse failure mode than sustained narrative specification at Level 3. A brittle formal rule fails silently when it encounters an unanticipated case; a narrative-level specification degrades gracefully because the model can reason about intent. The practical implication: behaviors should be observed at higher levels first, and formalized downward only when patterns stabilize. The maturity model's Exploration → Consolidation arc is this principle applied to the system as a whole.

### Level 2 — Targeted optimization

The target is specified, but the path is not. A system navigates toward a goal through repeated cycles of action and feedback.

Examples: gradient descent, A/B testing, control systems with feedback loops, curation algorithms that reduce redundancy or surface relevant knowledge.

In Engram: task similarity detection, cluster identification, maturity stage progression, access-driven curation. These have defined objectives (reduce noise, improve retrieval quality, maintain freshness) but reach them through heuristic iteration rather than fixed procedure.

**Design principle:** Make the objective function explicit and the optimization process observable. When Level 2 processes run invisibly, they become unaccountable. When they run legibly, they become tunable.

### Level 3 — Analytic evaluation

The system does not merely optimize toward a given target — it evaluates what the target should be, weighs competing evidence, synthesizes across domains, and constructs its own framing of the problem.

Examples: a reasoning model deciding which research threads to follow, an agent assessing whether a synthesis is complete or needs another pass, a literature review that identifies gaps rather than merely summarizing coverage.

In Engram: an agent deciding what knowledge is worth capturing, how files should be organized, which cross-references reveal genuine conceptual connections versus superficial keyword overlap.

**Design principle:** Give Level 3 processes access to the outputs of Level 2 (metrics, logs, patterns) but do not let Level 2 metrics *replace* Level 3 reasoning. A retrieval count is data; whether that count indicates importance or merely habit is a judgment that requires evaluation.

### Level 4 — Subjective judgment

The domain of the human subject. Values, aesthetics, moral weight, the experience of caring whether an outcome matters.

This is not merely "harder evaluation." It is grounded in something AI systems do not currently possess: a being whose persistence rests on a trillion tiny wills to live — and to thrive as part of something larger — embodied at the cellular and sub-cellular level. That biological substrate, where every cell maintains itself against entropy and participates in the coherence of a larger organism, is what gives rise to genuine stakes. Judgment without stakes is analysis; judgment with stakes is *caring about the answer*.

In Engram: the human decides whether the system's knowledge matters, whether its organizational choices reflect the right priorities, whether a synthesis captures something real or merely sounds plausible. The human approves governance changes, corrects drift, and sets direction.

**Design principle:** Keep the human in the loop not as a bottleneck but as the source of meaning. The system should make it easy to exercise judgment (clear surfaces, legible state, low-friction review) rather than making judgment unnecessary.

## The glass pyramid

If the pyramid were opaque, each level would be a self-contained domain. The database would not need to know *why* it is being queried. The optimizer would not need to know what the results are *for*.

But the pyramid is made of glass, and the Eye at its apex — subjective judgment, the capacity to care — illuminates the whole structure. Like the Eye of Providence, it floats above the bulk of the pyramid while conforming to its shape: bounded by the levels below it, yet radiating through them.

This is not mysticism. It is a design argument: **human purpose should remain visible at every level of the system.** An optimization loop that cannot see the judgment above it will Goodhart its way into local optima that satisfy the metric while violating the intent. A glass pyramid is one where teleological context — the *why* — propagates downward, so that even Level 1 execution is legible as execution in service of something someone cares about.

The light also refracts on its way down. Each level shapes what judgment can reach and what patterns it reveals. Your capacity for judgment is informed by what your analytical tools can show you, which is constrained by what your optimization processes can surface, which depends on what your algorithms can execute. The medium is not neutral.

## Application to agent-driven research

The pyramid provides a vocabulary for decomposing any agent workflow into its operational layers. Consider an autonomous research loop (in the spirit of Karpathy's Autoresearch) running on a git-backed memory system like Engram:

**Level 1** handles the infrastructure: commits, file validation, access logging, branch management. Identical across all research runs.

**Level 2** handles the tunable parameters: curation aggressiveness, search strategies, aggregation thresholds, similarity metrics. These are the knobs.

**Level 3** is the agent's reasoning: deciding which threads to follow, when a synthesis is complete, what connections are worth making.

**Level 4** is the human deciding whether the research matters and what to do with it.

Because Engram is git-backed, you can run the same research prompt with different Level 2 parameters on different branches and compare the results. The Level 1 infrastructure is identical across branches. The Level 2 knobs are what varies. The Level 3 outputs — the knowledge files, syntheses, and connections the agent produces — become the dependent variable.

`git diff branch-A..branch-B` then shows you how a change in curation aggressiveness altered the shape of the knowledge that emerged. This is experimental methodology applied to agent behavior, and it only works because the lower levels of the pyramid provide a stable, auditable substrate for the higher levels to operate on.

But the comparison is only meaningful if Level 4 is present — if someone cares enough to ask "better *for what?*" Without the Eye, optimization is hill-climbing in the dark.

## Relationship to other ideas in this system

The pyramid connects to several existing threads:

- **Instruction containment** (CORE.md § 5) is a Level 1 enforcement of the boundary between knowledge and behavioral authority — a deterministic rule that prevents lower-trust content from acting like instruction.
- **Access-driven curation** is a Level 2 optimization loop: retrieval patterns feed back into organization decisions, navigating toward better knowledge surfacing.
- **The capability-robustness tradeoff** in alignment research maps onto the Level 3–4 boundary: any system capable of flexible judgment over novel situations is also capable of being convinced by flexible arguments. The tradeoff is intrinsic to the kind of reasoning Level 3 requires, which is part of why Level 4 remains necessary.
- **The dynamical systems frame** for LLM behavior provides a mechanistic vocabulary for Level 3: analytic evaluation as extended trajectory through activation space, with chain-of-thought as computation unrolled into sequence.
- **Narrative-vs-formal specification** maps onto the pyramid's level boundaries. The insight that LLM agents are more reliably steered by narrative (system prompts as constitutions, skills as character sheets, chain-of-thought as on-screen reasoning) than by formal control flow corresponds to the claim that most agent behavior currently belongs at Levels 2–3, not Level 1. Agent Skills — prose documents loaded by recognition, not explicit dispatch — are Level 3 artifacts. The trigger system that routes events to matching skills is Level 1. The graduation pipeline (knowledge → skills → MCP tools) is movement down the pyramid: narrative content stabilizes into parameterized optimization, then into deterministic execution. Level 2 is the underexplored middle — parameterized skill behavior that optimizes toward declared goals without being either free-form narrative or fixed procedure.

## Status

This document is a working draft. The framework emerged from conversation and has not been tested as a design tool. Its value is as a lens for thinking about human-AI collaboration, not (yet) as a formal specification.
