---
created: '2026-03-20'
last_verified: '2026-03-20'
origin_session: core/memory/activity/2026/03/20/chat-002
source: agent-generated
trust: high
related: information-bottleneck-deep-learning.md, ../../cognitive-science/attention/attentional-bottleneck-limited-capacity.md, ../../social-science/network-diffusion/watts-information-cascades.md
---

# Mutual Information and Channel Capacity

## Mutual Information

### Definition

The **mutual information** between random variables $X$ and $Y$ is:

$$I(X; Y) = H(X) - H(X|Y) = H(Y) - H(Y|X) = H(X) + H(Y) - H(X, Y)$$

All three formulations are equivalent. Mutual information quantifies **how much knowing one variable reduces uncertainty about the other**. It is symmetric: $I(X; Y) = I(Y; X)$.

### Alternative Formulation via KL Divergence

$$I(X; Y) = D_{KL}(p(x, y) \| p(x)p(y)) = \sum_{x, y} p(x, y) \log_2 \frac{p(x, y)}{p(x)p(y)}$$

This expresses mutual information as the KL divergence between the joint distribution and the product of marginals. It measures **how far $X$ and $Y$ are from independence**. If $X \perp Y$, then $p(x,y) = p(x)p(y)$ and $I(X;Y) = 0$.

### Properties

| Property | Statement |
|----------|-----------|
| **Non-negativity** | $I(X; Y) \geq 0$, with equality iff $X \perp Y$ |
| **Symmetry** | $I(X; Y) = I(Y; X)$ |
| **Relation to entropy** | $I(X; Y) = H(X) + H(Y) - H(X, Y)$ |
| **Upper bound** | $I(X; Y) \leq \min(H(X), H(Y))$ |
| **Self-information** | $I(X; X) = H(X)$ (entropy is the mutual information of a variable with itself) |

### The Information Venn Diagram

The entropy-mutual-information relations map onto a Venn diagram:

- Left circle: $H(X)$
- Right circle: $H(Y)$
- Overlap: $I(X; Y)$
- Union: $H(X, Y)$
- Left only: $H(X|Y)$
- Right only: $H(Y|X)$

This visualization makes the chain rule and mutual information formulas intuitive.

### Conditional Mutual Information

$$I(X; Y | Z) = H(X|Z) - H(X|Y,Z)$$

How much $Y$ tells about $X$ when $Z$ is already known. Important for multivariate settings.

**Chain rule for mutual information:**
$$I(X_1, \ldots, X_n; Y) = \sum_{i=1}^{n} I(X_i; Y | X_1, \ldots, X_{i-1})$$

## The Data Processing Inequality

### Statement

If $X \to Y \to Z$ is a Markov chain (i.e., $Z$ depends on $X$ only through $Y$), then:

$$I(X; Z) \leq I(X; Y)$$

**Processing never creates information.** Any function of $Y$ can capture at most as much information about $X$ as $Y$ itself contains. This is a fundamental constraint on all information processing systems.

### Implications

1. **No post-hoc enhancement.** If a measurement $Y$ captures only $I(X;Y)$ bits about source $X$, no amount of subsequent processing can extract more than $I(X;Y)$ bits about $X$. Clever analysis helps you *approach* the bound, not exceed it.

2. **Representation learning.** When a neural network maps input $X$ through layers $L_1 \to L_2 \to \ldots \to L_k$, the mutual information between each layer and the input is monotonically non-increasing: $I(X; L_1) \geq I(X; L_2) \geq \ldots \geq I(X; L_k)$. Each layer can only lose information about the input (although it can organize the remaining information to be more useful for the task).

3. **Compression bounds.** Any summary of data discards information. The data processing inequality quantifies how much: if a summary $S$ is computed from data $D$, then $I(\text{truth}; S) \leq I(\text{truth}; D)$. Better summaries preserve more relevant information, but no summary can exceed the original data's mutual information with the truth.

## Channel Capacity

### The Communication Problem

A **discrete memoryless channel** (DMC) is defined by a conditional probability distribution $p(y|x)$ — the probability of receiving output $y$ given input $x$.

The problem: given a channel with noise (non-deterministic $p(y|x)$), what is the maximum rate at which information can be transmitted reliably?

### Channel Capacity Definition

$$C = \max_{p(x)} I(X; Y)$$

where the maximization is over all possible input distributions $p(x)$. Channel capacity is measured in bits per channel use.

### Shannon's Channel Coding Theorem (1948)

**Achievability:** For any rate $R < C$, there exist block codes of sufficient length that achieve reliable communication (probability of error $\to 0$ as block length $\to \infty$).

**Converse:** For any rate $R > C$, reliable communication is impossible — any code of any block length has a non-vanishing error probability.

### Key Channels

| Channel | Description | Capacity |
|---------|-------------|----------|
| **Noiseless binary** | Input = Output, no errors | $C = 1$ bit/use |
| **Binary symmetric (BSC)** | Each bit flipped with probability $\varepsilon$ | $C = 1 - H(\varepsilon)$ |
| **Binary erasure (BEC)** | Each bit erased with probability $\varepsilon$ (receiver knows when) | $C = 1 - \varepsilon$ |
| **Gaussian** | $Y = X + N$, $N \sim \mathcal{N}(0, N_0)$, power constraint $P$ | $C = \frac{1}{2}\log_2(1 + P/N_0)$ |

