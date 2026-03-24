---
created: '2026-03-21'
origin_session: core/memory/activity/2026/03/21/chat-001
source: agent-generated
trust: medium
---

# NP-Completeness: Cook-Levin and Karp Reductions

## Core Idea

NP-completeness identifies a class of problems that are the *hardest* in NP: if any one of them admits a polynomial-time algorithm, then P = NP. Cook's theorem (1971) established that SAT is NP-complete; Karp (1972) showed 21 diverse problems share this status via polynomial reductions. The resulting web of reductions reveals deep structural connections between seemingly unrelated combinatorial problems.

## Polynomial-Time Reductions

A **many-one (Karp) reduction** from language $A$ to language $B$ is a polynomial-time computable function $f$ such that:
$$x \in A \iff f(x) \in B$$

Written $A \leq_p B$. If $B \in P$ and $A \leq_p B$, then $A \in P$ (closure under reduction).

A **Turing (Cook) reduction** allows the reducing machine to make multiple adaptive queries to $B$ — strictly more general than Karp reductions but less commonly used for NP-completeness because Karp reductions preserve the asymmetry between NP and co-NP.

## NP-Completeness Definition

A language $L$ is **NP-hard** if every language in NP reduces to $L$: $\forall A \in \text{NP}: A \leq_p L$.

$L$ is **NP-complete** if $L$ is NP-hard and $L \in \text{NP}$.

## Cook-Levin Theorem

**Theorem** (Cook 1971, Levin 1973 independently): SAT is NP-complete.

**Proof sketch**: Given any NP language $L$ with verifier $V(x, w)$ running in time $p(|x|)$:
1. Encode the computation of $V$ on input $(x, w)$ as a Boolean circuit $C_x$
2. $C_x$ has $p(|x|)$ input bits (the witness $w$) and outputs 1 iff $V$ accepts
3. Convert $C_x$ to a CNF formula $\varphi_x$ using the Tseytin transformation (introducing auxiliary variables for each gate)
4. $\varphi_x$ is satisfiable iff $x \in L$
5. The reduction runs in polynomial time

The key insight: any polynomial-time computation can be "compiled" into a Boolean formula of polynomial size. This is why SAT is *universal* for NP.

**3-SAT**: The Tseytin transformation produces clauses of size ≤ 3, so 3-SAT is also NP-complete. (2-SAT, by contrast, is in P via implication graphs.)

## Karp's 21 NP-Complete Problems

Karp (1972) demonstrated NP-completeness for 21 problems by a chain of reductions from SAT:

**From SAT** → 3-SAT → {CLIQUE, VERTEX COVER, SET COVER, INDEPENDENT SET}

**Graph problems**: CLIQUE, INDEPENDENT SET, VERTEX COVER, GRAPH COLOURING (chromatic number), HAMILTONIAN CYCLE, HAMILTONIAN PATH

**Set/number problems**: SET COVER, EXACT COVER, SUBSET SUM, PARTITION, 3D MATCHING, KNAPSACK

**Logic/satisfiability**: SAT, 3-SAT, MAX-2-SAT (optimisation variant)

**Sequencing**: JOB SCHEDULING, TRAVELLING SALESMAN (decision version)

The reduction structure often reveals hidden equivalences:
- CLIQUE ↔ INDEPENDENT SET (complement graph)
- VERTEX COVER ↔ INDEPENDENT SET ($S$ is a vertex cover iff $V \setminus S$ is independent)
- König's theorem: in bipartite graphs, VERTEX COVER = MAXIMUM MATCHING (polynomial!)

## The Art of Reduction

A well-crafted reduction $A \leq_p B$ must:
1. Map YES-instances of $A$ to YES-instances of $B$ (completeness)
2. Map NO-instances of $A$ to NO-instances of $B$ (soundness)
3. Run in polynomial time

**Gadget reductions**: Most reductions from 3-SAT work by designing *gadgets* — small substructures that enforce variable/clause semantics within the target problem's domain:
- For GRAPH 3-COLOURING: triangle gadgets force True/False/Base colours; clause gadgets connect literals
- For HAMILTONIAN CYCLE: crossover gadgets route paths to simulate literal selection

