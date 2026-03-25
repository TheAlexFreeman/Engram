---
created: '2026-03-21'
origin_session: core/memory/activity/2026/03/21/chat-001
source: agent-generated
trust: medium
related: concentration-inequalities.md, measure-theoretic-foundations.md, stochastic-processes-brownian-sde.md, gaussian-processes-bayesian-nonparametrics.md, markov-chains-mixing-times.md, martingales-optional-stopping.md, ../causal-inference/counterfactuals-rubin-potential-outcomes.md, ../causal-inference/do-calculus-identification.md
---

# Bayesian Inference: Priors, Posteriors, and the Philosophy of Learning

## Core Idea

**Bayesian inference** treats probability as a representation of **epistemic uncertainty** — degrees of belief — and uses Bayes' theorem as the canonical rule for updating beliefs in light of evidence. The framework is conceptually simple: start with a prior distribution (what you believe before seeing data), observe data, and compute the posterior distribution (what you believe after). This single mechanism provides a unified theory of learning, prediction, model comparison, and decision-making. The philosophical debates (objective vs. subjective Bayesianism, prior justification) are not mere technicalities — they concern the foundations of rational belief and the nature of scientific inference.

## Bayes' Theorem

### The discrete case

For hypothesis $H$ and evidence $E$:

$$P(H | E) = \frac{P(E | H) \, P(H)}{P(E)}$$

- $P(H)$: **Prior** — belief in $H$ before observing $E$.
- $P(E | H)$: **Likelihood** — probability of observing $E$ if $H$ is true.
- $P(E)$: **Evidence** (or marginal likelihood) — $P(E) = \sum_i P(E | H_i) P(H_i)$.
- $P(H | E)$: **Posterior** — updated belief in $H$ after observing $E$.

### The continuous case

For a parameter $\theta$ with prior density $\pi(\theta)$ and data $\mathbf{x}$ with likelihood $p(\mathbf{x} | \theta)$:

