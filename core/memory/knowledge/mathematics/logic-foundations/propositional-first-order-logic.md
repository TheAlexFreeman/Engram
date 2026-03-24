---
created: '2026-03-20'
last_verified: '2026-03-20'
origin_session: core/memory/activity/2026/03/20/chat-002
source: agent-generated
trust: high
related: godels-first-incompleteness.md, ../complexity-theory/descriptive-complexity-logic.md, ../../ai/history/origins/cybernetics-perceptrons-and-the-first-connectionist-wave.md
---

# Propositional and First-Order Logic

## Propositional Logic

### Syntax

**Propositional logic** deals with statements that are either true or false, and combinations of those statements using logical connectives.

**Alphabet:**
- **Propositional variables:** $p, q, r, \ldots$ (atomic statements)
- **Connectives:** $\neg$ (not), $\land$ (and), $\lor$ (or), $\to$ (if-then), $\leftrightarrow$ (if and only if)
- **Parentheses:** $(, )$ for grouping

**Well-formed formulas (wffs):** Defined recursively:
1. Every propositional variable is a wff
2. If $\varphi$ is a wff, then $\neg\varphi$ is a wff
3. If $\varphi$ and $\psi$ are wffs, then $(\varphi \land \psi)$, $(\varphi \lor \psi)$, $(\varphi \to \psi)$, and $(\varphi \leftrightarrow \psi)$ are wffs
4. Nothing else is a wff

### Semantics: Truth Tables

An **interpretation** (or **valuation**) is a function $v: \{p, q, r, \ldots\} \to \{T, F\}$ assigning truth values to propositional variables.

| $\varphi$ | $\psi$ | $\neg\varphi$ | $\varphi \land \psi$ | $\varphi \lor \psi$ | $\varphi \to \psi$ | $\varphi \leftrightarrow \psi$ |
|-----------|--------|--------------|---------------------|--------------------|--------------------|-------------------------------|
| T | T | F | T | T | T | T |
| T | F | F | F | T | F | F |
| F | T | T | F | T | T | F |
| F | F | T | F | F | T | T |

**Key:** The material conditional $\varphi \to \psi$ is false only when $\varphi$ is true and $\psi$ is false. This is counterintuitive but essential: "if pigs fly, then 2+2=5" is vacuously true.

### Key Semantic Concepts

| Term | Definition | Example |
|------|-----------|---------|
| **Tautology** | True under every interpretation | $p \lor \neg p$ |
| **Contradiction** | False under every interpretation | $p \land \neg p$ |
| **Satisfiable** | True under at least one interpretation | $p \land q$ |
| **Logical consequence** | $\Gamma \models \varphi$ if every interpretation satisfying all of $\Gamma$ also satisfies $\varphi$ | $\{p, p \to q\} \models q$ |
| **Logical equivalence** | $\varphi \equiv \psi$ if they have the same truth value under every interpretation | $\neg(p \land q) \equiv \neg p \lor \neg q$ |

### Proof Systems

Three major approaches to proving theorems in propositional logic:

**1. Hilbert-style systems:**
- A few axiom schemas (e.g., $\varphi \to (\psi \to \varphi)$)
- One inference rule: modus ponens ($\varphi$ and $\varphi \to \psi$ yield $\psi$)
- Proofs are sequences of formulas, each an axiom instance or derived by modus ponens
- Theoretically elegant but proofs are often long and unreadable

**2. Natural deduction (Gentzen, 1935):**
- No axioms; only rules for introducing and eliminating each connective
- $\land$-intro: from $\varphi$ and $\psi$, derive $\varphi \land \psi$
- $\land$-elim: from $\varphi \land \psi$, derive $\varphi$ (or $\psi$)
- $\to$-intro: assume $\varphi$; if you can derive $\psi$, conclude $\varphi \to \psi$ and discharge the assumption
- $\to$-elim: from $\varphi$ and $\varphi \to \psi$, derive $\psi$ (modus ponens)
- Mirrors how humans argue: "suppose P; then Q; therefore P implies Q"
- Most proof assistants use natural deduction variants

