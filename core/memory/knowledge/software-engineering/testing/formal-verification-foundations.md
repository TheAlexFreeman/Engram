---
created: 2026-03-20
last_verified: 2026-03-20
origin_session: core/memory/activity/2026/03/20/chat-003
source: agent-generated
trust: medium
type: knowledge
related:
  - testing-foundations-epistemology.md
  - model-checking-abstract-interpretation.md
  - software-qa-metrics-process.md
---

# Formal Verification Fundamentals

Formal verification uses mathematical reasoning to prove properties of software. Where testing shows the presence of bugs for tested inputs, formal verification can demonstrate the *absence* of bugs for all inputs — within the scope of what the formal model captures. It is the limit case of static analysis and the highest-confidence software assurance technique.

---

## 1. The formal methods spectrum

Formal methods span a wide range from lightweight to heavyweight, with different cost-confidence tradeoffs:

```
Lightweight ←────────────────────────────────────────────→ Heavyweight
                                                          
Type checking   Design by contract   Model checking   Interactive theorem proving
(always on)     (assert statements)  (state machines) (Coq, Isabelle, Lean)
   ↑                    ↑                  ↑                    ↑
Low cost            Low-medium           Medium-high           Very high
Low assurance      (local properties)   (protocol props)      (full proofs)
```

**Applicability decision:** The cost of formal verification must be weighed against the cost of undetected bugs. Use formal methods where:
- Bug cost is catastrophic (aviation, medical devices, nuclear control)
- The specification is stable and well-defined
- The problem is amenable to formal modeling (finite state, algebraic properties)
- The codebase is small enough for the method to be tractable

---

## 2. Hoare logic

**Hoare triple:** The fundamental construct of Hoare logic, written `{P} C {Q}`:
- `P` is the **precondition** — what holds before executing command C
- `C` is the **command** — the piece of code being specified
- `Q` is the **postcondition** — what holds after C executes (assuming C terminates)

**Reading the triple:** "If P holds in the state before C executes, and C terminates, then Q holds in the state after C executes."

