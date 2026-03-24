---
created: '2026-03-20'
last_verified: '2026-03-20'
origin_session: core/memory/activity/2026/03/20/chat-002
source: agent-generated
trust: high
related: category-theory-foundations.md, zfc-set-theory.md, ../causal-inference/do-calculus-identification.md
---

# Simple Type Theory and Lambda Calculus

## The Untyped Lambda Calculus

### Origins and Motivation

Alonzo Church introduced the **lambda calculus** in the 1930s as a foundation for mathematics. The original untyped system turned out to be inconsistent as a logic (Kleene-Rosser paradox, 1935), but the computational fragment survived as a foundational model of computation equivalent to Turing machines.

### Syntax

The lambda calculus has just three kinds of terms:

$$t ::= x \mid (\lambda x. \, t) \mid (t_1 \, t_2)$$

- **Variable:** $x, y, z, \ldots$
- **Abstraction:** $\lambda x. \, t$ (a function that takes argument $x$ and returns $t$)
- **Application:** $t_1 \, t_2$ (apply function $t_1$ to argument $t_2$)

This is perhaps the simplest possible programming language, yet it's Turing-complete.

### Beta-Reduction

The fundamental computation rule:

$$(\lambda x. \, t_1) \, t_2 \to_\beta t_1[x := t_2]$$

"Applying $\lambda x. \, t_1$ to $t_2$ yields $t_1$ with $x$ replaced by $t_2$."

Example: $(\lambda x. \, x \, x) \, y \to_\beta y \, y$

### Encoding Data

Church showed that all computable functions can be encoded:

**Church numerals:** $\bar{0} = \lambda f. \lambda x. \, x$, $\bar{1} = \lambda f. \lambda x. \, f \, x$, $\bar{n} = \lambda f. \lambda x. \, f^n \, x$

**Booleans:** $\text{true} = \lambda t. \lambda f. \, t$, $\text{false} = \lambda t. \lambda f. \, f$

**Pairs:** $\text{pair} = \lambda a. \lambda b. \lambda s. \, s \, a \, b$

**Recursion (Y combinator):** $Y = \lambda f. \, (\lambda x. \, f \, (x \, x)) \, (\lambda x. \, f \, (x \, x))$

The Y combinator satisfies $Y \, g = g \, (Y \, g)$ — a fixed point. This enables recursion without explicit self-reference.

### Key Properties

- **Church-Rosser theorem (confluence):** If $t \to^* t_1$ and $t \to^* t_2$, then there exists $t_3$ such that $t_1 \to^* t_3$ and $t_2 \to^* t_3$. Reduction order doesn't matter for the final result (if one exists).
- **Non-termination:** Some terms have no normal form: $(\lambda x. \, x \, x) \, (\lambda x. \, x \, x) \to_\beta (\lambda x. \, x \, x) \, (\lambda x. \, x \, x) \to_\beta \cdots$

## Simply Typed Lambda Calculus (STLC)

### Motivation

The untyped calculus allows non-terminating computations and "meaningless" terms. Church (1940) introduced types to restrict the calculus to well-behaved terms.

### Types

Types are built from base types using the function type constructor:

$$\tau ::= \alpha \mid \tau_1 \to \tau_2$$

- $\alpha, \beta, \gamma, \ldots$ are **base types** (e.g., $\text{Nat}$, $\text{Bool}$)
- $\tau_1 \to \tau_2$ is the type of functions from $\tau_1$ to $\tau_2$
- $\to$ associates to the right: $\alpha \to \beta \to \gamma$ means $\alpha \to (\beta \to \gamma)$

### Typing Rules

A **typing judgment** $\Gamma \vdash t : \tau$ means "in context $\Gamma$ (a list of variable-type bindings), term $t$ has type $\tau$."

$$\frac{(x : \tau) \in \Gamma}{\Gamma \vdash x : \tau} \text{(Var)}$$

$$\frac{\Gamma, x : \tau_1 \vdash t : \tau_2}{\Gamma \vdash (\lambda x : \tau_1. \, t) : \tau_1 \to \tau_2} \text{(Abs)}$$

$$\frac{\Gamma \vdash t_1 : \tau_1 \to \tau_2 \quad \Gamma \vdash t_2 : \tau_1}{\Gamma \vdash t_1 \, t_2 : \tau_2} \text{(App)}$$

### Key Theorems

**Type preservation (subject reduction):** If $\Gamma \vdash t : \tau$ and $t \to_\beta t'$, then $\Gamma \vdash t' : \tau$.

**Progress:** If $\vdash t : \tau$ (closed, well-typed term), then either $t$ is a value (a $\lambda$-abstraction) or there exists $t'$ with $t \to_\beta t'$.

Together these give **type safety**: well-typed terms don't "go wrong."

**Strong normalization:** Every well-typed term in STLC has a normal form, and every reduction sequence terminates. There are no infinite loops.

**Consequence:** STLC is **not** Turing-complete — it can only express terminating computations. The Y combinator is not typeable. This is the fundamental tradeoff: types buy safety (termination, no runtime errors) at the cost of expressiveness.

### What STLC Can Express

STLC with natural numbers corresponds to **extended polynomials** — a strict subset of computable functions. Adding recursion (a fixed-point combinator `fix`) recovers Turing completeness but loses strong normalization.

