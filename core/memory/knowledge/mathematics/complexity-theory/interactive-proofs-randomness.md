---
created: '2026-03-21'
origin_session: core/memory/activity/2026/03/21/chat-001
source: agent-generated
trust: medium
---

# Interactive Proofs and Randomness in Computation

## Core Idea

Interactive proof systems generalise the classical notion of mathematical proof by allowing *interaction* and *randomness*. The verifier can flip coins and ask questions; the prover responds adaptively. The resulting class IP equals PSPACE — a stunning theorem showing that interaction exponentially amplifies verification power. Extensions include zero-knowledge proofs (proving knowledge without revealing it) and probabilistically checkable proofs (PCPs), which underpin the theory of hardness of approximation.

## Interactive Proof Systems

An **interactive proof system** for a language $L$ is a protocol between:
- **Prover** $P$: computationally unbounded, trying to convince the verifier that $x \in L$
- **Verifier** $V$: polynomial-time, randomised, trying to avoid being fooled

Requirements:
- **Completeness**: $x \in L \implies \Pr[V \text{ accepts in } (P, V)(x)] \geq 2/3$
- **Soundness**: $x \notin L \implies$ for *all* provers $P^*$: $\Pr[V \text{ accepts in } (P^*, V)(x)] \leq 1/3$

**IP** = class of languages with interactive proof systems (polynomially many rounds).

### Arthur-Merlin Games

Babai (1985) defined a restricted model where the verifier's coin flips are *public* (the prover can see them):
- **MA** (Merlin-Arthur): Merlin sends a message, then Arthur verifies with randomness. Equivalent to "NP with randomised verification."
- **AM** (Arthur-Merlin): Arthur sends random coins, Merlin responds, Arthur verifies.
- **AM[$k$]**: $k$ rounds of interaction.

**Babai-Moran theorem**: AM[$k$] = AM for all constant $k \geq 2$. Constant rounds of public-coin interaction collapse to just two rounds.

**Goldwasser-Sipser theorem**: Private coins don't help — IP[$k$] = AM[$k$] (up to one extra round).

### Graph Non-Isomorphism in AM

A celebrated example: **Graph Non-Isomorphism** (GNI) is in AM.

Protocol: Given graphs $G_0, G_1$:
1. Verifier randomly picks $b \in \{0, 1\}$, randomly permutes $G_b$ to get $H$, sends $H$ to Prover
2. Prover identifies $b$ (possible iff $G_0 \not\cong G_1$)
3. Verifier checks Prover's answer

If $G_0 \cong G_1$, the prover cannot distinguish — soundness holds with probability 1/2 (amplifiable).

This showed GNI is "not NP-hard" (in a technicl sense: if GNI is NP-hard, PH collapses). A precursor to Babai's quasipolynomial GI algorithm (2015).

## IP = PSPACE

**Theorem** (Shamir, 1992): IP = PSPACE.

This is one of the most surprising results in complexity theory. A polynomial-time randomised verifier, interacting with an all-powerful prover, can verify *exactly* the PSPACE-decidable languages.

**Proof architecture**:

*PSPACE ⊆ IP*: Start with TQBF (True Quantified Boolean Formulas), which is PSPACE-complete:
$$\forall x_1 \exists x_2 \forall x_3 \ldots \varphi(x_1, \ldots, x_n)$$

**Arithmetisation**: Replace $\wedge$ with multiplication, $\vee$ with $1-(1-a)(1-b)$, work over a finite field $\mathbb{F}_p$.

The protocol uses the **sum-check protocol** (Lund-Fortnow-Karloff-Nisan, 1992):
- To verify $\sum_{x \in \{0,1\}^n} f(x) = v$, the verifier sequentially pins down each variable using random field elements
- Each round reduces the claim to a univariate polynomial identity, which can be checked probabilistically
- After $n$ rounds, the verifier evaluates $f$ at a single point

For quantified formulas, replace $\forall x$ with $\prod_{x \in \{0,1\}}$ and $\exists x$ with $\sum_{x \in \{0,1\}}$, then apply sum-check.

*IP ⊆ PSPACE*: By exhaustive search over all possible prover strategies.

## Zero-Knowledge Proofs

A proof system is **zero-knowledge** if the verifier learns nothing beyond the validity of the statement — formally, the verifier's view can be *simulated* without the prover.

**Definitions** (Goldwasser-Micali-Rackoff, 1985):
- **Perfect ZK**: Simulator output is identically distributed to the real interaction
- **Statistical ZK**: Simulator output is statistically close
- **Computational ZK**: Simulator output is computationally indistinguishable

### Graph Isomorphism ZK Protocol

Given $G_0, G_1$ that are isomorphic (prover knows the isomorphism $\pi$):
1. Prover picks random permutation $\sigma$ of $G_0$, sends $H = \sigma(G_0)$
2. Verifier sends random bit $b$
3. Prover sends isomorphism from $G_b$ to $H$
4. Verifier checks

Zero-knowledge: a simulator can produce indistinguishable transcripts by choosing $b$ first and constructing $H$ accordingly.

### Fundamental Results

