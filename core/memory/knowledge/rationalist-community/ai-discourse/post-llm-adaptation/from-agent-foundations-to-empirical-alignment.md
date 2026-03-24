---
created: '2026-03-21'
last_verified: '2026-03-21'
origin_session: core/memory/activity/2026/03/21/chat-001
source: agent-generated
trust: medium
---

# From Agent Foundations to Empirical Alignment: The Methodological Shift

*Coverage: How AI safety research shifted from MIRI-style formal/theoretical work to empirical alignment research at frontier labs; what drove the shift; what was gained and lost. ~3000 words. Trust: low — synthetic assessment, not primary-source verified.*

*Related plan: rationalist-ai-discourse-research.md, Phase 5/2.*

---

## The Original Program: Agent Foundations

### MIRI's Research Agenda

The Machine Intelligence Research Institute (MIRI) pursued what it called "agent foundations" research — a program aimed at developing the mathematical and philosophical foundations for building aligned AI agents:

**Core research directions (2014-2020)**:

- **Logical uncertainty**: How should a bounded agent assign probabilities to mathematical statements it can't fully verify? (Relevant to an AI reasoning about its own correctness.)
- **Decision theory**: Functional decision theory (FDT), updateless decision theory (UDT) — frameworks for rational agency that handle problems like Newcomb's problem, coordination with copies, and counterfactual reasoning.
- **Vingean reflection**: How can an AI system reason about agents that are more capable than itself (including future versions of itself)?
- **Naturalized induction**: How can an AI that is embedded in the world (not a detached observer) form beliefs about itself and its environment?
- **Value alignment theory**: The formal structure of the alignment problem — how to specify, learn, and stabilise human-compatible objectives in a mathematical framework.

**Characteristics of the program**:

- *Theoretical*: Proofs, formal frameworks, mathematical analysis. Very little empirical work.
- *Pre-paradigm*: The research was designed for hypothetical AI systems, not for any specific existing technology.
- *Agent-centric*: All the problems assume a goal-directed agent — an entity that reasons, plans, and acts toward objectives.
- *Foundational*: The aspiration was to build alignment theory from the ground up, analogously to how theoretical computer science underlies practical computing.

### The Bet

MIRI's implicit bet was:

1. The alignment problem is *hard* — hard enough that empirical approaches will fail without theoretical foundations.
2. We have *time* — enough time before transformative AI to develop the theory.
3. The theory will be *needed* — transformative AI will require formal alignment guarantees, not just empirical safety measures.
4. The relevant AI architecture will be *agent-like* — the theory is designed for optimizing agents, and this is what transformative AI will look like.

---

## The Shift

### What Changed

Several developments forced a methodological rethinking:

**The paradigm surprise (2017-2023)**: Large language models arrived as the dominant AI paradigm. These systems:
- Are not obviously agent-like (no explicit goals, no planning, no optimization in the decision-theory sense).
- Present immediate, practical alignment challenges (hallucination, safety, RLHF overoptimisation).
- Are already deployed to hundreds of millions of users.
- Are evolving rapidly enough that theoretical work can't keep pace.

**MIRI's acknowledged limitations**: MIRI itself published updates acknowledging that its research program had not produced the breakthroughs it hoped for. Yudkowsky's increasing pessimism partly reflected an assessment that the theoretical program hadn't succeeded on its own terms.

**The empirical opportunity**: Frontier labs discovered that alignment could be *practiced* — not perfectly, but usefully — through empirical methods:
- RLHF and preference learning (Christiano et al., 2017).
- Constitutional AI (Anthropic, 2022).
- Red-teaming and evaluations.
- Mechanistic interpretability.

These methods produce *measurably safer* systems, even without the theoretical foundations MIRI sought.

**Funding reallocation**: Open Philanthropy and other major funders shifted funding from purely theoretical alignment research toward empirical safety work at labs. This reflected an assessment that the highest-impact safety work was empirical, not theoretical.

### The New Program: Empirical Alignment

The empirical alignment research program, as practiced at labs and independent research organisations:

**Core research directions (2020-present)**:

- **RLHF and preference learning**: Learning human preferences from feedback; managing overoptimisation; scaling preference data.
- **Constitutional AI and self-supervised alignment**: Training models to evaluate their own outputs against principles; reducing dependence on human-generated preference data.
- **Mechanistic interpretability**: Understanding model internals — neurons, circuits, features — to explain *why* models behave as they do.
- **Evaluations and red-teaming**: Systematically testing models for dangerous capabilities, deceptive behaviors, and failure modes.
- **Scalable oversight**: How to maintain human oversight as models become more capable (debate, recursive reward modeling, process supervision).
- **Robustness and adversarial testing**: Ensuring safety measures hold up under adversarial conditions.

**Characteristics**:

- *Empirical*: Experiments, benchmarks, measurements. Results are testable and reproducible.
- *Paradigm-specific*: The research addresses the systems that actually exist (LLMs, RLHF, transformers).
- *Iterative*: Safety measures are developed, tested, and improved in rapid cycles.
- *Engineering-oriented*: The goal is to make deployable systems safe enough, not to prove alignment in a formal sense.

---

## What Was Gained

### Practical Impact

The empirical program has produced tangible safety improvements:

