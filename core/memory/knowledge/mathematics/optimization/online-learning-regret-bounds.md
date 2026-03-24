---
created: '2026-03-21'
origin_session: core/memory/activity/2026/03/21/chat-001
source: agent-generated
trust: medium
---

# Online Learning and Regret Bounds

## Core Idea

Online learning is a sequential decision-making framework where a learner repeatedly chooses actions and observes losses, without any distributional assumptions on the data — the losses can be chosen adversarially. Performance is measured by **regret**: the gap between the learner's cumulative loss and the best fixed action in hindsight. The achievability of $O(\sqrt{T})$ regret — sublinear growth meaning the average per-round regret vanishes — is a cornerstone result connecting optimisation, game theory, and statistical learning.

## The Online Convex Optimisation (OCO) Framework

At each round $t = 1, 2, \ldots, T$:
1. Learner chooses $x_t \in \mathcal{K}$ (a convex decision set)
2. Adversary reveals convex loss function $f_t : \mathcal{K} \to \mathbb{R}$
3. Learner incurs loss $f_t(x_t)$

**Regret** against the best fixed action:
$$R_T = \sum_{t=1}^T f_t(x_t) - \min_{x \in \mathcal{K}} \sum_{t=1}^T f_t(x)$$

The goal: algorithms with $R_T = o(T)$, so the average regret $R_T/T \to 0$.

**No distributional assumptions**: The loss functions $f_t$ can be chosen adversarially, even adaptively based on the learner's past actions. This is the strongest possible setting.

## Online Gradient Descent (OGD)

**Algorithm** (Zinkevich 2003):
$$x_{t+1} = \Pi_\mathcal{K}\left(x_t - \eta_t \nabla f_t(x_t)\right)$$

where $\Pi_\mathcal{K}$ is the Euclidean projection onto $\mathcal{K}$.

**Regret bound**: With $\eta_t = D/(G\sqrt{t})$ where $D = \text{diam}(\mathcal{K})$ and $G = \max_t \|\nabla f_t\|$:
$$R_T \leq DG\sqrt{T} = O(\sqrt{T})$$

For **strongly convex** losses ($\mu$-strongly convex), with $\eta_t = 1/(\mu t)$:
$$R_T \leq \frac{G^2}{2\mu}(1 + \ln T) = O(\log T)$$

## Follow The Regularised Leader (FTRL)

A unifying framework: at each round, choose the action that minimises past cumulative loss plus a regulariser:

$$x_{t+1} = \arg\min_{x \in \mathcal{K}} \left\{\sum_{s=1}^t f_s(x) + R(x)\right\}$$

where $R : \mathcal{K} \to \mathbb{R}$ is a strongly convex regulariser.

Different choices of $R$ yield different algorithms:
| Regulariser $R(x)$ | Algorithm | Setting |
|--------------------|-----------|---------|
| $\frac{1}{2\eta}\|x\|_2^2$ | OGD / Follow the Leader | Euclidean geometry |
| $\frac{1}{\eta}\sum_i x_i \ln x_i$ | Multiplicative Weights / Hedge | Probability simplex |
| $\frac{1}{\eta}\|x\|_p^2$ | $p$-norm algorithm | Sparse comparators |

**FTRL regret bound**: If $R$ is $\lambda$-strongly convex w.r.t. norm $\|\cdot\|$:
$$R_T \leq \frac{R(x^*)}{\eta} + \eta \sum_{t=1}^T \|\nabla f_t(x_t)\|_*^2$$

Optimising $\eta$ gives $R_T = O(\sqrt{T})$.

## Multiplicative Weights / Hedge

The **expert problem**: $N$ experts, learner assigns weights $w_t \in \Delta_N$ (probability simplex), loss vector $\ell_t \in [0, 1]^N$ revealed.

**Multiplicative Weights Update**:
$$w_{t+1,i} = \frac{w_{t,i} \cdot e^{-\eta \ell_{t,i}}}{\sum_j w_{t,j} \cdot e^{-\eta \ell_{t,j}}}$$

This is FTRL with negative entropy regulariser $R(w) = \sum_i w_i \ln w_i$.

**Regret bound**: With $\eta = \sqrt{2 \ln N / T}$:
$$R_T \leq \sqrt{2T \ln N}$$

Remarkably, the dependence on $N$ is only $\sqrt{\ln N}$ — the algorithm works well even with exponentially many experts.

### Applications of Multiplicative Weights

The MW algorithm is ubiquitous:
- **Boosting** (AdaBoost): Each round trains a weak learner on a reweighted distribution; the weights follow MW dynamics
- **Solving LPs approximately**: MW over constraints gives a near-feasible, near-optimal solution in $O(\sqrt{\log m / \varepsilon^2})$ iterations (Plotkin-Shmoys-Tardos)
- **Solving zero-sum games**: Both players running MW converge to a Nash equilibrium in $O(\log N / \varepsilon^2)$ rounds
- **Combinatorial optimisation**: Maximum flow, minimum cut, packing/covering LPs

