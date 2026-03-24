---
created: '2026-03-20'
last_verified: '2026-03-20'
origin_session: core/memory/activity/2026/03/20/chat-002
source: agent-generated
trust: high
related: information-bottleneck-deep-learning.md, ../complexity-theory/circuit-complexity-lower-bounds.md, ../optimization/online-learning-regret-bounds.md
---

# PAC Learning and Sample Complexity

## Probably Approximately Correct Learning

### The PAC Framework

**PAC learning** (Valiant, 1984) provides a rigorous framework for asking: **how many examples does a learner need to learn a concept?**

**Setup:**
- **Instance space** $\mathcal{X}$: The set of all possible inputs (e.g., all binary strings of length $n$)
- **Concept class** $\mathcal{C}$: A set of Boolean functions $c: \mathcal{X} \to \{0, 1\}$ (the "true" labeling functions we want to learn)
- **Hypothesis class** $\mathcal{H}$: A set of functions the learner can output (may or may not equal $\mathcal{C}$)
- **Distribution** $\mathcal{D}$: Unknown distribution over $\mathcal{X}$ from which examples are drawn
- **Training set** $S = \{(x_1, c(x_1)), \ldots, (x_m, c(x_m))\}$: $m$ labeled examples drawn i.i.d. from $\mathcal{D}$

**Definition:** A concept class $\mathcal{C}$ is **PAC-learnable** by $\mathcal{H}$ if there exists an algorithm $A$ and a polynomial $p(\cdot, \cdot, \cdot)$ such that for every:
- target concept $c \in \mathcal{C}$
- distribution $\mathcal{D}$ over $\mathcal{X}$
- accuracy parameter $\varepsilon > 0$
- confidence parameter $\delta > 0$

the algorithm $A$, given $m \geq p(1/\varepsilon, 1/\delta, n)$ examples, outputs $h \in \mathcal{H}$ such that:

$$\Pr[\text{error}(h) \leq \varepsilon] \geq 1 - \delta$$

where $\text{error}(h) = \Pr_{x \sim \mathcal{D}}[h(x) \neq c(x)]$.

**In words:** With probability at least $1 - \delta$ (**probably**), the learner outputs a hypothesis with error at most $\varepsilon$ (**approximately correct**). The sample size needed is polynomial in $1/\varepsilon$, $1/\delta$, and the problem size $n$.

### The Two Parameters

| Parameter | Controls | Interpretation |
|-----------|----------|----------------|
| $\varepsilon$ (accuracy) | How close to perfect | "the hypothesis is within $\varepsilon$ of the true concept" |
| $\delta$ (confidence) | Probability of failure | "this guarantee holds with probability $\geq 1-\delta$" |

The framework quantifies **both** approximation quality and the probability of achieving it — a significant advance over asymptotic consistency guarantees.

### Distribution-Free Learning

A crucial feature: PAC learning is **distribution-free**. The guarantee holds for every distribution $\mathcal{D}$. The learner doesn't need to know or estimate $\mathcal{D}$ — it works regardless.

This is both a strength (universal guarantees) and a weakness (the bounds may be loose for specific, well-behaved distributions).

## Sample Complexity

### Definition

The **sample complexity** of learning concept class $\mathcal{C}$ is:

$$m(\varepsilon, \delta) = \text{minimum number of examples needed to PAC learn } \mathcal{C}$$

This is the central quantity of computational learning theory.

### Finite Hypothesis Classes

For a finite hypothesis class $|\mathcal{H}| < \infty$:

$$m(\varepsilon, \delta) \leq \frac{1}{\varepsilon} \left(\ln |\mathcal{H}| + \ln \frac{1}{\delta}\right)$$

**Proof sketch:** After $m$ examples, any hypothesis with true error $> \varepsilon$ has probability $\leq (1-\varepsilon)^m$ of being consistent with the training set. By union bound over all $|\mathcal{H}|$ hypotheses, the probability that any bad hypothesis survives is $\leq |\mathcal{H}| \cdot (1-\varepsilon)^m \leq |\mathcal{H}| \cdot e^{-m\varepsilon}$. Setting this $\leq \delta$ and solving for $m$ gives the bound.

**Key insight:** The sample complexity grows logarithmically with $|\mathcal{H}|$. Even enormous hypothesis classes can be learned efficiently if they are finite. What matters is $\ln |\mathcal{H}|$ — the "description length" of a hypothesis (bits needed to specify which hypothesis, connecting to MDL).

### Infinite Hypothesis Classes

When $|\mathcal{H}| = \infty$ (e.g., all linear classifiers in $\mathbb{R}^d$), $\ln |\mathcal{H}| = \infty$ and the finite bound is vacuous. Sample complexity for infinite classes is characterized by the **VC dimension** (next file).

## Agnostic PAC Learning

### Beyond Realizability

Standard PAC learning assumes **realizability**: the true concept $c \in \mathcal{C}$ is in the hypothesis class $\mathcal{H}$ (or can be represented exactly). In practice, this is rarely true.

**Agnostic PAC learning** drops the realizability assumption:

$$\Pr\left[\text{error}(h) \leq \min_{h' \in \mathcal{H}} \text{error}(h') + \varepsilon\right] \geq 1 - \delta$$

The learner is compared to the **best hypothesis in $\mathcal{H}$**, not to the true concept. Even if no hypothesis in $\mathcal{H}$ achieves zero error, the learner should find one that's approximately as good as the best available.

### Relation to Empirical Risk Minimization

**Empirical Risk Minimization** (ERM): Choose the hypothesis that minimizes error on the training set:

$$\hat{h} = \arg\min_{h \in \mathcal{H}} \hat{\text{error}}_S(h) = \arg\min_{h \in \mathcal{H}} \frac{1}{m} \sum_{i=1}^{m} \mathbb{1}[h(x_i) \neq y_i]$$