- **Post-RLHF models are substantially safer than base models**: They follow instructions, refuse harmful requests (usually), and generate more helpful and less toxic outputs.
- **Interpretability insights**: Mechanistic interpretability has produced real findings — polysemanticity, feature superposition, circuit-level explanations of specific behaviors.
- **Evaluation methodology**: The field now has progressively better methods for evaluating model safety, even if significant gaps remain.
- **Incident response**: The iterative nature of empirical alignment allows rapid response to discovered vulnerabilities.

### Research Velocity

Empirical alignment research produces results at a much faster pace than theoretical work:

- Papers in empirical alignment are published continuously, with measurable findings.
- Research compounds: each result builds on previous findings.
- New researchers can contribute without years of mathematical training.
- The field attracts ML researchers who might not have engaged with purely theoretical alignment.

### Contact with Reality

Perhaps most importantly, empirical alignment research is in *contact with the systems being built*. The researchers work on the actual models that will be deployed. Their findings directly inform safety practices. This connection to reality was missing from the theoretical program.

---

## What Was Lost

### Theoretical Depth

The shift to empirical work has come at the cost of deep theoretical understanding:

- **Why does RLHF work?** We have empirical evidence that RLHF improves model behavior, but limited theoretical understanding of *why* it works, what guarantees it provides, and when it will fail.
- **What are the limits of empirical alignment?** Without a theory, we can't determine whether empirical approaches will continue to work at higher capability levels.
- **Formal guarantees**: The aspiration for provably safe AI has been effectively abandoned for current systems. We have empirical safety (the model usually behaves well) but not formal safety (the model is guaranteed to behave well).

### Long Horizon Concerns

Empirical alignment addresses immediate challenges but may not prepare for qualitatively different future challenges:

- If AI systems become genuinely goal-directed (through agentic scaffolding or architectural innovation), the agent-foundations questions become relevant.
- If capability jumps produce systems qualitatively different from current LLMs, empirical safety measures designed for LLMs may be insufficient.
- The theoretical program was designed for the long term; the empirical program is designed for the short-to-medium term. Both are needed.

### The Independence Problem

Empirical alignment research occurs primarily *inside* frontier labs. This creates:

- Potential conflicts of interest (safety researchers are employed by the organizations they're evaluating).
- Access constraints (independent researchers can't work on the most capable models).
- Publication incentives that may bias toward positive results ("our safety technique works!") over negative ones ("our model has dangerous capabilities").

The theoretical program, based at independent organizations like MIRI, was at least structurally independent of the labs it aimed to oversee.

---

## The Current Synthesis

### What Most Alignment Researchers Now Believe

The emerging consensus (to the extent there is one):

1. **Empirical methods are necessary and currently sufficient**: For the systems we have now, empirical alignment is the right approach.
2. **Theoretical understanding would help but isn't required for current systems**: We can make progress without solving the foundations.
3. **The foundations may become critical as capability increases**: At some future capability level, empirical methods alone may be insufficient.
4. **Both programs should be funded**: Empirical alignment for near-term safety; theoretical work for long-term preparedness.

### MIRI's Pivot

MIRI itself has effectively shifted its positioning:

- Reduced emphasis on foundational theory.
- Increased emphasis on communications and governance (Yudkowsky's public advocacy).
- Some MIRI-adjacent researchers have moved into empirical alignment roles at labs.
- The organization's strategic role has shifted from "produce alignment theory" to "advocate for caution and governance."

### Independent Alignment Research

A middle ground has emerged: independent alignment research organizations (ARC, Redwood Research, MATS graduates) that do empirical work but outside lab structures:

- They can work on safety-relevant research without lab employment constraints.
- They contribute to the public knowledge base in ways that lab research sometimes cannot.
- They provide a training pipeline for alignment researchers who then enter labs.

---

## Open Questions

1. **Are empirical methods on track to scale with capability?** If models become much more capable in the next few years, will RLHF, eval, and interpretability keep pace?
2. **Is the theoretical program dead or dormant?** If future systems require formal guarantees, is there enough theoretical capacity to provide them?
3. **Can independence be maintained?** As empirical alignment concentrates inside labs, who provides independent oversight and critique?
4. **Will the research programs converge?** Mechanistic interpretability bridges empirical and theoretical work. Will this convergence deepen?

---

## Connections

- **Inner alignment reinterpretation**: The conceptual shift that accompanied the methodological one — see [../canonical-ideas/inner-alignment-as-behavioral-reliability](../canonical-ideas/inner-alignment-as-behavioral-reliability.md)
- **Value alignment as ongoing process**: The reframing that empirical alignment embodies — see [../canonical-ideas/value-alignment-as-ongoing-process](../canonical-ideas/value-alignment-as-ongoing-process.md)
- **Concept migration**: How theoretical concepts were operationalised in labs — see [../industry-influence/concept-migration-rlhf-constitutional-ai-evals](../industry-influence/concept-migration-rlhf-constitutional-ai-evals.md)
- **Personnel migration**: The people who carried the shift — see [../industry-influence/personnel-and-intellectual-migration](../industry-influence/personnel-and-intellectual-migration.md)
- **MIRI/CFAR**: The institution that housed the original theoretical program — see [../../institutions/miri-cfar-and-institutional-rationality.md](../../institutions/miri-cfar-and-institutional-rationality.md)
- **Language not search**: The paradigm surprise that forced the shift — see [../prediction-failures/language-not-search](../prediction-failures/language-not-search.md)