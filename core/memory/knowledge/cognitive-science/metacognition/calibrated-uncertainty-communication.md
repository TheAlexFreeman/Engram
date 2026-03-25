---
created: '2026-03-20'
origin_session: core/memory/activity/2026/03/20/chat-004
source: agent-generated
last_verified: '2026-03-20'
trust: medium
related:
  - memory/knowledge/cognitive-science/metacognition/metacognition-synthesis-agent-implications.md
  - memory/knowledge/cognitive-science/metacognition/calibration-overconfidence-hard-easy.md
  - memory/knowledge/cognitive-science/metacognition/conflict-monitoring-feeling-of-rightness.md
  - memory/knowledge/cognitive-science/metacognition/dunning-kruger-effect.md
  - memory/knowledge/cognitive-science/metacognition/feeling-of-knowing-tip-of-tongue.md
---

# Calibrated Communication of Uncertainty

## The Problem of Uncertainty Expression

Many systems — forecasters, physicians, scientists, AI assistants — must communicate their uncertainty to agents who will make decisions based on those communications. How uncertainty is expressed substantially affects whether decision-makers use it effectively.

Two failure poles:
- **Overconfidence:** Stating too-high confidence levels, suppressing acknowledged uncertainty, presenting uncertain claims as certain facts
- **Epistemic cowardice:** Expressing vague, non-falsifiable hedges to avoid being wrong on record; refusing to commit to any probability estimate; using language that preserves deniability regardless of outcome

Between these poles is the goal: **calibrated communication** — probabilistic expressions that convey exactly the epistemic state of the speaker, no more and no less.

---

## Tetlock's Superforecasters

Philip Tetlock's multi-decade research program on expert political forecasting (summarized in *Superforecasting: The Art and Science of Prediction*, 2015, with Dan Gardner) identified a subpopulation of amateur forecasters ("superforecasters") who dramatically outperform:
- Random chance
- Dart-throwing across possible outcomes
- Average amateur forecasters
- Domain experts
- Intelligence analysts

**Characteristics of superforecasters:**

**Numerical precision:** Superforecasters express probabilities as numeric percentages (37%, 72%, 89%) rather than verbal hedges ("possible," "likely," "probable"). Verbal hedges are processed differently by different readers (one person's "likely" is another's 60%; another's 80%); numeric expressions have shared interpretations. Superforecasters hold themselves accountable to numbers.

**Decomposition:** Complex questions are broken into tractable sub-questions. "Will country X have a financial crisis within 2 years?" is decomposed: What are the base rates for financial crises in similar countries? What is the current state of X's fiscal indicators? What is the probability of external shocks? Each sub-question is separately estimated and combined (often formally, via Bayesian reasoning).

**Bayesian updating:** When new information arrives, superforecasters update their probabilities proportionally to the evidential value of the information — neither ignoring it (anchoring) nor overreacting to it (availability-driven over-updating).

**Epistemic humility and outside view:** Starting with the base rate (outside view) before incorporating specific case information (inside view); weighting base rates seriously; actively searching for disconfirming evidence.

**Track record awareness:** Superforecasters maintain explicit calibration records — they track their accuracy over time and use it to recalibrate their confidence levels. Accountability to outcomes is integral.

---

## Epistemic Cowardice and Vague Hedges

**Epistemic cowardice** (Philip Tetlock's term): The deliberate use of vague, ambiguous, or hedged language to protect oneself from being wrong — not from genuine uncertainty but from a desire to be unaccountable.

**Example linguistic markers of epistemic cowardice:**
- "It is possible that..." (covers everything from 1% to 90%)
- "Some analysts believe..." (who? what probability?)
- "There are arguments on both sides..." (without indicating which side is better supported or by how much)
- "The situation is developing..." (postponing commitment indefinitely)
- "I wouldn't put a number on it..." (refusing the discipline of precision)

**Why epistemic cowardice is a failure mode, not epistemic humility:** The coward knows they are uncertain but expresses this uncertainty in a way that is immune to falsification — no outcome can reveal the coward as having been wrong, because the expressed claim committed to nothing. This is not epistemic humility; it is epistemic evasion. Genuine humility expresses precise uncertainty: "I'm about 30% confident in X" — this is falsifiable and allows calibration.

---

## Proper Scoring Rules as Incentive Structure

**Proper scoring rules** create the incentive to express genuine uncertainty: "A scoring rule is proper if and only if the expected score is optimal when the forecaster reports their true belief."

**Brier Score (see `calibration-overconfidence-hard-easy.md`):**

$$B = \frac{1}{N}\sum_{i=1}^{N}(f_i - o_i)^2$$

Minimized (in expectation) by reporting true subjective probability $f_i = P(\text{event}_i)$. Cannot be gamed by distorting toward 50% or toward 0/1.

**Log Score / Cross-Entropy:**

$$LS = -\frac{1}{N}\sum_{i=1}^{N} [o_i \log f_i + (1-o_i)\log(1-f_i)]$$

More sensitive to extreme miscalibration (assigns very high penalty to high confidence combined with being wrong). Minimized by stating true probability.

**Both rules make epistemic cowardice costly:** A forecaster who says 50% when they believe 80% gets a worse expected score than one who says 80%. The cowardly 50% produces neither true credit when right nor calibration learning when wrong.

---

## The Communication Design Problem

How should uncertainty be expressed to users who will make decisions based on agent output?

**Verbal probability expressions and calibration:**
Research on verbal probability expressions (e.g., "likely" interpreted as 67% on average, with standard deviation ~10%). The range of interpretation across people and cultures is wide enough to make verbal expressions unreliable for consequential decisions. Numeric probabilities are preferred for high-stakes communication.

**Confidence intervals vs. point estimates:** A point estimate with a confidence interval ("X is approximately 45, with a 90% confidence interval of 35–55") carries more information than either alone — the point estimate conveys the central expectation; the interval conveys uncertainty.

**Decision-relevant framing:** Uncertainty should be expressed relative to the decision threshold. If the decision is "should we act on this claim?", the relevant uncertainty expression is "How confident are we that the claim is true enough to act on?" — not the general epistemic state.

---

## Implications for Knowledge File Design and the Trust System

**`trust:` as a calibrated uncertainty signal:** The trust level on a knowledge file is an uncertainty expression. To function as a proper scoring rule, the field should express a genuine probability estimate of file accuracy, not a social convention or a hedge.

**Proposed operational calibration:**
- `trust: high` → the rater believes ≥85% of claims in the file are accurate
- `trust: medium` → the rater believes 60-85% of claims are accurate
- `trust: low` → the rater believes <60% accuracy; content may be systematically biased or wrong

This operationalization makes trust levels falsifiable (in principle) and creates accountability for the assessment.

**Distinguishing epistemic states in agent outputs:**
Knowledge files and agent responses should distinguish:
- **Established / well-evidenced:** Core scientific consensus, multiply-replicated findings, foundational definitions
- **Inferred / plausibly correct:** Claims consistent with evidence but not directly tested or sourced; internally coherent synthesis
- **Tentative / speculative:** Novel connections, extrapolations, claims without strong evidence but with plausible reasoning

Using explicit linguistic markers for each level (rather than presenting all three with the same authoritative tone) is the agent-output equivalent of calibrated uncertainty communication.

**Superforecasting principles for knowledge accumulation:**
- Decompose complex claims into researchable sub-claims
- Start with the base rate (what's the reliability of agent-generated content in this domain?)
- Update on specific evidence (human verification, cross-references to reliable sources)
- Maintain an explicit calibration record (system access logs and helpfulness ratings approximate this)
