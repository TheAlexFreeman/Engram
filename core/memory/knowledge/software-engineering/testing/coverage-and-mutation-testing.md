---
created: 2026-03-20
last_verified: 2026-03-20
origin_session: core/memory/activity/2026/03/20/chat-003
source: agent-generated
trust: medium
type: knowledge
related:
  - testing-foundations-epistemology.md
  - black-box-test-design.md
  - property-based-testing.md
---

# Coverage and Mutation Testing

Coverage metrics measure what code constructs a test suite exercises. Mutation testing directly measures how well the test suite can distinguish the correct program from nearly-correct variants. Together, they answer complementary questions: "what did we execute?" and "would our tests catch bugs?"

---

## 1. Statement coverage

The weakest structural criterion: every *executable* statement is executed at least once.

```python
def absolute_value(x):
    if x >= 0:      # branch A
        return x    # statement 1
    else:
        return -x   # statement 2

# 100% statement coverage requires:
test_positive = absolute_value(5)   # executes statement 1
test_negative = absolute_value(-3)  # executes statement 2
```

**Limitation:** Statement coverage does not distinguish which branches were taken. A function with a complex condition can have 100% statement coverage with very few tests. It is the minimum credible coverage criterion, not a useful target by itself.

---

## 2. Branch coverage (decision coverage)

Every possible branch outcome of every control-flow decision is exercised. For an `if/else`, both the true and false branches must be taken. Branch coverage subsumes statement coverage: 100% branch coverage implies 100% statement coverage.

```python
def login(user, password):
    if not user.is_active:    # decision 1
        raise InactiveUser()  # branch 1a
    if user.check_password(password):  # decision 2
        return create_session(user)    # branch 2a
    else:
        raise InvalidCredentials()     # branch 2b

# Minimum branch coverage:
# Test 1: inactive user → branch 1a
# Test 2: active user, correct password → branches 1b, 2a
# Test 3: active user, wrong password → branches 1b, 2b
```

**Branch vs. decision coverage:** In most definitions these are equivalent. Some tools distinguish them when dealing with compound conditions (`if (a and b)`): decision coverage only requires each full condition to be true and false; branch coverage requires the same.

**Industry baseline:** 80% branch coverage is a common industry minimum standard; 90%+ is typical for safety-important code; 100% for safety-critical modules.

---

## 3. Path coverage

Every distinct path from entry to exit through the control flow graph. This subsumes branch coverage but is infeasible for programs with loops (which have infinite paths) or even moderate complexity (a function with 10 independent binary conditions has 1,024 paths).

**Approximation — Basis path testing (cyclomatic complexity):** McCabe's cyclomatic complexity V(G) = E − N + 2P (edges minus nodes plus 2 × connected components) gives the number of linearly independent paths. Testing all basis paths achieves branch coverage and covers the complexity-generating structure of the code. V(G) is also a useful maintainability metric: functions with V(G) > 10 are candidates for decomposition.

**Path coverage in practice:** Used primarily as a theoretical benchmark; practically achieved via mutation testing rather than direct path enumeration.

---

## 4. MC/DC — Modified Condition/Decision Coverage

**Origin:** DO-178B/C (aviation software standard), MIL-HDBK-338B. Required for Level A (catastrophic failure) aviation software. Adopted in automotive (ISO 26262), aerospace, and nuclear domains.

**Definition:** For each condition in a compound decision, there must exist a test case where:
1. That condition independently affects the outcome of the decision
2. All other conditions are held constant (or their contributions neutralized)

This means each Boolean condition must be shown to independently control the outcome — not just be executed.

**Example:** Decision `if (a and b and c)`:
| Test | a | b | c | Decision |
|------|---|---|---|---------|
| T1   | T | T | T | True    |
| T2   | F | T | T | False   | ← a independently causes False (b,c held True)
| T3   | T | F | T | False   | ← b independently causes False (a,c held True)
| T4   | T | T | F | False   | ← c independently causes False (a,b held True)

MC/DC requires N+1 tests for N conditions in a compound decision (vs. 2^N for exhaustive). It is achievable while being far stronger than branch coverage.

**Why it matters:** High-assurance software must demonstrate that every condition in every safety-relevant decision is tested. MC/DC provides this at practical cost.

---

## 5. Data-flow analysis

Control-flow coverage metrics track which branches are taken. Data-flow analysis tracks variable definitions and uses.

**Use-definition (def-use) chains:** A *definition* of variable v is a point where v is assigned. A *use* of v is a point where v is read. A def-use chain pair (d, u) requires that a definition at d can reach use u without v being redefined in between.

**Du-path coverage:** Every def-use chain pair is exercised by at least one test. This catches bugs like:
- Variables defined but never used (dead code)
- Variables used before being defined (uninitialized variable bugs)
- Definitions that are immediately overwritten before any use (redundant computation)

