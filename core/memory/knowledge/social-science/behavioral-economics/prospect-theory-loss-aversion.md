---
created: '2026-03-21'
last_verified: '2026-03-21'
origin_session: manual
source: agent-generated
trust: low
---

# Prospect Theory and Loss Aversion

## Overview

Prospect theory, developed by Daniel Kahneman and Amos Tversky in their landmark 1979 *Econometrica* paper "Prospect Theory: An Analysis of Decision under Risk," is the most influential descriptive theory of choice under uncertainty. It replaces expected utility theory (EUT) as an account of how people actually make decisions involving risk — not how a perfectly rational agent should decide. The theory's core innovations are: (1) reference dependence — outcomes are evaluated as gains or losses relative to a reference point, not as absolute wealth levels; (2) loss aversion — losses loom larger than equivalent gains; (3) the S-shaped value function — diminishing sensitivity in both gain and loss domains; and (4) probability weighting — people overweight small probabilities and underweight moderate-to-large ones.

---

## Expected Utility Theory and Its Failure

Von Neumann-Morgenstern expected utility theory (EUT) holds that rational agents maximize $E[U(x)] = \sum_i p_i \cdot u(x_i)$, where $u$ is a monotone utility function over final wealth states and $p_i$ are objective probabilities. EUT makes several predictions: choices depend only on final wealth, not on how outcomes are framed; people treat equal probabilities symmetrically regardless of magnitude; preferences satisfy transitivity, continuity, and independence axioms.

**Violations (the Allais paradox and others):**
- **Allais paradox (1953):** People prefer a certain $1M to a lottery offering 89% chance of $1M, 10% of $5M, 1% of nothing — violating the independence axiom when the alternative is modified consistently.
- **Reflection effect:** People are risk-*averse* over gains (prefer certain $500 to 50% chance of $1000) but risk-seeking over losses (prefer 50% chance of losing $1000 to certain loss of $500). EUT with a concave utility function cannot accommodate both.
- **Isolation effect:** When choices are presented in different frames (a two-stage lottery vs its equivalent single-stage form), different choices result despite mathematical equivalence.

---

## The Core Features of Prospect Theory

### 1. Reference Dependence

Value is assigned to *changes* relative to a reference point (typically the status quo or an expectation), not to absolute levels of wealth. The same outcome can be experienced as a gain or a loss depending on the reference:

- Receiving $500 when you expected $0 → gain
- Receiving $500 when you expected $1000 → loss

This explains framing effects: "90% fat-free" vs "10% fat" triggers different evaluations of the same fact.

### 2. The S-Shaped Value Function

The value function $v(x)$ is:
- **Concave for gains** — diminishing sensitivity; going from $0 to $100 is more valuable than $900 to $1000
- **Convex for losses** — diminishing sensitivity in losses; $0 to -$100 loss is worse than -$900 to -$1000 loss

$$v(x) = \begin{cases} x^\alpha & \text{if } x \geq 0 \\ -\lambda(-x)^\beta & \text{if } x < 0 \end{cases}$$

where $\alpha, \beta \approx 0.88$ and $\lambda \approx 2.25$ (Tversky & Kahneman 1992).

### 3. Loss Aversion

The most empirically robust finding: **losses are approximately twice as painful as equivalent gains are pleasurable** ($\lambda \approx 2-2.5$). People typically require ~$200 to offset a 50% chance of losing $100 in a mixed gamble.

**Consequences:**
- **Endowment effect:** People demand more to give up something they own than they would pay to acquire it (Thaler 1980). A mug given to a subject is immediately valued 2-3× its purchase price.
- **Status quo bias:** Loss aversion makes the current state of affairs feel "safe" — deviations risk losses. Opt-out vs opt-in defaults have large behavioral effects.
- **Disposition effect:** Investors hold losing stocks too long (hoping to avoid realizing a loss) and sell winning stocks too early (capturing a gain before it disappears).

### 4. Probability Weighting

People do not treat stated probabilities at face value. The weighting function $\pi(p)$ is:
- **Overweighting of small probabilities:** $\pi(0.01) > 0.01$ — people are attracted to lottery tickets and terrified of rare catastrophes.
- **Underweighting of moderate/large probabilities:** $\pi(0.99) < 0.99$ — the certain-outcome preference disappears before true certainty.
- **Subadditivity:** $\pi(p) + \pi(1-p) < 1$ — small chances on both sides of a gamble are both overweighted simultaneously.

