---
created: '2026-03-21'
origin_session: core/memory/activity/2026/03/21/chat-001
source: agent-generated
trust: medium
---

# Structural Causal Models and Directed Acyclic Graphs

## Core Idea

A **structural causal model** (SCM) encodes the data-generating process of a system as a set of deterministic functional equations with independent noise terms, together with a directed acyclic graph (DAG) that makes the causal structure visually explicit. The DAG's topology encodes every conditional independence implied by the causal structure via **d-separation**, providing a complete bridge between causal assumptions and observable statistical properties. SCMs are the formal backbone of Pearl's causal hierarchy.

---

## Structural Causal Models

### Definition

An SCM $\mathcal{M} = (U, V, F, P(U))$ consists of:

- **Exogenous variables** $U = \{U_1, \dots, U_n\}$: external factors, mutually independent, unobserved
- **Endogenous variables** $V = \{V_1, \dots, V_n\}$: the variables of interest
- **Structural equations** $F = \{f_1, \dots, f_n\}$: each $V_i = f_i(\text{Pa}_i, U_i)$ where $\text{Pa}_i \subseteq V \setminus \{V_i\}$ are the direct causes ("parents") of $V_i$
- **Exogenous distribution** $P(U)$: a joint distribution over noise terms

The structural equations are **autonomous**: each equation represents an independent causal mechanism. This modularity means that intervening on $V_j$ (replacing its equation) does not affect the equations for other variables — the **principle of independent mechanisms**.

### Example: Drug Treatment

$$U_Z, U_X, U_Y \text{ mutually independent}$$
$$Z = f_Z(U_Z) \quad \text{(socioeconomic status)}$$
$$X = f_X(Z, U_X) \quad \text{(treatment decision)}$$
$$Y = f_Y(X, Z, U_Y) \quad \text{(health outcome)}$$

Here $Z$ confounds the $X \to Y$ effect because it influences both treatment and outcome.

### From SCM to Joint Distribution

An SCM coupled with $P(U)$ induces a unique joint distribution $P(V_1, \dots, V_n)$ by recursive substitution (the DAG ensures no circular dependencies). Conversely, many different SCMs can produce the same joint distribution — the mapping from models to distributions is many-to-one.

---

## Directed Acyclic Graphs

### Construction

The **causal DAG** $\mathcal{G}$ has:

- One node per endogenous variable $V_i$
- A directed edge $V_j \to V_i$ whenever $V_j \in \text{Pa}_i$ (i.e., $V_j$ appears in the structural equation for $V_i$)
- No directed cycles (acyclicity ensures well-defined recursive computation)

### Ancestral Relations

- **Parents** $\text{Pa}(X)$: direct causes
- **Children**: direct effects
- **Ancestors**: all variables reachable by directed paths going backwards
- **Descendants**: all variables reachable by directed paths going forwards

---

## The Causal Markov Condition

### Statement

Every variable $V_i$ is conditionally independent of its non-descendants given its parents:

$$V_i \perp\!\!\!\perp \text{NonDesc}(V_i) \mid \text{Pa}(V_i)$$

This is the bridge between the causal graph and the probability distribution. It implies a **Markov factorisation**:

$$P(V_1, \dots, V_n) = \prod_{i=1}^n P(V_i | \text{Pa}(V_i))$$

Each factor $P(V_i | \text{Pa}(V_i))$ corresponds to the stochastic version of one structural equation.

### Faithfulness

The **faithfulness assumption** states that the *only* conditional independencies in $P$ are those implied by the Markov condition on $\mathcal{G}$. Without faithfulness, additional "accidental" independencies could hide true causal edges. Faithfulness is a genericity assumption: the set of parameters that violate it has Lebesgue measure zero.

---

## D-Separation

### The Central Algorithm

**D-separation** is a purely graphical criterion that determines which conditional independence statements are implied by the DAG. A path between $X$ and $Y$ is **blocked** by a conditioning set $Z$ if it contains:

1. A **chain** $A \to B \to C$ or **fork** $A \leftarrow B \rightarrow C$ where $B \in Z$ (conditioning blocks the flow)
2. A **collider** $A \to B \leftarrow C$ where $B \notin Z$ and no descendant of $B$ is in $Z$ (not conditioning blocks the flow at colliders)

$X$ and $Y$ are **d-separated** given $Z$ if every undirected path between them is blocked.

### The Soundness and Completeness Result

**Theorem (Verma & Pearl, 1988):** Under the causal Markov condition and faithfulness:

