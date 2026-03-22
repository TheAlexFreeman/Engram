---
created: 2026-03-20
last_verified: 2026-03-20
origin_session: core/memory/activity/2026/03/20/chat-003
source: agent-generated
trust: medium
type: knowledge
related:
  - testing-foundations-epistemology.md
  - coverage-and-mutation-testing.md
  - property-based-testing.md
---

# Black-Box Test Design Techniques

Black-box (behavioral) test design derives test cases from specifications without examining the source code. These systematic techniques ensure complete coverage of the input-output space as described by requirements. They are independent of implementation and remain valid through refactoring.

---

## 1. Equivalence partitioning

**Principle:** Divide the input space into partitions (equivalence classes) such that all members of a partition are expected to be processed identically. If one test from a partition fails, all others in the same partition should fail; if one passes, all should pass. Test one representative per partition.

**Why it works:** Testing multiple inputs that trigger the same code path gives diminishing returns. Equivalence partitioning allocates testing effort across genuinely different behaviors.

**Valid and invalid partitions:** Always consider both valid inputs (the program should process correctly) and invalid inputs (the program should handle gracefully — reject, raise an exception, return an error code). Each invalid input category is its own partition.

**Example — age validation (valid range: 0–120):**
| Partition | Representative | Type |
|-----------|---------------|------|
| Negative ages | -1 | Invalid |
| Valid ages | 25 | Valid |
| Ages over 120 | 150 | Invalid |
| Non-integer input | "thirty" | Invalid |

**Step-by-step process:**
1. Identify all input variables and parameters
2. For each variable, identify equivalence classes based on:
   - Ranges that produce the same behavior
   - Valid vs. invalid values
   - Special values (null, empty string, zero, maximum)
3. For each class, select one (or a few) representative values
4. Construct test cases combining representatives from each variable's classes

---

## 2. Boundary value analysis (BVA)

**Principle:** Defects cluster at the edges of equivalence partitions. Off-by-one errors, fence-post errors, and range-boundary logic errors are among the most common bugs in software. BVA focuses test effort at these boundaries.

**Three-point analysis:** For each boundary, test:
- The value just below the boundary (boundary − 1)
- The value at the boundary itself
- The value just above the boundary (boundary + 1)

**Example — discount threshold (discount applied if purchase ≥ $100):**
| Test value | Boundary | Expected |
|------------|----------|----------|
| $99 | Below lower boundary | No discount |
| $100 | At lower boundary | Discount applied |
| $101 | Above lower boundary | Discount applied |

**Robust BVA (also tests invalid range):**
| Test value | Expected |
|------------|----------|
| -$1 | Error / rejection |
| $0 | No discount (edge case) |
| $99 | No discount |
| $100 | Discount |
| $101 | Discount |
| Maximum cart value | Discount (if applicable) |
| Maximum + 1 | Error / overflow handling |

**Why BVA subsumes equivalence partitioning for ranges:** BVA selects representatives at boundaries, providing partition coverage as a side effect.

**Multi-dimensional BVA:** When multiple variables have boundaries, test all combinations of boundaries (combinatorial explosion — see pairwise testing for mitigation).

---

## 3. Decision table testing

**Principle:** Decision tables capture complex business logic with multiple conditions and actions. Each column represents a rule (combination of conditions → combination of actions). The table makes implicit logic explicit and reveals missing or contradictory rules.

**Structure:**
```
                Rule 1  Rule 2  Rule 3  Rule 4
Condition 1:      T       T       F       F
Condition 2:      T       F       T       F
─────────────────────────────────────────────
Action A:         ✓               ✓
Action B:                 ✓               ✓
```

**Example — loan approval with two conditions (income ≥ $50K, credit score ≥ 700):**
```
                Rule 1  Rule 2  Rule 3  Rule 4
Income ≥ 50K:     Y       Y       N       N
Credit ≥ 700:     Y       N       Y       N
────────────────────────────────────────────
Approve:          ✓
Counter-offer:            ✓       ✓
Reject:                                   ✓
```

Each rule is one test case. A missing rule (no column for some condition combination) is a specification gap.

**Collapsed decision tables:** When an action is independent of some conditions, a rule can have "don't care" entries, reducing the table to fewer rules (fewer test cases). Use collapsed tables when exhaustive tables are impractical.

**When to use:** High-value applications for requirements with many Boolean conditions that combine to determine outcomes (e.g., insurance pricing, access control rules, tax calculation, pricing tiers).

---

## 4. State transition testing