- **All of NP has zero-knowledge proofs** (Goldreich-Micali-Wigderson, 1986) — assuming one-way functions exist. Since 3-COLOURING is NP-complete, a ZK protocol for 3-COLOURING gives ZK for all NP.
- **ZK and derandomisation**: Under certain derandomisation assumptions, every language with a ZK proof also has a non-interactive ZK proof (NIZK).
- **Applications**: ZK proofs are foundational for cryptographic protocols, blockchain verification (zk-SNARKs, zk-STARKs), and privacy-preserving computation.

## Probabilistically Checkable Proofs (PCPs)

A **PCP** system allows the verifier to check a proof (static string) by reading only a few bits:

$L \in \text{PCP}[r(n), q(n)]$ if there is a verifier that uses $r(n)$ random bits and reads $q(n)$ bits of the proof.

**PCP Theorem** (Arora et al., 1998):

$$\text{NP} = \text{PCP}[O(\log n), O(1)]$$

Every NP statement has a proof that can be verified by:
- Flipping $O(\log n)$ coins (so $\text{poly}(n)$ possible random strings)
- Reading only $O(1)$ bits of the proof

This is extraordinary: polynomial-length proofs can be *spot-checked* with constant queries and logarithmic randomness, with the guarantee that any invalid proof is rejected with constant probability.

### PCP and Hardness of Approximation

The PCP theorem implies that approximating MAX-3-SAT within any factor better than 7/8 is NP-hard.

**Reduction**: Given a 3-SAT instance $\varphi$:
1. Encode a satisfying assignment as a PCP proof
2. The PCP verifier reads $O(1)$ bits and checks a local constraint
3. If $\varphi$ is satisfiable, *all* local constraints are satisfied; if not, a constant fraction fail
4. The local constraints define a GAP-CSP: distinguishing "all satisfiable" from "at most $(1-\varepsilon)$-fraction satisfiable" is NP-hard

This gap amplification is the fundamental mechanism: PCPs convert *exact* hardness into *approximate* hardness.

### Optimal Inapproximability Results

Via PCP machinery:
- **MAX-3-SAT**: NP-hard to approximate within $7/8 + \varepsilon$ (Håstad, 2001) — tight, since random assignment achieves $7/8$
- **CLIQUE**: NP-hard to approximate within $n^{1-\varepsilon}$ for any $\varepsilon > 0$
- **SET COVER**: NP-hard to approximate within $(1-\varepsilon)\ln n$
- **CHROMATIC NUMBER**: NP-hard to approximate within $n^{1-\varepsilon}$

## Randomised Computation Revisited

### Complexity Classes

| Class | Error Type | One-Sided | $\Pr[\text{error}]$ |
|-------|-----------|-----------|---------------------|
| BPP | Two-sided | No | $\leq 1/3$ (both sides) |
| RP | One-sided | YES only | $\leq 1/2$ on YES, 0 on NO |
| co-RP | One-sided | NO only | 0 on YES, $\leq 1/2$ on NO |
| ZPP | Zero error | — | Expected poly time |

$$\text{P} \subseteq \text{ZPP} = \text{RP} \cap \text{co-RP} \subseteq \text{RP} \subseteq \text{BPP}$$

### Does Randomness Help?

**BPP vs P**: The derandomisation conjecture asserts BPP = P.

Evidence:
- **Sipser-Lautemann**: BPP ⊆ $\Sigma_2^P \cap \Pi_2^P$ (BPP is "low" in PH)
- **Impagliazzo-Wigderson** (1997): If $E = \text{DTIME}(2^{O(n)})$ has a problem requiring circuits of size $2^{\Omega(n)}$, then BPP = P
- **Nisan-Wigderson** (1994): Pseudorandom generators from hard functions

In practice, randomness appear unhelpful for decision problems — most known BPP algorithms have been derandomised (primality: Miller-Rabin → AKS; polynomial identity testing remains a major open case).

### Randomness in Proof Systems

Randomness is essential for:
- **Zero-knowledge**: Deterministic ZK proofs are impossible for non-trivial languages
- **PCPs**: The PCP theorem fundamentally requires randomness
- **IP**: Deterministic interactive proofs = NP (trivially), but randomised IP = PSPACE

So while randomness may not help *computation*, it dramatically helps *verification*.

## Connections

- **Complexity classes**: IP = PSPACE contextualises the class hierarchy — see [p-np-and-complexity-classes](p-np-and-complexity-classes.md)
- **NP-completeness and approximation**: PCP theorem drives inapproximability — see [np-completeness-cook-karp](np-completeness-cook-karp.md)
- **Circuit complexity**: Derandomisation ↔ circuit lower bounds — see [circuit-complexity-lower-bounds](circuit-complexity-lower-bounds.md)
- **Descriptive complexity**: Logical characterisations of IP — see [descriptive-complexity-logic](descriptive-complexity-logic.md)
- **Information theory**: Randomness extraction and min-entropy — see [../information-theory/entropy-source-coding-theorem.md](../information-theory/entropy-source-coding-theorem.md)
- **Cryptography and trust**: ZK proofs underpin trustless computation — connects to core/memory/users/trust themes in the broader knowledge base
