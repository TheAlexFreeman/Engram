---
created: '2026-03-20'
last_verified: '2026-03-20'
origin_session: core/memory/activity/2026/03/20/chat-002
source: agent-generated
trust: high
related: compression-generalization-connection.md, double-descent-benign-overfitting.md, ../logic-foundations/kolmogorov-complexity-chaitin.md
---

# The Minimum Description Length Principle

## Core Idea

The **Minimum Description Length** (MDL) principle states: **the best model for data is the one that compresses the data most** — the model that provides the shortest total description of the data.

This connects Occam's razor to information theory: simpler models are better not because simplicity is inherently virtuous, but because **shorter descriptions correspond to better compression**, and better compression means the model has captured more regularity in the data.

## Historical Development

### Kolmogorov Complexity (1960s)

The theoretical foundation is **Kolmogorov complexity**: the length of the shortest program that produces a string $x$.

$$K(x) = \min\{ |p| : U(p) = x \}$$

where $U$ is a universal Turing machine and $|p|$ is program length in bits.

Properties:
- $K(x)$ is **not computable** — no algorithm can compute it for all strings
- It is **invariant** up to an additive constant across universal Turing machines
- Random strings have $K(x) \approx |x|$ (incompressible)
- Structured strings have $K(x) \ll |x|$ (a short program generates the pattern)

Kolmogorov complexity is the theoretical ideal but impractical. MDL is the practical approximation: instead of all possible programs, restrict to a model class.

### Rissanen's MDL (1978)

Jorma Rissanen formulated MDL as a practical statistical principle. The key insight: model selection is a coding problem.

## Two-Part MDL (Crude MDL)

### Formulation

Given data $D$ and model class $\mathcal{M}$, the two-part description length is:

$$L(M) + L(D | M)$$

where:
- $L(M)$: **Model complexity** — the number of bits to describe the model $M$ (its structure and parameters)
- $L(D|M)$: **Data fit** — the number of bits to describe the data given the model (the residuals, prediction errors, or negative log-likelihood)

The MDL-optimal model minimizes the total: $M^* = \arg\min_M [L(M) + L(D|M)]$.

### Interpretation

The two terms embody a fundamental trade-off:

| Term | What it penalizes | Extreme case |
|------|-------------------|--------------|
| $L(M)$ | Model complexity | Null model: $L(M)$ small, $L(D|M)$ large |
| $L(D|M)$ | Poor fit | Maximum-likelihood: $L(D|M)$ small, $L(M)$ large |
| $L(M) + L(D|M)$ | Total | MDL optimum: balanced trade-off |

This is a direct formalization of Occam's razor: a complex model needs to achieve sufficiently better fit to justify its complexity cost.

### Relationship to Existing Criteria

Two-part MDL relates to established model selection criteria:

| Criterion | Form | MDL interpretation |
|-----------|------|-------------------|
| **AIC** | $-2\log L + 2k$ | Approximate MDL with equal parameter costs |
| **BIC** | $-2\log L + k \log n$ | Approximate MDL with data-dependent parameter costs |
| **MAP** | $-\log p(D|M) - \log p(M)$ | Two-part MDL with Bayesian prior as model code |

BIC is closer to MDL than AIC: both penalize complexity more heavily as data grows. But two-part MDL is more general — it doesn't require a parametric model class or a likelihood function.

## Refined MDL: Normalized Maximum Likelihood

### The Problem with Two-Part MDL

Two-part MDL requires choosing a code for the model description $L(M)$, which introduces arbitrary choices. Different coding schemes for the same model class yield different MDL rankings.

### The NML Distribution

Rissanen (1996, 2001) developed the **Normalized Maximum Likelihood** (NML) as the unique minimax-optimal universal code for a model class:

