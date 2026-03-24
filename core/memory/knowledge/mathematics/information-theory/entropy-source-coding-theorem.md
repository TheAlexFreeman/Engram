---
created: '2026-03-20'
last_verified: '2026-03-20'
origin_session: core/memory/activity/2026/03/20/chat-002
source: agent-generated
trust: high
related: kl-divergence-cross-entropy.md, vc-dimension-fundamental-theorem.md, ../statistical-mechanics/thermodynamics-entropy-unification.md
---

# Entropy and the Source Coding Theorem

## Shannon Entropy

### Self-Information

The **self-information** (or surprisal) of an event $x$ with probability $p(x)$ is:

$$I(x) = -\log_2 p(x) \text{ bits}$$

Intuition: a certain event ($p = 1$) carries zero information; a very unlikely event ($p \to 0$) carries large information. This matches the common-sense relationship between surprise and learning — you learn nothing from something you already know, and a great deal from something unexpected.

The logarithm is essential. If two independent events $x$ and $y$ occur, their joint information should be **additive**: $I(x, y) = I(x) + I(y)$. Since $p(x, y) = p(x) p(y)$ for independent events, only the logarithm converts multiplication to addition:

$$I(x, y) = -\log_2[p(x)p(y)] = -\log_2 p(x) - \log_2 p(y) = I(x) + I(y)$$

### Shannon Entropy

The **Shannon entropy** of a discrete random variable $X$ with probability mass function $p$ is:

$$H(X) = -\sum_{x \in \mathcal{X}} p(x) \log_2 p(x) = \mathbb{E}[I(X)]$$

The entropy is the **expected self-information** — the average number of bits needed to describe the outcome of $X$.

### Properties

| Property | Statement | Intuition |
|----------|-----------|-----------|
| **Non-negativity** | $H(X) \geq 0$ | Uncertainty is never negative |
| **Maximum** | $H(X) \leq \log_2 |\mathcal{X}|$, with equality iff $X$ is uniform | Maximum uncertainty when all outcomes are equally likely |
| **Minimum** | $H(X) = 0$ iff $X$ is deterministic | Zero uncertainty iff outcome is certain |
| **Concavity** | $H$ is a concave function of $p$ | Mixing distributions increases entropy |

### Examples

**Fair coin:** $H = -\frac{1}{2}\log_2 \frac{1}{2} - \frac{1}{2}\log_2 \frac{1}{2} = 1$ bit

**Biased coin ($p = 0.9$):** $H = -0.9\log_2 0.9 - 0.1\log_2 0.1 \approx 0.469$ bits

The biased coin has lower entropy — less uncertainty, fewer bits needed to describe outcomes on average.