ERM is the simplest learning rule. The fundamental theorem of statistical learning theory connects ERM to PAC learning:

**Theorem:** For binary classification, the following are equivalent:
1. $\mathcal{H}$ is agnostic PAC learnable
2. $\mathcal{H}$ has finite VC dimension
3. ERM is a consistent learner for $\mathcal{H}$ (with sufficiently many samples)

### Uniform Convergence

The key technical ingredient: **uniform convergence** of empirical risk to true risk.

$$\Pr\left[\sup_{h \in \mathcal{H}} |\hat{\text{error}}_S(h) - \text{error}(h)| \leq \varepsilon\right] \geq 1 - \delta$$

When this holds, every hypothesis's training error is close to its true error. Then ERM automatically finds a near-optimal hypothesis: if $\hat{h}$ has low training error, it has low true error too.

Uniform convergence for infinite $\mathcal{H}$ requires VC dimension to be finite.

## Computational Aspects

### Efficient PAC Learning

PAC learnability has two dimensions:
1. **Sample complexity:** How many examples are needed (information-theoretic)
2. **Computational complexity:** How much computation is needed (algorithmic)

A concept class is **efficiently PAC learnable** if both the sample complexity and the runtime of the learning algorithm are polynomial in $1/\varepsilon$, $1/\delta$, and $n$.

### Hardness Results

Some concept classes are PAC learnable (polynomial sample complexity) but not **efficiently** PAC learnable (unless P = NP):
- Learning DNF formulas (3-term DNF over $n$ variables: sample-efficient but NP-hard to find consistent hypothesis)
- Learning intersections of halfspaces
- Proper learning of various geometric concepts

This separation between information-theoretic and computational learnability is a fundamental theme.

### Cryptographic Hardness

Valiant and subsequent work showed that under cryptographic assumptions, some concept classes are provably hard to PAC learn. The existence of one-way functions implies hard-to-learn concept classes — connecting learning theory to cryptography.

## Extensions of PAC

### Online Learning

**Mistake-bound model** (Littlestone, 1988): Instead of a batch of i.i.d. examples, examples arrive one at a time. The learner must predict before seeing the label.

The **Littlestone dimension** characterizes online learnability analogously to how VC dimension characterizes PAC learnability. The halving algorithm achieves $\text{mistakes} \leq \text{Ldim}(\mathcal{H})$ for realizable online learning.

### PAC-Bayes

**PAC-Bayes bounds** (McAllester, 1999) combine PAC analysis with Bayesian ideas:

$$\text{error}(Q) \leq \hat{\text{error}}_S(Q) + \sqrt{\frac{D_{KL}(Q \| P) + \ln(m/\delta)}{2(m-1)}}$$

where $P$ is a prior distribution over hypotheses, $Q$ is the posterior, and $\text{error}(Q)$ is the expected error under the posterior.

The KL divergence $D_{KL}(Q \| P)$ is the complexity term — how far the learned distribution deviates from the prior. This connects PAC learning directly to information theory: the sample complexity depends on how many bits the training data forces the learner to "communicate" (the information gained from the data, measured as divergence from prior to posterior).

PAC-Bayes bounds are among the tightest available for neural networks and connect to MDL (the KL term is a description length).

## Implications for the Engram System

### 1. Knowledge Acquisition as PAC Learning

The agent's learning process maps onto PAC:
- **Concept class:** The true patterns in the user's domain
- **Hypothesis class:** What the agent can represent in knowledge files
- **Training data:** Conversations and research sessions
- **$\varepsilon$ (accuracy):** How well the knowledge captures the truth
- **$\delta$ (confidence):** The probability that the knowledge is misleading

Sample complexity applies: the agent needs enough diverse interactions to reliably learn the user's domain. A handful of conversations about a topic gives high $\varepsilon$ (rough understanding); many focused sessions drive $\varepsilon$ lower (refined knowledge).

### 2. The Unverified → Verified Threshold

Promoting knowledge from `_unverified/` to verified can be framed as a confidence threshold:
- **Unverified:** The agent has constructed a hypothesis from limited data. It may be approximately correct but with insufficient confidence ($\delta$ is too high)
- **Verified:** After human review or repeated confirmatory evidence, confidence increases ($\delta$ decreases below threshold)
- The governance rules requiring human review for promotion are enforcing a low $\delta$ standard

### 3. Distribution-Free vs. Domain-Adapted

PAC's distribution-free guarantee is analogous to writing general-purpose knowledge files: they should be correct regardless of how the topic comes up. But domain-adapted knowledge (written for a specific use pattern) can be much more efficient — just as distribution-specific bounds are tighter than distribution-free bounds.

This supports the filing system's approach: general knowledge goes in broad categories; project-specific knowledge goes in focused files that assume a particular context.

## Key References

- Valiant, L.G. (1984). A theory of the learnable. *Communications of the ACM*, 27(11), 1134–1142.
- Haussler, D. (1988). Quantifying inductive bias: AI learning algorithms and Valiant's learning framework. *Artificial Intelligence*, 36(2), 177–221.
- Kearns, M.J., & Vazirani, U.V. (1994). *An Introduction to Computational Learning Theory*. MIT Press.
- Shalev-Shwartz, S., & Ben-David, S. (2014). *Understanding Machine Learning: From Theory to Algorithms*. Cambridge University Press.
- McAllester, D.A. (1999). PAC-Bayesian model averaging. In *COLT 1999*.
- Littlestone, N. (1988). Learning quickly when irrelevant attributes abound: a new linear-threshold algorithm. *Machine Learning*, 2(4), 285–318.