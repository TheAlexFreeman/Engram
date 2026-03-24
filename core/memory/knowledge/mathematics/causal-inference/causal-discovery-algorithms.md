---
created: '2026-03-21'
origin_session: core/memory/activity/2026/03/21/chat-001
source: agent-generated
trust: medium
---

# Causal Discovery Algorithms

## Core Idea

**Causal discovery** aims to learn the causal graph structure from data, rather than assuming it is known. This is the inverse problem to causal identification: instead of "given the graph, what can I learn about effects?", it asks "from the data, what can I learn about the graph?" The fundamental limits are set by **Markov equivalence** — observational data can identify the graph only up to its equivalence class. Algorithms fall into two families: **constraint-based** methods that test conditional independencies, and **score-based** methods that search for the best-fitting graph. Functional assumptions (e.g., non-Gaussianity, non-linearity) can break equivalence and achieve full identifiability.

---

## The Markov Equivalence Barrier

### What Observations Can Tell Us

From observational data (rung 1), we can test conditional independence relationships $X \perp\!\!\!\perp Y \mid Z$. Under the faithfulness assumption, these map one-to-one onto d-separations in the causal DAG (see [structural-causal-models-dags.md](structural-causal-models-dags.md)).

But different DAGs can encode the same d-separations. The **Markov equivalence class** (MEC) groups all DAGs that share:

1. The same **skeleton** (undirected adjacencies)
2. The same **v-structures** (colliders $A \to B \leftarrow C$ where $A-C$ are non-adjacent)

Within an MEC, edges whose orientation cannot be determined from conditional independence tests alone remain **undirected** in the summary representation (the CPDAG — completed partially directed acyclic graph).

### Breaking Equivalence

To identify beyond the MEC, one needs additional information:

- **Interventional data**: Experiments that force values of variables
- **Time-series**: Temporal ordering constrains arrow directions
- **Functional assumptions**: Non-Gaussianity (LiNGAM), non-linearity (ANMs), restricted noise models
- **Multiple environments**: Different experimental conditions reveal invariant mechanisms

---

## Constraint-Based Methods

### The PC Algorithm (Spirtes & Glymour, 1991)

The PC algorithm recovers the CPDAG through conditional independence testing:

**Phase 1 — Skeleton discovery:**
1. Start with a complete undirected graph
2. For each pair $(X, Y)$: test $X \perp\!\!\!\perp Y$, then $X \perp\!\!\!\perp Y \mid Z_1$, then $X \perp\!\!\!\perp Y \mid Z_1, Z_2$, etc., with increasing conditioning set size
3. Remove edge $X - Y$ if any conditional independence is found; record the separating set

**Phase 2 — Orient v-structures:**
For each unshielded triple $X - Z - Y$ (where $X$ and $Y$ are non-adjacent): if $Z$ is not in the separating set of $(X, Y)$, orient as $X \to Z \leftarrow Y$

**Phase 3 — Propagate orientations:**
Apply Meek's rules (orientation rules that maintain acyclicity and avoid creating new v-structures) to orient as many remaining edges as possible.

**Complexity:** Number of CI tests is $O(n^k)$ where $n$ is the number of variables and $k$ is the maximum conditioning set size. For sparse graphs (bounded degree), this is polynomial.

**Assumptions:** Causal sufficiency (no latent confounders), faithfulness, correct CI tests.

### The FCI Algorithm (Fast Causal Inference)

FCI extends PC to allow **latent confounders** and **selection bias**:

- Outputs a **partial ancestral graph** (PAG) instead of a CPDAG
- Uses bidirected edges ($\leftrightarrow$) to represent possible latent common causes
- Uses circle marks ($\circ$) for undetermined edge endpoints

FCI is sound and complete under weaker assumptions than PC, at the cost of less informative output.

### Conditional Independence Testing

The CI test is the core primitive. Common choices:

| Data type | Test | Assumption |
|-----------|------|------------|
| Gaussian | Partial correlation + Fisher's z-test | Linearity, normality |
| Discrete | $\chi^2$ or G-test | Sufficient sample size |
| General | Kernel-based (KCIT, RCIT) | None (nonparametric) |
| General | Conditional mutual information | Density estimation |

CI testing in high dimensions is inherently difficult: the curse of dimensionality means that conditioning on large sets requires exponentially more data. This is the practical bottleneck of constraint-based methods.

---

## Score-Based Methods

### The Greedy Equivalence Search (GES)

GES (Chickering, 2002) searches over the space of MECs by optimising a scoring function:

**Phase 1 — Forward (edge addition):**
Greedily add edges that improve the score (e.g., BIC), exploring MECs reachable by single-edge additions

**Phase 2 — Backward (edge deletion):**
Greedily remove edges that improve the score

