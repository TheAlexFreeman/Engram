---
created: 2026-03-20
last_verified: 2026-03-20
origin_session: core/memory/activity/2026/03/20/chat-003
source: agent-generated
trust: medium
type: knowledge
related:
  - testing-foundations-epistemology.md
  - test-driven-development.md
  - coverage-and-mutation-testing.md
---

# Unit Testing Principles

Unit testing verifies that individual software units (functions, methods, classes) behave correctly in isolation from their collaborators. It is the fastest and most precise feedback mechanism in the test suite.

---

## 1. FIRST properties (Robert Martin)

Effective unit tests satisfy five properties:

**Fast** — Unit tests must run in milliseconds. A suite of 1,000 unit tests should complete in seconds, not minutes. Slow tests don't get run on every change, which defeats their purpose. If a unit test is slow, it is almost always because it touches a real resource (database, file system, network) — replace the resource with a test double.

**Isolated** — No test should depend on another test's setup, execution, or output. Tests must be runnable in any order, in parallel, and in isolation. Shared mutable state between tests is the primary cause of non-isolated tests.

**Repeatable** — The same test run under the same conditions must always produce the same result. Non-repeatability is caused by: external dependencies (network, third-party APIs), system time (`datetime.now()`), random number generation (without a fixed seed), concurrency with non-deterministic scheduling, or filesystem state not cleaned up between runs. Inject dependencies to control them.

**Self-validating** — A test must produce a binary pass/fail result that requires no human judgment to interpret. Tests that print to stdout and require a human to check the output are not self-validating. Use assertions.

**Timely** — Tests should be written at the time the code is written (ideally before, as in TDD). Tests written long after the code they test tend to be weaker, are often compromised by implementation knowledge, and don't benefit from the design pressure that test-first writing provides.

---

## 2. Test doubles taxonomy (Gerard Meszaros, 2007)

Test double is the umbrella term for any object that replaces a real collaborator in a test. There are five specific kinds:

### 2.1 Dummy

A dummy object is passed as an argument but never used. It exists only to satisfy a method signature requirement.

```python
def test_process_order():
    dummy_logger = None  # logger won't be called in this path
    order = Order(items=[item], logger=dummy_logger)
    assert order.total() == 10.00
```

### 2.2 Fake

A fake has a working implementation that is unsuitable for production. The canonical example is an in-memory repository that implements the same interface as a database-backed repository.

```python
class FakeUserRepository:
    def __init__(self):
        self._users = {}

    def save(self, user):
        self._users[user.id] = user

    def find_by_id(self, user_id):
        return self._users.get(user_id)
```

Fakes are maintained and tested themselves. They are more work than stubs but enable faster, more realistic tests.

### 2.3 Stub

A stub returns predetermined answers to calls made during the test. It provides canned responses and doesn't care whether or how it's called.

```python
def test_order_summary_with_discount():
    pricing_stub = Mock()
    pricing_stub.get_price.return_value = 8.00  # always returns 8.00
    order = Order(items=[item], pricing=pricing_stub)
    assert order.summary() == "Total: $8.00"
```

### 2.4 Spy

A spy records calls made to it for later verification. It acts as a stub (returns values) but also records how it was called.

```python
class EmailServiceSpy:
    def __init__(self):
        self.emails_sent = []

    def send(self, to, subject, body):
        self.emails_sent.append({"to": to, "subject": subject})

def test_welcome_email_is_sent():
    spy = EmailServiceSpy()
    register_user("alex@example.com", email_service=spy)
    assert len(spy.emails_sent) == 1
    assert spy.emails_sent[0]["to"] == "alex@example.com"
```

### 2.5 Mock

A mock is pre-programmed with expectations. It will fail the test if calls are made that do not match the expectations, or if expected calls are not made.

```python
def test_payment_gateway_is_called():
    gateway_mock = MagicMock()
    gateway_mock.charge.return_value = {"status": "success"}

    checkout(cart, payment_gateway=gateway_mock)

    gateway_mock.charge.assert_called_once_with(amount=50.00, currency="USD")
```

Mocks couple the test to the implementation's calling behavior. They make tests more brittle but catch interaction bugs that stubs miss.

---

## 3. Mock vs. stub: the canonical distinction

The key question: **where is the verification point?**

- **Stubs** answer questions during the test ("return this value when called"). Verification happens at the end via state-based assertions (`assert order.total() == 8.00`).
- **Mocks** verify behavior during/after the test ("assert this was called with these arguments"). Verification happens by checking the mock's call history.

**Martin Fowler's formulation:** "The key distinction is that stubs use state verification while mocks use behavior verification."

Mocks tend to make tests more brittle because they couple the test to the implementation's call graph. If the implementation is refactored to achieve the same result via a different call sequence, the mock-based test fails even though behavior is unchanged. Use mocks selectively — primarily when the interaction itself (not just the outcome) is the contract being tested.