**Schaefer's dichotomy theorem** (1978): For every finite set of Boolean relations $\Gamma$, the constraint satisfaction problem CSP($\Gamma$) is either in P or NP-complete. There are exactly six tractable cases (2-SAT, Horn-SAT, dual-Horn, affine, 0-valid, 1-valid); everything else is NP-complete. Bulatov (2017) extended this to all finite-domain CSPs.

## Approximability and the Optimisation Frontier

NP-completeness of the *decision* version doesn't fully characterise *optimisation* hardness. The theory of approximation algorithms reveals a rich structure:

**Polynomial-time approximation**:
- VERTEX COVER: 2-approximation (take both endpoints of a maximal matching)
- METRIC TSP: 3/2-approximation (Christofides-Serdyukov)
- MAX-CUT: 0.878-approximation (Goemans-Williamson SDP relaxation)

**Inapproximability** (assuming P ≠ NP):
- CLIQUE: no $n^{1-\varepsilon}$-approximation (Håstad/Zuckerman)
- SET COVER: no $(1 - \varepsilon) \ln n$-approximation (Dinur-Steurer)
- MAX-3-SAT: no 7/8 + ε approximation (Håstad, tight — random assignment achieves 7/8)

The **PCP theorem** (Arora-Safra, Arora-Lund-Motwani-Sudan-Szegedy, 1998) — NP = PCP[O(log n), O(1)] — is the engine behind these inapproximability results. It shows that NP proofs can be verified by reading only a constant number of random bits, which implies that approximating many NP-hard optimisation problems is itself NP-hard.

## The Unique Games Conjecture

Khot's **Unique Games Conjecture** (UGC, 2002): For every $\varepsilon > 0$, it is NP-hard to determine whether a unique-label-cover instance has value $\geq 1 - \varepsilon$ or $\leq \varepsilon$.

If true, UGC implies:
- The Goemans-Williamson 0.878 ratio for MAX-CUT is optimal
- Vertex Cover has no $(2 - \varepsilon)$-approximation
- A unified explanation for optimal approximation ratios across many problems

UGC remains unresolved but has been enormously productive as a research hypothesis.

## Practical Tractability Despite Worst-Case Hardness

NP-complete problems are ubiquitous in practice and often *solved*:

**SAT solvers**: Modern CDCL (Conflict-Driven Clause Learning) solvers handle industrial instances with millions of variables. The gap between worst-case theory and practice is enormous.

**Parameterised complexity**: FPT (fixed-parameter tractable) algorithms run in time $f(k) \cdot n^{O(1)}$ where $k$ is a structural parameter. Vertex Cover is FPT in the cover size $k$: $O(2^k \cdot n)$.

**Average-case complexity**: Some NP-complete problems are easy on random instances (e.g., random 3-SAT below the satisfiability threshold $\alpha_s \approx 4.267$ is easy for simple algorithms).

**Phase transitions**: Random instances of NP-complete problems exhibit sharp phase transitions at critical parameter values — connecting to [statistical mechanics of learning](../statistical-mechanics/statistical-mechanics-of-learning.md).

## Connections

- **P vs NP and the complexity zoo**: The broader landscape — see [p-np-and-complexity-classes](p-np-and-complexity-classes.md)
- **PCPs and interactive proofs**: The PCP theorem and zero-knowledge — see [interactive-proofs-randomness](interactive-proofs-randomness.md)
- **Circuit lower bounds**: Why separation proofs are hard — see [circuit-complexity-lower-bounds](circuit-complexity-lower-bounds.md)
- **Descriptive complexity**: Logical characterisations of NP — see [descriptive-complexity-logic](descriptive-complexity-logic.md)
- **Game theory**: Computing Nash equilibria is PPAD-complete, not NP-complete — a subtler hardness — see [../game-theory/normal-form-games-nash-equilibrium.md](../game-theory/normal-form-games-nash-equilibrium.md)
- **Statistical mechanics**: Phase transitions in random CSPs — see [../statistical-mechanics/spin-glasses-replica-method.md](../statistical-mechanics/spin-glasses-replica-method.md)
- **Gödel and undecidability**: NP-completeness vs undecidability — finite vs infinite witnesses — see [../logic-foundations/turing-undecidability-halting.md](../logic-foundations/turing-undecidability-halting.md)
