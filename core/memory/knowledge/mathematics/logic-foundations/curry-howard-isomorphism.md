---
created: '2026-03-20'
last_verified: '2026-03-20'
origin_session: core/memory/activity/2026/03/20/chat-002
source: agent-generated
trust: high
related: dependent-types-proof-assistants.md, simple-type-theory-lambda-calculus.md, godels-first-incompleteness.md
---

# The Curry-Howard Isomorphism

## Overview

The **Curry-Howard isomorphism** (also called **propositions-as-types**, **proofs-as-programs**, or the **Curry-Howard correspondence**) is a deep structural identity between logic and computation:

| Logic | Type Theory / Programming |
|-------|--------------------------|
| Proposition | Type |
| Proof | Program (term) |
| Proof of $A \to B$ | Function from $A$ to $B$ |
| Proof of $A \land B$ | Pair of type $A \times B$ |
| Proof of $A \lor B$ | Tagged union (sum type) $A + B$ |
| Proof normalization | Program evaluation (β-reduction) |
| A proposition is provable | The corresponding type is inhabited |

This is not a vague analogy — it is a precise, formal isomorphism discovered incrementally by Curry (1934), Howard (1969/1980), and elaborated by many others.

## The Correspondence in Detail

### Implication ↔ Function Types

**Logic:** A proof of $A \to B$ is a method that transforms any proof of $A$ into a proof of $B$.

**Types:** A term of type $A \to B$ is a function that takes an input of type $A$ and produces an output of type $B$.

**Proof rule (→-introduction):**
$$\frac{\begin{array}{c} [A] \\ \vdots \\ B \end{array}}{A \to B}$$

"Assume $A$; derive $B$; conclude $A \to B$, discharging the assumption."

**Typing rule (λ-abstraction):**
$$\frac{\Gamma, x : A \vdash t : B}{\Gamma \vdash (\lambda x : A. \, t) : A \to B}$$

"If adding $x : A$ to the context lets you build a term $t : B$, then $\lambda x. t$ has type $A \to B$."

These are the *same rule* — the proof structure and the type derivation are identical.

**Modus ponens ↔ function application:**
$$\frac{A \to B \quad A}{B} \qquad \longleftrightarrow \qquad \frac{\Gamma \vdash f : A \to B \quad \Gamma \vdash a : A}{\Gamma \vdash f \, a : B}$$

### Conjunction ↔ Product Types

**Logic:** A proof of $A \land B$ consists of a proof of $A$ and a proof of $B$.

**Types:** A term of type $A \times B$ is a pair $(a, b)$ where $a : A$ and $b : B$.

| Logic | Types |
|-------|-------|
| $\land$-intro: from proofs of $A$ and $B$, conclude $A \land B$ | Pair constructor: from $a : A$ and $b : B$, form $(a, b) : A \times B$ |
| $\land$-elim: from proof of $A \land B$, extract proof of $A$ | First projection: $\text{fst}(p) : A$ from $p : A \times B$ |

### Disjunction ↔ Sum Types

**Logic:** A proof of $A \lor B$ is either a proof of $A$ or a proof of $B$ (with a tag indicating which).

**Types:** A term of type $A + B$ is either $\text{inl}(a)$ with $a : A$ or $\text{inr}(b)$ with $b : B$.

**Disjunction elimination ↔ pattern matching (case analysis).**

### Falsity ↔ Empty Type

**Logic:** Falsity ($\bot$) has no proof. From a proof of $\bot$, anything follows (*ex falso quodlibet*).

**Types:** The empty type ($\text{Void}$, $\bot$, `Never`) has no inhabitants. Given a term of type $\text{Void}$, you can produce a term of any type (vacuously).

### Negation ↔ Function to Void

**Logic:** $\neg A \equiv A \to \bot$. A refutation of $A$ is a function that takes any proof of $A$ and derives a contradiction.

**Types:** $\neg A \equiv A \to \text{Void}$. A term of type $A \to \text{Void}$ is a function that, given any $a : A$, produces an element of the empty type — which is impossible unless $A$ is also empty.

### Universal Quantification ↔ Dependent Function Types