**Scoring functions:**
- **BIC/MDL**: $\text{Score}(\mathcal{G}) = \log P(D | \hat{\theta}, \mathcal{G}) - \frac{d}{2}\log n$ (balance fit vs complexity — connects to [kl-divergence-cross-entropy.md](../information-theory/kl-divergence-cross-entropy.md) and MDL)
- **Bayesian score**: $\text{Score}(\mathcal{G}) = \log P(D | \mathcal{G}) = \log \int P(D | \theta, \mathcal{G}) P(\theta | \mathcal{G}) d\theta$

**Result (Chickering, 2002):** Under faithfulness and correct scoring, GES recovers the true CPDAG in the large-sample limit.

### NOTEARS (Zheng et al., 2018)

Formulate structure learning as a continuous optimisation problem:

$$\min_W \ell(W; D) + \lambda \|W\|_1 \quad \text{subject to } \text{tr}(e^{W \circ W}) - d = 0$$

where $W$ is the weighted adjacency matrix, $\ell$ is the least-squares loss, and the constraint $\text{tr}(e^{W \circ W}) = d$ enforces acyclicity (a smooth characterisation of DAG-ness). This converts the combinatorial search into a continuous optimisation problem solvable by augmented Lagrangian methods.

---

## Functional Causal Models and Full Identifiability

### LiNGAM (Linear Non-Gaussian Acyclic Model)

Shimizu et al. (2006) showed that if the structural equations are linear:

$$X_i = \sum_j B_{ij} X_j + U_i$$

and the noise terms $U_i$ are **non-Gaussian** and independent, then the full causal DAG (not just the MEC) is identifiable from observational data.

**Algorithm:** Apply independent component analysis (ICA) to the observed data; the mixing matrix $B$ encodes the causal structure. The permutation that makes $B$ lower-triangular gives the causal ordering.

**Why non-Gaussianity?** For Gaussian variables, the joint distribution depends only on the covariance matrix, which doesn't distinguish between equivalent DAGs. Non-Gaussian higher-order statistics break this symmetry.

### Additive Noise Models (ANMs)

For non-linear functional relationships $Y = f(X) + U$, $U \perp\!\!\!\perp X$:

If the true causal direction is $X \to Y$, then the residuals from regressing $Y$ on $X$ will be independent of $X$. Regressing $X$ on $Y$ will generally *not* yield independent residuals (Peters et al., 2014).

This asymmetry — the real causal mechanism "decomposes" into function + independent noise, but the reverse does not — can be tested empirically to determine causal direction between two variables, even without conditional independence tests.

### Invariant Causal Prediction (ICP)

Peters, Bühlmann, and Meinshausen (2016): If data is collected across multiple environments (e.g., different experimental conditions), the **causal parents** of a target $Y$ are the variables for which the conditional distribution $P(Y | \text{Pa}(Y))$ is invariant across environments.

This leverages the principle of independent mechanisms: causal mechanisms are stable across environments, while spurious associations change. ICP provides confidence sets for the causal parents with finite-sample type-I error guarantees.

---

## Hybrid and Modern Methods

### Combining Constraints and Scores

Many modern methods combine CI testing with scoring:

- **Max-Min Hill-Climbing (MMHC)**: Use CI tests to restrict the search space, then apply score-based search
- **Bayesian approaches**: Place a prior over DAG structures, compute the posterior; can integrate over entire MECs

### Causal Discovery with Neural Networks

- **DAG-GNN** and **GRAN-DAG**: Parameterise the structural equations with neural networks, enforce acyclicity via continuous constraints
- **Variational approaches**: Learn a posterior over graph structures using amortised inference

### Scale and Practical Challenges

| Challenge | State of the art |
|-----------|-----------------|
| High dimensionality ($p \gg n$) | Sparse methods (Lasso + DAG), debiased estimators |
| Latent confounders | FCI, ancestral graph methods |
| Non-stationarity | Regime-switching models, environment-indexed methods |
| Cyclic causal structures | Cyclic SEMs, equilibrium-based methods (limited theory) |
| Computational cost | NOTEARS and variants scale to thousands of variables |

---

## Connections

- **do-calculus**: Once the graph is discovered, the do-calculus can be applied for identification — see [do-calculus-identification.md](do-calculus-identification.md)
- **Bayesian inference**: Bayesian structure learning places priors over DAGs and integrates over uncertainty — see [bayesian-inference-priors-posteriors.md](../probability/bayesian-inference-priors-posteriors.md)
- **MDL/BIC**: Score-based methods use information-theoretic model selection criteria — see the information-theory files
- **Concentration inequalities**: Finite-sample CI testing requires bounds on test statistics — see [concentration-inequalities.md](../probability/concentration-inequalities.md)
- **Pearl's causal hierarchy**: Causal discovery bridges rungs 1 and 2 by extracting causal structure from associational data — see [pearls-causal-hierarchy.md](pearls-causal-hierarchy.md)
