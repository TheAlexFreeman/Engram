---
created: '2026-03-20'
last_verified: '2026-03-20'
origin_session: core/memory/activity/2026/03/20/chat-002
source: agent-generated
trust: high
related: curry-howard-isomorphism.md, ../../cognitive-science/concepts/conceptual-change-types.md, godels-second-incompleteness.md
---

# Dependent Types and Proof Assistants

## Dependent Types

### The Core Idea

In simple type systems, types and terms live in separate worlds — a type like `List<Int>` doesn't depend on any runtime value. **Dependent types** break this barrier: types can depend on values.

**Example:** Instead of `List<Int>` (a list of integers, unknown length), dependent types allow `Vec<Int, 5>` — a vector of exactly 5 integers, where `5` is a *value* appearing in the *type*.

This collapses the distinction between types and terms, enabling types to express arbitrary logical propositions (via Curry-Howard) and programs to carry machine-checked proofs of their own correctness.

### Dependent Function Types (Π-types)

$$\Pi_{x : A} B(x) \quad \text{or} \quad (x : A) \to B(x)$$

A function whose return type depends on its input value. If $B$ doesn't depend on $x$, this reduces to the ordinary function type $A \to B$.

**Example:** A function that takes a natural number $n$ and returns a vector of length $n$:

$$\text{replicate} : \Pi_{n : \mathbb{N}} \, (a : A) \to \text{Vec}(A, n)$$

The *type* of the output ($\text{Vec}(A, n)$) depends on the *value* of the input ($n$).

### Dependent Pair Types (Σ-types)

$$\Sigma_{x : A} B(x) \quad \text{or} \quad (x : A) \times B(x)$$

A pair where the type of the second component depends on the value of the first. If $B$ doesn't depend on $x$, this reduces to the ordinary product type $A \times B$.

**Example:** A pair of a natural number $n$ and a vector of length $n$ (an "existential" — there exists some $n$ and a vector of that length):

$$(n : \mathbb{N}) \times \text{Vec}(A, n)$$

This is the computational interpretation of $\exists n : \mathbb{N}. \, \text{Vec}(A, n)$.

### Identity Types

The **identity type** $\text{Id}_A(a, b)$ (or $a =_A b$) is the type of *proofs that $a$ and $b$ are equal*. It has a single constructor:

$$\text{refl} : \Pi_{a : A} \, \text{Id}_A(a, a)$$

Reflexivity: for any $a$, `refl` witnesses that $a = a$.

Identity types are where dependent type theory becomes much richer than simple type theory:
- Proving $a = b$ requires constructing a term of type $\text{Id}_A(a, b)$
- Equalities can be composed (transitivity), inverted (symmetry), and transported (substitution)
- In homotopy type theory, identity types have non-trivial higher structure (paths, homotopies, etc.)

## Martin-Löf Type Theory (MLTT)

### Overview

Per Martin-Löf developed **intuitionistic type theory** (1971, refined 1972, 1979, 1984) as a foundational framework for constructive mathematics, building on the Curry-Howard correspondence.

### Core Type Formers

| Type Former | Introduction | Elimination | Computation |
|------------|-------------|------------|-------------|
| **Π-type** $(x : A) \to B(x)$ | $\lambda$-abstraction | Application | β-reduction |
| **Σ-type** $(x : A) \times B(x)$ | Pair $(a, b)$ | Projections $\pi_1, \pi_2$ | β for projections |
| **Id-type** $a =_A b$ | $\text{refl}$ | J-eliminator (path induction) | J computes on refl |
| **ℕ** (natural numbers) | $0$, $S(n)$ | Recursion/induction | Computes on constructors |
| **𝟎** (empty type) | (none) | Absurdity elimination | (vacuous) |
| **𝟏** (unit type) | $\star$ | Trivial | Trivial |
| **+** (disjoint union) | $\text{inl}$, $\text{inr}$ | Case split | Computes on constructors |
| **W-types** (well-founded trees) | $\text{sup}$ | Elimination principle | Structural recursion |
| **Universe** $\mathcal{U}$ | Type codes | Decoding | El(code) = type |

### Universes

A **universe** $\mathcal{U}$ is a type whose elements are (codes for) types. This allows quantifying over types:

$$\text{id} : \Pi_{A : \mathcal{U}} \, A \to A$$

