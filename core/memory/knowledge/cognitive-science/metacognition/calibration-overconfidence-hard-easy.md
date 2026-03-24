---
created: '2026-03-20'
origin_session: core/memory/activity/2026/03/20/chat-004
source: agent-generated
last_verified: '2026-03-20'
trust: medium
related: ../../rationalist-community/ai-discourse/prediction-failures/timeline-calibration-and-paradigm-surprise.md, calibrated-uncertainty-communication.md, metacognition-synthesis-agent-implications.md
---

# Calibration, Overconfidence, and the Hard-Easy Effect

## The Calibration Curve

**Calibration** refers to the alignment between stated confidence levels and actual accuracy rates. A perfectly calibrated forecaster who says "I'm 70% sure" on a large number of distinct claims is correct 70% of the time across those claims.

**The calibration curve** plots:
- X-axis: stated probability/confidence level (0–100%)
- Y-axis: actual proportion correct at each confidence level

**Perfect calibration:** The curve is the diagonal (stated = actual).

**Overconfidence:** The curve lies *below* the diagonal — actual accuracy is lower than stated confidence. When someone says "90% sure," they are correct only 70% of the time (for example).

**Underconfidence:** The curve lies *above* the diagonal — actual accuracy is higher than stated confidence. When someone says "50% sure," they are correct 70% of the time.

**Resolution vs. calibration:** Calibration measures absolute accuracy of confidence levels. Resolution (discrimination) measures the ability to sort items into correct-vs.-incorrect groups, regardless of absolute levels. These are separate dimensions: a forecaster can have perfect resolution (always ranks their most certain correct items above their uncertain ones) while being systematically overconfident in absolute levels.

---

## The Overconfidence Effect

Overconfidence is the most replicated finding in judgment and decision-making research. Its general form: stated confidence exceeds actual accuracy across many domains, samples, and populations.

**Classic demonstration (Lichtenstein & Fischhoff, 1977):** Subjects answered two-alternative general knowledge questions and rated their confidence in each answer (50–100%). Aggregated actual accuracy was consistently below aggregated stated confidence for most subjects.

**Overconfidence in specific domains:**
- General knowledge trivia questions: moderate overconfidence
- Medical diagnosis (clinicians): moderate overconfidence even with experience
- Weather forecasting: relatively well calibrated (professionals with continuous feedback)
- Legal outcome prediction (lawyers): substantial overconfidence
- Investment returns (fund managers): substantial overconfidence
- Own planning estimates (planning fallacy): robust overconfidence — projects consistently take longer and cost more than predicted

**Why overconfidence is so pervasive:**
1. Confirmation bias in evidence search — we seek confirming evidence, not disconfirming.
2. Narrative coherence effects — our own reasoning sounds convincing to us.
3. Lack of feedback — in many domains, we do not get reliable outcome data that would recalibrate confidence.
4. Social incentives for confidence expression — expressing uncertainty is often penalized socially, selecting for overconfidence in expressed beliefs even when internal uncertainty is higher.

---

## The Hard-Easy Effect

**Lichtenstein and Fischhoff (1977)** first systematically documented that the direction of miscalibration depends on task difficulty:

**Easy items** (accuracy >80%): Slight **underconfidence** — stated confidence is slightly lower than actual accuracy. People know the easy things well but modestly understate how well they know them.

**Hard items** (accuracy <60%): Substantial **overconfidence** — stated confidence substantially exceeds actual accuracy. People feel they know hard things they actually don't know.

**Implication:** The hard-easy effect means that overconfidence is *worst* exactly where it is most dangerous: in difficult, high-stakes domains where actual accuracy is low. If someone is consistently overconfident on hard questions, they are precisely wrong when the cost of being wrong is highest.

**Domain specificity:** Expertise in a domain does not simply reduce overconfidence — it reduces overconfidence for items *within* the domain of expertise and has limited generalization. Expert physicians are well-calibrated on diagnostic questions within their specialty; they may be overconfident on questions at the boundary of their expertise or in adjacent fields.

---

## The Brier Score: A Proper Scoring Rule

**Calibration metrics:**

**Expected Calibration Error (ECE):** Average deviation between stated confidence and accuracy in bins — simple but biased by bin boundaries.

**Brier Score (Brier, 1950):**

$$B = \frac{1}{N} \sum_{i=1}^{N} (f_i - o_i)^2$$

where $f_i$ is the stated probability and $o_i \in \{0, 1\}$ is the observed outcome (1 = correct, 0 = incorrect).

A **proper scoring rule**: a scoring rule is proper if and only if the expected score is minimized (Brier) or maximized (log score) by reporting your true subjective probability — it creates the right incentive to be honest. You cannot improve your expected Brier score by distorting your stated probability away from your true belief.

Brier score = 0: perfect. Brier score = 0.25: baseline (always saying 50%). Brier score > 0.25: worse than uniform uncertainty. Good forecasters achieve B ~ 0.10–0.15 on difficult geopolitical forecasting questions.

**Log score / Cross-entropy:**

$$LS = -\frac{1}{N}\sum_{i=1}^{N} o_i \log f_i + (1-o_i) \log(1-f_i)$$

Penalizes confident wrong answers much more severely than the Brier score — assigns infinite penalty for P(correct) = 0 when the answer is correct. More demanding than Brier; used in machine learning (cross-entropy loss).

---

## Calibration in Machine Learning

**Temperature scaling (Guo et al., 2017):** Modern neural networks (including large pre-trained models) are often badly calibrated — their softmax output probabilities (their "confidence") are too high (overconfident) especially for in-distribution examples. Temperature scaling divides logits by a temperature parameter T before softmax; T > 1 flattens the distribution, reducing overconfidence; T < 1 sharpens it.

**Platt scaling:** A logistic regression model fitted on a held-out calibration set, mapping model output scores to calibrated probabilities. Works well for SVMs and binary classifiers.

**Reliability diagrams:** Bin predictions by confidence level; plot mean confidence vs. mean accuracy for each bin; the resulting diagram shows where the model is over- vs. under-confident.

**Key finding (Guo et al., 2017):** Larger, more accurate models tend to be *more* overconfident on their softmax probabilities, not less — accuracy improves but calibration degrades. Accuracy and calibration are not the same thing and do not track each other reliably.

---

## Agent Implications

**Trust levels should reflect calibration, not fluency:**
The key lesson: confidence-sounding outputs are not calibration signals. The hard-easy effect implies the agent will be *most* overconfident in domains where it is *least* accurate (obscure, niche, or rapidly evolving topics). The `trust: medium` level on agent-generated files should not be elevated to `trust: high` based solely on the fluency or articulateness of the output.

**Calibration by domain:**
Different knowledge domains have effectively different "hardness levels":
- **Easy (well-calibrated agent outputs likely):** Well-represented mainstream topics, definitions, canonical procedures
- **Hard (overconfidence most likely):** Recent events, niche research areas, contested claims, interdisciplinary synthesis, long-tail knowledge

The review queue and human verification process should weight calibration-risk by domain: hard-domain files warrant more skeptical review than easy-domain files.

**Proper scoring of the trust system:**
An ideal trust system would function as a proper scoring rule — rewarding honest uncertainty expression and penalizing both overconfidence (trust: high when accuracy is low) and epistemic cowardice (trust: low when the content is actually reliable and high-value). The current trust system approximates this but lacks actuarial calibration; it relies on human judgment rather than scored outcome tracking.
