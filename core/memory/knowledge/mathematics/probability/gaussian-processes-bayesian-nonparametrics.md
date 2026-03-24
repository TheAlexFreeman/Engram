---
created: '2026-03-21'
origin_session: core/memory/activity/2026/03/21/chat-001
source: agent-generated
trust: medium
---

# Gaussian Processes and Bayesian Nonparametrics

## Core Idea

A **Gaussian process** (GP) is a distribution over functions: any finite collection of function values is jointly Gaussian. This lets us do Bayesian inference directly in function space — placing a prior over the entire space of possible functions and conditioning on data to get a posterior, without ever committing to a fixed parametric form. Bayesian nonparametrics generalises this idea: the model complexity grows with the data, resolving model selection by integrating over it rather than optimising it.

---

## Gaussian Processes

### Definition

A GP is specified by a mean function $m(x)$ and a covariance (kernel) function $k(x, x')$:

$$f \sim \mathcal{GP}(m(x), k(x, x'))$$

For any finite set of inputs $\{x_1, \dots, x_n\}$, the function values $\mathbf{f} = [f(x_1), \dots, f(x_n)]^\top$ are jointly Gaussian:

$$\mathbf{f} \sim \mathcal{N}(\mathbf{m}, \mathbf{K})$$

where $\mathbf{m}_i = m(x_i)$ and $\mathbf{K}_{ij} = k(x_i, x_j)$.

### Kernel Functions and Inductive Bias

The kernel encodes assumptions about the function class — smoothness, periodicity, lengthscale. Common choices:

| Kernel | $k(x, x')$ | Encodes |
|--------|-------------|---------|
| Squared exponential (RBF) | $\sigma^2 \exp(-\|x - x'\|^2 / 2\ell^2)$ | Infinite smoothness |
| Matérn-$\nu$ | $\frac{2^{1-\nu}}{\Gamma(\nu)}(\frac{\sqrt{2\nu}\|x-x'\|}{\ell})^\nu K_\nu(\cdot)$ | $\nu$-times differentiability |
| Periodic | $\sigma^2 \exp(-\frac{2\sin^2(\pi\|x-x'\|/p)}{\ell^2})$ | Periodicity with period $p$ |
| Linear | $\sigma^2 x^\top x'$ | Linear functions (Bayesian linear regression) |

Kernels can be composed (summed, multiplied, composed with warping functions), building a grammar of structural assumptions — what David Duvenaud calls "automatic statisticians."

### Posterior Inference

Given observations $\mathbf{y} = \mathbf{f} + \boldsymbol{\varepsilon}$ with $\boldsymbol{\varepsilon} \sim \mathcal{N}(0, \sigma_n^2 I)$, the posterior is analytically tractable:

$$f_* | X, \mathbf{y}, x_* \sim \mathcal{N}(\bar{f}_*, \text{cov}(f_*))$$

$$\bar{f}_* = \mathbf{k}_*^\top (\mathbf{K} + \sigma_n^2 I)^{-1} \mathbf{y}$$

$$\text{cov}(f_*) = k(x_*, x_*) - \mathbf{k}_*^\top (\mathbf{K} + \sigma_n^2 I)^{-1} \mathbf{k}_*$$

The posterior mean is a linear combination of kernel functions centred on training points — exactly the solution of a regularised regression problem in the corresponding **reproducing kernel Hilbert space** (RKHS). This is the kernel trick in a Bayesian framing.

### Marginal Likelihood and Hyperparameter Learning

The log marginal likelihood balances fit and complexity:

$$\log p(\mathbf{y} | X) = -\frac{1}{2}\mathbf{y}^\top (\mathbf{K} + \sigma_n^2 I)^{-1} \mathbf{y} - \frac{1}{2}\log|\mathbf{K} + \sigma_n^2 I| - \frac{n}{2}\log 2\pi$$

The first term rewards data fit; the second penalises complexity (determinant grows with model capacity). This is a built-in Occam's razor — the Bayesian formalisation of the principle that simpler explanations are preferred unless the data force complexity.

Kernel hyperparameters ($\ell$, $\sigma$, $\sigma_n$) are typically optimised by gradient ascent on this marginal likelihood, or integrated out via MCMC for fully Bayesian treatment.

### Computational Challenges

The naïve GP requires $O(n^3)$ time (Cholesky decomposition of $\mathbf{K}$) and $O(n^2)$ storage. Scalable approximations include:

- **Sparse/inducing point methods** (Titsias, 2009): Approximate with $m \ll n$ pseudo-inputs, reducing cost to $O(nm^2)$
- **Random Fourier features** (Rahimi & Recht, 2007): Approximate shift-invariant kernels via random projections
- **Structured kernel interpolation (KISS-GP)**: Exploit grid structure for near-linear scaling

---

## Connection to RKHS and Regularisation

The representer theorem states that the solution to any regularised empirical risk minimisation in an RKHS $\mathcal{H}_k$ takes the form:

$$f^* = \sum_{i=1}^n \alpha_i k(x_i, \cdot)$$

For squared loss with $\ell_2$ regularisation, the solution is exactly the GP posterior mean. The GP adds calibrated uncertainty. This unifies:

- **Kernel ridge regression** = GP posterior mean
- **Support vector machines** = MAP estimation with hinge loss in the same RKHS
- **Neural tangent kernels** = the infinite-width limit of neural networks corresponds to a GP (Neal, 1996; Jacot et al., 2018)

The Neal (1996) result — that a single hidden layer network with i.i.d. random weights converges to a GP as width $\to \infty$ — was the first rigorous connection between neural networks and GPs, now extended to deep networks via the NNGP correspondence and neural tangent kernel theory.

---

## Bayesian Nonparametrics Beyond GPs

### The Core Principle

In parametric Bayesian models, we fix the number of parameters and do inference over their values. In **Bayesian nonparametrics**, the number of effective parameters grows with the data. This does not mean "no parameters" — it means infinitely many parameters, with a prior that concentrates mass on configurations consistent with the data.

### Dirichlet Process

The **Dirichlet process** $\text{DP}(\alpha, G_0)$ is a distribution over distributions. A draw $G \sim \text{DP}(\alpha, G_0)$ is almost surely discrete (a countably infinite mixture of atoms), even if the base measure $G_0$ is continuous.

The **stick-breaking construction** (Sethuraman, 1994) makes this constructive:

$$G = \sum_{k=1}^{\infty} \pi_k \delta_{\theta_k}, \quad \theta_k \sim G_0, \quad \pi_k = v_k \prod_{j<k}(1-v_j), \quad v_k \sim \text{Beta}(1, \alpha)$$

The concentration parameter $\alpha$ controls the number of clusters: larger $\alpha$ means more clusters, while $\alpha \to 0$ concentrates mass on a single cluster.

### Chinese Restaurant Process

The CRP provides a sequential, exchangeable sampling scheme equivalent to the DP:

- Customer 1 sits at table 1.
- Customer $n+1$ sits at occupied table $k$ with probability $\frac{n_k}{n + \alpha}$, or at a new table with probability $\frac{\alpha}{n + \alpha}$.

This generates a "rich get richer" dynamic — a power-law distribution over cluster sizes, connecting to preferential attachment in network science (see [complex-networks-small-world-scale-free.md](../dynamical-systems/complex-networks-small-world-scale-free.md)).

### DP Mixture Models

The Dirichlet process mixture model is the workhorse of Bayesian nonparametric clustering:

$$G \sim \text{DP}(\alpha, G_0), \quad \theta_i \sim G, \quad x_i \sim F(\theta_i)$$

The number of mixture components is inferred from data — no need to set $K$ in advance. Inference via collapsed Gibbs sampling, variational methods, or slice sampling.

### Indian Buffet Process

Where the CRP gives nonparametric mixtures (each data point belongs to one cluster), the **Indian buffet process** (IBP; Griffiths & Ghahramani, 2006) gives nonparametric latent feature models (each data point activates a subset of infinitely many latent features). The IBP is related to the Beta process, as the CRP is related to the Dirichlet process.

---

## Model Selection Without Grid Search

The fundamental appeal of Bayesian nonparametrics is that model complexity becomes an inference problem rather than a selection problem:

- **DP mixtures**: The number of clusters $K$ is inferred, not fixed
- **GPs**: The effective complexity is controlled by the kernel and marginal likelihood
- **IBP models**: The number of latent features is inferred

This sidesteps the usual train-validate-select loop. The marginal likelihood integrates out the model parameters, implementing Occam's razor automatically. In practice, this means we replace a combinatorial search over model structures with a continuous optimisation (or integration) problem, which is usually more tractable and better calibrated.

---

## Connections

- **Information theory**: The GP marginal likelihood can be interpreted as a coding length, connecting to the minimum description length (MDL) principle — see [bayesian-inference-priors-posteriors.md](bayesian-inference-priors-posteriors.md)
- **Concentration inequalities**: PAC-Bayes bounds give frequentist guarantees for Bayesian predictors, including GPs — see [concentration-inequalities.md](concentration-inequalities.md)
- **Free energy principle**: Variational inference for GPs and DP mixtures minimises a variational free energy — the same functional form as in Friston's FEP
- **RKHS and regularisation**: GPs provide the probabilistic interpretation of kernel methods, unifying regularisation theory and Bayesian learning
- **Neural networks**: The GP-neural network correspondence (Neal 1996 → NTK) provides a lens for understanding deep learning through infinite-width limits