**3. Sequent calculus (Gentzen, 1935):**
- Sequents: $\Gamma \vdash \Delta$ ("from assumptions $\Gamma$, conclude one of $\Delta$")
- Rules operate on both sides of the sequent
- The **cut rule** allows intermediate lemmas; cut elimination shows they're never necessary (but proofs without cuts can be exponentially longer)
- Foundational for proof theory and the Curry-Howard correspondence

### Completeness (Propositional)

**Theorem:** In each of these proof systems, every tautology is provable (completeness), and every provable formula is a tautology (soundness).

$$\models \varphi \iff \vdash \varphi$$

This is straightforward for propositional logic (truth tables are finite and checkable). The deep version is for first-order logic.

### Decidability

**Propositional satisfiability (SAT)** is decidable: truth tables always work (enumerate all $2^n$ interpretations). But:
- SAT is **NP-complete** (Cook-Levin theorem, 1971): unless P = NP, no polynomial-time algorithm exists
- Modern SAT solvers (DPLL, CDCL) handle practical instances with millions of variables despite worst-case exponential time
- SAT solving is the backbone of hardware verification, planning, and constraint satisfaction

## First-Order (Predicate) Logic

### Extension Beyond Propositional

First-order logic adds:
- **Variables** ranging over a domain of objects: $x, y, z, \ldots$
- **Constants** naming specific objects: $a, b, c, \ldots$
- **Function symbols:** $f(x)$, $g(x, y)$, etc.
- **Predicate (relation) symbols:** $P(x)$, $R(x, y)$, etc.
- **Quantifiers:** $\forall x$ (for all $x$) and $\exists x$ (there exists an $x$)
- **Equality:** $=$ (optional but standard)

**Example:** "Every student who studies passes the exam":

$$\forall x \, (\text{Student}(x) \land \text{Studies}(x) \to \text{Passes}(x))$$

### Semantics: Structures/Models

A **first-order structure** (or **model**) $\mathcal{M} = (D, I)$ consists of:
- A non-empty **domain** $D$ (the set of objects)
- An **interpretation** $I$ that assigns:
  - To each constant $c$: an element $c^\mathcal{M} \in D$
  - To each $n$-ary function symbol $f$: a function $f^\mathcal{M}: D^n \to D$
  - To each $n$-ary predicate $P$: a relation $P^\mathcal{M} \subseteq D^n$

Truth is defined relative to a structure and a variable assignment. The quantifiers range over the domain:
- $\mathcal{M} \models \forall x \, \varphi(x)$ iff $\varphi(a)$ holds for every $a \in D$
- $\mathcal{M} \models \exists x \, \varphi(x)$ iff $\varphi(a)$ holds for some $a \in D$

### Gödel's Completeness Theorem (1929)

**Theorem (Gödel, 1929):** A first-order sentence is provable (in any standard proof system) if and only if it is true in every model.

$$\vdash \varphi \iff \models \varphi$$

This says:
- **Soundness** ($\vdash \implies \models$): Proofs don't lie — every provable formula is valid
- **Completeness** ($\models \implies \vdash$): The proof system misses nothing — every valid formula can be proved

**Significance:** Gödel's completeness theorem says first-order logic has exactly the right proof power: the syntactic (proof-based) and semantic (model-based) notions of "follows from" coincide. This is remarkable and not automatic — it fails for second-order logic.

**Distinction from incompleteness:** The completeness theorem says the *logic* is complete (all valid formulas are provable). The *incompleteness* theorems say that specific *theories* within first-order logic (like Peano arithmetic) are incomplete — not all true sentences about the natural numbers are provable from the axioms.

### Soundness and Completeness as Design Ideals

| Property | Means | Consequence of failure |
|----------|-------|----------------------|
| **Soundness** | Everything provable is true | The system proves false statements (useless) |
| **Completeness** | Everything true is provable | The system misses some truths (limited) |

Both are desirable. Soundness is negotiable in no context — an unsound proof system is worse than useless. Completeness is often sacrificed in practice:
- Peano arithmetic is sound but incomplete (Gödel)
- ZFC is (presumably) sound but incomplete for questions like CH
- Type checkers are typically sound but not complete (reject some valid programs)

### Undecidability of First-Order Logic

**Church-Turing theorem (1936):** First-order logic is **undecidable** — there is no algorithm that, given a first-order sentence, always correctly determines whether it is valid.

