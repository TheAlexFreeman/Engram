---
created: '2026-03-21'
origin_session: core/memory/activity/2026/03/21/chat-001
source: agent-generated
trust: medium
---

# Counterfactuals and the Rubin Potential Outcomes Framework

## Core Idea

The **potential outcomes framework** (Rubin, 1974; Neyman, 1923) defines causal effects as comparisons between potential states of the world: "What would have happened under treatment $X = 1$ versus $X = 0$?" The **fundamental problem of causal inference** is that we observe at most one potential outcome per unit — the other is a missing data problem. This framework, dominant in economics, epidemiology, and the social sciences, makes identification assumptions explicit and maintains a tight coupling between causal definitions and statistical estimation.

---

## Potential Outcomes

### Definition

For a binary treatment $X \in \{0, 1\}$ and outcome $Y$, define for each unit $i$:

- $Y_i(1)$: the outcome if unit $i$ receives treatment
- $Y_i(0)$: the outcome if unit $i$ receives control

The **individual treatment effect** (ITE) is:

$$\tau_i = Y_i(1) - Y_i(0)$$

The fundamental problem: we observe $Y_i = X_i \cdot Y_i(1) + (1 - X_i) \cdot Y_i(0)$, never both $Y_i(1)$ and $Y_i(0)$.

### The SUTVA Assumption

The **stable unit treatment value assumption** (SUTVA) requires:

1. **No interference**: Unit $i$'s potential outcome depends only on $i$'s own treatment, not on others' treatments
2. **No hidden versions**: There is only one version of each treatment level

SUTVA fails in network settings (vaccination spillovers, peer effects) and when treatment implementation varies across contexts. When SUTVA fails, potential outcomes must be indexed by the full treatment vector $Y_i(\mathbf{X})$, and the framework becomes much more complex.

---

## Causal Estimands

### Average Treatment Effect (ATE)

$$\tau_\text{ATE} = \mathbb{E}[Y(1) - Y(0)] = \mathbb{E}[Y(1)] - \mathbb{E}[Y(0)]$$

The average effect across the entire population.

### Average Treatment Effect on the Treated (ATT)

$$\tau_\text{ATT} = \mathbb{E}[Y(1) - Y(0) | X = 1]$$

The average effect among those who actually received treatment. Often more policy-relevant (e.g., "Did the program help those who enrolled?").

### Local Average Treatment Effect (LATE)

$$\tau_\text{LATE} = \frac{\mathbb{E}[Y | Z = 1] - \mathbb{E}[Y | Z = 0]}{\mathbb{E}[X | Z = 1] - \mathbb{E}[X | Z = 0]}$$

The effect among "compliers" — units whose treatment status is affected by the instrument $Z$. The LATE is what instrumental variable estimation identifies (see [do-calculus-identification.md](do-calculus-identification.md)).

### Conditional Average Treatment Effect (CATE)

$$\tau(x) = \mathbb{E}[Y(1) - Y(0) | X_{\text{covariates}} = x]$$

The treatment effect as a function of covariates — the target of heterogeneous treatment effect estimation and personalised decision-making.

---

## Identification Assumptions

### Ignorability (Unconfoundedness)

$$\{Y(0), Y(1)\} \perp\!\!\!\perp X \mid Z$$

Given covariates $Z$, treatment assignment is independent of potential outcomes. This is the potential-outcomes analogue of the backdoor criterion in Pearl's framework: $Z$ blocks all confounding paths.

Under ignorability:

$$\mathbb{E}[Y(x)] = \mathbb{E}_Z[\mathbb{E}[Y | X = x, Z]]$$

which is the **g-formula** (Robins) or equivalently the backdoor adjustment formula.

### Overlap (Positivity)

$$0 < P(X = 1 | Z = z) < 1 \quad \text{for all } z \text{ with } P(Z = z) > 0$$

Every unit has a positive probability of receiving either treatment or control. Without overlap, some subpopulations provide no information about the missing potential outcome.

### Randomised Controlled Trials

An RCT ensures ignorability by design ($X$ is assigned independently of everything). With complete randomisation:

$$\tau_\text{ATE} = \mathbb{E}[Y | X = 1] - \mathbb{E}[Y | X = 0]$$

is an unbiased estimator — no adjustment needed. This is why RCTs are the gold standard: they guarantee rung 2 identification without structural assumptions.

---

## Estimation Methods

### Inverse Probability Weighting (IPW)

Define the **propensity score** $e(z) = P(X = 1 | Z = z)$. The Horvitz-Thompson estimator:

$$\hat{\tau}_\text{IPW} = \frac{1}{n} \sum_i \left[\frac{X_i Y_i}{e(Z_i)} - \frac{(1 - X_i) Y_i}{1 - e(Z_i)}\right]$$

