---
created: 2026-03-20
last_verified: 2026-03-20
origin_session: core/memory/activity/2026/03/20/chat-003
source: agent-generated
trust: medium
type: knowledge
related:
  - unit-testing-principles.md
  - testing-foundations-epistemology.md
  - black-box-test-design.md
---

# Test-Driven Development (TDD) and BDD

Test-Driven Development (TDD) inverts the conventional order of coding and testing: tests are written first, and code is written to satisfy them. BDD extends TDD to connect automated tests with natural-language specifications.

---

## 1. The Red-Green-Refactor cycle

TDD operates as a tight feedback loop with three states:

```
RED    → Write a failing test for the next small increment of behavior
GREEN  → Write the minimal code to make it pass (nothing more)
REFACTOR → Clean up code and tests while keeping tests green
Repeat
```

**Red:** The test must fail before any code is written. A test that passes without implementation either tests something that was already implemented, or tests the wrong thing. The red state confirms that the test is capable of detecting the absence of the behavior.

**Green:** Write the simplest code that makes the test pass. "Simplest" is literal — Kent Beck's "fake it 'til you make it" pattern is acceptable: returning a hardcoded value is valid green-state code when only one test exists. Premature generalization at this stage is a mistake.

**Refactor:** With the safety net of a passing test suite, clean up without changing behavior. Extract duplication, rename for clarity, reorganize structure. If refactoring causes tests to fail, the refactoring changed behavior and is incorrect. The tests are the specification; they define what behavior is preserved.

**Rhythm matters:** Each full cycle should take 2-5 minutes, not 30 minutes. Large cycles indicate the next increment of behavior is too large. Break it down further.

---

## 2. TDD as specification discipline

Writing the test first forces you to specify exactly what behavior you want before writing code to implement it. This has several consequences:

**Behavioral precision:** You must decide, before writing code, what the function should return or do for given inputs. Ambiguities that would remain hidden during implementation-first coding surface immediately as unanswerable questions about what the test should assert.

**Interface design pressure:** To write a test for code that doesn't exist yet, you must decide the interface of that code first — what it's called, what arguments it takes, what it returns. This design pressure tends to produce cleaner, more usable interfaces than implementation-first design.

**Tests as executable documentation:** A TDD test suite is an executable specification of the system's behavior. New developers can read the tests to understand what the system is supposed to do, and verify their understanding by running the tests.

---

## 3. Triangulation

Triangulation is a TDD strategy for deriving correct general implementations from multiple test cases:

1. Write one test case → make it pass with a hardcoded return value
2. Write a second test case that requires a different return value → the hardcoded answer now fails
3. The only way to make both tests pass is to write the general algorithm

Example:
```python
# Test 1: passes with return 2
def test_add_zeros():
    assert add(1, 1) == 2

# Test 2: forces generalization — return 2 no longer works
def test_add_larger():
    assert add(3, 4) == 7

# Now we must implement actual addition
def add(a, b):
    return a + b
```

Triangulation prevents premature generalization (guessing a general algorithm before tests require it) and premature abstraction (adding flexibility before it is needed). It also guards against accidentally writing tests that are satisfied by the wrong implementation.

---

## 4. Emergent design

TDD practitioners argue that good designs emerge naturally from test-first development:

- **High cohesion:** To test a unit in isolation, it must have a single, clear responsibility. Code that mixes concerns is hard to test with a single-purpose test.
- **Low coupling:** To test a unit without its collaborators, it must accept collaborators as dependencies (dependency injection). This automatically produces loosely coupled, injectable architectures.
- **Simple design:** The pressure to write the minimal code to pass each test prevents over-engineering. Features are added only when a failing test requires them.

This is not automatic — it requires discipline and experience. It does not generate the right architecture in the absence of thinking; it creates conditions that make good architecture easier to arrive at.

---

## 5. London school vs. Detroit/classic school

The two main TDD traditions disagree about the role of mocks:

### London school (mockist TDD)
- Mock all collaborators at all times; the SUT is always isolated
- Start from the outermost component (controller, use case) and work inward, mocking everything below
- **Advantage:** Extreme isolation, can test code whose dependencies don't exist yet
- **Disadvantage:** Tests coupled to implementation via mocks; heavy mock setup; refactoring breaks tests even when behavior is preserved
- Key proponents: Steve Freeman, Nat Pryce ("Growing Object-Oriented Software, Guided by Tests")