## No-Regret Learning and Game Theory

The deepest connection of online learning is to game theory.

**Theorem** (Freund-Schapire 1999): If all players in a repeated game use no-regret strategies (i.e., $R_T = o(T)$), then the empirical frequency of play converges to the set of **coarse correlated equilibria**.

**Stronger**: If all players use no-*internal*-regret strategies, play converges to **correlated equilibria**.

**No-regret ↔ Nash equilibria in zero-sum games**: If both players in a zero-sum game use MW, the time-average strategies converge to a Nash equilibrium at rate $O(\sqrt{\log N / T})$.

This provides a *computational* route to game-theoretic solution concepts — and explains why many machine learning algorithms (GANs, self-play in games) use adversarial training.

## Bandit Feedback

In the **bandit** (partial information) setting, the learner only observes the loss of the chosen action, not the full loss vector.

**Multi-armed bandits**: $N$ arms, each round choose arm $i_t$, observe only $\ell_t(i_t)$.

**EXP3** (Auer et al. 2002): Uses importance-weighted loss estimates:
$$\hat{\ell}_{t,i} = \frac{\ell_{t,i} \cdot \mathbf{1}[i_t = i]}{w_{t,i}}$$

This gives an unbiased estimate: $\mathbb{E}[\hat{\ell}_{t,i}] = \ell_{t,i}$.

**Regret**: $R_T = O(\sqrt{TN \ln N})$ — a $\sqrt{N}$ price for bandit feedback.

**Stochastic bandits** (UCB, Thompson sampling): When losses are i.i.d., much better regret $O(\sqrt{NT})$ or even $O(\sqrt{N \log T})$ is achievable.

## Online-to-Batch Conversion

Online learning provides a generic route to statistical (batch) learning bounds.

**Theorem**: If an online algorithm achieves regret $R_T$, then for i.i.d. data:
$$\mathbb{E}[f(\bar{x}_T)] - \min_{x \in \mathcal{K}} \mathbb{E}[f(x)] \leq \frac{R_T}{T}$$

where $\bar{x}_T = \frac{1}{T}\sum_t x_t$ is the average iterate.

For OGD with $R_T = O(\sqrt{T})$: the excess risk is $O(1/\sqrt{T}) = O(1/\sqrt{n})$ — matching the statistical minimax rate.

This means SGD (viewed as online gradient descent on i.i.d. samples) automatically achieves optimal statistical rates — the online learning perspective *explains* why SGD works for machine learning.

## Dynamic Regret and Non-Stationarity

**Static regret** competes against the best *fixed* action. **Dynamic regret** competes against a *changing* sequence of comparators:

$$R_T^{\text{dyn}} = \sum_{t=1}^T f_t(x_t) - \sum_{t=1}^T f_t(x_t^*)$$

where $x_t^* = \arg\min_x f_t(x)$.

**Bound**: $R_T^{\text{dyn}} \leq O(\sqrt{T(1 + P_T)})$ where $P_T = \sum_{t=1}^{T-1} \|x_{t+1}^* - x_t^*\|$ is the *path length* of the comparator sequence.

This captures non-stationary environments — relevant for continual learning and adaptive control.

## Connections

- **Gradient descent**: OGD is the online analogue of gradient descent — see [gradient-descent-convergence](gradient-descent-convergence.md)
- **Convex analysis**: OCO requires convexity of loss functions — see [convex-analysis-separation](convex-analysis-separation.md)
- **Duality and minimax**: No-regret dynamics solve minimax problems — see [duality-theory-minimax](duality-theory-minimax.md)
- **Non-convex landscapes**: Bandit optimisation of non-convex functions — see [nonconvex-landscapes-saddle-points](nonconvex-landscapes-saddle-points.md)
- **Game theory**: No-regret dynamics converge to equilibria — see [../game-theory/normal-form-games-nash-equilibrium.md](../game-theory/normal-form-games-nash-equilibrium.md)
- **PAC learning**: Online-to-batch conversion connects to sample complexity — see [../information-theory/pac-learning-sample-complexity.md](../information-theory/pac-learning-sample-complexity.md)
- **Bayesian inference**: Thompson sampling connects bandit algorithms to posterior sampling — see [../probability/bayesian-inference-priors-posteriors.md](../probability/bayesian-inference-priors-posteriors.md)
- **Concentration inequalities**: Regret bounds use martingale and Chernoff techniques — see [../probability/concentration-inequalities.md](../probability/concentration-inequalities.md)
