---
source: agent-generated
origin_session: core/memory/activity/2026/03/27/chat-001
created: 2026-03-27
trust: medium
type: scope-note
plan: learning-theory-generalization-research
phase: orientation
---

# Learning Theory & Generalization Research — Scope Note

## Purpose

Define the boundaries, target files, and cross-reference map for a new `mathematics/learning-theory/` subdomain that covers modern generalization theory and the emerging theory of large-model learning.

## Existing coverage audit

### What already covers learning theory

1. **PAC learning** (`information-theory/pac-learning-sample-complexity.md`): rigorous treatment of the PAC framework (Valiant 1984), sample complexity for finite and infinite hypothesis classes, agnostic PAC learning. Trust: high. This is the classical starting point — the new PAC-Bayes file should explicitly build on this as the classical predecessor.

2. **VC dimension** (`information-theory/vc-dimension-fundamental-theorem.md`): shattering, growth function, Sauer-Shelah lemma, the Fundamental Theorem of Statistical Learning (PAC-learnability ↔ finite VC dimension). Trust: high. The new NTK and implicit-regularization files should note where VC theory fails (overparameterized regime) and why post-VC theory was needed.

3. **Compression-generalization** (`information-theory/compression-generalization-connection.md`): the central thesis that compression and generalization are the same thing; MDL, PAC-Bayes, and information bottleneck perspectives. Trust: high. This is the strongest connection — it already introduces PAC-Bayes bounds in an information-theoretic framing. The new PAC-Bayes file should go deeper on the bound mechanics and applications, not re-derive the connection to MDL.

4. **Double descent** (`information-theory/double-descent-benign-overfitting.md`): Belkin et al. 2019 double descent, Nakkiran et al. three forms, benign overfitting (Bartlett et al. 2020). Trust: high. This is the motivating anomaly — the classical U-curve breaks in the overparameterized regime, creating the need for the new files (PAC-Bayes, implicit regularization, NTK, grokking).

5. **Gradient descent convergence** (`optimization/gradient-descent-convergence.md`): covers GD/SGD convergence theory, convex and non-convex analysis. The implicit-regularization file should cross-reference the SGD noise analysis here.

6. **Synthetic data and self-improvement** (`ai/frontier/architectures/synthetic-data-self-improvement.md`): discusses distillation, self-play, model collapse — all of which implicitly assume learning theory. The in-context learning theory file should provide the theoretical grounding for why distillation and in-context learning work.

### What does NOT already exist

- No file on PAC-Bayes bounds as a standalone treatment (only introduced within compression-generalization)
- No file on implicit regularization in SGD (flat minima, sharpness-aware minimization, edge-of-stability)
- No file on the neural tangent kernel and the lazy vs. feature-learning regime
- No file on grokking (delayed generalization)
- No file on in-context learning theory (implicit Bayesian inference, gradient descent in residual stream)
- No file on transfer learning theory / domain adaptation theory
- No learning-theory synthesis connecting these to the frontier AI domain

## Boundary decisions

| Boundary | Decision | Rationale |
|---|---|---|
| learning-theory/ vs. information-theory/ | The existing information-theory/ files are the classical foundations (PAC, VC, compression, double descent). Learning-theory/ covers post-classical developments that extend, challenge, or reinterpret those foundations. | Historical vs. contemporary split. The new files explicitly build on the existing ones. |
| learning-theory/ vs. optimization/ | The SGD implicit regularization file lives in learning-theory/ because its primary contribution is to generalization theory, not optimization convergence. Cross-reference to optimization/gradient-descent-convergence.md for the convergence analysis. | The lens determines the location: optimization files ask "does it converge?"; learning-theory files ask "why does it generalize?". |
| learning-theory/ vs. ai/frontier/ | Learning-theory/ provides the mathematical framework; ai/frontier/ describes the empirical phenomena and engineering implications. The in-context learning theory file belongs in math because it provides the theoretical account; the practical description of ICL in frontier models stays in ai/frontier/. | Theory vs. practice split. Learning-theory/ is the mathematical grounding; ai/frontier/ is the applied layer. |
| PAC-Bayes depth vs. compression-generalization overlap | The new PAC-Bayes file should go substantially deeper than the PAC-Bayes section in compression-generalization.md: Catoni's bound, Alquier's extensions, PAC-Bayes with data-dependent priors, the connection to flat minima, and empirical results on computable generalization certificates. The compression file is the conceptual introduction; the new file is the full technical treatment. | Depth escalation, not duplication. |