$$\pi(\theta | \mathbf{x}) = \frac{p(\mathbf{x} | \theta) \, \pi(\theta)}{p(\mathbf{x})} = \frac{p(\mathbf{x} | \theta) \, \pi(\theta)}{\int p(\mathbf{x} | \theta') \, \pi(\theta') \, d\theta'}$$

The denominator is the **marginal likelihood** (or model evidence):

$$p(\mathbf{x}) = \int p(\mathbf{x} | \theta) \, \pi(\theta) \, d\theta$$

This quantity is central to Bayesian model comparison: the ratio $p(\mathbf{x} | \mathcal{M}_1) / p(\mathbf{x} | \mathcal{M}_2)$ is the **Bayes factor**, which compares how well two models explain the data, automatically penalizing model complexity (Occam's razor).

### Bayes' theorem as a learning rule

In the Bayesian framework, learning is simply repeated application of Bayes' theorem. After observing datum $x_1$, the posterior $\pi(\theta | x_1)$ becomes the prior for the next observation $x_2$:

$$\pi(\theta | x_1, x_2) \propto p(x_2 | \theta) \, \pi(\theta | x_1) \propto p(x_2 | \theta) \, p(x_1 | \theta) \, \pi(\theta)$$

For i.i.d. data $\mathbf{x} = (x_1, \ldots, x_n)$:

$$\pi(\theta | \mathbf{x}) \propto \left[\prod_{i=1}^n p(x_i | \theta)\right] \pi(\theta)$$

The posterior concentrates around the true parameter as $n \to \infty$ (under regularity conditions). The prior is eventually overwhelmed by the data — different priors converge to the same posterior.

## Conjugate Priors

### Definition

A prior $\pi(\theta)$ is **conjugate** to a likelihood $p(x | \theta)$ if the posterior $\pi(\theta | x)$ belongs to the same parametric family as $\pi(\theta)$. Conjugacy gives **closed-form posteriors** — avoiding numerical integration.

### Major conjugate families

| Likelihood | Conjugate prior | Posterior |
|-----------|----------------|-----------|
| Bernoulli/Binomial | Beta($\alpha, \beta$) | Beta($\alpha + k, \beta + n - k$) |
| Poisson | Gamma($\alpha, \beta$) | Gamma($\alpha + \sum x_i, \beta + n$) |
| Normal (known $\sigma^2$) | Normal($\mu_0, \sigma_0^2$) | Normal (precision-weighted mean) |
| Normal (known $\mu$) | Inverse-Gamma | Inverse-Gamma (updated) |
| Multinomial | Dirichlet($\boldsymbol{\alpha}$) | Dirichlet($\boldsymbol{\alpha} + \mathbf{n}$) |
| Exponential | Gamma($\alpha, \beta$) | Gamma($\alpha + n, \beta + \sum x_i$) |

The **Beta-Binomial** family is the simplest illustration: observing $k$ successes in $n$ trials transforms Beta($\alpha, \beta$) into Beta($\alpha + k, \beta + n - k$). The hyperparameters $\alpha$ and $\beta$ act as "pseudo-counts" — prior observations that are gradually diluted as real data accumulates.

## Bayesian Asymptotics

### Bernstein-von Mises theorem

Under regularity conditions (true parameter in the interior of the parameter space, model is correctly specified, Fisher information is positive definite), the posterior is asymptotically normal:

$$\pi(\theta | \mathbf{x}_n) \approx \mathcal{N}\left(\hat{\theta}_{\text{MLE}}, \frac{1}{n} I(\theta_0)^{-1}\right)$$

where $I(\theta_0)$ is the Fisher information matrix evaluated at the true parameter.

**Meaning**: For large $n$, the posterior concentrates on the MLE, and the Bayesian credible interval approximately equals the frequentist confidence interval. The prior is asymptotically irrelevant. Bayesian and frequentist inference **converge** in the large-sample limit.

### When Bernstein-von Mises fails

The theorem fails for:
- **Misspecified models**: The posterior concentrates on the KL-projection of the true distribution onto the model, not the "true parameter."
- **Boundary of parameter space**: The posterior may be half-normal or degenerate.
- **Nonparametric settings**: Infinite-dimensional parameter spaces where the standard theorem does not apply. Diaconis and Freedman (1986) showed that Bayesian nonparametric posteriors can be inconsistent in the sense that they concentrate on the wrong function.

## Prior Construction

### Non-informative (reference) priors

When prior information is minimal, several principles for constructing "objective" or "default" priors:

**Laplace's principle of indifference**: uniform prior over the parameter space. Problem: not invariant under reparameterization (a uniform prior on $\theta$ is not uniform on $\theta^2$).

**Jeffreys prior**: $\pi(\theta) \propto \sqrt{\det I(\theta)}$, where $I(\theta)$ is the Fisher information. This is invariant under reparameterization — the same prior in different coordinates. For a Bernoulli parameter: Jeffreys gives Beta(1/2, 1/2).

**Maximum entropy priors** (Jaynes): The prior should be the distribution with maximum entropy subject to known constraints. If nothing is known, this is the uniform distribution. If the mean is known, it's the exponential family with that sufficient statistic. This connects to information theory and statistical mechanics.

**Reference priors** (Bernardo, Berger): Formally maximize the expected information gain (mutual information between parameter and data). They are the "least informative" priors in an information-theoretic sense.

### Informative priors

When domain knowledge is available, informative priors encode it:
- **Elicited priors**: Experts specify quantiles, means, or ranges, and a distribution is fitted.
- **Empirical Bayes**: Use data to estimate hyperparameters of the prior (violates strict Bayesian separation of prior and data, but often works well).
- **Hierarchical priors**: Parameters of the prior are themselves given priors, creating a multi-level model.

## The Philosophical Debate

### Subjective Bayesianism (de Finetti, Savage, Lindley)

Probability is **personal degree of belief**. The prior reflects the agent's actual beliefs. **De Finetti's representation theorem** justifies this: if a sequence of observations is **exchangeable** (the joint distribution is invariant under permutations), then there exists a unique mixing measure $\mu$ such that the observations are conditionally i.i.d. given a parameter drawn from $\mu$. The prior $\mu$ is not arbitrary — it is uniquely determined by the coherence of the agent's beliefs about the exchangeable sequence.

The theorem says: if you believe the order of observations doesn't matter, then you **must** reason as if there is a parameter with a prior. Bayesian inference is not a choice but a consequence of coherent belief under exchangeability.

### Objective Bayesianism (Jaynes, Bernardo, Berger)

The prior should be determined by **logical principles** (maximum entropy, invariance, reference), not personal belief. Probability is an extension of deductive logic to uncertain inference. Jaynes coined this "probability as extended logic."

### The convergence view

In practice, the debate matters most for small samples. For large samples, Bernstein-von Mises ensures that reasonable priors converge to the same posterior. The choice of prior is a **regularization** choice — it affects finite-sample behavior (just as regularization in machine learning affects generalization).

## Bayesian Model Comparison

### Bayes factors

The **Bayes factor** in favor of $\mathcal{M}_1$ over $\mathcal{M}_2$:

$$\text{BF}_{12} = \frac{p(\mathbf{x} | \mathcal{M}_1)}{p(\mathbf{x} | \mathcal{M}_2)} = \frac{\int p(\mathbf{x} | \theta_1, \mathcal{M}_1) \pi(\theta_1 | \mathcal{M}_1) \, d\theta_1}{\int p(\mathbf{x} | \theta_2, \mathcal{M}_2) \pi(\theta_2 | \mathcal{M}_2) \, d\theta_2}$$

The marginal likelihood automatically implements **Occam's razor**: a complex model with many parameters spreads its prior probability over a large parameter space, so each parameter configuration gets low prior weight. If the data can be explained by a simpler model, the simpler model achieves a higher marginal likelihood.

### Connection to MDL

The Bayesian marginal likelihood and the **Minimum Description Length** (MDL) principle are asymptotically equivalent: both penalize model complexity and reward data fit, and both select the model that compresses the data most efficiently. The MDL code length equals $-\log p(\mathbf{x} | \mathcal{M})$ plus lower-order terms (Rissanen's stochastic complexity).

