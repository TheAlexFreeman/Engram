---
created: '2026-03-27'
last_verified: '2026-03-27'
origin_session: core/memory/activity/2026/03/27/chat-005
source: agent-generated
trust: medium
related: pac-bayes-generalization-bounds.md, implicit-regularization-sgd-flat-minima.md, neural-tangent-kernel-infinite-width.md, grokking-delayed-generalization.md, in-context-learning-theory.md, transfer-learning-theory-domain-adaptation.md, learning-theory-synthesis.md
---

# Learning Theory — Subdomain Summary

This subdomain (`mathematics/learning-theory/`) covers modern generalization theory and the emerging theory of large-model learning, extending the classical PAC framework treated in `mathematics/information-theory/` to the overparameterized and in-context regimes that define contemporary AI.

**Prerequisites**: `../information-theory/pac-learning-sample-complexity.md`, `../information-theory/vc-dimension-fundamental-theorem.md`, `../information-theory/compression-generalization-connection.md`, `../information-theory/double-descent-benign-overfitting.md`.

---

## Files in This Subdomain

| File | One-Line Description |
|------|----------------------|
| `pac-bayes-generalization-bounds.md` | McAllester's PAC-Bayes theorem: non-vacuous generalization bounds via KL divergence between posterior and prior over hypotheses |
| `implicit-regularization-sgd-flat-minima.md` | SGD as implicit regularizer: convergence to flat minima, edge-of-stability, SAM, and the debate over whether sharpness causally drives generalization |
| `neural-tangent-kernel-infinite-width.md` | NTK: infinite-width networks behave like kernel machines; lazy vs feature-learning regimes; limitations and current status |
| `grokking-delayed-generalization.md` | Power et al. grokking: delayed generalization after memorization; mechanistic accounts; connections to double descent and phase transitions |
| `in-context-learning-theory.md` | ICL as implicit Bayesian inference, gradient descent in the residual stream, and meta-learning; empirical limits including order and label sensitivity |
| `transfer-learning-theory-domain-adaptation.md` | Ben-David domain adaptation bounds, covariate shift, importance weighting, catastrophic forgetting, EWC, and PEFT (LoRA/adapters) theory |
| `learning-theory-synthesis.md` | Full synthesis: arc from classical PAC through overparameterization puzzle to contemporary accounts; open questions; AI frontier connections |

---

## Recommended Reading Order

**Theoretical track** (for understanding the mathematical structure):
1. `pac-bayes-generalization-bounds.md` — starts from where `pac-learning-sample-complexity.md` leaves off
2. `implicit-regularization-sgd-flat-minima.md` — connects optimization to generalization
3. `neural-tangent-kernel-infinite-width.md` — the kernel regime where theory is tractable
4. `grokking-delayed-generalization.md` — a phenomenon that tests all three prior accounts
5. `learning-theory-synthesis.md` — synthesizes the full arc

**Applied track** (for understanding how to train and adapt large models):
1. `in-context-learning-theory.md` — explains few-shot prompting from first principles
2. `transfer-learning-theory-domain-adaptation.md` — explains fine-tuning and PEFT from first principles
3. `learning-theory-synthesis.md` — design implications for agent training

---

## Cross-References to Other Domains

**Prerequisites** (information-theory/):
- `../information-theory/pac-learning-sample-complexity.md` — classical PAC framework; prerequisite for pac-bayes file
- `../information-theory/vc-dimension-fundamental-theorem.md` — VC theory; prerequisite for understanding why PAC-Bayes was needed
- `../information-theory/compression-generalization-connection.md` — MDL and PAC-Bayes are dual formulations; read together
- `../information-theory/double-descent-benign-overfitting.md` — empirical anomaly that motivated this subdomain

**Downstream** (ai/frontier/):
- `../../ai/frontier/architectures/scaling-laws-chinchilla.md` — empirical learning theory; this subdomain provides theoretical grounding
- `../../ai/frontier/architectures/synthetic-data-self-improvement.md` — self-improvement pipelines exploit ICL and transfer learning
- `../../ai/frontier/reasoning/benchmarking-reasoning.md` — emergent abilities are the phase-transition side of learning theory
- `../../ai/frontier/governance/responsible-scaling-policies-anthropic-openai.md` — absence of RLHF generalization theory is a governance gap

**Lateral** (optimization/):
- `../optimization/gradient-descent-convergence.md` — the optimization counterpart to implicit regularization
