---
created: '2026-03-21'
last_verified: '2026-03-21'
origin_session: manual
source: agent-generated
trust: low
---

# Kahneman & Tversky: Heuristics and Biases

## Overview

Daniel Kahneman and Amos Tversky launched the heuristics-and-biases research program in a landmark 1974 *Science* paper, demonstrating that human judgment under uncertainty relies on cognitive shortcuts (heuristics) that are generally useful but produce systematic, predictable errors (biases). Their work fundamentally challenged the assumption of homo economicus — the idealized rational agent maximizing expected utility — and established behavioral economics as a discipline. The program culminates in Kahneman's *Thinking, Fast and Slow* (2011), which reorganizes the findings under the dual-process (System 1/System 2) framework.

---

## The Three Core Heuristics

### 1. Availability Heuristic

People judge the probability of an event by how easily an example comes to mind. If instances are cognitively available — recent, vivid, emotionally salient — the event seems frequent or likely.

**Key demonstrations:**
- *Frequency of death by cause:* Dramatic causes (plane crashes, shark attacks) are overestimated; mundane causes (heart disease, diabetes) are underestimated — because dramatic events are over-represented in news and memory.
- *Letter frequency task:* People judge letters that appear in a word's first position more frequent than letters in the third position, because it is easier to search memory by word-initial letters.

**Bias produced:** Availability bias — probability distorted toward memorable rather than actual base rates. Drives excessive insurance purchases after disasters, stock market overreaction to salient news.

**Connection to cultural evolution:** Availability functions as a mechanism for *content bias* — salient, emotional, and easily memorable content spreads faster regardless of truth value. See `idea-fitness-vs-truth.md` and `transmission-biases-cognitive-attractors.md`.

### 2. Representativeness Heuristic

People judge the probability that X belongs to category Y by how much X resembles the prototype of Y, rather than by base rates or probability calculus.

**Key demonstrations:**
- *Linda problem:* Linda is described as concerned with social justice. "Linda is a bank teller AND a feminist" is judged more probable than "Linda is a bank teller" — a conjunction fallacy. Representativeness overwhelms the logic that A∧B ≤ P(A).
- *Base rate neglect:* Given that 15 of 100 engineers are engineers (vs 85 lawyers), and a description that matches engineer stereotypes, subjects assign 90%+ probability to "engineer" — ignoring the base rate.
- *Gambler's fallacy:* After string of reds in roulette, people expect black, because a long red run "doesn't look random."

**Bias produced:** Stereotyping, conjunction fallacy, base-rate neglect, overconfidence in predictions from non-predictive descriptions.

### 3. Anchoring and Adjustment Heuristic

People estimate unknown quantities by starting from an initial value (anchor) and adjusting, but adjustment is typically insufficient — estimates remain too close to the anchor.

**Key demonstrations:**
- *Wheel of fortune:* A rigged wheel stopping at 10 or 65 influenced subsequent estimates of African countries' UN membership percentage — a striking case of anchoring from an obviously arbitrary number.
- *Real-estate valuation:* Both experienced agents and novice students anchor on listing price when estimating property value, even when told the listing is arbitrary.

**Bias produced:** Framing effects, excessive anchoring on first offers in negotiation, price anchoring in retail.

---

## The Heuristics-and-Biases vs. Gigerenzen Debate

Gerd Gigerenzen and colleagues mounted a major critique: the heuristics-and-biases program misidentifies adaptive cognitive processes as errors. Key arguments:

1. **Ecological rationality:** Heuristics are not irrational — they are well-adapted to real-world information environments. Fast-and-frugal heuristics (take-the-best, recognition heuristic) often outperform elaborate statistical models when data is limited.
2. **Natural frequencies:** Many supposedly robust biases (e.g., base-rate neglect) disappear when problems are stated in natural frequency format rather than probabilities — suggesting the problem format, not cognition, is the bug.
3. **Task environment matters:** What counts as a bias depends on what the correct response is, which requires specifying the task environment and the fitness measure.

**Kahneman-Tversky response:** The biases are real in every-day probability-judgment tasks relevant to medical diagnosis, legal reasoning, financial decisions, and policy. The dispute is largely about what counts as "rational" in what contexts. See `bounded-rationality-simon.md` for Simon's earlier framing.

