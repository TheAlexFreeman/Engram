---
created: '2026-03-20'
last_verified: '2026-03-20'
origin_session: core/memory/activity/2026/03/20/chat-002
source: agent-generated
trust: high
related: entropy-source-coding-theorem.md, ../statistical-mechanics/thermodynamics-entropy-unification.md, mutual-information-channel-capacity.md
---

# KL Divergence and Cross-Entropy

## Kullback-Leibler Divergence

### Definition

The **Kullback-Leibler divergence** (relative entropy) from distribution $q$ to distribution $p$ is:

$$D_{KL}(p \| q) = \sum_x p(x) \log_2 \frac{p(x)}{q(x)} = \mathbb{E}_p\left[\log_2 \frac{p(x)}{q(x)}\right]$$

For continuous distributions:

$$D_{KL}(p \| q) = \int p(x) \log_2 \frac{p(x)}{q(x)} \, dx$$

KL divergence measures **how much extra information is needed to describe data from $p$ using a code optimized for $q$**, beyond the minimum needed by an optimal code for $p$.

### Properties

| Property | Statement | Consequence |
|----------|-----------|-------------|
| **Non-negativity** (Gibbs' inequality) | $D_{KL}(p \| q) \geq 0$ | $q$ is never better than $p$ at coding $p$-distributed data |
| **Zero iff identical** | $D_{KL}(p \| q) = 0 \iff p = q$ | KL divergence detects all distributional differences |
| **Asymmetry** | $D_{KL}(p \| q) \neq D_{KL}(q \| p)$ in general | KL divergence is not a metric |
| **Not a metric** | Violates symmetry and triangle inequality | Cannot be used as a distance function directly |
| **Additive for independent distributions** | $D_{KL}(p_1 p_2 \| q_1 q_2) = D_{KL}(p_1 \| q_1) + D_{KL}(p_2 \| q_2)$ | Divergence decomposes over independent components |

### The Asymmetry of KL Divergence

The two "directions" of KL divergence have different behaviors:

**Forward KL** $D_{KL}(p \| q)$ — also called the **moment-matching** or **mean-seeking** direction:
- Expectation under $p$: penalizes $q$ for placing low probability where $p$ has high probability
- If $p(x) > 0$ and $q(x) \approx 0$, the term $p(x) \log \frac{p(x)}{q(x)} \to \infty$
- Minimizing forward KL forces $q$ to **cover** all of $p$'s support — $q$ tends to be broader than $p$
- Used in variational inference (ELBO maximization), moment matching

**Reverse KL** $D_{KL}(q \| p)$ — also called the **mode-seeking** direction:
- Expectation under $q$: penalizes $q$ for placing probability where $p$ has low probability
- If $q(x) > 0$ and $p(x) \approx 0$, the term $q(x) \log \frac{q(x)}{p(x)} \to \infty$
- Minimizing reverse KL forces $q$ to **concentrate** on $p$'s modes — $q$ tends to be narrower than $p$
- Used in policy optimization, expectation propagation

### Information-Theoretic Interpretation

$$D_{KL}(p \| q) = H(p, q) - H(p)$$

The KL divergence is the **extra cost** of using the wrong code: the cross-entropy of $p$ under $q$ minus the entropy of $p$ (the optimal code length).

Equivalently: if you use code $q$ instead of optimal code $p$ to encode data from distribution $p$, you need $D_{KL}(p \| q)$ additional bits per symbol on average.

### Connection to Mutual Information

Mutual information is a KL divergence:

$$I(X; Y) = D_{KL}(p(x,y) \| p(x) p(y))$$

The mutual information between $X$ and $Y$ is the KL divergence from the joint distribution to the product of marginals — how much the joint differs from independence.

### Gaussian KL Divergence

For univariate Gaussians $p = \mathcal{N}(\mu_1, \sigma_1^2)$ and $q = \mathcal{N}(\mu_2, \sigma_2^2)$:

$$D_{KL}(p \| q) = \log\frac{\sigma_2}{\sigma_1} + \frac{\sigma_1^2 + (\mu_1 - \mu_2)^2}{2\sigma_2^2} - \frac{1}{2}$$

This closed form is essential for VAEs and Gaussian process models, where KL terms are computed analytically.

## Cross-Entropy

### Definition

The **cross-entropy** of distribution $p$ under model $q$:

$$H(p, q) = -\sum_x p(x) \log_2 q(x) = H(p) + D_{KL}(p \| q)$$

Cross-entropy measures the **average number of bits needed to identify an event from $p$ using a code optimized for $q$**. It is always at least $H(p)$, with equality iff $q = p$.

### Cross-Entropy as a Training Objective

In supervised learning with classification, the training objective is the empirical cross-entropy:

$$\mathcal{L}(\theta) = -\frac{1}{N} \sum_{i=1}^{N} \log_2 q_\theta(y_i | x_i)$$

where $q_\theta$ is the model's predicted distribution and $(x_i, y_i)$ are training examples. This can be viewed as:

1. **Cross-entropy:** The cross-entropy between the empirical distribution $\hat{p}$ (which puts all mass on the true label) and the model's output $q_\theta$
2. **Negative log-likelihood:** The average negative log probability assigned to the correct answer
3. **KL divergence (plus a constant):** Since $H(\hat{p})$ is constant (0 for one-hot labels, or entropy of the data for soft labels), minimizing cross-entropy is equivalent to minimizing $D_{KL}(\hat{p} \| q_\theta)$ — fitting the model to match the empirical distribution

### For Language Models

For next-token prediction, the cross-entropy loss is:

$$\mathcal{L}(\theta) = -\frac{1}{T} \sum_{t=1}^{T} \log_2 p_\theta(w_t | w_1, \ldots, w_{t-1})$$

This is the empirical cross-entropy between the true distribution of language and the model's distribution. **Perplexity** is the exponentiated cross-entropy:

$$\text{PPL} = 2^{\mathcal{L}(\theta)}$$

A perplexity of $k$ means the model is "as confused as" a uniform distribution over $k$ tokens at each position. Lower perplexity = better model.

The bound: $\text{PPL} \geq 2^{H(\text{language})}$, where $H(\text{language})$ is the true entropy rate of the language. No model can achieve perplexity below this limit.

## f-Divergences: The General Family

KL divergence and many other divergences are special cases of **f-divergences**:

$$D_f(p \| q) = \sum_x q(x) f\left(\frac{p(x)}{q(x)}\right)$$

where $f$ is a convex function with $f(1) = 0$.

| f-Divergence | $f(t)$ | Notes |
|-------------|---------|-------|
| **KL divergence** | $t \log t$ | Most common in ML |
| **Reverse KL** | $-\log t$ | Mode-seeking |
| **Total variation** | $\frac{1}{2}|t - 1|$ | A true metric; Pinsker's inequality connects it to KL |
| **Chi-squared** | $(t-1)^2$ | Local approximation of KL |
| **Jensen-Shannon** | $\frac{1}{2}(t\log t - (t+1)\log\frac{t+1}{2})$ | Symmetric, bounded; used in GANs |
| **Hellinger** | $(\sqrt{t} - 1)^2$ | Symmetric, bounded |

### The Jensen-Shannon Divergence

$$\text{JSD}(p, q) = \frac{1}{2} D_{KL}(p \| m) + \frac{1}{2} D_{KL}(q \| m), \quad m = \frac{p + q}{2}$$

JSD is always finite (unlike KL), symmetric, and its square root is a metric. The original GAN objective minimizes an approximation to $2 \cdot \text{JSD}(p_{\text{data}} \| p_{\text{gen}}) - \log 4$.

## Applications Beyond Training Objectives

### Model Comparison

The KL divergence between two models measures their disagreement:

$$D_{KL}(p_{\theta_1} \| p_{\theta_2})$$

This is used in:
- **Knowledge distillation:** Training a student model $q$ to minimize $D_{KL}(p_{\text{teacher}} \| q)$
- **Policy gradient methods:** KL penalty terms to prevent large policy updates (TRPO, PPO)
- **Bayesian inference:** The ELBO optimizes $D_{KL}(q_\phi(z|x) \| p(z|x))$

### Variational Inference

The evidence lower bound (ELBO):

$$\log p(x) \geq \mathbb{E}_{q_\phi(z|x)}[\log p_\theta(x|z)] - D_{KL}(q_\phi(z|x) \| p(z))$$

The KL term regularizes the approximate posterior $q_\phi$ to stay close to the prior $p(z)$. The reconstruction term is a (conditional) cross-entropy. Maximizing the ELBO simultaneously minimizes the KL from the approximate posterior to the true posterior.

### Distribution Shift Detection

If a model is trained on distribution $p_{\text{train}}$ but deployed on $p_{\text{test}}$:

$$D_{KL}(p_{\text{test}} \| p_{\text{train}})$$

Large KL divergence indicates distribution shift — the test data looks very different from training data. The model's cross-entropy on test data decomposes as:

$$H(p_{\text{test}}, q_\theta) = H(p_{\text{test}}) + D_{KL}(p_{\text{test}} \| q_\theta)$$

Even a perfect model (trained to match $p_{\text{train}}$ exactly) will have excess loss on shifted data equal to $D_{KL}(p_{\text{test}} \| p_{\text{train}})$.

## Implications for the Engram System

### 1. Knowledge Quality as Cross-Entropy

A knowledge file's quality can be framed as the cross-entropy between the file's claims and the true distribution of facts:
- **Perfect knowledge:** $H(p, q) = H(p)$ — the file assigns high probability to true facts, equal to the theoretical minimum
- **Inaccurate knowledge:** High cross-entropy — the file's model of reality assigns low probability to true states
- **Outdated knowledge:** Distribution shift — the file was accurate when written but $p$ has changed, increasing $D_{KL}(p_{\text{now}} \| q_{\text{file}})$

This frames the curation policy as cross-entropy minimization: reviewing and updating knowledge files reduces the divergence between what the files claim and what is true.

### 2. Summarization as Forward KL Minimization

When summarizing a detailed file into a compact summary, the summary $q$ should minimize:

$$D_{KL}(p_{\text{detail}} \| q_{\text{summary}})$$

This is the forward KL direction, which forces the summary to **cover** all important content (mean-seeking). A summary that uses reverse KL would instead concentrate on a few salient points while potentially missing important details — which is a different editorial choice (executive summary vs. comprehensive summary).

### 3. Redundancy Between Files

The KL divergence between two knowledge files' "models" of a topic measures their asymmetric redundancy:
- $D_{KL}(\text{file}_1 \| \text{file}_2)$: how much extra information $\text{file}_1$ provides beyond $\text{file}_2$
- If $D_{KL}$ is near zero in both directions, the files are nearly redundant and one could be consolidated

## Key References

- Kullback, S., & Leibler, R.A. (1951). On information and sufficiency. *Annals of Mathematical Statistics*, 22(1), 79–86.
- Csiszár, I. (1967). Information-type measures of difference of probability distributions and indirect observations. *Studia Scientiarum Mathematicarum Hungarica*, 2, 299–318.
- Goodfellow, I., et al. (2014). Generative adversarial nets. In *NeurIPS 2014*.
- Kingma, D.P., & Welling, M. (2014). Auto-encoding variational Bayes. In *ICLR 2014*.
- Hinton, G., Vinyals, O., & Dean, J. (2015). Distilling the knowledge in a neural network. arXiv:1503.02531.