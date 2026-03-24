---
created: '2026-03-21'
origin_session: core/memory/activity/2026/03/21/chat-001
source: agent-generated
trust: medium
---

# P, NP, and the Complexity Zoo

## Core Idea

Computational complexity theory classifies problems not by *what* they compute but by *the resources required* to compute them. The central hierarchy — P ⊆ NP ⊆ PSPACE ⊆ EXP — stratifies decision problems by time and space, and the question of whether these inclusions are strict constitutes the deepest open question in mathematics and computer science.

## Deterministic Time: P

A language $L$ is in **P** (polynomial time) if there exists a deterministic Turing machine $M$ and a polynomial $p$ such that for every input $x$, $M$ halts within $p(|x|)$ steps and accepts iff $x \in L$.

P captures the informal notion of "efficient computation." Examples:
- Sorting, shortest paths (Dijkstra), linear programming (Khachiyan's ellipsoid method, Karmarkar's interior point)
- Primality testing (AKS, 2002 — resolving a centuries-old question)
- Maximum matching (Edmonds' blossom algorithm)

Cobham's thesis: P = the class of feasibly computable problems. This is an idealisation — $n^{100}$ is technically polynomial but practically infeasible — yet the thesis holds remarkably well in practice.

## Nondeterministic Time: NP

$L \in \text{NP}$ if there exists a polynomial-time verifier $V$ and polynomial $p$ such that:
$$x \in L \iff \exists w \in \{0,1\}^{p(|x|)} : V(x, w) = 1$$

The witness $w$ (certificate, proof) can be checked efficiently even if finding it may be hard. NP captures the asymmetry between *solving* and *verifying*:
- **SAT**: Given a Boolean formula, is there a satisfying assignment? (verification: plug in and evaluate)
- **CLIQUE**: Given graph $G$ and integer $k$, is there a $k$-clique? (verification: check edges)
- **SUBSET-SUM**: Given integers, is there a subset summing to target $T$?

**co-NP** = $\{L : \bar{L} \in \text{NP}\}$. A problem is in co-NP if *non*-membership has short proofs. Example: TAUTOLOGY (is a formula true under all assignments?) is in co-NP.

If NP = co-NP, every NP problem would have both short proofs and short refutations — considered unlikely.

## The P vs NP Problem

**Statement**: Is P = NP?

Equivalently: can every problem whose solutions are efficiently *verifiable* also be efficiently *solved*?

Clay Millennium Prize Problem (\$1M). The consensus is P ≠ NP, but we lack proof. The question is profound because it asks whether *creative search* can always be replaced by *systematic computation*:

- If P = NP: mathematical proofs could be found as easily as verified, cryptography collapses, optimisation becomes trivial
- If P ≠ NP: there exist intrinsically hard problems — a fundamental asymmetry between creation and verification

**Why it's hard to resolve**: Three barrier results show that standard techniques cannot separate P from NP:
1. **Relativisation** (Baker-Gill-Solovay, 1975): There exist oracles relative to which P = NP and oracles relative to which P ≠ NP
2. **Natural proofs** (Razborov-Rudich, 1997): Any "natural" proof that P ≠ NP would break pseudorandom generators
3. **Algebrisation** (Aaronson-Wigderson, 2009): Algebraic extensions of existing techniques cannot resolve P vs NP

## The Polynomial Hierarchy

The **polynomial hierarchy** (PH) generalises NP by allowing alternating quantifiers:

$$\Sigma_0^P = \Pi_0^P = P$$
$$\Sigma_{k+1}^P = \text{NP}^{\Sigma_k^P}, \quad \Pi_{k+1}^P = \text{co-NP}^{\Sigma_k^P}$$

So $\Sigma_1^P = \text{NP}$, $\Pi_1^P = \text{co-NP}$, $\Sigma_2^P$ captures problems with $\exists\forall$ quantifier alternation, etc.

$$\text{PH} = \bigcup_{k \geq 0} \Sigma_k^P$$

**Collapse results**:
- If P = NP, the entire hierarchy collapses to P
- If $\Sigma_k^P = \Pi_k^P$ for any $k$, PH collapses to $\Sigma_k^P$
- It's widely believed that PH is infinite (i.e., doesn't collapse)