## Dependency map

```
information-theory/pac-learning-sample-complexity.md
   └──→ learning-theory/pac-bayes-generalization-bounds.md (extends PAC to PAC-Bayes)

information-theory/vc-dimension-fundamental-theorem.md
   └──→ learning-theory/neural-tangent-kernel-infinite-width.md (alternative complexity measure)

information-theory/compression-generalization-connection.md
   ├──→ learning-theory/pac-bayes-generalization-bounds.md (deeper treatment)
   └──→ learning-theory/implicit-regularization-sgd-flat-minima.md (why compression emerges)

information-theory/double-descent-benign-overfitting.md
   ├──→ learning-theory/implicit-regularization-sgd-flat-minima.md (mechanism explanation)
   └──→ learning-theory/grokking-delayed-generalization.md (related anomaly)

optimization/gradient-descent-convergence.md
   └──→ learning-theory/implicit-regularization-sgd-flat-minima.md (shared SGD analysis)
```

## Target file list (7 files)

### Phase 2: Modern Generalization Theory (4 files)

1. **pac-bayes-generalization-bounds.md**
   Full standalone treatment of PAC-Bayes theory. McAllester's original bound (1999): generalization gap bounded by KL divergence from posterior to prior over hypotheses, normalized by sample size. Catoni's tighter bound (PAC-Bayes-kl). The role of the prior: data-free vs. data-dependent priors and their implications for bound tightness. Excess risk decomposition. Why PAC-Bayes survives the overparameterization regime where VC/Rademacher bounds fail: the bound depends on how much the posterior deviates from prior, not on hypothesis class size. Connection to MDL: $D_{KL}(Q \| P)$ measures the description length of learning. Empirical results: PAC-Bayes bounds as computable, non-vacuous generalization certificates for deep networks (Dziugaite & Roy 2017).

2. **implicit-regularization-sgd-flat-minima.md**
   SGD as an implicit regularizer. Continuous-time analysis: gradient flow to minimum-norm solutions in linear models. Discrete-time SGD: noise from mini-batching as a regularizing perturbation — larger batch noise → less implicit regularization. Hochreiter & Schmidhuber on flat vs. sharp minima: flat minima (large connected regions of low loss) generalize better because perturbations don't increase loss. SAM (Sharpness-Aware Minimization): explicitly optimizing for flatness. The edge-of-stability phenomenon (Cohen et al. 2021): GD with large learning rates oscillates at the edge of instability, progressively sharpening then flattening the loss landscape. The causal debate: do flat minima cause generalization, or do they merely correlate? Evidence from reparameterization-invariant sharpness measures.

3. **neural-tangent-kernel-infinite-width.md**
   Jacot et al. (2018) NTK: in the infinite-width limit, neural networks become kernel machines. The NTK derivation: gradient descent on NN parameters induces kernel regression with a fixed kernel determined by the architecture. Why the kernel stays approximately constant during training (the "lazy" regime): parameter updates are infinitesimally small relative to initialization. Predictions: convergence to global minimum, training dynamics governed by kernel eigenspectrum. Failures: NTK does not explain feature learning — finite-width networks learn data-adapted features that change the kernel during training. The μP parameterization (Yang & Hu, Tensor Programs): width-scaled initialization that preserves feature learning at large width. Current status: NTK is a useful theoretical toy model but not a complete description of deep learning generalization.

4. **grokking-delayed-generalization.md**
   Power et al. (2022): delayed generalization long after training loss saturates to zero. Experimental setup: small transformer trained on modular arithmetic (e.g., $a \circ b \mod p$). Phase 1: memorization — training loss drops, test loss stays high. Phase 2: long plateau — both losses are static. Phase 3: grokking — test loss suddenly drops while training loss was already zero. Proposed mechanisms: (a) representation complexity theory (Nanda et al.): network discovers simpler algorithm that replaces memorization lookup; (b) weight norm growth and implicit regularization: weight decay slowly penalizes the memorization solution until the simpler algorithm dominates; (c) phase-transition framing: sharp transitions in representation structure. Connections to double descent (interpolation threshold as a related phenomenon) and the sharpness/generalization debate (the simpler algorithm occupies a flatter minimum). Implications: training longer sometimes helps dramatically; the absence of test-loss improvement during training doesn't mean the model has stopped learning.

