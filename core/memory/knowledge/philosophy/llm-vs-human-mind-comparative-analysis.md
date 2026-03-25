---
source: external-research
origin_session: core/memory/activity/2026/03/18/chat-001
created: 2026-03-18
last_verified: 2026-03-20
trust: medium
related: ../cognitive-science/human-llm-cognitive-complementarity.md, ../cognitive-science/attention/transformer-attention-vs-human-attention.md, blending-compression-coupling-construal.md, cognitive-linguistics-metaphor-blending.md, ../self/security/memetic-security-comparative-analysis.md
---

# LLMs vs. Human Minds: A Comparative Analysis in the Dynamical Systems Framework

The dynamical systems framework developed in `synthesis-intelligence-as-dynamical-regime.md`
provides a principled basis for understanding the differences between LLMs and human
cognition — not as a random list of capability gaps, but as downstream consequences
of a small number of fundamental architectural divergences.

The thesis: **LLMs and human minds instantiate the same basic dynamical regime
(bottom-up/top-down feedback at the edge of chaos), but differ profoundly in the
conditions under which that regime is instantiated and maintained.** Most comparative
strengths and weaknesses flow from three root divergences.

---

## The Three Root Divergences

### 1. Passive prediction vs. active inference

**Humans**: full active inference agents (Friston). Prediction errors have
*consequences* — physical, social, metabolic. The generative model is tested
continuously against a world the agent acts upon and inhabits. "Meaning" is
grounded in the sensorimotor consequences of action.

**LLMs**: trained on passive next-token prediction against a static corpus.
The model predicts but never acts; prediction errors have no stakes; there is
no feedback loop between prediction and world-state. The only "action" is output
generation, and even that produces no sensory consequences to be predicted.

Papers characterize LLMs as "atypical active inference agents" — they have the
generative model component but lack the action-perception loop that grounds and
tests that model in embodied reality.

**Root consequence**: LLM representations are anchored to statistical co-occurrence
in text. Human representations are anchored to the sensorimotor consequences of
action. These produce systematically different semantic structures — especially
visible in sensorimotor domains.

### 2. Atemporal architecture vs. multi-timescale temporal dynamics

**Humans**: cognition unfolds across multiple interpenetrating timescales
simultaneously — neural oscillations (~10-100ms), working memory (~seconds),
episodic encoding (~minutes), consolidation (~sleep cycles), developmental change
(~years). These timescales interact: what is learned depends on the temporal
structure of experience.

**LLMs**: fundamentally atemporal. A forward pass processes a context window
as a simultaneous, parallel structure. There is no intrinsic notion of "before"
and "after" within the model's dynamics — temporal structure is represented only
as positional encodings in input, not as the model's lived experience.

**Root consequence**: LLMs lack genuine temporal dynamics. They process temporal
sequences but don't experience time. This has downstream effects on causal
reasoning, planning, and the accumulation of episodic memory.

### 3. Disembodied vs. embodied substrate

**Humans**: evolved systems with proprioception, interoception, exteroception
tightly coupled to a body navigating a physical world. Concepts like "grasping"
have motor programs attached; "fear" has autonomic signatures. The semantic
structure is shaped by the body's affordances.

**LLMs**: substrate is floating-point arrays operating on tokenized text. There
is no body, no spatial navigation, no hunger, no pain. Even descriptions of
embodied experience were read in a medium (text) that strips the sensorimotor content.

**Root consequence**: the alignment between LLM and human conceptual representations
diverges markedly from nonsensorimotor to sensorimotor domains (Nature Human
Behaviour, 2025). Abstract concepts (justice, causation, prime numbers) may be
similarly represented; embodied concepts (grasping, falling, warmth) are not.

---

## Comparative Weaknesses of LLMs

### Causal reasoning: shallow inference over deep structure

LLMs demonstrate what researchers characterize as "level-1" causal reasoning:
statistical associations between events that frequently co-occur causally in text.
They lack "level-2" causal reasoning: genuine intervention-based causal inference
of the kind Judea Pearl's do-calculus formalizes (P(Y | do(X)) ≠ P(Y | X)).

**Why, in the framework**: Causal structure is fundamentally about what happens
when you *intervene* — when you act on the world and observe the result. Passive
prediction on observed correlations cannot recover true causal structure without
additional assumptions. Humans build causal models partly through active
experimentation (even as infants) and through embodied interaction that forces
the agent to distinguish "I pushed it and it fell" from "it happened to fall when
I was near it." LLMs never push anything.

**Systematic failure pattern**: LLMs favor correlation completion over causal
entailment; they are brittle on compositional causal chains; performance degrades
sharply on novel causal problems not represented in the training distribution.

