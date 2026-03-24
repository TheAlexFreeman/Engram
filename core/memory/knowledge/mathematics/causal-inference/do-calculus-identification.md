---
created: '2026-03-21'
origin_session: core/memory/activity/2026/03/21/chat-001
source: agent-generated
trust: medium
---

# The do-Calculus and Causal Identification

## Core Idea

The **identification problem** asks: when can we compute the interventional distribution $P(Y | \text{do}(X = x))$ from purely observational data $P(V)$ and knowledge of the causal graph? Pearl's **do-calculus** — three inference rules for manipulating expressions involving $\text{do}(\cdot)$ — provides a complete system for answering this question. When identification succeeds, it yields an **adjustment formula** expressing the causal effect in terms of observational quantities. The **backdoor criterion** and **frontdoor criterion** are the two most commonly used special cases.

---

## The Identification Problem

### When Experiments Are Impossible

We want $P(Y | \text{do}(X = x))$ but cannot run an experiment. We have:

- Observational data: $P(V_1, \dots, V_n)$
- Causal knowledge: the structure of the DAG $\mathcal{G}$

A causal effect is **identifiable** if every SCM compatible with $\mathcal{G}$ that generates the same $P(V)$ agrees on $P(Y | \text{do}(X))$. Equivalently: the causal effect is a unique function of the observational distribution given the graphical assumptions.

If a quantity is not identifiable, no amount of observational data (no matter how much) can determine it — the limitation is structural, not statistical. See [pearls-causal-hierarchy.md](pearls-causal-hierarchy.md) for why this is a fundamental collapse-theorem result.

---

## The Backdoor Criterion

### Statement

A set of variables $Z$ satisfies the **backdoor criterion** relative to $(X, Y)$ if:

1. No node in $Z$ is a descendant of $X$
2. $Z$ blocks every path between $X$ and $Y$ that has an arrow into $X$ (every "backdoor path")

### The Backdoor Adjustment Formula

If $Z$ satisfies the backdoor criterion:

$$P(Y | \text{do}(X = x)) = \sum_z P(Y | X = x, Z = z) \, P(Z = z)$$

This is a weighted average of the conditional distribution $P(Y | X, Z)$ over the marginal distribution of the adjustment set $Z$. It works because conditioning on $Z$ blocks the confounding paths while the marginal weighting removes the selection bias introduced by conditioning.

### Intuition

Backdoor adjustment simulates an experiment by:

1. Stratifying on all confounders $Z$
2. Within each stratum, the $X \to Y$ association is unconfounded
3. Averaging across strata with the natural weights $P(Z = z)$

For the drug-treatment example (with confounder $Z$ = socioeconomic status):

$$P(Y | \text{do}(\text{Drug})) = \sum_z P(Y | \text{Drug}, Z = z) \, P(Z = z)$$

---

## The Frontdoor Criterion

### The Problem: Unobserved Confounders

Sometimes there is no set $Z$ that satisfies the backdoor criterion (e.g., the confounder is unobserved). The **frontdoor criterion** handles certain such cases using a mediating variable.

### Statement

A set of variables $M$ satisfies the **frontdoor criterion** relative to $(X, Y)$ if:

1. $X$ blocks all directed paths from $M$ to $Y$ that do not go through $X$ (technical condition ensuring $M$ is "between" $X$ and $Y$)
2. There is no unblocked backdoor path from $X$ to $M$
3. All backdoor paths from $M$ to $Y$ are blocked by $X$

More concisely: $M$ mediates the entire effect of $X$ on $Y$, and the $X \to M$ and $M \to Y$ links are each separately identifiable.

### The Frontdoor Adjustment Formula