To avoid Russell-like paradoxes ($\mathcal{U} : \mathcal{U}$ is inconsistent — Girard's paradox), MLTT uses a **cumulative hierarchy** of universes:

$$\mathcal{U}_0 : \mathcal{U}_1 : \mathcal{U}_2 : \cdots$$

Each $\mathcal{U}_i : \mathcal{U}_{i+1}$, and $A : \mathcal{U}_i$ implies $A : \mathcal{U}_{i+1}$ (cumulativity).

### Decidability Properties

| Property | Status |
|----------|--------|
| Type checking (given term and type, verify) | **Decidable** (for MLTT without univalence) |
| Type inference (given term, find type) | **Decidable** (with sufficient annotations) |
| Type inhabitation (given type, find term) | **Undecidable** (in general) |

Type inhabitation is undecidable because:  dependent types can encode arbitrary logical propositions, and provability of arbitrary propositions is undecidable by the incompleteness theorems.

## Proof Assistants

### Coq (1984–present, now "Rocq")

**Foundation:** Calculus of Inductive Constructions (CIC) — extends the Calculus of Constructions with inductive types.

**Key features:**
- **Tactic-based proving:** Write proofs interactively using tactics (commands like `intro`, `apply`, `rewrite`, `induction`) rather than constructing proof terms directly
- **Extraction:** Automatically extract verified programs from proofs (to OCaml, Haskell, or Scheme)
- **Universes:** Predicative hierarchy + an impredicative `Prop` universe for propositions
- **Proof irrelevance in Prop:** Two proofs of the same proposition in `Prop` are considered equal for extraction purposes

**Major results proved in Coq:**
- Four-color theorem (Gonthier, 2005) — first significant mathematical theorem fully formalized
- Feit-Thompson (odd-order) theorem (Gonthier et al., 2012) — ~170,000 lines, 6 years
- CompCert verified C compiler (Leroy, ongoing)
- VST (Verified Software Toolchain): framework for verifying C programs against specifications

### Agda (1999–present)

**Foundation:** Martin-Löf type theory with pattern matching and sized types.

**Key features:**
- **Dependent pattern matching:** Instead of J-eliminator, proofs by pattern matching on constructors — more natural for programmers
- **No tactics:** Proofs are written directly as functional programs (terms)
- **Unicode-heavy syntax:** Uses mathematical notation ($\forall$, $\Sigma$, $\to$, etc.)
- **Cubical Agda:** Variant implementing cubical type theory (homotopy type theory with computation for univalence)

**Strengths:** Clean foundation, excellent for exploring type-theoretic ideas, HoTT research.

### Lean (2013–present)

**Foundation:** Dependent type theory (Lean 4 uses its own variant of CIC called "Lean's type theory").

**Key features:**
- **Lean 4:** Also a general-purpose programming language (bootstrapped in itself), combining theorem proving with practical programming
- **Mathlib:** The largest unified library of formalized mathematics (~1.5 million+ lines), covering analysis, algebra, topology, number theory, etc.
- **Tactic framework:** Powerful, extensible tactics written in Lean itself
- **Metaprogramming:** Full access to the compiler internals for custom automation

**Major developments:**
- Liquid Tensor Experiment (Scholze's challenge, 2022): formalized a key theorem from condensed mathematics
- Growing use in mathematics departments (Imperial College, CMU, etc.)
- AlphaProof (DeepMind, 2024): uses Lean for IMO-level automated theorem proving

### Isabelle/HOL (1986–present)

**Foundation:** Higher-order logic (not full dependent types, but a logical framework approach).

**Key features:**
- **LCF-style kernel:** All proofs reduce to a small, trusted kernel — tactics can be arbitrarily complex without compromising soundness
- **Sledgehammer:** Integrates external ATP (automated theorem provers) and SMT solvers to find proofs automatically
- **Isar:** Structured proof language resembling mathematical prose
- **Code generation:** Extract verified code to SML, OCaml, Haskell, Scala

**Major results:**
- seL4 verified microkernel (170,000+ lines of proof)
- Formal verification of cryptographic protocols
- Large parts of the Archive of Formal Proofs (AFP)

### Comparison

| Feature | Coq | Agda | Lean 4 | Isabelle |
|---------|-----|------|--------|----------|
| Foundation | CIC | MLTT | CIC variant | HOL |
| Dependent types | Yes | Yes | Yes | Limited |
| Tactics | Yes (Ltac, Ltac2) | No (direct terms) | Yes (meta) | Yes (Isar) |
| Automation | Moderate | Low | Growing | Strong (Sledgehammer) |
| Programming language | Limited | Limited | Yes (full) | Via extraction |
| Math library size | Medium | Small | Large (Mathlib) | Large (AFP) |
| Learning curve | Steep | Steep | Moderate | Moderate |

## Program Verification via Dependent Types

### Intrinsic vs. Extrinsic Verification

**Extrinsic:** Write the program first, then prove properties about it separately.

```
sort : List<Int> -> List<Int>
-- then prove: for all xs, sorted(sort(xs)) and permutation(xs, sort(xs))
```

**Intrinsic:** Encode the specification in the type, so a well-typed program is correct by construction.

```
sort : (xs : List<Int>) -> { ys : List<Int> | sorted(ys) ∧ perm(xs, ys) }
```

Dependent types enable the intrinsic approach. The compiler rejects programs that don't satisfy the specification — errors become type errors, caught at compile time rather than runtime.

### Examples of Dependent-Type Specifications

| Specification | Dependent Type |
|--------------|---------------|
| Array access within bounds | `access : Vec(A, n) -> (i : Fin(n)) -> A` |
| Matrix multiplication dimensions | `mult : Mat(m, n) -> Mat(n, p) -> Mat(m, p)` |
| Sorting preserves length | `sort : Vec(A, n) -> Vec(A, n)` |
| Red-black tree invariants | Type encodes color and black-height constraints |
| Well-scoped lambda terms | De Bruijn indices indexed by context length |
| Protocol compliance | Session types indexed by protocol state |

## Current Frontiers

### Formalized Mathematics at Scale

- **Mathlib** (Lean): 1.5M+ lines, fastest-growing formalized math library, aiming to cover undergraduate mathematics curriculum
- **Xena Project** (Buzzard): teaching mathematicians to use Lean, bridging the formalization gap
- **Formalization of key theorems:** Perfectoid spaces (Buzzard et al.), sphere eversion (van Doorn et al.), Liquid Tensor Experiment

### AI for Proof Finding

- **AlphaProof** (DeepMind, 2024): RL-trained system that finds proofs in Lean; solved 4/6 IMO 2024 problems at silver medal level
- **LLM-based proving:** GPT-4, Claude, and others can suggest proof strategies and tactics, though not yet reliable for complex proofs
- **Autoformalization:** Translating informal mathematics to formal proofs (Wu et al., 2022; Jiang et al., 2023)

### Cubical Type Theory and Homotopy Type Theory

- **Univalence axiom** (Voevodsky): equivalent types are identical — computationally meaningful in cubical type theory (CCHM, 2017)
- Potential new foundations for mathematics where equality is defined up to homotopy equivalence

## Implications for the Engram System

### 1. Verified Knowledge Pipelines

Dependent types suggest a vision for knowledge systems where transformations (summarization, cross-referencing, promotion) are *type-checked* — i.e., proven to preserve the semantic content of the original. Current LLM-based systems can't do this, but the theoretical possibility exists.

### 2. Maturity as Type Refinement

The progression from unverified → reviewed → core knowledge in the Engram system is analogous to **type refinement** in dependent types:
- Unverified: `Claim(topic)` — a claim about a topic, no guarantees
- Reviewed: `VerifiedClaim(topic, source, date)` — a claim with provenance
- Core: `EstablishedFact(topic, evidence, [reviews])` — a fact with a chain of evidence

Each promotion adds constraints to the "type" (metadata requirements, review records).

### 3. The Automation Frontier

AlphaProof demonstrates that AI can find proofs/programs in dependently-typed systems. As these capabilities mature, AI agents could potentially:
- Formally verify cross-references between knowledge files
- Prove consistency properties of the knowledge base
- Automatically find and flag contradictions

Currently far from practical, but the theoretical framework (Curry-Howard + dependent types + AI proof search) provides the roadmap.

## Key References

- Martin-Löf, P. (1984). *Intuitionistic Type Theory*. Bibliopolis.
- The Coq Development Team. *The Coq Proof Assistant Reference Manual*. https://coq.inria.fr
- Norell, U. (2007). *Towards a practical programming language based on dependent type theory*. PhD thesis, Chalmers.
- de Moura, L. & Ullrich, S. (2021). The Lean 4 theorem prover and programming language. In *CADE 2021*.
- Nipkow, T., Wenzel, M., & Paulson, L.C. (2002). *Isabelle/HOL: A Proof Assistant for Higher-Order Logic*. Springer.
- Univalent Foundations Program. (2013). *Homotopy Type Theory: Univalent Foundations of Mathematics*.
- Trinh, T.H. et al. (2024). Solving Olympiad geometry without human demonstrations. *Nature*, 625, 476–482.
- mathlib Community. (2020). The Lean mathematical library. In *CPP 2020*.