**Tools:** Static analysis tools (Pylance, Mypy, Clang's static analyzer) perform data-flow analysis. Coverage tools like `coverage.py` measure control-flow coverage; data-flow coverage requires specialized tools (e.g., academic tools or specialized security analyzers).

---

## 6. Goodhart's Law applied to coverage

**Goodhart's Law:** "When a measure becomes a target, it ceases to be a good measure."

Applied to coverage: when organizations mandate a coverage percentage (e.g., "all new code must have 80% branch coverage"), developers write tests that reach code without meaningful assertions — coverage goes up but bug-catching ability does not.

**Symptoms of coverage gaming:**
- Tests with no assertions (`assert True` after calling the function)
- Tests that call complex functions with trivial inputs just to execute the code path
- Assertion-free integration tests that merely verify no exception is raised

**What coverage is genuinely good for:**
- **Red alert:** A module with <40% line coverage has significant untested territory — this is worth immediate investigation
- **Regression:** Coverage dropping after a change indicates the change added untested code paths
- **Gap identification:** Use line-level coverage reports to find specific untested branches, then write targeted tests for those branches
- **Trend monitoring:** Coverage trends over time reveal whether testing discipline is holding

**Correct framing:** Coverage should inform testing decisions, never be the goal itself. A 100% coverage requirement creates perverse incentives; a 0% coverage tool is a visible quality risk.

---

## 7. Mutation testing — measuring test quality directly

**Core idea:** If the SUT contains a defect (a "mutation"), at least one test should fail. Mutation testing systematically introduces artificial defects and checks whether the test suite detects them.

**Mutation operators** are syntactic transformations that produce plausible bugs:
| Operator class | Example transformation |
|---------------|----------------------|
| Conditional boundary | `>=` → `>` or `<` |
| Negate conditionals | `==` → `!=`, `if x` → `if not x` |
| Arithmetic operator | `+` → `-`, `*` → `/` |
| Return value | `return x` → `return None` |
| Void method call | Delete a method call (side-effect removal) |
| Increment/decrement | `i++` → `i--` |
| Boolean literal | `True` → `False` |

**Mutation score:** `killed_mutants / total_non_equivalent_mutants`. A mutation score of 1.0 means every synthesized bug was caught by the test suite. Industry typical: 60-75% before mutation testing is applied; 85%+ is achievable with focused effort.

**Interpreting survivors:** A surviving mutant is either:
1. An **equivalent mutant** — syntactically different but semantically identical; cannot be killed; must be manually identified and excluded
2. A **specification gap** — the test suite cannot distinguish the mutated behavior from the correct behavior; a candidate for a new test case

**Surviving mutant analysis workflow:**
1. Run mutation testing tool
2. Review surviving mutants (the tool diffs the mutant against original code)
3. For each survivor: is it equivalent? If not, what test would kill it? Write that test.
4. Re-run until mutation score is satisfactory or remaining survivors are confirmed equivalent

---

## 8. Mutation testing tools

| Tool | Language | Notes |
|------|----------|-------|
| **Mutmut** | Python | Simple, fast; integrates with pytest; reports surviving mutants with diffs |
| **Cosmic-Ray** | Python | More mutation operators; supports distributed execution |
| **PIT (Pitest)** | Java | De facto standard for Java; IntelliJ and Maven plugin support |
| **Stryker** | JS/TS, C#, Scala | Multi-language; excellent HTML report; active development |
| **mutagen** | Go | Standard library mutation for Go |

**Practical usage (Mutmut + pytest):**
```bash
mutmut run --paths-to-mutate=src/ --tests-dir=tests/
mutmut results        # summary table
mutmut show <id>      # show diff for specific surviving mutant
mutmut html           # generate HTML report
```

---

## 9. Sampling strategies for large codebases

Mutation testing is computationally expensive (O(mutations × test_suite_cost)). Strategies to make it practical:

- **Module-level sampling:** Run mutation testing only on the most critical or recently changed modules
- **Mutant sampling:** Run a random 10-20% of mutants; estimate the full score from the sample
- **Incremental mutation testing:** Only mutate code changed in the current diff (integrate into PR pipelines)
- **Operator subsetting:** Use a curated subset of operators (e.g., only boundary and negate operators) for speed; these operators catch the most impactful bugs

**Stubborn mutants:** Syntactically distinct, semantically non-equivalent mutants that are extremely difficult to kill. Often indicate that the feature being mutated is genuinely hard to specify with unit tests. Consider property-based tests or a manual inspection.

---

## 10. Coverage and mutation as complementary diagnostics

| Question | Tool |
|----------|------|
| Is this code being executed? | Coverage metrics |
| Would tests catch a bug in this code? | Mutation testing |
| Where are the testing gaps? | Combined: find unkilled mutants in executed code |
| Is testing improving over time? | Coverage trend + mutation score trend |

The combination: high coverage + high mutation score = credibly well-tested code. High coverage + low mutation score = tests are reaching code without validating it (assertion-free or trivial tests). Low coverage + high mutation score (unusual) = existing tests are strong but coverage is narrow.
