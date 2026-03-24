---
created: '2026-03-21'
origin_session: core/memory/activity/2026/03/21/chat-001
source: agent-generated
trust: medium
---

# Pearl's Causal Hierarchy

## Core Idea

Judea Pearl's **causal hierarchy** (the "ladder of causation") distinguishes three fundamentally different types of reasoning about the world, each requiring strictly more information than the last:

1. **Association** (seeing): $P(Y | X)$ — What does observing $X$ tell me about $Y$?
2. **Intervention** (doing): $P(Y | \text{do}(X))$ — What happens to $Y$ if I actively set $X$?
3. **Counterfactual** (imagining): $P(Y_x | X' = x', Y' = y')$ — Given what actually happened, what *would* have happened if $X$ had been different?

Each rung cannot be answered from data at a lower rung alone. This hierarchy formalises why correlation does not imply causation, why observational studies cannot replace experiments (without additional assumptions), and why "what if?" questions require a structural model of the world.

---

## Rung 1: Association

### The Purely Statistical Level

At the associational level, we observe joint distributions $P(X, Y)$ and compute conditional probabilities, correlations, and statistical dependencies. All standard machine learning — regression, classification, density estimation — operates here.

**Typical questions:**
- What is $P(\text{recovery} | \text{took drug})$?
- Are education and income correlated?
- What category does this image belong to?

**Limitations:** Association cannot distinguish between:
- $X$ causes $Y$
- $Y$ causes $X$
- $X$ and $Y$ share a common cause $Z$
- The association is due to selection bias

Simpson's paradox — where a statistical association reverses when data is disaggregated — is an associational-level phenomenon that can only be resolved by moving to rung 2.

---

## Rung 2: Intervention

### The do-Operator

Pearl introduced the $\text{do}(X = x)$ operator to distinguish "setting $X$ to $x$" (intervention) from "observing $X = x$" (conditioning). The interventional distribution:

$$P(Y | \text{do}(X = x))$$

answers: "What would the distribution of $Y$ be if we surgically set $X = x$, regardless of what would have caused $X$ naturally?"

### The Fork-Chain-Collider Trichotomy

Three basic causal structures illustrate why intervention ≠ observation:

**Fork (common cause):** $X \leftarrow Z \rightarrow Y$
- $P(Y | X) \neq P(Y)$ (associated via $Z$)
- $P(Y | \text{do}(X)) = P(Y)$ (intervening on $X$ cuts the path through $Z$)

**Chain (mediation):** $X \rightarrow Z \rightarrow Y$
- $P(Y | X) \neq P(Y)$ (associated through $Z$)
- $P(Y | \text{do}(X)) \neq P(Y)$ ($X$ genuinely affects $Y$)

**Collider:** $X \rightarrow Z \leftarrow Y$
- $P(Y | X) = P(Y)$ (independent marginally)
- $P(Y | X, Z) \neq P(Y | Z)$ (conditioning on the collider opens the path — "explaining away")

### Randomised Controlled Trials

An RCT physically implements $\text{do}(X = x)$: the experimenter assigns treatment independently of all other variables. The randomisation ensures that confounders are (in expectation) balanced across treatment and control groups. Pearl's framework shows that an RCT estimates $P(Y | \text{do}(X))$ by design, and that under certain graphical conditions (see [do-calculus-identification.md](do-calculus-identification.md)), the same quantity can be estimated from observational data.

---

## Rung 3: Counterfactuals

### Structural Semantics

Counterfactuals require the full structural causal model (see [structural-causal-models-dags.md](structural-causal-models-dags.md)). Given structural equations $Y = f_Y(\text{Pa}_Y, U_Y)$ and observed evidence $(X = x', Y = y')$:

$$P(Y_x | X = x', Y = y')$$

reads: "Given that we *observed* $X = x'$ and $Y = y'$, what would $Y$ have been if $X$ had been $x$?"

This requires:

1. **Abduction**: Infer the exogenous variables $U$ from the evidence $(X = x', Y = y')$
2. **Action**: Modify the structural equations to set $X = x$ (sever the equation for $X$)
3. **Prediction**: Compute $Y$ under the modified model with the inferred $U$

