---
created: '2026-03-20'
last_verified: '2026-03-20'
origin_session: core/memory/activity/2026/03/20/chat-002
source: agent-generated
trust: high
related: ../dynamical-systems/ergodic-theory-mixing.md, ../dynamical-systems/bifurcation-theory-catastrophe.md, ../optimization/duality-theory-minimax.md
---

# Rate-Distortion Theory

## The Lossy Compression Problem

Shannon's source coding theorem gives the fundamental limit for **lossless** compression: at least $H(X)$ bits per symbol are needed. But what if we accept some distortion — how many fewer bits do we need?

**Rate-distortion theory** answers: given a maximum tolerable distortion $D$, what is the minimum number of bits per source symbol (the **rate**) needed to describe the source?

This is the theory of **lossy compression** — image compression (JPEG), audio compression (MP3), video compression (H.264), and any system where approximate reproduction suffices.

## Distortion Measures

A **distortion measure** $d(x, \hat{x})$ quantifies the cost of reproducing source symbol $x$ as $\hat{x}$.

| Distortion | $d(x, \hat{x})$ | Domain |
|------------|------------------|--------|
| **Hamming** | $\mathbb{1}[x \neq \hat{x}]$ | Discrete; symbol error rate |
| **Squared error** | $(x - \hat{x})^2$ | Continuous; MSE |
| **Absolute error** | $|x - \hat{x}|$ | Continuous; MAE |
| **Log-loss** | $-\log q(\hat{x})$ | Probabilistic; cross-entropy |

The **expected distortion** of a reproduction scheme is:

$$D = \mathbb{E}[d(X, \hat{X})] = \sum_{x, \hat{x}} p(x) p(\hat{x}|x) \, d(x, \hat{x})$$

## The Rate-Distortion Function

### Definition

$$R(D) = \min_{p(\hat{x}|x): \mathbb{E}[d(X,\hat{X})] \leq D} I(X; \hat{X})$$

The **rate-distortion function** $R(D)$ is the minimum mutual information (in bits) between source and reproduction, over all conditional distributions $p(\hat{x}|x)$ that achieve expected distortion at most $D$.

### Properties

| Property | Statement |
|----------|-----------|
| **Monotonically non-increasing** | Higher tolerated distortion → lower required rate |
| **Convex** | The curve $R(D)$ is convex in $D$ |
| **Boundary values** | $R(0) = H(X)$ for discrete sources (lossless requires full entropy); $R(D_{\max}) = 0$ (maximum distortion needs no bits) |
| **Achievable** | Shannon proved codes exist achieving any $(R, D)$ on or above the curve |
| **Converse** | Below the curve is impossible — no code can achieve rate below $R(D)$ at distortion $D$ |

### The Rate-Distortion Theorem

**Theorem (Shannon 1959):** For any rate $R > R(D)$, there exist block codes of sufficient length that achieve expected distortion $\leq D$ at rate $R$. For $R < R(D)$, this is impossible.

This is the lossy compression analog of the channel coding theorem: it identifies a fundamental limit and proves it is achievable.

## Key Examples

### Binary Source with Hamming Distortion

Source: $X \sim \text{Bernoulli}(p)$, distortion: $d(x, \hat{x}) = \mathbb{1}[x \neq \hat{x}]$.

$$R(D) = \begin{cases} H(p) - H(D) & \text{if } 0 \leq D \leq \min(p, 1-p) \\ 0 & \text{if } D \geq \min(p, 1-p) \end{cases}$$

At zero distortion, the rate equals the source entropy $H(p)$. Tolerating a bit-flip probability of $D$ saves $H(D)$ bits per symbol. At $D = \min(p, 1-p)$, no bits are needed (just output the more probable symbol always).

### Gaussian Source with Squared Error Distortion

Source: $X \sim \mathcal{N}(0, \sigma^2)$, distortion: $d(x, \hat{x}) = (x - \hat{x})^2$.

$$R(D) = \begin{cases} \frac{1}{2} \log_2 \frac{\sigma^2}{D} & \text{if } 0 < D \leq \sigma^2 \\ 0 & \text{if } D > \sigma^2 \end{cases}$$

This is the most important continuous example:
- At $D = \sigma^2$: 0 bits needed (just output 0 always — same as ignoring the source)
- Halving the distortion costs exactly 0.5 bits per symbol
- Each bit of rate buys a factor of 4 reduction in distortion (6 dB per bit)
- This is the theoretical limit for all analog-to-digital conversion and signal compression

### The Reverse Water-Filling Construction

For a multivariate Gaussian source with covariance matrix having eigenvalues $\lambda_1 \geq \lambda_2 \geq \ldots \geq \lambda_n$, the optimal strategy allocates bits preferentially to high-variance components. Components with variance below a threshold $\theta$ (the "water level") are not coded at all — they are reproduced as zero.