### Detroit/classic school (statist TDD)
- Use real collaborators when they are in-memory and deterministic; mock only at system boundaries (external APIs, databases, file system)
- Start from the innermost components and build upward
- **Advantage:** Less brittle tests; tests survive refactoring as long as behavior is preserved; higher confidence in integration
- **Disadvantage:** Requires more setup; tests run slower; can't test before collaborators exist
- Key proponents: Kent Beck, Martin Fowler

**Synthesis:** Most experienced practitioners are pragmatic: mock external dependencies and unstable or slow collaborators; use real implementations for stable, fast, in-memory collaborators. Prefer state-based assertions over interaction-based assertions where possible.

---

## 6. When TDD is most valuable (and least)

**Most valuable for:**
- Business logic with clear input-output semantics (pricing, calculation, validation)
- Data transformations and processing pipelines
- Algorithms with well-specified behavior
- Code with complex conditional logic where equivalence partitioning reveals many cases

**Harder to apply for:**
- Exploratory code where the right interface is unclear (spike first, then write tests before committing)
- UI code with complex layout behavior (use snapshot testing or visual regression tools instead)
- Performance-critical code where the implementation is constrained by hardware details not captured in tests
- Code heavily dependent on third-party behavior that is itself undocumented or unreliable

**For exploratory work:** Write a spike (quick prototype without tests) to understand the problem, then throw it away and rewrite test-first. Don't try to retrofit tests onto exploratory code.

---

## 7. Behavior-Driven Development (BDD)

BDD extends TDD by expressing test cases in a structured natural language (Gherkin) that non-technical stakeholders can read and sometimes write:

```gherkin
Feature: User registration
  As a new user
  I want to register an account
  So that I can access the platform

  Scenario: Successful registration with valid data
    Given no account exists for "alex@example.com"
    When I register with email "alex@example.com" and password "securepass123"
    Then my account should be created
    And a welcome email should be sent to "alex@example.com"

  Scenario: Registration fails when email is already taken
    Given an account exists for "alex@example.com"
    When I register with email "alex@example.com" and password "securepass123"
    Then I should see the error "Email already in use"
```

**Given-When-Then:** The three-part structure of BDD scenarios:
- **Given** — preconditions / system state before the test
- **When** — the action the actor takes
- **Then** — the expected observable outcome

This maps directly to the Arrange-Act-Assert pattern of unit tests, but in natural language.

**BDD tools:** Cucumber (Java, Ruby), Behave (Python), SpecFlow (.NET), Playwright BDD (TypeScript). The tool parses Gherkin files, maps Given/When/Then clauses to step definitions implemented in code, and executes them.

**Living documentation:** When BDD scenarios are kept in sync with the code they test, they become executable documentation of the system's behavior — readable by product owners, verifiable by developers.

---

## 8. Acceptance-Test TDD (ATDD)

ATDD is an outside-in variant that starts with failing acceptance tests:

1. Collaborate with stakeholders to write acceptance tests in Gherkin (or similar)
2. Watch the acceptance tests fail
3. Drive the implementation using unit-level TDD until the acceptance tests pass
4. Refactor

The walking skeleton pattern initiates ATDD: build the thinnest possible end-to-end implementation of the most critical feature first, with acceptance tests verifying it. This establishes the technical architecture and development workflow before building out breadth.

**Relationship to TDD:** ATDD and TDD operate at different levels. TDD drives unit design; ATDD drives feature design. They are complementary, not competing.

---

## 9. Practical TDD quick reference

```
Before writing any code:
1. Write the test
2. Confirm it fails for the right reason (the feature doesn't exist yet)
3. Write minimal implementation
4. Confirm it passes
5. Refactor — code and test both
6. Confirm it still passes

Red flags to act on:
- Tests longer than 30 lines → behavior scope is too large; split the test or the feature
- Test setup takes more than 5 lines → the SUT has too many dependencies; refactor
- Cycle longer than 5 minutes → the increment is too large; break it down
- Test passes without implementation → delete or fix the test
```