### Why Rung 3 Goes Beyond Rung 2

Interventional distributions describe populations; counterfactuals describe individuals. For instance:

- **Rung 2**: "Among people like Alice, what fraction would recover if treated?" — $P(Y = 1 | \text{do}(X = 1))$
- **Rung 3**: "Alice was treated and recovered. Would she have recovered *without* treatment?" — $P(Y_0 = 1 | X = 1, Y = 1)$

The latter quantity (probability of necessity) cannot be computed from interventional data alone — it requires assumptions about the functional relationships.

---

## The Formal Collapse Theorem

Pearl and Bareinboim (2022) proved the **causal hierarchy theorem**: for generic structural causal models, knowledge of the distribution at rung $k$ does not determine any quantity at rung $k+1$. Specifically:

- There exist models with identical observational distributions $P(X, Y, Z, \dots)$ but different interventional distributions $P(Y | \text{do}(X))$
- There exist models with identical interventional distributions but different counterfactual probabilities

This is not just an epistemic limitation; it is a structural impossibility. The only way to bridge rungs is to add assumptions — structural (the DAG), parametric, or experimental.

---

## Pearl vs Rubin

The causal inference literature has two major frameworks:

| | Pearl (graphical) | Rubin (potential outcomes) |
|---|---|---|
| Primitive | Structural equations + DAG | Potential outcomes $Y(0), Y(1)$ |
| Notation | $\text{do}(X = x)$ | $Y(x)$ or $Y^x$ |
| Assumptions encoded in | Graph structure (d-separation) | Ignorability conditions |
| Identification | Graphical criteria (backdoor, frontdoor, do-calculus) | Design-based arguments |
| Counterfactuals | Built into the model (rung 3) | Primitive (but not always used) |
| Strengths | Transparent assumptions, general identification theory | Close to experimental practice, clear estimation |

The frameworks are **formally equivalent** (Pearl, 2000, Ch. 7): potential outcomes can be derived from SCMs, and SCMs can (with some work) be encoded in the Rubin framework. The difference is practical emphasis: Pearl prioritises transparent modelling of assumptions; Rubin prioritises design and estimation.

See [counterfactuals-rubin-potential-outcomes.md](counterfactuals-rubin-potential-outcomes.md) for the Rubin framework in detail.

---

## Implications for AI and ML

### ML Operates at Rung 1

Standard supervised learning models learn $P(Y | X)$ — associations. They cannot answer:

- "What would happen if we changed feature $X$?" (intervention)
- "Why did the model predict this?" (counterfactual explanation)

This limits their use in decision-making, policy evaluation, and explanation.

### Causal AI

Moving ML beyond rung 1 requires:

- **Causal representation learning**: Learning representations that capture causal structure, not just statistical associations
- **Invariant risk minimisation**: Training models whose predictive mechanism is stable across environments (a proxy for causal mechanisms)
- **Counterfactual fairness**: A decision is fair if it would have been the same in a counterfactual world where the individual belonged to a different protected group — a rung 3 notion

### Connection to Agency

The hierarchy maps onto agents' capabilities:

- Rung 1: Passive observers (pure ML)
- Rung 2: Agents that can intervene (reinforcement learning, experimental design)
- Rung 3: Agents that can reason about hypothetical alternative histories (planning, moral reasoning)

This connects to the dynamical systems view of intelligence: agents at higher rungs of the hierarchy maintain richer internal models of the world that allow more sophisticated prediction and action.

---

## Connections

- **Bayesian inference**: Bayes' theorem operates at rung 1; Bayesian causal inference extends to rung 2 — see [bayesian-inference-priors-posteriors.md](../probability/bayesian-inference-priors-posteriors.md)
- **Mechanism design**: Designing systems that incentivise truthful revelation uses interventional reasoning — see [mechanism-design-revelation-principle.md](../game-theory/mechanism-design-revelation-principle.md)
- **Game theory**: Strategic interaction involves reasoning about counterfactual actions — see [normal-form-games-nash-equilibrium.md](../game-theory/normal-form-games-nash-equilibrium.md)
