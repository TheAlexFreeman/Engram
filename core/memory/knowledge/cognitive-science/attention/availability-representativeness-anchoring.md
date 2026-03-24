---
created: '2026-03-20'
origin_session: core/memory/activity/2026/03/20/chat-004
source: agent-generated
last_verified: '2026-03-20'
trust: medium
related: attention-synthesis-agent-implications.md, dual-process-system1-system2.md, ../../social-science/behavioral-economics/kahneman-tversky-heuristics-biases.md
---

# Availability, Representativeness, and Anchoring Heuristics

## Overview

Kahneman and Tversky identified a systematic family of **cognitive heuristics** — rules of thumb that the cognitive system (System 1) uses to make probability estimates and judgments quickly. These heuristics are not random errors; they are predictable approximation strategies that exploit features of the environment that usually (but not always) correlate with the target quantity. Their failures are systematic, replicable, and culturally widespread.

The three most well-established are **availability**, **representativeness**, and **anchoring**. Each involves substituting a simpler question (easy to compute by System 1) for the target question (which requires effortful System 2 processing).

---

## Availability Heuristic

**Substitution:** "How frequent or probable is X?" → "How easily does an instance of X come to mind?"

**Tversky and Kahneman (1973):** Subjects estimated relative word frequencies based on how easily examples came to mind. Words beginning with 'K' were judged more frequent than words with 'K' as the third letter, despite the reverse being true — because searching memory by first-letter is easy, searching by third-letter is hard.

**When availability tracks frequency well:** Recent events, personally experienced events, and vivid events are cognitively available *and* genuinely salient. The heuristic is adaptive in environments where availability reliably indexes importance.

**When availability fails:**

- **Media-amplified rare risks:** Plane crashes and shark attacks are memorable and vivid; they dominate availability despite being statistically rare. Cardiovascular disease kills far more people than both combined, but it is not a newsworthy event — each instance is unremarkable. Availability produces risk overestimation for dramatic causes and underestimation for mundane ones.

- **Ease-of-imagination effects:** Slovic, Fischhoff, and Lichtenstein (1979) showed that people underestimate risks they can barely imagine (botulism) and overestimate risks they can easily imagine (tornadoes).

- **Availability cascade (Kuran & Sunstein, 1999):** Media attention increases an event's cognitive availability; this amplifies perceived risk, generates regulatory attention, which produces more media coverage — a self-sustaining feedback loop between availability and public concern, independent of actual risk.

**Agent relevance:** Training data availability acts like cognitive availability — topics and claims that are heavily represented in training data are more "available" to the model's associative retrieval. Obscure but important topics may be systematically underweighted because they appear in fewer training documents.

---

## Representativeness Heuristic

**Substitution:** "What is the probability that X belongs to category Y?" → "How closely does X resemble the prototype of Y?"

**Kahneman and Tversky (1972):** Subjects read a description of "Tom W." as intelligent, analytical, cold, and precise, and were asked to estimate the probability that Tom was studying computer science (vs. education, law, etc.). Subjects rated computer science as most probable despite it having very few graduate students (low base rate) — because Tom strongly resembled the stereotype.

**Failures of representativeness:**

**Base-rate neglect:** The probability of category membership depends on the base rate (prior probability) of that category as well as similarity. Bayes' theorem specifies the correct combination. Representativeness substitutes similarity for the full Bayesian calculation, systematically underweighting base rates.