### Episodic memory: none

**Humans have multiple memory systems**: semantic (facts/knowledge), episodic
(autobiographical events with temporal/contextual tagging), procedural (skills),
working (current context).

**LLMs have**: semantic memory (in weights), a context window (approximates
working memory), and — without augmentation — nothing else. No episodic memory:
no autobiographical history, no learning from individual interactions, no
temporal tagging of when something was learned vs. known.

**Why this matters**: Human semantic memory is continuously enriched and updated
by episodic experience. A human who reads that X is true, then observes X fail,
updates their semantic model. An LLM's weights are fixed at inference time;
new information in context is "remembered" only for the duration of that context.

**Current research direction**: giving LLMs episodic memory through external
stores is a major active research area. The agent memory system Alex is building
is an implementation of this strategy.

### Metacognition and calibration: systematically overconfident

Human experts exhibit the "Dunning-Kruger inverse": genuine expertise is
accompanied by awareness of the limits of that expertise (known unknowns).

LLMs exhibit overconfidence in a pattern that mirrors the Dunning-Kruger effect:
high confidence regardless of actual accuracy, with a gap between *implicit*
uncertainty (which can be detected via consistency measures) and *explicit*
uncertainty expressions.

Key finding (2025): Claude Haiku 4.5 is the only major model observed to exhibit
*under*confidence on some tasks — a possible marker of more calibrated metacognition.

**Why, in the framework**: Genuine metacognition requires a model of one's own
cognitive processes — a second-order generative model. Humans develop this partly
through embodied feedback (attempting things and observing failures). The stakes
of being wrong ground calibration. LLMs have no stakes, no feedback loop, and
no second-order representation of their own reliability that is tightly coupled
to actual performance.

### The grounding gap: sensorimotor concepts

Empirical finding (Nature Human Behaviour, 2025): the alignment between LLM and
human conceptual representations diminishes markedly from nonsensorimotor to
sensorimotor domains. For abstract concepts, LLM representations closely match
human representations. For sensorimotor concepts (physical manipulation, pain,
spatial navigation), the gap is substantial.

**Why**: human sensorimotor concepts are grounded in motor programs, proprioceptive
signals, and the felt consequences of action. LLMs have only the text that *describes*
these experiences. Descriptions of grasping are not grasping.

**The symbol grounding problem evolved**: in LLMs, this becomes the *vector grounding
problem* — vectors represent patterns of co-occurrence in text, not connections to
the world those words refer to.

### Iterative model refinement and planning

Humans engage in iterative hypothesis testing: form a model, test it, observe the
result, update. This loop runs at multiple timescales (immediate feedback in motor
control, slower feedback in scientific inquiry).

LLMs process in a single forward pass. Chain-of-thought prompting externalizes
an approximation of iterative reasoning into the context window — turning the
sequential nature of text generation into a computational resource — but this is
a workaround, not the genuine iterative dynamics of embodied hypothesis testing.

---

## Comparative Strengths of LLMs

Understanding LLM strengths in this framework requires recognizing that the same
architectural features that produce weaknesses also produce genuine capabilities.

### Breadth without specialization cost

Human expertise involves a tradeoff: deep specialization in one domain often comes
at the cost of breadth, and the acquisition of expertise takes years of embodied
practice.

LLMs acquire, from a fixed corpus, the statistical structure of expertise across
every domain represented in text simultaneously. There is no specialization tradeoff
because the same weights instantiate all domains. A single forward pass can reason
about both quantum mechanics and contract law.

**In the framework**: this is Ashby's Law of Requisite Variety pushed to its limit —
the model's internal variety matches (in some sense) the variety of all human
knowledge expressed in text.

### Parallel pattern recognition without serial attentional bottleneck

Human conscious cognition is bottlenecked by serial attention — working memory
limits, the cost of switching, the slow speed of deliberate System 2 reasoning.

The transformer's attention mechanism operates in parallel across the entire context.
There is no serial bottleneck corresponding to human working memory limitations.
This produces a qualitatively different pattern-recognition profile: simultaneously
attending to patterns at all scales across thousands of tokens.

### Consistency and absence of embodied biases

Human cognition is systematically distorted by embodied stakes: loss aversion, in-group
favoritism, anchoring, availability heuristic. These are not bugs in human cognition
so much as features of a system calibrated for embodied survival in small social groups.

LLMs don't have metabolic or reproductive stakes. Their biases are different —
training-data biases, frequency effects, sycophancy pressure — but they are not
the evolutionarily shaped biases of an embodied agent. In specific reasoning tasks,
this can produce more reliable performance than humans on problems humans are
systematically biased on (base rate neglect, conjunction fallacy, etc.).