**Partial vs. total correctness:**
- *Partial correctness:* If C terminates, Q holds (the triple doesn't guarantee termination)
- *Total correctness:* C terminates AND Q holds (requires a termination proof, typically via a loop variant)

### 2.1 Hoare logic rules

**Assignment axiom:**
$$\{P[x/e]\} \; x := e \; \{P\}$$
To prove P holds after assigning e to x, prove P with all occurrences of x substituted by e holds before the assignment.

```
{x + 1 > 0} x := x + 1 {x > 0}   (substitute x → x+1 in postcondition)
```

**Composition rule:**
$$\{P\} C_1 \{Q\}, \quad \{Q\} C_2 \{R\} \;\vdash\; \{P\} C_1; C_2 \{R\}$$
If C1 transforms P to Q, and C2 transforms Q to R, then executing C1 then C2 transforms P to R. The intermediate assertion Q is called the *mid-condition*.

**Conditional rule:**
$$\{P \wedge B\} C_1 \{Q\}, \quad \{P \wedge \neg B\} C_2 \{Q\} \;\vdash\; \{P\} \text{ if } B \text{ then } C_1 \text{ else } C_2 \{Q\}$$

**Loop rule (while loop):**
$$\{I \wedge B\} C \{I\} \;\vdash\; \{I\} \text{ while } B \text{ do } C \{I \wedge \neg B\}$$
Where `I` is the **loop invariant** — a predicate that holds before the first iteration, is preserved by each iteration, and combined with the loop-exit condition `¬B`, implies the postcondition.

**Consequence rule:**
$$P' \Rightarrow P, \quad \{P\} C \{Q\}, \quad Q \Rightarrow Q' \;\vdash\; \{P'\} C \{Q'\}$$
Allows strengthening the precondition and weakening the postcondition. Essential for composing verified components.

### 2.2 Loop invariants

Finding the right loop invariant is the creative core of Hoare logic verification. For a sorting algorithm, the invariant might be "the first k elements of the array are sorted and contain the k smallest elements of the original array."

**Example — partial sum:**
```
{n ≥ 0}
sum := 0;
i := 0;
while i < n do
  sum := sum + a[i];
  i := i + 1
{sum = Σ a[0..n-1]}

Invariant: sum = Σ a[0..i-1]  ∧  0 ≤ i ≤ n
Termination argument (loop variant): n - i, which decreases each iteration and is bounded below by 0
```

---

## 3. Weakest precondition calculus (Dijkstra, 1976)

Dijkstra's *weakest precondition transformer* `wp(C, Q)` computes the *weakest* predicate that guarantees postcondition Q after executing C. "Weakest" means: any other precondition that suffices to guarantee Q is stronger than (implies) `wp(C, Q)`.

**Practical use:** Instead of guessing a precondition and proving the triple, compute the weakest precondition backward from the postcondition. This turns verification into a calculation.

**Rules:**
- `wp(x := e, Q) = Q[x/e]` (substitute e for x in Q)
- `wp(C1; C2, Q) = wp(C1, wp(C2, Q))` (compose backward)
- `wp(if B then C1 else C2, Q) = (B → wp(C1, Q)) ∧ (¬B → wp(C2, Q))`
- `wp(while B do C, Q)` — requires finding a loop invariant and termination argument

**Example:**
```
Postcondition: x > 0
Command: x := x + 1
wp(x := x + 1, x > 0) = (x > 0)[x / x+1] = x + 1 > 0 = x > -1

Therefore, if x > -1 holds before x := x + 1, then x > 0 holds after.
```

---

## 4. Design by contract (DbC)

Design by contract (Bertrand Meyer, Eiffel language, 1988) brings Hoare logic ideas into everyday programming via language-level support for:

**Preconditions:** Obligations the caller must satisfy before calling a method. If the precondition is violated, the caller is at fault.

**Postconditions:** Guarantees the method makes to the caller when the precondition is satisfied. If the postcondition is violated after a call that satisfied the precondition, the method is at fault.

**Class invariants:** Predicates that must hold for all instances of the class at all observable points (after construction, before and after every public method call). Encode the valid-state contract of the class.

**The substitution connection:** DbC formalizes the Liskov Substitution Principle — subclasses may weaken preconditions (accept more callers) and strengthen postconditions (guarantee more), but not vice versa. This is *behavioral subtyping*.

### 4.1 DbC in Python

Python has no native contract syntax, but contracts can be approximated:

```python
def withdraw(self, amount: float) -> float:
    # Preconditions
    assert amount > 0, f"amount must be positive, got {amount}"
    assert amount <= self.balance, f"insufficient funds: {amount} > {self.balance}"
    
    # Implementation
    self.balance -= amount
    
    # Postcondition
    assert self.balance >= 0, "balance invariant violated"
    return self.balance

# Or with the 'deal' or 'icontract' library:
import icontract

@icontract.require(lambda amount: amount > 0)
@icontract.require(lambda self, amount: amount <= self.balance)
@icontract.ensure(lambda self: self.balance >= 0)
def withdraw(self, amount: float) -> float:
    self.balance -= amount
    return self.balance
```

**`hypothesis` + contracts:** Property-based testing (Hypothesis) can test DbC preconditions and postconditions systematically. The `@given` strategy generates inputs; `assume()` enforces preconditions; assertions check postconditions.

---

## 5. Practical limits of formal verification

### 5.1 The specification problem

Formal verification proves that code matches its specification. But specifications can be wrong. If the specification is incorrect, a formally verified system can still be incorrect by the actual requirements. Formal verification transfers correctness responsibility to the specification.

### 5.2 Cost and scaling

- Interactive theorem provers (Coq, Isabelle, Lean) require expert users and significant person-hours per verified property. The seL4 microkernel verification required ~20 person-years.
- Model checking scales to tens of millions of reachable states; many real systems have state spaces too large (state explosion problem — → `model-checking-abstract-interpretation.md`).
- Automated tools (static analyzers, bounded model checkers) scale better but provide weaker guarantees.

### 5.3 Where formal methods are economically justified

| Domain | Rationale |
|--------|-----------|
| Avionic flight control software (DO-178C Level A) | Failure cost (lives) overwhelmingly justifies cost |
| Medical device firmware | Regulatory requirement; liability cost |
| Cryptographic protocol implementations | Protocol correctness is hard to test exhaustively; attacks are subtle |
| Core algorithms in distributed systems (consensus, leader election) | AWS and Microsoft use TLA+ for distributed protocol verification |
| Compilers and interpreters | Correctness of the compilation transforms can be formally verified |
| OS kernels (seL4) | Security and reliability properties of the API surface |

For typical web application business logic, formal methods are generally not economically justified. Property-based testing and mutation testing provide strong assurance at far lower cost.

---

## 6. Assertions as lightweight formal methods

Even without full formal verification infrastructure, systematic assertion use brings the benefit of runtime-verified contracts:

```python
class BankAccount:
    def __init__(self, initial_balance: float):
        assert initial_balance >= 0, "Initial balance cannot be negative"
        self._balance = initial_balance
        self._check_invariant()

    def _check_invariant(self):
        assert self._balance >= 0, f"Invariant violated: negative balance {self._balance}"

    def deposit(self, amount: float) -> None:
        assert amount > 0, f"Deposit amount must be positive, got {amount}"
        self._balance += amount
        self._check_invariant()  # postcondition / invariant check

    def withdraw(self, amount: float) -> None:
        assert amount > 0, f"Withdrawal amount must be positive"
        assert amount <= self._balance, f"Insufficient funds"
        self._balance -= amount
        self._check_invariant()
```

**Assertions vs. exception handling:** Assertions document programmer assumptions about what should be true. Exceptions handle conditions that can legitimately occur. Disable assertions in production (`python -O`) only if: (1) they are confirmed to be in hot paths and (2) the conditions they check are verified correct by other means. In most code, assertions should remain enabled in production.

---

## 7. Connection to testing

Formal methods and testing are complementary, not competing:

| Concern | Formal verification | Testing |
|---------|--------------------|----|
| Shows presence of bugs | ✗ (it proves absence or finds a counterexample) | ✓ |
| Shows absence of bugs | ✓ (for what the model covers) | ✗ |
| Scales to full applications | Rarely | ✓ |
| Works with underspecified behavior | ✗ (requires precise specification) | ✓ (oracle can be partial) |
| Finds unexpected bugs | Counterexamples from model checking | Property-based testing |

The highest-assurance systems use formal methods to verify core invariants and safety properties, combined with extensive testing for behavioral coverage. TLA+ model checking + property-based testing + mutation testing is a strong combination for protocol and algorithm verification.
