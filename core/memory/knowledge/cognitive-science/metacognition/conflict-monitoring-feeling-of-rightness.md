---

created: '2026-03-20'
origin_session: core/memory/activity/2026/03/20/chat-004
source: agent-generated
last_verified: '2026-03-20'
trust: medium
related:
  - feeling-of-knowing-tip-of-tongue.md
  - metacognitive-monitoring-control.md
  - source-monitoring-reality-monitoring.md
---

# Conflict Monitoring and the Feeling of Rightness

## Dual-Process Conflict: The Setup

In dual-process theory (see `dual-process-system1-system2.md`), System 1 produces fast, automatic responses and System 2 produces slow, deliberate responses. The critical question for dual-process theory: how does the cognitive system "decide" when to engage System 2? If System 1 dominates by default, what triggers the override?

**The Feeling of Rightness (FOR)** is the proposed answer: an intermediate metacognitive signal that signals whether the System 1 output "feels right" before System 2 commits to it.

**The mechanism:**
1. System 1 produces a fast response to a problem
2. A FOR judgment is generated (high FOR: System 1 answer feels correct; low FOR: system detects something wrong)
3. High FOR → System 2 does not engage; System 1 answer stands
4. Low FOR → System 2 is triggered to scrutinize the System 1 output

The FOR is the **threshold mechanism** that determines whether the costly deliberate intervention of System 2 is worth engaging.

---

## Conflict Detection: Empirical Evidence (De Neys & Glumicic, 2008)

Wim De Neys and colleagues provided experimental evidence that people detect conflict between intuitive and normative responses **even when they fail to correct their intuition**.

**Critical finding:** When given reasoning problems where the System 1 response is incorrect (e.g., base-rate neglect problems, the Cognitive Reflection Test), subjects who ultimately give the wrong answer still show behavioral and physiological signs of conflict detection:
- Longer response times on conflict problems than on matched non-conflict problems — even for incorrect responders
- Greater skin conductance response (arousal) for conflict items — an implicit stress/uncertainty signal
- Lower confidence in the incorrect answer on conflict items vs. non-conflict items
- More frequent blinks (physiological arousal proxy) during conflict items

**The implication:** Conflict detection (metacognitive awareness that something is wrong) is dissociable from conflict resolution (actually correcting the error). People can detect that their intuition may be wrong while still following it. The FOR system is not sufficient to override powerful or fluent System 1 responses; it triggers System 2 engagement, but System 2 may be insufficiently engaged, may confirm the intuition through motivated reasoning, or may simply lose the battle against the System 1 response.

---

## The Feeling of Rightness as a Metacognitive Signal

**Thompson et al. (2011)** developed a systematic research program on FOR in reasoning tasks.

**Measurement:** After producing an initial System 1 answer to a reasoning problem, subjects are stopped and asked to rate their Feeling of Rightness for their initial answer before proceeding to any deliberation. They then have the option to change their answer.

**Key findings:**
- Low FOR predicts answer change attempts (System 2 engagement is triggered)
- High FOR predicts answer persistence (System 2 is not engaged)
- When System 1 produces the *correct* answer, FOR is high and System 2 non-engagement is adaptive
- When System 1 produces an *incorrect* answer, FOR is high in some cases — these are the failure cases: no conflict signal is generated, System 2 is not triggered, and the error is not corrected

**FOR calibration:** Like all metacognitive signals, FOR is not perfectly calibrated. The error cases where FOR is high for incorrect System 1 outputs are systematically predictable:
- When the incorrect answer is fluent (comes easily to mind)
- When the problem involves a familiar surface structure that maps to an unrelated learned solution
- When prior successful use of the same incorrect heuristic has reinforced high FOR for it
- In domains of high apparent competence where overconfidence is structurally likely (Dunning-Kruger)

---

## Monitoring Failure Under Cognitive Load

Metacognitive monitoring — including the FOR signal — degrades under cognitive load (working memory load, time pressure, divided attention, emotional arousal).

**Nelson (1996)** on monitoring resource demands: Monitoring itself requires cognitive resources. Under high load, monitoring fidelity decreases — the meta level has less capacity to observe the object level accurately.

**Implications:**
- Under load, System 1 outputs are less likely to trigger System 2 review — the FOR detection threshold is effectively raised (weaker conflict signals don't register)
- Errors made under cognitive load are less likely to be self-detected
- The bias is asymmetric: load impairs error detection more than it impairs error commission

**Frontal syndrome as extreme case:** Patients with prefrontal cortex damage (Luria's frontal syndrome; see Damasio's *Descartes' Error*) show extreme failures of conflict monitoring:
- Perseverative errors: continuing behaviors that are clearly wrong, without noticing
- Impulsive actions without checking appropriateness
- Confabulation without recognizing the confabulation as such
- No functional FOR signal — System 2 is not engaged even by the clearest conflicts

The frontal syndrome reveals what conflict monitoring does by showing what happens when it catastrophically fails: behavior becomes a series of unchecked System 1 responses.

---

## Agent Implications

**Absence of an intrinsic FOR signal in LLMs:** Language models do not have a Feeling of Rightness in any direct sense. The equivalent of the FOR signal theoretically could be implemented as:
- Model-computed uncertainty estimates (perplexity, entropy of the predicted token distribution)
- Consistency checking (generating the same answer from multiple framings and comparing)
- Self-critique modules (generating a critique of an initial answer)

None of these is truly equivalent to the FOR as a real-time gating mechanism that triggers deeper deliberation before an answer is committed. The model produces an output in a single forward pass without an intermediate metacognitive checkpoint.

**Chain-of-thought as FOR supplement:** Requiring chain-of-thought reasoning imposes a structure where intermediate steps can be evaluated, which partially implements the FOR function — the model will sometimes self-correct within a chain of reasoning (noticing that a step contradicts a prior claim). But this correction depends on producing an explicit contradiction in text, not on a metacognitive monitoring signal operating independently of the object-level response.

**System-level conflict detection:** The agent memory system's human review stage implements system-level conflict monitoring: a human reviewer detects conflicts between knowledge files, between a file's claims and known facts, between a file's stated trust level and its evidential basis. This compensates for the agent's lack of intrinsic FOR monitoring.

**Load-monitoring as design principle:** Because monitoring degrades under cognitive load, designing sessions to minimize unnecessary cognitive load (Sweller's extraneous load) is also a metacognitive strategy — maintaining spare capacity for conflict detection. Loading unnecessary context files, imposing complex formatting requirements, and managing many competing goals simultaneously reduce the effective "FOR budget" available for quality monitoring.