$$p_{\text{NML}}(x) = \frac{p(x | \hat{\theta}(x))}{\sum_{x'} p(x' | \hat{\theta}(x'))} = \frac{\max_\theta p(x | \theta)}{\text{COMP}(\mathcal{M})}$$

where:
- $\hat{\theta}(x)$: Maximum likelihood estimate for data $x$
- $\text{COMP}(\mathcal{M}) = \sum_{x'} \max_\theta p(x' | \theta)$: **Parametric complexity** of model class $\mathcal{M}$

The NML distribution assigns to each data sequence $x$ a probability proportional to how well the model class can fit it (via MLE). The normalization constant $\text{COMP}(\mathcal{M})$ measures the model class's **total fitting capacity** — the sum of best possible fits across all data sequences.

### Stochastic Complexity

The **stochastic complexity** of data $x$ under model class $\mathcal{M}$ is:

$$\text{SC}(x | \mathcal{M}) = -\log p_{\text{NML}}(x) = -\log p(x | \hat{\theta}(x)) + \log \text{COMP}(\mathcal{M})$$

This decomposes as:
- $-\log p(x | \hat{\theta}(x))$: Best achievable fit (negative log-likelihood at MLE)
- $\log \text{COMP}(\mathcal{M})$: Complexity penalty (model class's total capacity)

Stochastic complexity is the refined MDL criterion: it uniquely determines the optimal model class without arbitrary coding choices.

### Parametric Complexity

For regular parametric models with $k$ parameters and $n$ data points:

$$\log \text{COMP}(\mathcal{M}) \approx \frac{k}{2} \log \frac{n}{2\pi} + \log \int \sqrt{\det I(\theta)} \, d\theta$$

where $I(\theta)$ is the Fisher information matrix. The first term grows as $\frac{k}{2} \log n$ (matching BIC's penalty), while the second captures the model's geometry — how parameters interact and how the model's predictions vary across parameter space.

## MDL and Generalization

### The Compression-Generalization Connection

MDL provides a direct link between compression and generalization:

1. **A model that compresses training data well has captured genuine regularities** — patterns that recur and can be exploited for shorter descriptions
2. **Genuine regularities generalize** — if the pattern is real (not noise), it will appear in new data too
3. **Therefore:** better compression → better generalization

This is not just intuition. MDL bounds on generalization error can be derived:

$$\text{generalization error} \leq \frac{L(M) + L(D|M)}{n}$$

(in simplified form). Models with shorter total description lengths have lower generalization error bounds.

### Overfitting as Incompressibility

An overfit model has:
- Small $L(D|M)$: excellent fit (memorizing the data)
- Large $L(M)$: very complex model (many parameters tuned to noise)
- Total $L(M) + L(D|M)$ is large — poor compression

The overfit model doesn't compress because the noise is incompressible. Fitting noise costs parameter bits ($L(M)$) without reducing data-given-model bits ($L(D|M)$) commensurately. MDL automatically rejects overfitting because the model complexity cost overwhelms the marginal fit improvement.

### Underfitting as Poor Compression

An underfit model has:
- Large $L(D|M)$: poor fit (missing genuine patterns)
- Small $L(M)$: simple model
- Total is large — also poor compression

The underfit model doesn't compress because it misses exploitable regularities. The data-given-model description is long because the model's predictions are inaccurate.

## MDL in Practice

### Model Selection Examples

**Polynomial regression:** Choosing polynomial degree $d$ for data $(x_i, y_i)$:
- $L(M)$: $d+1$ coefficients, each needing some precision → grows with $d$
- $L(D|M)$: Residuals from degree-$d$ fit → decreases with $d$ (up to a point)
- MDL selects the degree that minimizes the total

**Histogram density estimation:** Choosing bin count $k$:
- $L(M)$: $k$ bin probabilities → grows with $k$
- $L(D|M)$: How well the histogram predicts data → decreases with $k$
- MDL selects the optimal bin count automatically

**Neural network architecture:** Choosing layer widths and depth:
- $L(M)$: Number of parameters × precision per parameter
- $L(D|M)$: Training loss (cross-entropy)
- MDL perspective on neural scaling: larger models can be "worth it" if their compression gain ($L(D|M)$ reduction) exceeds their complexity cost ($L(M)$ increase)

### Prequential MDL

An alternative to NML: the **prequential** (predictive sequential) approach computes description length by online prediction:

$$L_{\text{preq}}(x_1, \ldots, x_n) = -\sum_{i=1}^{n} \log p(x_i | x_1, \ldots, x_{i-1})$$

This uses the model's sequential predictions — no separate model description needed. The model's coding efficiency is measured by how well it predicts each data point given previous data.

Prequential MDL connects directly to cross-entropy loss in sequence modeling: the total code length is exactly the negative log-likelihood under the model's autoregressive predictions.

## MDL and Deep Learning

### Neural Network Compression

Practical neural network compression aligns with MDL:
- **Pruning:** Setting weights to zero reduces $L(M)$ (fewer parameters to describe)
- **Quantization:** Reducing weight precision reduces $L(M)$ (fewer bits per parameter)
- **Knowledge distillation:** A smaller student achieves similar $L(D|M)$ with lower $L(M)$
- **Weight sharing / hashing:** Fewer unique parameter values → shorter model description

The lottery ticket hypothesis (Frankle & Carlin, 2019) is an MDL claim: within a randomly initialized network, there exists a sparse subnetwork (short model description) that achieves comparable fit — the total MDL is nearly as good.

### Scaling Laws through MDL

The neural scaling laws (Kaplan et al., 2020; Hoffmann et al., 2022) can be interpreted through MDL:

$$L \propto N^{-\alpha_N} + D^{-\alpha_D}$$

where $L$ is test loss, $N$ is parameter count, $D$ is dataset size. The first term represents model capacity ($L(D|M)$ improvement from more parameters). The second represents data coverage (more data → better estimation of the true distribution).

The compute-optimal frontier (Chinchilla scaling) says: given a compute budget, allocate equally between model size and data size. In MDL terms: balance the model description cost and the data-given-model description cost.

## Implications for the Engram System

### 1. Knowledge Management as MDL

The entire Engram system can be viewed as an MDL system:
- **Model:** The structured knowledge base (knowledge files, taxonomy, summaries)
- **Data:** The raw experience (conversations, research, observations)
- **$L(M)$:** The size and complexity of the knowledge base
- **$L(D|M)$:** How well the knowledge base predicts/explains new situations (residual surprise)

Good curation minimizes the total: a well-organized knowledge base is compact (low $L(M)$) while explaining most of what the agent encounters (low $L(D|M)$). Adding knowledge files is justified only when they reduce total description length — the information gain exceeds the storage cost.

### 2. File Granularity

MDL provides guidance on knowledge file granularity:
- **Too granular** (many small files): $L(M)$ is large (filesystem overhead, cross-references, redundancy between files)
- **Too coarse** (few large files): Loading one file brings irrelevant information (effective $L(D|M)$ higher because context is diluted)
- **MDL-optimal:** File boundaries align with natural topic boundaries, each file is self-contained for its scope

### 3. Promotion Decisions

Promoting a file from `_unverified/` to verified should correspond to an MDL improvement:
- Verified files are loaded more readily (higher prior weight in retrieval)
- Promotion is only justified if the file compresses the agent's experience: it should make future interactions more predictable (lower $L(D|M)$)
- Files that are rarely relevant have high $L(M)$ cost (maintenance, loading) relative to their $L(D|M)$ benefit and should remain low-priority

## Key References

- Rissanen, J. (1978). Modeling by shortest data description. *Automatica*, 14(5), 465–471.
- Rissanen, J. (1996). Fisher information and stochastic complexity. *IEEE Trans. Information Theory*, 42(1), 40–47.
- Rissanen, J. (2007). *Information and Complexity in Statistical Modeling*. Springer.
- Grünwald, P.D. (2007). *The Minimum Description Length Principle*. MIT Press.
- Kolmogorov, A.N. (1965). Three approaches to the quantitative definition of information. *Problems of Information Transmission*, 1(1), 1–7.
- Barron, A., Rissanen, J., & Yu, B. (1998). The minimum description length principle in coding and modeling. *IEEE Trans. Information Theory*, 44(6), 2743–2760.