**English text:** estimated at $\sim$1.0–1.5 bits per character (Shannon's 1951 experiment using human predictors; Brown et al. 1992 using n-gram models). Modern LLMs achieve character-level entropy estimates closer to $\sim$0.7–1.0 bits per character, suggesting they capture more of the language's structure.

## Joint and Conditional Entropy

### Joint Entropy

For two random variables $X, Y$:

$$H(X, Y) = -\sum_{x,y} p(x, y) \log_2 p(x, y)$$

The total uncertainty about the pair $(X, Y)$ jointly.

### Conditional Entropy

$$H(Y|X) = -\sum_{x,y} p(x, y) \log_2 p(y|x) = \sum_x p(x) H(Y|X=x)$$

The remaining uncertainty about $Y$ once you know $X$.

### Chain Rule

$$H(X, Y) = H(X) + H(Y|X) = H(Y) + H(X|Y)$$

The total uncertainty is the uncertainty about one variable plus the remaining uncertainty about the other given the first. This decomposes naturally to $n$ variables:

$$H(X_1, \ldots, X_n) = \sum_{i=1}^{n} H(X_i | X_1, \ldots, X_{i-1})$$

### The Independence Bound

$$H(X, Y) \leq H(X) + H(Y)$$

with equality iff $X$ and $Y$ are independent. Dependence reduces joint uncertainty.

## The Source Coding Theorem

### Statement (Shannon, 1948)

Let $X_1, X_2, \ldots$ be an i.i.d. source with distribution $p$ and entropy $H(X)$ bits/symbol.

**Achievability:** For any rate $R > H(X)$ and any $\epsilon > 0$, there exists a block code of sufficiently large block length $n$ that encodes the source with rate $R$ bits/symbol and probability of error less than $\epsilon$.

**Converse:** For any rate $R < H(X)$, any block code of any block length has a non-vanishing probability of error.

### What This Means

- **Entropy is the compression limit.** You cannot losslessly compress a source below its entropy rate (on average). Any attempt to code at rate $< H$ will inevitably lose information.
- **Entropy is achievable.** You can get arbitrarily close to the entropy rate with sufficiently clever coding and long enough blocks.
- **The gap between $H$ and any achievable code length measures the code's redundancy.** Good codes (Huffman, arithmetic coding, ANS) approach the limit with manageable block lengths.

### Practical Coding Schemes

**Huffman coding:** Assigns shorter codes to more probable symbols. Achieves $H(X) \leq L_{\text{Huffman}} < H(X) + 1$ bits/symbol. Optimal among prefix codes when coding symbol-by-symbol.

**Arithmetic coding:** Codes the *entire sequence* as a single number in $[0, 1)$. Achieves rate arbitrarily close to $H(X)$ for long sequences. This is the practical realization of the source coding theorem.

**ANS (Asymmetric Numeral Systems, Duda 2009):** Achieves arithmetic coding performance with the speed of Huffman-like table lookups. The state of the art in practical data compression.

## Entropy Applied to Language

### Language as a Stochastic Source

Shannon (1948, 1951) treated English text as the output of a stochastic process. If we could know the true probability distribution $p$ over sequences of English characters (or words), the entropy rate $h$ would be:

$$h = \lim_{n \to \infty} \frac{1}{n} H(X_1, X_2, \ldots, X_n)$$

This limit exists for any stationary ergodic process and represents the per-symbol entropy — the irreducible information content per character of English.

### Shannon's Estimations

Shannon estimated the entropy of English in several ways:

| Method | Estimate (bits/letter) |
|--------|----------------------|
| Zero-order (independent, uniform) | 4.76 |
| First-order (independent, English frequencies) | 4.03 |
| Second-order (bigram) | 3.32 |
| Human prediction experiment (1951) | ~1.0–1.5 |

The dramatic drop from 4.76 to ~1.3 shows how much structure (statistical dependence, grammar, semantics) exists in English text. Most of what we write is predictable given context.

### LLMs as Entropy Estimators

Modern language models provide upper bounds on $h$ by estimating $p(x_n | x_1, \ldots, x_{n-1})$ at each position. The cross-entropy of the model on held-out text is:

$$H_{\text{model}} = -\frac{1}{n} \sum_{i=1}^{n} \log_2 p_{\text{model}}(x_i | x_1, \ldots, x_{i-1})$$

Since cross-entropy $\geq$ true entropy, $H_{\text{model}}$ is an upper bound on $h$. Better models (lower perplexity) give tighter bounds. GPT-4-class models achieve character-level cross-entropy well below Shannon's 1951 estimates, suggesting they capture linguistic structure that humans don't consciously access.

## Entropy as a Measure of Uncertainty

### The Uniqueness Theorem

Shannon proved (and Khinchin later refined) that entropy is the **unique** measure of uncertainty satisfying:

1. **Continuity:** $H$ is a continuous function of the probabilities
2. **Maximality:** For a given alphabet size, $H$ is maximized by the uniform distribution
3. **Additivity:** For independent sources, $H(X, Y) = H(X) + H(Y)$
4. **Grouping:** Splitting an outcome into sub-outcomes preserves total uncertainty (the chain rule)

Any function satisfying these axioms is a constant multiple of $H(X)$. This uniqueness result is why entropy is the "right" measure of uncertainty — it's the only one that satisfies the basic requirements we'd want from such a measure.

### Differential Entropy (Continuous Case)

For continuous random variables:

$$h(X) = -\int p(x) \log_2 p(x) \, dx$$

Unlike discrete entropy, differential entropy can be negative. For a Gaussian with variance $\sigma^2$:

$$h(X) = \frac{1}{2} \log_2(2\pi e \sigma^2)$$

The Gaussian has the maximum differential entropy among all distributions with a given variance — it is the "most uncertain" distribution for a fixed spread.

## Implications for the Engram System

### 1. Knowledge Files Have an Entropy Rate

The information content of a knowledge file — the minimum compressed size that preserves all its content — is determined by its entropy rate. Files with more predictable content (formulaic structure, repeated patterns, boilerplate) have lower entropy; files with more novel, information-dense content have higher entropy.

**Practical implication:** The system's total information content is bounded by the sum of the entropy rates of all files. Redundancy across files (the same fact stated in multiple places) reduces the system's effective information density. A well-curated knowledge base should approach minimal redundancy — each file contributing unique information that isn't predictable from other files.

### 2. Summarization Is Lossy Compression

When the agent summarizes a file, it performs lossy compression: reducing the description length while accepting some loss of information. The rate-distortion framework (Phase 2) will formalize this, but the basic insight is from the source coding theorem: you cannot compress below the entropy without loss. Every summary loses information. The question is whether the lost information is important or not.

### 3. Cross-Entropy Loss Is Compression

The agent's language model training objective (cross-entropy loss) is directly an information-theoretic compression objective: minimize the average code length for the training data. A model with lower cross-entropy is a better compressor of the data — it has discovered more of the data's statistical structure.

This means **the agent's competence is literally measured by how well it compresses text**. Tasks where it excels (those where the text is well-predicted by the patterns in its training data) are tasks where it has good compression; tasks where it fails (adversarial prompts, novel reasoning, out-of-distribution queries) are tasks where its compression model doesn't fit the source.

## Key References

- Shannon, C.E. (1948). A mathematical theory of communication. *Bell System Technical Journal*, 27(3), 379–423.
- Shannon, C.E. (1951). Prediction and entropy of printed English. *Bell System Technical Journal*, 30(1), 50–64.
- Cover, T.M., & Thomas, J.A. (2006). *Elements of Information Theory* (2nd ed.). Wiley.
- Khinchin, A.I. (1957). *Mathematical Foundations of Information Theory*. Dover.
- Brown, P.F., Della Pietra, V.J., Mercer, R.L., Della Pietra, S.A., & Lai, J.C. (1992). An estimate of an upper bound for the entropy of English. *Computational Linguistics*, 18(1), 31–40.