$$D_i = \min(\lambda_i, \theta), \quad R(D) = \sum_{i: \lambda_i > \theta} \frac{1}{2} \log_2 \frac{\lambda_i}{\theta}$$

This is the theoretical basis for PCA-based compression: the principal components with smallest eigenvalues carry the least information and are discarded first.

## The Operational Meaning

### Coding Scheme

A rate-distortion code consists of:
1. **Encoder:** Maps source blocks $x^n = (x_1, \ldots, x_n)$ to indices from $\{1, \ldots, 2^{nR}\}$
2. **Decoder:** Maps indices to reproduction blocks $\hat{x}^n$
3. **Codebook:** The set of $2^{nR}$ reproduction codewords

The encoder finds the codeword closest to the source block (in distortion measure), sends its index, and the decoder outputs the corresponding codeword. This is **vector quantization**.

### Connection to Clustering

Rate-distortion coding is formally equivalent to clustering:
- The codebook entries are **cluster centroids**
- The encoder performs **nearest-centroid assignment**
- The distortion is the **average distance to assigned centroid**
- The rate is $\log_2$ of the number of clusters

K-means clustering with $K = 2^{nR}$ centroids is a practical (greedy) approach to this problem. The rate-distortion function gives the theoretical limit on how well $K$ clusters can represent the data.

## Rate-Distortion and Representation Learning

### Compression as Representation

A neural network's hidden representation is a **lossy compressed version** of its input. Rate-distortion theory provides the framework:

- **Rate:** $I(X; T)$ — the mutual information between input $X$ and representation $T$ (how many bits the representation preserves)
- **Distortion:** $\mathbb{E}[d(Y, \hat{Y}(T))]$ — the expected task loss when using $T$ to predict task variable $Y$
- **Rate-distortion trade-off:** The optimal representation minimizes $I(X; T)$ subject to adequate task performance

This is exactly the information bottleneck formulation (next file), which minimizes:

$$\mathcal{L}_{\text{IB}} = I(X; T) - \beta \cdot I(T; Y)$$

### Implications

1. **Lower layers:** Closer to the source, higher rate (more information preserved), lower distortion
2. **Higher layers:** More compressed, lower rate, potentially higher distortion on reconstructing inputs but lower distortion on the task
3. **Dropout/noise injection:** Effectively increases the channel noise, pushing the representation toward the rate-distortion curve (better compression at a given distortion level)
4. **Quantization of weights:** Rate-distortion theory applies to model compression too — how many bits per parameter are needed to maintain model quality?

## Implications for the Engram System

### 1. Knowledge File Compression Budget

Each knowledge file has an implicit rate-distortion trade-off:
- **Rate:** File size (bytes/tokens) — the storage and context-loading cost
- **Distortion:** Information loss relative to the source material — what the file omits or simplifies
- **Rate-distortion function:** The theoretical minimum file size needed to preserve a given level of fidelity

A well-written knowledge file operates near the rate-distortion curve: it is as short as possible while preserving the information that matters. A verbose file operates above the curve (same distortion could be achieved with fewer bits). A sloppy summary operates below what's achievable (unacceptable distortion given its length).

### 2. The Triage Problem as Reverse Water-Filling

When deciding which knowledge files to load into a limited context window, the agent faces a reverse water-filling problem:
- Each file has a "variance" (importance/relevance for the current task)
- The context window is the total rate budget
- Files below the relevance threshold should not be loaded at all
- More bits should be allocated to the most relevant files (loading full content vs. summaries)

### 3. Summarization Cascades

The hierarchical summarization structure (detail files → SUMMARY.md → plan SUMMARY.md) is a **successive refinement** scheme:
- Level 0 (full file): Maximum rate, minimum distortion
- Level 1 (section summary): Reduced rate, controlled distortion
- Level 2 (one-line entry): Minimum rate, maximum acceptable distortion

Rate-distortion theory guarantees that a well-designed cascade achieves the same rate-distortion curve as a single-stage compression — successive refinement is **optimal** for Gaussian sources and many other source models. This justifies the hierarchical structure.

## Key References

- Shannon, C.E. (1959). Coding theorems for a discrete source with a fidelity criterion. *IRE National Convention Record*, Part 4, 142–163.
- Berger, T. (1971). *Rate Distortion Theory: A Mathematical Basis for Data Compression*. Prentice-Hall.
- Cover, T.M., & Thomas, J.A. (2006). *Elements of Information Theory* (2nd ed.), Chapters 10–13. Wiley.
- Equitz, W.H.R., & Cover, T.M. (1991). Successive refinement of information. *IEEE Trans. Information Theory*, 37(2), 269–275.