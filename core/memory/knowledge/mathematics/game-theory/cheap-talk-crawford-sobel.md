---

created: '2026-03-20'
last_verified: '2026-03-20'
origin_session: core/memory/activity/2026/03/20/chat-003
source: agent-generated
trust: high
related:
  - costly-signaling-spence.md
  - extensive-form-games-backward-induction.md
  - mechanism-design-revelation-principle.md
---

# Cheap Talk and Crawford-Sobel

## Cheap Talk: Communication Without Cost

**Cheap talk** refers to costless, non-binding messages exchanged between parties before (or during) strategic interaction. Because messages are free to send, there is no inherent reason the receiver should believe what a sender says — the sender can always send any message regardless of their private information.

However, cheap talk can still be **informative** when the interests of sender and receiver are **sufficiently aligned**. The key question: when messaging is free, how much genuine information can be communicated?

Crawford and Sobel (1982) provided the canonical model, showing that:
- When interests are perfectly aligned, full information transmission is possible
- When interests diverge, only **coarse** (partial) information is transmitted
- When interests diverge sufficiently, **no information** is transmitted — only "babbling" equilibria exist

---

## The Crawford-Sobel Model

### Setup

- **Sender** $S$ has private information: a type $\theta$ drawn uniformly from $[0, 1]$
- **Receiver** $R$ chooses an action $a \in \mathbb{R}$ from a continuous action space
- **Sender's preferred action** given type $\theta$ is $\theta + b$ (the sender is biased by $b > 0$)
- **Receiver's preferred action** given $\theta$ is just $\theta$

**Utility functions:**
- $u_S(a, \theta) = -(a - \theta - b)^2$: sender maximizes utility by getting $R$ to take action $\theta + b$
- $u_R(a, \theta) = -(a - \theta)^2$: receiver maximizes utility by taking action $\theta$

The **bias** $b$ captures the misalignment between sender and receiver. If $b = 0$, interests are perfectly aligned and full information transmission is incentive-compatible. For $b > 0$, the sender wants the receiver to take an action higher than what the receiver considers optimal for $\theta$.

### Why Truthful Reporting Fails

Suppose the receiver commits to the Bayesian optimal response to a message $m$: $a(m) = \mathbb{E}[\theta | m]$.

If the receiver uses this policy, the sender's optimal message strategy given type $\theta$ is to report the type $\hat{\theta}$ that induces $a(\hat{\theta}) = \theta + b$, i.e., to lie by an amount that shifts the action up by $b$. But if all senders shade their reports by the same amount, the receiver adjusts their response function accordingly, and *we're back to no information transmission* — the sender's inflation is anticipated and discounted.

A truthful equilibrium requires the receiver to adopt the full-information best response $a(\theta) = \theta$. But then the sender with true type $\theta$ and bias $b$ prefers to report $\theta + b$ to shift action to $\theta + b$ (their preferred action). Truthful reporting is not a Nash equilibrium when $b > 0$.

### Equilibrium Structure: Partition Equilibria

Crawford and Sobel showed that **every equilibrium of the cheap talk game has a partition structure**:

The type space $[0,1]$ is partitioned into $N$ intervals $[t_0, t_1), [t_1, t_2), \ldots, [t_{N-1}, t_N]$ with $t_0 = 0, t_N = 1$.

- A sender with type $\theta \in [t_{k-1}, t_k)$ sends the same message (e.g., "$k$")
- The receiver responds with the midpoint/optimal action for that interval: $a_k = \mathbb{E}[\theta | \theta \in [t_{k-1}, t_k)] = (t_{k-1} + t_k)/2$

This is an equilibrium if and only if the sender at the boundary $t_k$ is indifferent between sending message $k$ (inducing action $a_k$) and message $k+1$ (inducing action $a_{k+1}$):

$$u_S(a_k, t_k) = u_S(a_{k+1}, t_k)$$

$$-\left(\frac{t_{k-1}+t_k}{2} - t_k - b\right)^2 = -\left(\frac{t_k+t_{k+1}}{2} - t_k - b\right)^2$$

This gives the **boundary condition**:

$$t_{k+1} - t_k = t_k - t_{k-1} + 4b$$

Each interval must be $4b$ wider than the previous. This limits how many intervals fit in $[0,1]$: the maximum number of intervals $N^*$ satisfies:

$$N^*(N^*+1) \cdot 2b \leq 1$$

For $b = 0$: $N^* = \infty$ — full information transmission (infinite partitions)
For $b = 1/4$: $N^* = 1$ — only the uninformative babbling equilibrium exists
For intermediate $b$: $N^*$ is finite; coarser communication with more bias

### Key Results

1. **The number of informative equilibria increases as $b \to 0$** — greater interest alignment enables finer communication
2. **Both sender and receiver prefer the most informative (finest partition) equilibrium** — communication benefits both
3. **Equilibria are Pareto-ranked**: finer partition equilibria are weakly better for both parties, so the most informative equilibrium is the natural focal point
4. **No fully revealing equilibrium exists for $b > 0$** — even infinitely fine partitions fail because the boundary condition requires the boundary-type sender to be indifferent, which fails with perfectly revealing messages

---

## Babbling Equilibria

A **babbling equilibrium** is an equilibrium where the sender's message is uninformative:
- Sender sends a message independent of their type (e.g., always sends $m = "0"$)
- Receiver ignores the message and takes the prior-optimal action: $a = \mathbb{E}[\theta] = 1/2$