This is a fundamental difference from propositional logic:
- Propositional: decidable (truth tables) but NP-complete (worst case exponential)
- First-order: **undecidable** — no algorithm works in all cases, regardless of time

First-order logic is **semi-decidable**: if a formula is valid, a systematic search will eventually find a proof. But if it's invalid, the search may run forever.

## Classical Logic vs. Other Logics

### Intuitionistic Logic

**Intuitionistic logic** (Brouwer, Heyting) rejects the law of excluded middle: $\varphi \lor \neg\varphi$ is not an axiom.

**Difference from classical:** In classical logic, $\neg\neg\varphi \to \varphi$ (double negation elimination). In intuitionistic logic, $\neg\neg\varphi$ does not imply $\varphi$ — knowing it's impossible that $\varphi$ is false doesn't mean you have a proof of $\varphi$.

**Why it matters:**
- The Curry-Howard isomorphism works most naturally for intuitionistic logic: a proof of $\varphi \lor \psi$ must specify which disjunct holds — constructive content
- Classical logic allows non-constructive proofs: "there exists an $x$" without exhibiting $x$ (proof by contradiction)
- Type theory and proof assistants are typically intuitionistic at their core, with classical axioms optionally added

### Modal Logic

**Modal logic** adds operators $\Box$ (necessarily) and $\Diamond$ (possibly):
- $\Box\varphi$: $\varphi$ is necessarily true (true in all "accessible" worlds)
- $\Diamond\varphi$: $\varphi$ is possibly true (true in at least one accessible world)
- Kripke semantics: truth evaluated relative to a "possible world" with an accessibility relation between worlds

Used in:
- Epistemic logic: $\Box_i\varphi$ means "agent $i$ knows $\varphi$"
- Deontic logic: $\Box\varphi$ means "it is obligatory that $\varphi$"
- Temporal logic: $\Box\varphi$ means "always in the future, $\varphi$"
- Program verification: $[\alpha]\varphi$ means "after executing program $\alpha$, $\varphi$ holds"

## Implications for the Engram System

### 1. Knowledge Representation Limits

First-order logic is the theoretical foundation for knowledge representation, but:
- The undecidability of first-order validity means no knowledge system can automatically verify all consequences of its knowledge base
- This is why practical knowledge representation (description logics, RDF/OWL) restricts to **decidable fragments** of first-order logic — trading expressiveness for computability
- The Engram system's natural-language knowledge files sidestep this by relying on the LLM's approximate reasoning rather than formal deduction — but this means conclusions lack formal guarantees

### 2. Soundness Over Completeness

The governance emphasis on accuracy over coverage reflects the soundness-over-completeness trade-off:
- **Soundness priority:** Better to have a knowledge base that doesn't contain false claims (even if incomplete) than one that covers everything but includes errors
- **Verification as soundness checking:** Human review of knowledge files is a soundness check — ensuring the "proofs" (knowledge claims) are valid
- **Unverified files as conjectures:** `_unverified/` files are like unproved lemmas — they might be useful but haven't been checked

### 3. Expressiveness and Decidability for Retrieval

The filing system's flat structure (files with frontmatter) is a restricted representation system, analogous to choosing a decidable fragment of logic:
- More structured representations (formal ontologies, knowledge graphs) would be more expressive but harder to maintain and query reliably
- The current system trades expressiveness for simplicity — the LLM handles the "reasoning" that a formal system would do via inference rules
- This is a pragmatic choice aligned with the undecidability result: since perfect formal reasoning about knowledge is impossible anyway, approximate but flexible reasoning may be optimal

## Key References

- Enderton, H.B. (2001). *A Mathematical Introduction to Logic* (2nd ed.). Academic Press.
- Mendelson, E. (2015). *Introduction to Mathematical Logic* (6th ed.). CRC Press.
- Gentzen, G. (1935). Untersuchungen über das logische Schließen. *Mathematische Zeitschrift*, 39, 176–210.
- Gödel, K. (1929). Über die Vollständigkeit des Logikkalküls. Doctoral thesis, University of Vienna.
- Cook, S.A. (1971). The complexity of theorem-proving procedures. In *STOC 1971*.
- van Dalen, D. (2013). *Logic and Structure* (5th ed.). Springer.