Classic demonstration: A taxicab is involved in a hit-and-run. 85% of taxis are Blue, 15% Green. A witness identifies the cab as Green; the witness is 80% reliable in such conditions. Naive response: 80% chance it was Green (resemblance to witness's testimony). Bayesian answer: ~41% chance it was Green. Base rates are discounted (Kahneman & Tversky, 1973).

**Conjunction fallacy:** The probability of a conjunction (A ∧ B) cannot exceed the probability of either constituent. Yet when A ∧ B better matches a prototype than A alone, people judge P(A ∧ B) > P(A).

The "Linda problem" (Tversky & Kahneman, 1983): Linda is 31, outspoken, social justice activist. Is she more likely to be (a) a bank teller, or (b) a bank teller and feminist activist? ~87% of subjects choose (b), despite (b) being logically a subset of (a). Linda resembles the prototype of a feminist activist, and "bank teller AND feminist" is more representative than "bank teller" alone — overriding the logical constraint.

**Insensitivity to sample size:** System 1 treats small and large samples as equally representative. A coin producing 70% heads in 10 flips seems as surprising as 70% in 1,000 flips — intuition fails to account for sampling variability. This underlies many misinterpretations of statistics.

**Regression to the mean neglect:** Sports commentators attribute performance improvements after criticism to the criticism (counterfactual narrative) rather than regression to the mean (statistical). Exceptional performance on trial N is partly due to transient factors that regress on trial N+1.

---

## Anchoring and Adjustment Heuristic

**Core process:** When estimating an unknown quantity, people start from an **anchor value** (an initial number or cue) and adjust from it. Adjustment is typically insufficient — final estimates remain biased toward the anchor.

**Tversky and Kahneman (1974):** Subjects estimated percentages of African countries in the UN. Before estimating, a random number (e.g., 10 or 65) was spun on a wheel of fortune in their presence. Subjects who saw 10 estimated lower percentages (~25%) than those who saw 65 (~45%). The arbitrary, obviously random anchor contaminated the estimate.

**Mechanisms:**

1. **Insufficient adjustment:** People adjust until they reach a "plausible" value and stop — but stopping too early because the adjustment process is associated with effort (System 2 fatigue).

2. **Selective accessibility (Mussweiler & Strack, 2000):** The anchor activates anchor-consistent information from memory — information that confirms the anchor value — making anchor-consistent values more cognitively accessible and thus more available for estimation.

3. **Anchoring in negotiation:** First offers in negotiation strongly anchor final agreements. The party who sets the first price has a structural advantage even when the first price is arbitrary.

**Anchoring in expert judgment:** Legal sentencing: judges who rolled two dice showing high numbers recommended longer prison sentences than those who rolled low numbers (Englich, Mussweiler, & Strack, 2006) — even experienced experts with relevant domain knowledge are susceptible.

**Anchoring and LLMs:** When a query contains numerical values, the model's numerical outputs are pulled toward those values. When a query describes a position (e.g., "most economists would say X..."), the model's response is anchored toward that position. This is partially a training-data availability effect (anchor-consistent content is more represented) and partially a structural feature of attention over the input context.

---

## Practical Debiasing

Heuristics are resistant to debiasing because they operate automatically (System 1) and produce outputs that feel correct. Effective debiasing strategies:

1. **Consider the opposite:** Explicitly generating counter-arguments or alternative hypotheses disrupts anchor-consistent selective accessibility and representativeness-driven prototype matching.
2. **Actuarial methods over clinical judgment:** Mechanical combination of cues (weighted algorithms) consistently outperforms expert intuition in forecasting tasks — by bypassing heuristic availability and representativeness effects.
3. **Reference class forecasting (Kahneman & Lovallo, 1993):** Ask "What is the base rate for this type of project/outcome?" before forming any specific estimate. Forces base-rate information into the calculation.
4. **Pre-mortem analysis (Klein, 2007):** Assume the plan has failed and ask what went wrong — exploits imaginative availability to surface risks that prospective optimism suppresses.

---

## Agent Implications

The applicability of heuristic biases to LLM behavior is well-evidenced:
- Availability: training corpus coverage → topic frequency biases
- Representativeness: prototype matching in classification tasks → statistical neglect
- Anchoring: numerical and positional values in prompts → estimate drift

Designing prompts and knowledge file retrieval pipelines to include explicit reference class information (base rates), contrary evidence, and anchor-disrupting framing reduces heuristic contamination in model outputs.