IPW reweights observations to simulate a randomised experiment. Extreme propensity scores (near 0 or 1) cause high variance.

### Doubly Robust Estimation (AIPW)

The **augmented IPW** estimator combines outcome modelling and propensity score weighting:

$$\hat{\tau}_\text{DR} = \frac{1}{n}\sum_i \left[\hat{\mu}_1(Z_i) - \hat{\mu}_0(Z_i) + \frac{X_i(Y_i - \hat{\mu}_1(Z_i))}{e(Z_i)} - \frac{(1-X_i)(Y_i - \hat{\mu}_0(Z_i))}{1 - e(Z_i)}\right]$$

where $\hat{\mu}_x(z) = \hat{\mathbb{E}}[Y | X = x, Z = z]$. This estimator is **doubly robust**: it is consistent if *either* the outcome model or the propensity score model is correctly specified (but not necessarily both). It also achieves the semiparametric efficiency bound.

### Matching

Match treated units to similar control units (on covariates or propensity score):

$$\hat{\tau}_i = Y_i - Y_{j(i)}$$

where $j(i)$ is the closest control unit to treated unit $i$. Matching makes the comparison explicit but can introduce bias if matches are poor.

---

## Mediation Analysis

### Natural Direct and Indirect Effects

For treatment $X$, mediator $M$, and outcome $Y$:

- **Natural direct effect** (NDE): $\mathbb{E}[Y(1, M(0)) - Y(0, M(0))]$ — the effect of $X$ on $Y$ not through $M$
- **Natural indirect effect** (NIE): $\mathbb{E}[Y(1, M(1)) - Y(1, M(0))]$ — the effect through $M$
- **Total effect** = NDE + NIE (on the difference scale)

The nested counterfactual $Y(x, M(x'))$ — the outcome when treatment is $x$ but the mediator takes the value it *would have taken* under $x'$ — is a rung 3 quantity. It cannot be identified from experimental data alone without cross-world assumptions (see [pearls-causal-hierarchy.md](pearls-causal-hierarchy.md)).

### Identification of Mediational Effects

Under sequential ignorability:

1. $\{Y(x, m)\} \perp\!\!\!\perp X \mid Z$ (unconfounded treatment)
2. $\{Y(x, m)\} \perp\!\!\!\perp M \mid X, Z$ (unconfounded mediator)

the mediation formula (Pearl's mediation formula or the g-computation formula for mediation) identifies both NDE and NIE from observational data.

---

## Connection to Pearl's Framework

### Formal Equivalence

Pearl (2000) showed that potential outcomes can be derived from an SCM:

$$Y_i(x) = Y_i \big|_{\text{do}(X = x)} = f_Y(x, \text{Pa}_Y \setminus X, U_{Y,i})$$

The potential outcome is the counterfactual value of $Y$ computed from the structural equations after intervening on $X$.

### Ignorability vs the Backdoor Criterion

| Rubin | Pearl |
|-------|-------|
| $\{Y(0), Y(1)\} \perp X \mid Z$ | $Z$ satisfies the backdoor criterion relative to $(X, Y)$ |
| Propensity score $e(z)$ | $P(X \mid Z)$ in the observational model |
| IPW estimator | Backward adjustment formula |

The assumptions are formally equivalent but differ in transparency: Pearl's graphical conditions make causal assumptions visible; Rubin's conditions are stated in terms of potential outcomes, which are unobservable.

### Where They Diverge

- **Mediation**: Pearl's mediation formula is derived graphically; the potential outcomes framework requires sequential ignorability stated in terms of cross-world independence
- **Complex structures**: For multi-treatment, time-varying settings, Pearl's do-calculus provides systematic identification; the potential outcomes framework requires careful sequential application of ignorability
- **Communication**: The potential outcomes framework dominates in statistics and economics; Pearl's framework dominates in AI and computer science

---

## Connections

- **Structural causal models**: SCMs provide the generative model from which potential outcomes are derived — see [structural-causal-models-dags.md](structural-causal-models-dags.md)
- **Bayesian inference**: Bayesian causal inference places priors on potential outcome distributions and treatment effects — see [bayesian-inference-priors-posteriors.md](../probability/bayesian-inference-priors-posteriors.md)
- **Concentration inequalities**: Finite-sample guarantees for treatment effect estimators use Hoeffding/Bernstein bounds — see [concentration-inequalities.md](../probability/concentration-inequalities.md)
- **Mechanism design**: The designer's problem is: what treatment (mechanism) maximises the social welfare, accounting for strategic responses? — see [mechanism-design-revelation-principle.md](../game-theory/mechanism-design-revelation-principle.md)