$$P(Y | \text{do}(X = x)) = \sum_m P(M = m | X = x) \sum_{x'} P(Y | M = m, X = x') \, P(X = x')$$

### Classic Example: Smoking → Tar → Cancer

If "smoking" ($X$) causes "cancer" ($Y$) only through "tar deposits" ($M$), and there is an unobserved confounder (e.g., genetic predisposition) linking $X$ and $Y$:

$$P(\text{Cancer} | \text{do}(\text{Smoking})) = \sum_m P(\text{Tar} = m | \text{Smoking}) \sum_{x'} P(\text{Cancer} | \text{Tar} = m, \text{Smoking} = x') P(\text{Smoking} = x')$$

The frontdoor formula identifies the causal effect even though the confounder is latent — a remarkable result that demonstrates the power of structural assumptions.

---

## Pearl's do-Calculus

### The Three Rules

Let $\mathcal{G}$ be a causal DAG over variables $V$. For disjoint subsets $X, Y, Z, W \subseteq V$:

**Rule 1 (Insertion/deletion of observations):**

$$P(Y | \text{do}(X), Z, W) = P(Y | \text{do}(X), W)$$

if $Y \perp_{\mathcal{G}_{\overline{X}}} Z \mid X, W$ (i.e., $Y$ and $Z$ are d-separated by $\{X, W\}$ in the graph $\mathcal{G}_{\overline{X}}$ obtained by deleting all edges into $X$)

**Rule 2 (Action/observation exchange):**

$$P(Y | \text{do}(X), \text{do}(Z), W) = P(Y | \text{do}(X), Z, W)$$

if $Y \perp_{\mathcal{G}_{\overline{X}, \underline{Z}}} Z \mid X, W$ (in the graph with edges into $X$ and out of $Z$ deleted)

**Rule 3 (Insertion/deletion of actions):**

$$P(Y | \text{do}(X), \text{do}(Z), W) = P(Y | \text{do}(X), W)$$

if $Y \perp_{\mathcal{G}_{\overline{X}, \overline{Z(S)}}} Z \mid X, W$ where $Z(S)$ is the set of $Z$-nodes that are not ancestors of any $W$-node in $\mathcal{G}_{\overline{X}}$

### Completeness

**Theorem (Huang & Valtorta, 2006; Shpitser & Pearl, 2006):** The do-calculus is **complete** for the identification of causal effects. If a causal effect is identifiable from the graph and observational data, the do-calculus can derive an expression for it. If it is not identifiable, no combination of rules will produce one.

The completeness result also yields an algorithmic procedure: the **ID algorithm** (Tian & Pearl, 2002) and its extensions provide a mechanical method for determining identifiability and computing the identifying expression.

---

## Instrumental Variables

### The Classical Setup

When a confounder between $X$ and $Y$ is unobserved and no mediator is available for the frontdoor criterion, an **instrumental variable** $Z$ can sometimes identify the causal effect:

- $Z$ affects $X$ (relevance)
- $Z$ affects $Y$ only through $X$ (exclusion restriction)
- $Z$ shares no common cause with $Y$ (independence)

### Identification

For linear models: $\text{ACE} = \frac{\text{Cov}(Z, Y)}{\text{Cov}(Z, X)}$ (the Wald estimator or two-stage least squares).

For non-linear models, the IV identifies the **local average treatment effect** (LATE) — the effect among "compliers" (units whose treatment status is influenced by the instrument). See [counterfactuals-rubin-potential-outcomes.md](counterfactuals-rubin-potential-outcomes.md).

### Examples

- **Draft lottery → military service → earnings**: The draft lottery ($Z$) randomly assigns propensity for military service ($X$), affecting earnings ($Y$) only through actual service
- **Mendelian randomisation**: Genetic variants ($Z$) affect a biomarker ($X$), which affects a disease outcome ($Y$). The "randomisation" is Mendel's law of independent assortment

---

## Identification Beyond Single Effects

### Conditional and Marginal Effects

The do-calculus extends to conditional causal effects $P(Y | \text{do}(X), Z)$, effects on distributions (quantiles, variances), and multi-variable interventions $P(Y | \text{do}(X_1), \text{do}(X_2))$.

### Transportability

Bareinboim and Pearl (2013) extended identification theory to **transportability**: when can experimental results from one population (source) be used to predict interventional effects in a different population (target)? The answer depends on the causal differences between populations, encoded in an augmented DAG ("selection diagram").

### Bounds When Not Fully Identified

When $P(Y | \text{do}(X))$ is not point-identified, it may still be **partially identified** — bounded within an interval. Balke-Pearl bounds use linear programming on the observable distribution to derive sharp bounds on the causal effect. These bounds are tight: no additional information (short of further assumptions or experiments) can narrow them.

---

## Connections

- **Structural causal models**: The DAG and SCM provide the necessary structure for applying the do-calculus — see [structural-causal-models-dags.md](structural-causal-models-dags.md)
- **Causal discovery**: The do-calculus assumes the graph is known; causal discovery aims to learn it — see [causal-discovery-algorithms.md](causal-discovery-algorithms.md)
- **Bayesian inference**: Bayesian approaches to causal inference place priors over the graph space — see [bayesian-inference-priors-posteriors.md](../probability/bayesian-inference-priors-posteriors.md)
- **Mechanism design**: Designing incentive-compatible mechanisms requires reasoning about interventions on agent strategies — see [mechanism-design-revelation-principle.md](../game-theory/mechanism-design-revelation-principle.md)