**Principle:** Model the SUT as a finite state machine (FSM). States represent stable conditions of the system; transitions represent events that cause state changes; actions are produced by transitions. Tests verify that:
1. Valid transitions produce correct state changes and actions
2. Invalid transitions are rejected appropriately

**State transition diagram:**
```
             register
[Unregistered] ──────────────→ [Active]
                                  │  │
                    suspend ←─────┘  └──────→ [Admin] (promote)
                      │
                      ▼
                  [Suspended]
                      │
              reactivate │
                      ▼
                  [Active]
```

**State transition table:**
| Current State | Event | Next State | Action |
|--------------|-------|-----------|--------|
| Unregistered | register | Active | send welcome email |
| Active | suspend | Suspended | notify user |
| Active | promote | Admin | grant permissions |
| Suspended | reactivate | Active | notify user |
| Suspended | register | Suspended | error: "already registered" |
| Active | register | Active | error: "already registered" |

**Test cases from the table:**
- One test per valid transition (minimum N-switch-0 coverage: exercise all valid states and transitions)
- One test per invalid transition (all invalid events in each state)
- Extended: N-switch-1 coverage (test all pairs of consecutive transitions)

**When to use:** Account management, order workflows, authentication state machines, network protocol implementations, UI state management.

---

## 5. Pairwise (all-pairs) testing

**Problem:** Exhaustive combination testing of k parameters each with n values requires n^k tests — for 10 parameters with 3 values each, 59,049 test cases. This is infeasible.

**Insight:** Most bugs are triggered by interactions of 2 (occasionally 3) parameters. Testing all pairwise combinations of parameters requires far fewer tests.

**Covering array:** A set of test cases where every pair of parameter values appears in at least one test case. For t=2 (pairwise), empirically this covers the vast majority of real bugs.

**Example — 3 parameters × 3 values = 27 exhaustive tests, ~9 pairwise tests:**
```
Configuration: Browser={Chrome, Firefox, Safari}, OS={Win, Mac, Linux}, Theme={Light, Dark, System}

Pairwise test set:
  1: Chrome, Win,   Light
  2: Chrome, Mac,   Dark
  3: Chrome, Linux, System
  4: Firefox, Win,  Dark
  5: Firefox, Mac,  System
  6: Firefox, Linux, Light
  7: Safari, Win,   System
  8: Safari, Mac,   Light
  9: Safari, Linux, Dark
```
Every pair of (Browser, OS), (Browser, Theme), and (OS, Theme) values appears at least once.

**Tools:** PICT (Microsoft, free), AllPairs, Jenny, Hexawise. These generate minimal covering arrays automatically.

**Limitations:** Pairwise may miss bugs that require specific 3-way or higher-order interactions. For safety-critical systems, use higher-strength covering arrays (t=3 or t=4). For typical business applications, t=2 is sufficient.

---

## 6. Cause-effect graphing

**Principle:** A formal technique that translates the logical relationship between inputs (causes) and outputs (effects) into a Boolean graph, then derives a decision table from the graph. Useful when requirements describe complex condition/action relationships in natural language that are ambiguous or contradictory.

**Process:**
1. Identify causes (input conditions) and effects (outputs/actions)
2. Draw the cause-effect graph connecting causes to effects via logical operators (AND, OR, NOT, etc.)
3. Translate the graph into a limited-entry decision table
4. Derive test cases from the decision table

**Example:**
- Cause 1 (C1): User is authenticated
- Cause 2 (C2): User has admin role
- Effect 1 (E1): Show admin panel (C1 AND C2)
- Effect 2 (E2): Show error "access denied" (C1 AND NOT C2)
- Effect 3 (E3): Redirect to login (NOT C1)

**Status in practice:** Cause-effect graphing is rarely used directly in modern agile workflows — decision tables provide similar benefits with less formal overhead. It remains conceptually important for understanding the formal foundations of test case derivation from specifications.

---

## 7. Combining techniques

Black-box techniques are complementary, not exclusive:

| Situation | Recommended technique |
|-----------|----------------------|
| Input has ranges or numeric bounds | Equivalence partitioning + BVA |
| Complex multi-condition business rules | Decision table testing |
| System with distinct modes or states | State transition testing |
| Many configuration parameters to combine | Pairwise testing |
| Complex cause-effect relationships | Cause-effect graphing → decision table |

**Minimum viable black-box test design for any feature:**
1. List all inputs and classify into equivalence partitions (including invalid partitions)
2. For each partition with a numeric range, apply BVA at all boundaries
3. If multiple conditions combine to determine outcomes, build a decision table
4. If the system has significant state, draw a state transition diagram and generate tests from it