This explains why people simultaneously buy insurance (risk-averse over losses from unlikely catastrophes) and lottery tickets (risk-seeking over gains from unlikely windfalls) — in tension with EUT's requirement of consistent risk preferences.

---

## Cumulative Prospect Theory (1992)

Tversky and Kahneman extended the 1979 theory in 1992 to handle gambles with more than two outcomes and to avoid violations of stochastic dominance. Cumulative prospect theory (CPT) applies the weighting function to *cumulative* distributions rather than individual probabilities, maintaining monotonicity. CPT is the standard formulation used in economics today.

---

## Behavioral Implications

### Endowment Effect and Market Anomalies

Thaler (1980) coined "endowment effect" for the loss-aversion-driven overvaluation of owned goods. Classic demonstration: undergraduate students given a mug demand ~$5 to sell it but are willing to pay only ~$2.50 to acquire it. Markets should arbitrage this away, but loss aversion in real asset markets (housing, stocks) produces documented inefficiencies.

### Status Quo Bias in Policy

Johnson & Goldstein (2003): organ donation rates differ dramatically by country not due to culture but due to default — opt-out countries (Spain, Austria) have 85-90%+ donation rates vs opt-in countries (USA, Germany) at 15-30%. Loss aversion makes the active decision to change the status quo feel like a risk.

### Mental Accounting

Thaler (1985): people segregate financial decisions into mental accounts rather than treating wealth as fungible. A windfall gain is spent differently than equivalent regular income; a bonus is spent more freely than salary. Loss aversion at the account level produces suboptimal portfolio management.

### Negotiations and Anchoring

Offers in negotiations serve as loss aversion anchors. Concessions are experienced as losses; gains from an agreement are discounted. This predicts systematic inefficiencies in negotiated outcomes.

---

## Connection to Cultural Evolution and Knowledge Transmission

Loss aversion is a deep feature of human motivation with direct implications for how ideas and practices spread:

1. **Risk of change:** When existing practices or beliefs are the reference point, any proposed change is framed as a potential loss. This produces conservatism even when change would be beneficial — a mechanism for cultural inertia. See `boyd-richerson-dual-inheritance.md`.

2. **Negativity bias in content transmission:** Threatening, alarming, or loss-framed information is disproportionately memorable and transmissible — a loss-aversion-driven content bias. Media and political messaging exploit this systematically.

3. **Sunk cost fallacy:** Because losses from past investments are psychologically salient, people continue projects that should be abandoned (escalation of commitment). This applies at both individual and institutional levels.

4. **Framing in argument:** The same policy position framed as "preventing job losses" vs "creating jobs" elicits different support even when the outcomes are identical. Cultural institutions that control framing shape preferences via reference-point manipulation.

---

## Implications for the Engram System

- **Calibration:** Loss aversion can distort probability assignment — unlikely catastrophes receive excessive weight. Structured calibration practices (explicitly separating probability from value) are one corrective.
- **Intellectual conservatism:** When updating beliefs, the loss of a previously held position is psychologically felt as a loss. This produces under-updating relative to Bayesian norms — the rationalist "updating on evidence" ideal is in direct tension with loss aversion.
- **Framing of arguments:** When synthesizing conflicting views, awareness of loss-framing effects guards against rhetorical asymmetry (evaluating ideas framed as "defending" vs "losing" differently).

---

## Related

- [kahneman-tversky-heuristics-biases.md](kahneman-tversky-heuristics-biases.md) — The broader heuristics-and-biases program; dual-process framework
- [thaler-sunstein-nudge-theory.md](thaler-sunstein-nudge-theory.md) — Policy applications: defaults, mental accounting, choice architecture
- [bounded-rationality-simon.md](bounded-rationality-simon.md) — Bounded rationality as earlier framing; satisficing vs loss aversion
- [behavioral-economics-rationality-synthesis.md](behavioral-economics-rationality-synthesis.md) — Rationality debate synthesis
- [transmission-biases-cognitive-attractors.md](../cultural-evolution/transmission-biases-cognitive-attractors.md) — Content biases; loss-framed content spreads faster
- [idea-fitness-vs-truth.md](../cultural-evolution/idea-fitness-vs-truth.md) — Why fitness-for-spread ≠ truth; loss aversion as a fitness-boosting content property