---

## 4. Sociable vs. solitary tests (Martin Fowler)

**Solitary tests** (also called "London school") mock all collaborators. The SUT is truly isolated. Advantages: fast, precise failure attribution, can be written before collaborators exist. Disadvantages: may pass while the integrated system fails; coupling to internal implementation via mocks.

**Sociable tests** (also called "Detroit/classic school") use real collaborators where doing so doesn't introduce non-determinism or slowness. A service test might use a real in-memory repository but mock the external payment API. Advantages: higher confidence in integration behavior; less coupling to implementation details. Disadvantages: slower, wider failure blast radius.

**Neither approach is universally correct.** The right mix depends on:
- How stable the collaborator interfaces are (unstable interfaces → prefer sociable tests with real collaborators)
- Whether collaborators are fast and deterministic (deterministic in-memory store → use the real thing)
- Whether the test is checking an interaction (is this service being called?) or an outcome (is the result correct?)

---

## 5. Assertion design

**One logical assertion per test:** Each test should fail for exactly one reason. When a test asserts multiple things, a failure doesn't immediately tell you which assertion failed or why. "One assertion per test" means one *logical* assertion — a single semantic claim may require multiple assertion lines.

```python
# Bad: multiple independent logical assertions — which one failed?
def test_user_creation():
    user = create_user("alex", "alex@example.com")
    assert user.name == "alex"
    assert user.email == "alex@example.com"
    assert user.is_active == True
    assert user.created_at is not None

# Better: split into separate tests per concern
def test_user_creation_sets_name():
    user = create_user("alex", "alex@example.com")
    assert user.name == "alex"

def test_user_creation_sets_active():
    user = create_user("alex", "alex@example.com")
    assert user.is_active is True
```

**Expected/actual order consistency:** All assertion libraries have a convention for argument order. Violating it produces misleading failure messages. In pytest, the assertion is natural Python (`assert result == expected`); pytest rewrites assertions to produce rich output. In JUnit-style (`assertEquals(expected, actual)`), the order is expected first.

**Assertion messages:** Provide a message that diagnoses the failure without requiring re-reading the test. A bare `assert result == 5` that fails produces "AssertionError"; a message like `assert result == 5, f"Expected 5 but got {result!r} for input {input!r}"` is self-diagnosing.

**Fluent assertion libraries:** AssertJ (Java), Hamcrest (Java/Python), Shouldly (C#) provide readable, chainable assertions: `assertThat(result).isGreaterThan(0).isLessThan(100)`. Pytest's assert rewriting provides similar readability without a library.

---

## 6. Test smells (anti-patterns)

**Mystery Guest:** The test depends on external state — a file, a database row, a global variable — that is not set up within the test itself. The reader cannot understand the test without knowing about the external state. Fix: create all dependencies within the test or test fixture.

**Eager Test:** One test verifies too many different behaviors. Any failure requires reading the whole test to understand which behavior failed. Fix: one test per behavior.

**Fragile Test / Overspecified Test:** The test breaks when the implementation changes in ways that don't affect the observable behavior. Caused by over-reliance on mocks that record exact call signatures, or assertions on implementation details rather than outcomes. Fix: assert on outcomes; mock only at system boundaries.

**Slow Test:** The test takes seconds to run due to touching real resources. Fix: replace external dependencies with test doubles; use fake implementations.

**Conditional Test Logic:** The test contains `if`/`else` or `try`/`except` logic. A given test run only exercises one branch, leaving the other untested. A test with branching is really two tests. Fix: split into multiple tests.

**Test Code Duplication:** Copy-paste of setup code across many tests. When the setup changes, all copies must be updated. Fix: extract shared setup into fixtures or factory methods.

**Erratic Test:** The test sometimes passes and sometimes fails without code changes. Caused by timing dependencies, non-deterministic ordering, or shared state. Fix: eliminate sources of non-determinism; isolate test state.

---

## 7. Test naming conventions

A good test name is a sentence describing the behavior under test:

```
test_<unit>_<scenario>_<expected_behavior>
```

Examples:
- `test_order_with_expired_coupon_raises_invalid_coupon_error`
- `test_user_registration_sends_welcome_email`
- `test_empty_cart_returns_zero_total`

The test name should be readable in test output without context. A failing test named `test_order_with_expired_coupon_raises_invalid_coupon_error` tells you exactly what went wrong; a failing test named `test_order_3` does not.

---

## 8. Practical checklist

| Question | If No → Action |
|----------|---------------|
| Does every failing test identify exactly one failure? | Split eager tests |
| Do tests run under a second total for 100 tests? | Replace real resources with doubles |
| Can tests be run in any order? | Eliminate shared state |
| Does each test set up everything it needs? | Eliminate mystery guests |
| Do test names describe behavior, not implementation? | Rename |
| Are mocks used only at system boundaries? | Replace with fakes or state-based assertions |