**Logic:** A proof of $\forall x : A. \, B(x)$ is a method that, given any $a : A$, produces a proof of $B(a)$.

**Types:** A term of type $\Pi_{x : A} B(x)$ (dependent function type) is a function that takes $a : A$ and returns a value of type $B(a)$ — where the *output type depends on the input value*.

### Existential Quantification ↔ Dependent Pair Types

**Logic:** A proof of $\exists x : A. \, B(x)$ consists of a witness $a : A$ and a proof of $B(a)$.

**Types:** A term of type $\Sigma_{x : A} B(x)$ (dependent pair type) consists of a value $a : A$ and a value of type $B(a)$.

## Full Correspondence Table

| Natural Deduction | Lambda Calculus | Programming |
|-------------------|----------------|-------------|
| Proposition $A$ | Type $A$ | Type/specification |
| Proof of $A$ | Term $t : A$ | Program satisfying spec |
| $A \to B$ | $A \to B$ | Function type |
| $A \land B$ | $A \times B$ | Product type / struct |
| $A \lor B$ | $A + B$ | Sum type / tagged union |
| $\bot$ (falsity) | $\text{Void}$ | Empty type (`Never`) |
| $\top$ (truth) | $\text{Unit}$ | Unit type `()` |
| $\forall x. B(x)$ | $\Pi_{x:A} B(x)$ | Dependent function / generic |
| $\exists x. B(x)$ | $\Sigma_{x:A} B(x)$ | Dependent pair / existential type |
| Proof normalization | β-reduction | Program execution |
| Hypothesis | Free variable | Function parameter |
| Cut elimination | β-reduction | Inlining / evaluation |

## Constructive vs. Classical

### The Correspondence is Naturally Constructive

The Curry-Howard correspondence works most cleanly for **intuitionistic (constructive) logic**:
- A proof of $A \lor B$ must specify which disjunct holds → a program of type $A + B$ must produce a concrete value tagged as left or right
- A proof of $\exists x. B(x)$ must exhibit a witness → a program of type $\Sigma_{x:A} B(x)$ must produce a concrete value

**Classical logic** allows non-constructive proofs (proof by contradiction, excluded middle), which don't directly correspond to terminating programs.

### Extending to Classical Logic

**Griffin's discovery (1990):** The classical law of excluded middle $A \lor \neg A$ corresponds to **call/cc** (call with current continuation) — a control operator that captures the continuation (the "rest of the computation"):

$$\text{call/cc} : ((A \to \bot) \to A) \to A$$

This type is Peirce's law, which is equivalent to excluded middle classically.

| Classical Axiom | Computational Interpretation |
|----------------|------------------------------|
| Excluded middle: $A \lor \neg A$ | `callCC` (capture continuation) |
| Double negation elimination: $\neg\neg A \to A$ | Continuation-passing style transform |
| Peirce's law: $((A \to B) \to A) \to A$ | `callCC` directly |

**CPS transform:** Any classical proof can be translated into a constructive proof in continuation-passing style. This gives the computational content of classical mathematics — it's just "harder to read" (every step is mediated by continuations).

## Proof Assistants and Verified Programming

### The Practical Power of Curry-Howard

Since proofs = programs, **proof assistants** are simultaneously:
- Programming languages (write programs/algorithms)
- Theorem provers (write proofs of mathematical theorems)
- Verification tools (prove properties of programs within the same framework)

**Major proof assistants built on Curry-Howard:**

| System | Foundation | Notable achievements |
|--------|-----------|---------------------|
| **Coq** | Calculus of Inductive Constructions | Four-color theorem (Gonthier 2005), CompCert verified C compiler, Feit-Thompson theorem |
| **Agda** | Martin-Löf type theory with pattern matching | Homotopy type theory libraries, verified programming idioms |
| **Lean** | Dependent type theory (Lean 4: also a general-purpose language) | Mathlib (largest unified math library), Liquid Tensor Experiment |
| **Isabelle/HOL** | Higher-order logic (not strictly Curry-Howard) | seL4 verified OS kernel, formal verification of crypto protocols |

### Verified Software Examples