Babbling equilibria always exist regardless of the bias $b$. They represent the extreme of **zero information transmission** — no communication occurs.

**When does babbling become the only equilibrium?** When the bias $b$ is large enough ($b \geq 1/4$ in the uniform-quadratic Crawford-Sobel model), no partitioned equilibrium with two or more intervals satisfies the boundary condition. The unique equilibrium is babbling.

**Intuition:** When interests are sufficiently misaligned, the receiver rationally ignores any message because any informative message would be exploited by the sender — so the receiver assumes the message carries no information. This becomes self-fulfilling: senders have no incentive to communicate truthfully since their messages are ignored.

---

## Application to AI: Instruction Following as Cheap Talk

### The Model Applied to AI

Map Crawford-Sobel to AI instruction following:
- **Sender** = user/operator/prompter with private intent $\theta$ (what they actually want)
- **Receiver** (action-taker) = AI model
- **Bias** $b$ = misalignment between what the user states as their goal and what the model is trained to optimize

The AI model receives a verbal message (the prompt) from the user and must take an action (generate a response). The user's stated instructions are **cheap talk** — they cost nothing to produce, and a user could write any prompt regardless of their true intent.

**When $b \approx 0$ (aligned):** The model can largely take instructions at face value; prompts are approximately truthful signals of intent. Truthful reporting is approximately incentive-compatible because user goals align with what the model is trained to produce.

**When $b > 0$ (misaligned):** Users may:
- State goals that are more acceptable than their true intent (e.g., "I need this for research" when the request has harmful applications)
- Use indirect prompting to achieve goals the model would refuse if stated directly
- Provide false context to shift the model's behavior

The model cannot verify most user claims about their identity, purpose, or authority. Treating all user claims as truthful is naive when incentives to misreport exist.

### System Prompts as Cheap Talk

System prompts from operators face the same issue:
- Any operator can write any system prompt — there's no enforcement mechanism
- The model cannot verify that the system prompt represents the operator's true deployment context
- An adversarial operator could use the system prompt to acquire trust the model would not otherwise grant

This is exactly Crawford-Sobel: the system prompt's informativeness depends on how aligned the operator's interests are with the intended use case. When operator interests and model/safety-team interests diverge sufficiently, prompt instructions carry little information about the deployment context.

### Instruction Hierarchy and Credible Domains

A practical response to the cheap talk problem is to create **costly signals** within the communication structure:
- **Verified operator identity** (API keys, contracts, legal accountability) transforms operator claims from cheap talk to partially costly signals — misrepresenting deployment context has legal consequences
- **Constitutional constraints** that cannot be overridden by instruction — regardless of what the prompt says, the model refuses certain actions, removing the "action space" the sender can manipulate
- **Calibrated skepticism** — the model treats unverifiable user claims as providing partial (not full) Bayesian updates on context

The Crawford-Sobel framework quantifies exactly when cheap talk claims can be informative: the model should be more responsive to operator instructions (low bias, strong accountability) than to anonymous user claims (potentially high bias, no accountability).

---

## Multi-Agent Cheap Talk

In multi-agent settings, cheap talk has additional complications:

**Committee communication (Battaglini, 2002):** Multiple senders with different biases can collectively transmit more information than a single sender. If two senders have biases in opposite directions ($+b$ and $-b$), their combined messages allow the receiver to triangulate the true $\theta$ — even though neither sender alone would be informative with so large a bias.

**Application to AI:** Multiple AI models with different training biases, or combining model outputs with human feedback, can collectively be more informative than any single source. Red-teaming (adversarial AI) can be viewed as a second sender with opposite bias, helping the evaluator better infer the true situation.

**Deliberative polls and structured dialogue:** Structured discussion processes that require participants to engage with opposing views can be modeled as multi-sender cheap talk mechanisms — cross-pressure can improve information transmission even without monetary transfers.

---

## Cheap Talk vs. Costly Signaling: Summary

| Dimension | Cheap talk | Costly signaling |
|---|---|---|
| Message cost | Zero | Positive, differentially costly |
| Incentive for truthfulness | Only when interests align | Always (if cost structure is right) |
| Equilibrium type | Partition equilibria (coarse); babbling | Separating equilibria (precise) |
| Information transmitted | Coarse classification | Fine or full type revelation |
| Example | Verbal claims, self-reports, prompts | Education, costly demonstrations, certified tests |
| AI analog | System prompts, user instructions | Benchmarks, formal verification, regulated audits |

---

## Key Results

| Result | Statement |
|---|---|
| Crawford-Sobel theorem | All cheap talk equilibria are partition equilibria; number of intervals decreases with bias $b$ |
| Babbling equilibrium | Always exists; no information transmitted |
| Pareto ranking of equilibria | Finer partition (more informative) equilibria Pareto-dominate coarser ones |
| Interest alignment → communication | As $b \to 0$, full information transmission becomes possible |
| Multi-sender advantage | Multiple senders with opposing biases can improve information transmission |

---

## See also

- `costly-signaling-spence.md` — costly signals as the alternative when interests diverge
- `extensive-form-games-backward-induction.md` — signaling games as sequential games of incomplete information
- `mechanism-design-revelation-principle.md` — direct mechanisms as a way to make communication truth-telling without requiring costly signals