$$X \perp\!\!\!\perp Y \mid Z \text{ in } P \iff X \text{ and } Y \text{ are d-separated by } Z \text{ in } \mathcal{G}$$

This makes d-separation both:
- **Sound**: Every d-separation implies a conditional independence
- **Complete** (under faithfulness): Every conditional independence is implied by some d-separation

### Key D-Separation Patterns

| Structure | Unconditional | Conditional on $B$ |
|-----------|--------------|-------------------|
| $A \to B \to C$ (chain) | $A \not\perp C$ | $A \perp C \mid B$ |
| $A \leftarrow B \rightarrow C$ (fork) | $A \not\perp C$ | $A \perp C \mid B$ |
| $A \to B \leftarrow C$ (collider) | $A \perp C$ | $A \not\perp C \mid B$ |

The collider ("explaining away") is the surprising one: two independent causes become dependent when their common effect is observed.

---

## Interventions in the SCM

### The Truncated Factorisation

Intervening $\text{do}(X = x)$ in an SCM means replacing the structural equation for $X$ with $X = x$, leaving all other equations intact. In the DAG, this corresponds to removing all edges into $X$ (severing $X$ from its causes).

The interventional distribution:

$$P(V_1, \dots, V_n | \text{do}(X = x)) = \prod_{i: V_i \neq X} P(V_i | \text{Pa}(V_i)) \bigg|_{X=x}$$

This "truncated factorisation" (also called the "manipulation theorem" or "g-formula") removes the factor $P(X | \text{Pa}(X))$ and substitutes $X = x$ everywhere.

### Counterfactuals in the SCM

For counterfactual queries $P(Y_x | X = x', Y = y')$:

1. **Abduction**: Compute $P(U | X = x', Y = y')$ — update the exogenous variables given the evidence
2. **Action**: Replace the equation for $X$ with $X = x$
3. **Prediction**: Compute $Y$ under the modified model with the updated $U$

This three-step procedure requires the full SCM (not just the DAG or the interventional distribution).

---

## Markov Equivalence

### The Problem of Observational Indistinguishability

Different DAGs can encode exactly the same set of conditional independence relations. Such DAGs form a **Markov equivalence class**, represented by a **completed partially directed acyclic graph** (CPDAG):

- All DAGs in the equivalence class share the same skeleton (undirected edges) and the same **v-structures** (colliders $A \to B \leftarrow C$ where $A$ and $C$ are not adjacent)
- Edges present in all DAGs in the class are directed; those whose orientation varies are undirected

**Implication:** From observational data alone, we can identify the Markov equivalence class but not the unique causal DAG. Distinguishing among equivalent DAGs requires interventions, time-series information, or additional functional assumptions (e.g., non-Gaussianity in LiNGAM — see [causal-discovery-algorithms.md](causal-discovery-algorithms.md)).

---

## Assumptions and Limitations

### Causal Sufficiency

The standard SCM assumes no latent common causes. When latent confounders exist, the analysis must use:

- **Ancestral graphs** or **MAGs** (maximal ancestral graphs) that represent latent variable effects with bidirected edges
- The **FCI algorithm** for causal discovery with latent confounders

### No Cycles

Standard SCMs require acyclicity (DAGs). **Structural equation models with cycles** exist but require equilibrium assumptions and different identification techniques. Feedback loops are common in dynamical systems (see [dynamical-systems-fundamentals.md](../dynamical-systems/dynamical-systems-fundamentals.md)); the SCM framework handles them poorly, which is a known limitation.

### Modularity Assumption

The principle of independent mechanisms assumes that changing one equation does not affect others. This fails in tightly coupled systems where interventions propagate through feedback loops — another point where the dynamical systems and causal inference frameworks diverge.

---

## Connections

- **Pearl's causal hierarchy**: The SCM is the formal model underlying all three rungs — see [pearls-causal-hierarchy.md](pearls-causal-hierarchy.md)
- **do-calculus**: Graphical rules for deriving interventional distributions from the DAG — see [do-calculus-identification.md](do-calculus-identification.md)
- **Counterfactuals**: The three-step abduction-action-prediction procedure requires the full SCM — see [counterfactuals-rubin-potential-outcomes.md](counterfactuals-rubin-potential-outcomes.md)
- **Bayesian networks**: The DAG + Markov factorisation is a Bayesian network; the causal interpretation adds interventional semantics — see [bayesian-inference-priors-posteriors.md](../probability/bayesian-inference-priors-posteriors.md)