- **CompCert** (Leroy): C compiler formally verified in Coq. Every compilation step is proved to preserve program semantics. The bugs that plague GCC and Clang at optimization levels are provably absent.
- **seL4** (Klein et al.): Microkernel with a machine-checked proof that the C code implements the abstract specification correctly. Used in military and aerospace systems.
- **CertiKOS** (Gu et al.): Verified concurrent OS kernel.

### AlphaProof and AI-Assisted Proving

DeepMind's **AlphaProof** (2024) uses reinforcement learning to find proofs in Lean, demonstrating that:
- The Curry-Howard correspondence makes proof search a programming problem
- AI can navigate the enormous search space of proof terms
- Solved IMO-level problems by finding the right program/proof

## Deeper Extensions

### Linear Logic and Resource Management

**Girard's linear logic (1987):** Propositions are "resources" that must be used exactly once. The Curry-Howard correspondence for linear logic gives:

$$\text{Linear logic} \longleftrightarrow \text{Linear type systems}$$

Applications:
- **Rust's ownership system** is inspired by linear/affine types — values must be used exactly once (or at most once), preventing double-free and data races
- **Session types** use linear logic to type communication protocols
- **Quantum computing:** Quantum states cannot be copied (no-cloning theorem) — linear types naturally enforce this

### Homotopy Type Theory (HoTT)

The newest extension (Voevodsky, Awodey, Warren, ~2006–2013):

$$\text{Types} \longleftrightarrow \text{Spaces (homotopy theory)}$$

- Types are spaces
- Terms are points in spaces
- Equalities between terms are paths between points
- Equalities between equalities are homotopies between paths
- Identity types have non-trivial higher structure

This extends Curry-Howard from logic+computation to logic+computation+topology, with the **univalence axiom** providing a new foundational principle: equivalent types are identical.

## Implications for the Engram System

### 1. Governance as Type System

The Engram governance system functions as a type system for knowledge:
- **Well-typed = well-governed:** A knowledge file that passes governance checks is "well-typed" — it meets structural and quality requirements
- **Type preservation:** If a file passes governance initially and is transformed (updated, corrected), the governance rules should ensure the transformed version still passes
- **Progress:** A well-governed knowledge file can always be "evaluated" (used for retrieval, reasoning, etc.) without encountering undefined behavior

### 2. Proofs as Justifications

Each knowledge claim in the Engram system should ideally have a "proof" (justification, source, reasoning chain). The Curry-Howard correspondence suggests that the *structure* of the justification carries information:
- A justification by direct observation (≈ axiom) is different from one by inference (≈ function application)
- A justification that combines two pieces of evidence (≈ pair) is different from one that considers cases (≈ case analysis)
- Making the justification structure explicit (as in proof assistants) could enhance knowledge quality assessment

### 3. Constructive Knowledge

The constructive nature of the correspondence suggests a principle: knowledge claims should be *constructive* where possible — asserting "X exists" should ideally be accompanied by an example or construction, not just a proof by contradiction that non-existence leads to an absurdity. This aligns with the preference for concrete, actionable knowledge over purely abstract theorems.

## Key References

- Curry, H.B. & Feys, R. (1958). *Combinatory Logic*, Vol. I. North-Holland.
- Howard, W.A. (1980). The formulae-as-types notion of construction. In *To H.B. Curry: Essays on Combinatory Logic*, Academic Press. (Written 1969, published 1980.)
- Girard, J.-Y., Lafont, Y., & Taylor, P. (1989). *Proofs and Types*. Cambridge University Press.
- Wadler, P. (2015). Propositions as types. *Communications of the ACM*, 58(12), 75–84.
- Griffin, T. (1990). A formulae-as-types notion of control. In *POPL 1990*.
- Univalent Foundations Program. (2013). *Homotopy Type Theory: Univalent Foundations of Mathematics*. Institute for Advanced Study.
- Coquand, T. & Huet, G. (1988). The calculus of constructions. *Information and Computation*, 76, 95–120.
- Gonthier, G. (2008). Formal proof — the four-color theorem. *Notices of the AMS*, 55(11), 1382–1393.