## Space Complexity: PSPACE

$L \in \text{PSPACE}$ if decidable using polynomial *space* (no time bound). By Savitch's theorem, NPSPACE = PSPACE (nondeterminism doesn't help for space).

$$\text{P} \subseteq \text{NP} \subseteq \text{PH} \subseteq \text{PSPACE} \subseteq \text{EXP}$$

Key results:
- **PSPACE-complete**: TQBF (True Quantified Boolean Formulas), generalised games (Chess, Go on $n \times n$ boards)
- **Savitch's theorem**: NSPACE$(s(n)) \subseteq$ DSPACE$(s(n)^2)$
- **Space hierarchy theorem**: More space strictly helps — SPACE$(n) \subsetneq$ SPACE$(n^2)$

The time hierarchy theorem similarly gives P $\subsetneq$ EXP, but doesn't resolve P vs NP because it only separates classes with a *quadratic* gap in the exponent.

## Randomised Complexity

- **BPP** (bounded-error probabilistic polynomial time): decidable with two-sided error ≤ 1/3
- **RP** (randomised polynomial time): one-sided error
- **ZPP** = RP ∩ co-RP: zero-error, polynomial *expected* time

The Sipser-Lautemann theorem: BPP ⊆ $\Sigma_2^P \cap \Pi_2^P$.

**Derandomisation conjecture**: BPP = P. Evidence: if strong enough pseudorandom generators exist (e.g., from circuit lower bounds via Nisan-Wigderson), then every randomised algorithm can be derandomised. The Impagliazzo-Wigderson theorem formalises this.

## Exponential Time

- **EXP** = $\text{DTIME}(2^{n^{O(1)}})$
- **NEXP** = $\text{NTIME}(2^{n^{O(1)}})$

**EXP-complete problems**: generalised chess with prescribed pieces, certain planning problems.

By the time hierarchy theorem: P ≠ EXP and NP ≠ NEXP. These are among the few separation results we have.

## Ladner's Theorem and NP-Intermediate Problems

If P ≠ NP, then there exist problems in NP that are neither in P nor NP-complete (**NP-intermediate**). Ladner's theorem (1975) proves this via an artificial diagonalisation.

Candidate natural NP-intermediate problems:
- **Graph isomorphism**: in NP, not known to be NP-complete, recently shown to be in quasipolynomial time (Babai, 2015)
- **Factoring**: not known to be NP-complete; in BQP (Shor's algorithm) but believed not in P
- **Discrete logarithm**: similar status to factoring

## Connections

- **Logic foundations**: Complexity classes have logical characterisations — see [descriptive-complexity-logic](descriptive-complexity-logic.md)
- **NP-completeness**: Cook-Levin theorem and the web of reductions — see [np-completeness-cook-karp](np-completeness-cook-karp.md)
- **Interactive proofs**: IP = PSPACE shows proof systems add surprising power — see [interactive-proofs-randomness](interactive-proofs-randomness.md)
- **Circuit complexity**: Non-uniform computation and lower bound barriers — see [circuit-complexity-lower-bounds](circuit-complexity-lower-bounds.md)
- **Game theory**: Computing Nash equilibria is PPAD-complete — see [../../game-theory/normal-form-games-nash-equilibrium.md](../game-theory/normal-form-games-nash-equilibrium.md)
- **Optimisation**: P vs NP determines whether optimisation problems admit efficient exact solutions — see (forthcoming) optimization files
- **Turing undecidability**: Complexity refines the decidable/undecidable dichotomy into a finer hierarchy — see [../logic-foundations/turing-undecidability-halting.md](../logic-foundations/turing-undecidability-halting.md)