---

## Dual-Process Framework (System 1 / System 2)

Kahneman synthesized the heuristics-and-biases findings under a dual-process architecture in *Thinking, Fast and Slow*:

| Feature | System 1 (fast) | System 2 (slow) |
|---------|----------------|----------------|
| Processing | Automatic, parallel | Deliberate, serial |
| Effort | Low | High |
| Control | Involuntary | Voluntary |
| Examples | Face recognition, intuitions, heuristics | Logical reasoning, math, careful deliberation |

The core claim: System 1 does most of the work; System 2 is lazy and largely endorses System 1's outputs unless prompted to intervene. Biases arise when System 1 heuristics (fast, efficient, but domain-general) are applied to problems that require System 2 reasoning (probability, statistics, formal logic).

**Critique:** The System 1/2 framework is descriptively useful but theoretically underspecified — "System 2" is not a unified module but a grab-bag of diverse deliberative capacities. Stanovich & West (who named the distinction) and Evans note it is a characterization, not a mechanistic model.

---

## Cognitive Biases: A Partial Taxonomy

Beyond the three heuristics, the program identified dozens of specific biases:

- **Framing effect:** Logically equivalent choices presented differently elicit different preferences (gains vs losses frame in medical decisions).
- **Status quo bias / endowment effect:** People over-value what they already have; keeping the default is preferred regardless of its quality.
- **Overconfidence:** People's confidence intervals are too narrow; 90% confidence intervals contain the true answer only ~50% of the time.
- **Planning fallacy:** Plans are systematically too optimistic in cost, time, and risk.
- **Hindsight bias:** After learning an outcome, people overestimate how predictable it was.
- **Affect heuristic:** Emotional valence (liking/disliking) serves as a substitute for probability or risk judgment.

---

## Implications for the Engram System

The heuristics-and-biases program directly informs several recurring concerns in the Engram knowledge base:

1. **Availability as content bias:** The cultural evolution literature describes *content biases* — preferential transmission of easily remembered, emotionally resonant content. The availability heuristic provides the cognitive mechanism: memorable content is judged more probable/important, so it spreads and gets repeated. See `transmission-biases-cognitive-attractors.md`.

2. **Representativeness and pattern-matching in AI reasoning:** LLMs engage in something like representativeness — generating outputs that *look like* good answers (fit the prototype of a correct response) without reliable calibration. This is relevant to `llms-cultural-evolution-mechanism.md`.

3. **Anchoring in intellectual work:** When reading a new argument, the first framing encountered anchors subsequent evaluation. Engram's structured cross-referencing is partly a device to expose anchoring: presenting alternative frames before forming judgments.

4. **Overconfidence and calibration:** The rationalist community's emphasis on calibration (assigning accurate probability to beliefs) is a direct response to overconfidence bias. See `cognitive-metacognition-calibration-research.md` plan.

5. **Debiasing:** Knowing about biases doesn't automatically eliminate them (the "bias blind spot"). Structured protocols (pre-mortem, reference class forecasting, Fermi estimation) offer partial debiasing. System 2 interventions help, but require sustained motivation.

---

## Related

- [prospect-theory-loss-aversion.md](prospect-theory-loss-aversion.md) — Kahneman & Tversky's formal theory of choice under risk
- [bounded-rationality-simon.md](bounded-rationality-simon.md) — Herbert Simon's earlier concept; contrast with K&T's bias framing
- [thaler-sunstein-nudge-theory.md](thaler-sunstein-nudge-theory.md) — Policy applications of heuristics/biases research
- [behavioral-economics-rationality-synthesis.md](behavioral-economics-rationality-synthesis.md) — Synthesis and rationality debate
- [transmission-biases-cognitive-attractors.md](../cultural-evolution/transmission-biases-cognitive-attractors.md) — Conformist, content, and prestige biases in cultural transmission
- [idea-fitness-vs-truth.md](../cultural-evolution/idea-fitness-vs-truth.md) — When ideas spread for fitness rather than truth
- [social-psychology-transmission-biases-synthesis.md](../social-psychology/social-psychology-transmission-biases-synthesis.md) — Social psychology grounding for transmission biases