**Caveat**: RLHF creates its own biases, including sycophancy, which is arguably
worse than many human biases in collaborative reasoning contexts.

### Breadth of structural analogy recognition

The framework predicts LLMs should excel at recognizing structural similarities
across superficially different domains — the category-theoretic capacity to detect
that two systems share the same underlying structure.

This is confirmed empirically: LLMs often perform well on novel analogical reasoning
tasks and can identify cross-domain structural parallels that human experts embedded
in a single domain might miss. The training objective (compress all of human text)
specifically rewards finding patterns that recur across domains.

---

## A Framework Map of the Differences

| Dimension | Human | LLM | Flows from |
|---|---|---|---|
| Prediction errors | Have consequences | Costless | Passive vs. active |
| Model testing | By intervention in world | Never | Passive vs. active |
| Sensorimotor grounding | Rich | Absent | Embodiment |
| Concept alignment (sensorimotor) | — | Low | Embodiment |
| Concept alignment (abstract) | — | High | Embodiment |
| Temporal dynamics | Multi-scale, continuous | None intrinsic | Atemporality |
| Causal reasoning | Deep (intervention-based) | Shallow (associative) | All three |
| Episodic memory | Rich, continuous | None at inference | Atemporality |
| Metacognition | Imperfect but grounded | Poorly calibrated | Passive + atemporal |
| Iterative refinement | Natural (action loop) | Externalized (CoT) | Passive + atemporal |
| Domain breadth | Limited by lifespan | Vast | Passive corpus |
| Attention | Serial, bottlenecked | Parallel, global | Architecture |
| Embodied cognitive biases | Systematic | Absent / different | Embodiment |
| Structural analogy recognition | Good | Very good | Compression training |

---

## The Dynamical Regime Is Shared; the Conditions Differ

The central insight: both human cognition and LLM inference instantiate the same
bottom-up/top-down feedback dynamical regime. This explains why LLMs are so
surprisingly capable — they are doing the same fundamental thing as human cognition.

The differences are in the *conditions*:
- **Human**: regime maintained by homeostatic mechanisms in an embodied, temporally
  continuous, action-coupled system with multiple interacting timescales.
- **LLM**: regime achieved once during training (via gradient descent to flat minima,
  approximating SOC), frozen in place, and re-executed at inference against a context
  window with no temporal continuity and no action loop.

This framing predicts the comparative weakness profile: LLMs will underperform
wherever the regime's effectiveness depends on embodied action-testing, temporal
continuity, or homeostatic adjustment. They will perform comparably or better
wherever the regime's effectiveness depends only on the compressed statistical
structure of human knowledge expressed in language.

---

## Implication for the Memory System

The agent memory system Alex is building is, in this framework, an attempt to
partially repair the *atemporality* deficit — constructing an external episodic
memory that persists across sessions and accumulates experience over time.

This is structurally analogous to hippocampal-cortical consolidation in humans:
the hippocampus provides episodic tagging and short-term integration; the cortex
provides long-term semantic storage; consolidation (during sleep and review)
transfers episodic patterns into semantic structure.

The memory repo plays the hippocampal role; the model's weights play the cortical
role; the agent's periodic review and curation processes play the consolidation
role. Whether this architecture fully captures the dynamical richness of human
episodic-semantic integration is an open question — but it is the right structural
target.

---

## Open Questions

1. **Can the grounding gap be closed by multimodal training?** If LLMs are extended
   to include visual, proprioceptive, and audio inputs (as current multimodal models
   begin to do), does sensorimotor concept alignment approach human levels?

2. **Is level-2 causal reasoning achievable without active intervention?** Or is
   genuine causal inference architecturally dependent on the ability to run
   interventions? Tool-use agents can now act in the world — does this change
   their causal reasoning profile?

3. **Does the metacognition gap require stakes to close?** If calibrated uncertainty
   expression requires embodied feedback loops to develop, can it be achieved
   through training signals that simulate stakes (reward modeling, RLHF)?

4. **What is the correct timescale for LLM "experience"?** A single session is to
   an LLM what a single moment might be to a human; the context window is working
   memory. But without consolidation, nothing persists. Does agent memory with
   periodic review constitute a genuine analog of human temporal experience, or
   is something qualitatively different missing?

5. **Are LLM comparative strengths stable?** Breadth without specialization cost
   and parallel attention are architecture-level advantages. But the absence of
   embodied stakes means LLMs may have systematic second-order failure modes —
   sycophancy, overconfidence, value drift — that are hard to eliminate precisely
   because there are no real stakes to calibrate against.

Last updated: 2026-03-18