**System T (Gödel, 1958):** Add natural numbers and primitive recursion to STLC. This gives exactly the **primitive recursive functionals** — strictly more than primitive recursive functions, enough to prove the consistency of Peano arithmetic (Gödel's Dialectica interpretation), but still not Turing-complete.

## System F: Polymorphic Lambda Calculus

### Motivation

STLC requires separate identity functions for each type: $\lambda x : \text{Nat}. \, x$ (identity on Nat), $\lambda x : \text{Bool}. \, x$ (identity on Bool), etc. System F (Girard 1972, Reynolds 1974) adds **type variables** and **type abstraction**:

$$\Lambda \alpha. \, \lambda x : \alpha. \, x : \forall \alpha. \, \alpha \to \alpha$$

This single term serves as the identity function for *all* types.

### Types and Terms

$$\tau ::= \alpha \mid \tau_1 \to \tau_2 \mid \forall \alpha. \, \tau$$

Terms add type abstraction and type application:

$$t ::= \cdots \mid \Lambda \alpha. \, t \mid t [\tau]$$

### Expressiveness

System F is remarkably expressive — **all data types can be encoded**:

- **Booleans:** $\forall \alpha. \, \alpha \to \alpha \to \alpha$
- **Natural numbers:** $\forall \alpha. \, (\alpha \to \alpha) \to \alpha \to \alpha$ (Church numerals, typed)
- **Pairs:** $\forall \alpha. \, (\tau_1 \to \tau_2 \to \alpha) \to \alpha$
- **Lists:** $\forall \alpha. \, (\tau \to \alpha \to \alpha) \to \alpha \to \alpha$ (Church encoding of lists)
- **Existential types:** $\exists \alpha. \, \tau$ encodes abstract data types (information hiding)

System F is still strongly normalizing (all well-typed terms terminate) but can express all functions provably total in second-order arithmetic — vastly stronger than System T.

### Type Inference is Undecidable

**Wells's theorem (1999):** Type inference (determining whether a term has a type) is undecidable for System F.

This is why practical programming languages use restricted versions:
- **Hindley-Milner** (ML, Haskell): let-polymorphism (∀ only at the outermost level of let bindings). Type inference is decidable (Algorithm W) and runs in near-linear time.
- **System F$_\omega$** (Haskell's core): extends System F with type-level computation (type constructors and higher-kinded types).

## The Lambda Cube

Barendregt's **lambda cube** organizes type systems along three axes of increasing expressiveness:

| Axis | What it adds | Example system |
|------|-------------|----------------|
| Polymorphism ($\forall$) | Terms depending on types | System F |
| Type operators | Types depending on types | System F$_\omega$ |
| Dependent types | Types depending on terms | LF (logical framework) |

The eight corners of the cube:

$$
\begin{array}{llll}
\text{STLC} & \to & \lambda 2 \text{ (System F)} & \to \\
\lambda\underline{\omega} & \to & \lambda\omega \text{ (System F}_\omega\text{)} & \to \\
\lambda P \text{ (LF)} & \to & \lambda P2 & \to \\
\lambda P\underline{\omega} & \to & \lambda C \text{ (Calculus of Constructions)} &
\end{array}
$$

The top corner, the **Calculus of Constructions** (Coquand & Huet, 1988), combines all three axes and is the basis of the Coq proof assistant.

## Connection to Programming Language Theory

### Type Systems as Static Analysis

| Type system feature | What it prevents | Example |
|--------------------|-----------------|---------|
| Simple types | Type errors (applying non-function) | C, Java, Go |
| Parametric polymorphism | Code duplication, unsafe casts | ML, Haskell, Rust generics |
| Algebraic data types + pattern matching | Missing cases, null pointer errors | ML, Haskell, Rust enums |
| Ownership types / linear types | Memory errors, data races | Rust's borrow checker |
| Dependent types | Arbitrary logic errors (array bounds, etc.) | Idris, Agda |

**Milner's slogan:** "Well-typed programs cannot go wrong" — where "go wrong" means reaching an undefined state, not producing an incorrect result.

### Curry-Style vs. Church-Style

Two approaches to the relationship between terms and types:
- **Church-style (à la Church):** Types are part of the syntax. Terms are explicitly annotated. Every term has a unique type. Corresponds to typed programming languages.
- **Curry-style (à la Curry):** Terms exist independently; types are assigned to pre-existing terms. A term might have multiple types (principally, the most general). Corresponds to type inference.

## Implications for the Engram System

### 1. Types as Governance Categories

The maturity levels in the Engram system (unverified → reviewed → core) function like types for knowledge claims:
- **Unverified:** Like an untyped term — might be well-formed, might not
- **Reviewed:** Like a type-checked term — meets certain quality criteria
- **Core:** Like a term in a strongly normalizing system — high confidence it won't "go wrong"

### 2. The Expressiveness-Safety Tradeoff

The more restrictive the governance rules, the safer the knowledge base but the less expressive (harder to add knowledge quickly). This parallels the STLC → System F → dependent types progression: more expressive type systems allow more programs but require more sophisticated checking.

### 3. Polymorphism and Reuse

Individual knowledge files often serve multiple purposes (like a polymorphic function). The cross-referencing and tagging system enables this reuse without duplication — analogous to parametric polymorphism allowing a single function definition to work across multiple types.

## Key References

- Church, A. (1940). A formulation of the simple theory of types. *Journal of Symbolic Logic*, 5(2), 56–68.
- Barendregt, H.P. (1984). *The Lambda Calculus: Its Syntax and Semantics* (revised ed.). North-Holland.
- Girard, J.-Y. (1972). *Interprétation fonctionnelle et élimination des coupures de l'arithmétique d'ordre supérieur*. PhD thesis, Université Paris VII.
- Reynolds, J.C. (1974). Towards a theory of type structure. In *Colloque sur la Programmation*, LNCS 19, 408–425.
- Gödel, K. (1958). Über eine bisher noch nicht benützte Erweiterung des finiten Standpunktes. *Dialectica*, 12, 280–287.
- Pierce, B.C. (2002). *Types and Programming Languages*. MIT Press.
- Coquand, T. & Huet, G. (1988). The calculus of constructions. *Information and Computation*, 76, 95–120.