The Gaussian channel capacity formula $C = \frac{1}{2}\log_2(1 + \text{SNR})$ is the foundation of modern telecommunications. It says the maximum transmission rate grows logarithmically with the signal-to-noise ratio.

### The Channel Coding Theorem's Significance

The theorem's power lies in its **existence proof** nature:
- It proves that reliable communication at rates up to $C$ is *possible* — without necessarily telling you how to build the code
- It took decades to find practical codes (turbo codes, LDPC codes, polar codes) that approach capacity
- Modern 5G uses polar codes, which provably achieve capacity for binary-input channels

The theorem is the information-theoretic analog of the source coding theorem: it identifies a fundamental limit (capacity) and proves it is achievable.

## Mutual Information in Machine Learning

### Feature Selection

Mutual information between a feature $X_i$ and label $Y$ quantifies the feature's informativeness: $I(X_i; Y)$ bits of label information in feature $X_i$. Features with high MI are more informative.

The **interaction information** $I(X_i; Y) - I(X_i; Y | X_j)$ captures whether feature $X_i$'s information is redundant with or complementary to $X_j$'s.

### The Information Bottleneck

The information bottleneck (Tishby et al. 2000; detailed in the rate-distortion file) optimizes:

$$\min_{p(t|x)} I(X; T) - \beta \cdot I(T; Y)$$

where $T$ is a compressed representation of input $X$, and $Y$ is the task variable. This directly uses mutual information to balance compression (low $I(X;T)$) against task relevance (high $I(T;Y)$). The parameter $\beta$ controls the trade-off.

### Next-Token Prediction as Mutual Information Maximization

A language model trained with cross-entropy loss on next-token prediction is implicitly maximizing the mutual information between its internal representation of the context and the next token:

$$\max_\theta I_\theta(\text{context}; \text{next token})$$

where the subscript $\theta$ indicates the mutual information as estimated by the model with parameters $\theta$. A perfect language model ($p_\theta = p_{\text{true}}$) would capture all the mutual information between context and continuation — all the predictability in language.

The data processing inequality applies here: internal representations of the context are processed versions of the raw context, so they contain at most as much information about the continuation as the raw context does. The model's task is to extract the maximum possible relevant information from the context.

### Representation Quality

Mutual information provides a principled way to evaluate representation quality:
- $I(\text{representation}; \text{input})$: how much the representation preserves of the input (high = lossless, low = compressed)
- $I(\text{representation}; \text{task})$: how much task-relevant information the representation contains (high = useful, low = irrelevant)

A good representation has low $I(\text{rep}; \text{input})$ (compressed) and high $I(\text{rep}; \text{task})$ (informative for the task). This is the sufficient statistics view: a good representation captures all task-relevant structure while discarding irrelevant details.

## Implications for the Engram System

### 1. The Retrieval Channel

When the agent retrieves a knowledge file and loads it into context, this is a communication channel:
- **Input:** The knowledge in the file
- **Channel:** The loading + attention mechanism
- **Output:** The agent's internal representation of the knowledge
- **Noise:** Context window limits (truncation), attention competition (other loaded content), representation interference

Channel capacity applies: the maximum useful information the agent can extract from a loaded file is bounded by the mutual information between the file content and the agent's internal state. Loading more files doesn't help if the channel is already at capacity — the attention mechanism can only process so much per token position.

### 2. Data Processing and Summarization

The data processing inequality constrains summarization:

$$I(\text{truth}; \text{summary}) \leq I(\text{truth}; \text{original file})$$

Every summarization step irreversibly loses information about the underlying truth. A chain of summarizations (file → summary → summary of summaries) compounds the loss. This is the information-theoretic basis for the governance rule that original files should always be preserved.

### 3. Mutual Information Between Knowledge Files

Two knowledge files' mutual information $I(\text{file}_1; \text{file}_2)$ measures their **redundancy** — how much information they share. High MI between files means they cover mostly the same ground; low MI means they contain complementary information.

A well-curated knowledge base should have:
- High MI between each file and the domain of interest (each file is relevant)
- Low MI between files (each file contributes unique information)
- High total MI $I(\text{all files}; \text{truth})$ (the collection as a whole is informative)

This formalizes the intuition that a good knowledge base is comprehensive but non-redundant.

## Key References

- Shannon, C.E. (1948). A mathematical theory of communication. *Bell System Technical Journal*, 27(3), 379–423.
- Cover, T.M., & Thomas, J.A. (2006). *Elements of Information Theory* (2nd ed.). Wiley.
- Tishby, N., Pereira, F.C., & Bialek, W. (2000). The information bottleneck method. arXiv:physics/0004057.
- Goldsmith, A. (2005). *Wireless Communications*. Cambridge University Press.
- Arikan, E. (2009). Channel polarization: a method for constructing capacity-achieving codes for symmetric binary-input memoryless channels. *IEEE Trans. Information Theory*, 55(7), 3051–3073.