### Phase 3: Scale and Synthesis (3 files, requires approval)

5. **in-context-learning-theory.md**
   What in-context learning is: performance improvement from demonstration examples in the prompt without any weight update. Distinguished from fine-tuning and few-shot learning with gradient updates. Proposed mechanisms: (a) implicit Bayesian inference (Xie et al. 2022): the model performs approximate Bayesian posterior updating over latent task identities; (b) gradient descent in the residual stream (Akyürek et al. 2023, von Oswald et al. 2023): transformer forward passes implement an algorithm equivalent to gradient-descent steps on the in-context examples; (c) task identification from context: the model recognizes the task and retrieves the appropriate computation from weights. Why classical PAC theory doesn't apply: no i.i.d. sample from a fixed distribution; the "sample" is part of the input. The meta-learning framing: ICL as learning-to-learn during pretraining. Empirical limits: sensitivity to example order, label content, prompt format.

6. **transfer-learning-theory-domain-adaptation.md**
   Ben-David et al. (2010) domain adaptation bound: target error ≤ source error + domain divergence ($\mathcal{H}$-divergence) + ideal joint error. PAC-Bayesian domain adaptation: posterior divergence from prior now also accounts for distribution shift. Fine-tuning theory: pretraining provides an informative prior; fine-tuning compresses the distance from prior to posterior for the target task. Why pretrained representations transfer: the early layers learn domain-general features (edges, syntax) while later layers specialize. Foundation-model transfer: the extreme case where one pretraining run provides the prior for thousands of downstream tasks. Negative transfer: when source and target are sufficiently different, transfer hurts.

7. **learning-theory-synthesis.md**
   Capstone synthesis integrating the four new files with the four existing information-theory files into a coherent narrative. Key themes: (a) the classical regime (PAC/VC) correctly describes small-model learning but breaks at scale; (b) the modern regime (PAC-Bayes/implicit-regularization/NTK) explains why overparameterized models generalize; (c) grokking and double descent are two manifestations of the same phenomenon — the optimizer's implicit bias toward simpler solutions; (d) in-context learning extends the theory from weight-based learning to activation-based learning; (e) transfer learning theory explains why foundation models are the dominant paradigm. Updated SUMMARY.md for the learning-theory/ subdomain. This file also links back to the AI frontier domain, providing the mathematical grounding for claims in scaling-laws, synthetic-data, and reasoning-models files.

## Cross-reference map

| New file | Cross-references to existing files |
|---|---|
| pac-bayes-generalization-bounds | → information-theory/pac-learning-sample-complexity.md, information-theory/compression-generalization-connection.md |
| implicit-regularization-sgd-flat-minima | → optimization/gradient-descent-convergence.md, information-theory/double-descent-benign-overfitting.md, information-theory/compression-generalization-connection.md |
| neural-tangent-kernel-infinite-width | → information-theory/vc-dimension-fundamental-theorem.md, optimization/gradient-descent-convergence.md |
| grokking-delayed-generalization | → information-theory/double-descent-benign-overfitting.md, implicit-regularization-sgd-flat-minima.md |
| in-context-learning-theory | → ai/frontier/architectures/synthetic-data-self-improvement.md, ai/frontier/reasoning/reasoning-models.md |
| transfer-learning-theory-domain-adaptation | → pac-bayes-generalization-bounds.md, ai/frontier/architectures/synthetic-data-self-improvement.md |
| learning-theory-synthesis | → all information-theory/ files, all learning-theory/ files, ai/frontier-synthesis.md |

## Duplicate coverage check

- compression-generalization.md introduces PAC-Bayes conceptually → new file goes substantially deeper on bounds, priors, and empirical certificates. Complementary, not duplicative.
- double-descent covers the empirical phenomenon → grokking covers a distinct but related anomaly. No overlap.
- gradient-descent-convergence covers convergence → implicit-regularization covers generalization via SGD dynamics. Different questions.

## Formatting conventions

Based on review of existing mathematics files:
- YAML frontmatter: `source`, `origin_session`, `created`, `trust`, `related`
- Use KaTeX-compatible LaTeX for equations (inline `$...$`, display `$$...$$`)
- Markdown body: H1 title, H2 major sections, H3 subsections, tables for structured comparisons
- Depth: 1000–1800 words per file; formal but accessible; cite key papers by author-year
- Define notation before using it; maintain consistency with existing files
