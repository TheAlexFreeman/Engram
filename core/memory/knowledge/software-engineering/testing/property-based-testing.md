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
  - black-box-test-design.md
---

# Property-Based Testing

Property-based testing (PBT) replaces specific example-based test cases with properties — logical predicates that should hold for all inputs in a domain. The framework generates many inputs automatically, tests the property for each, and shrinks failing inputs to a minimal counterexample.

---

## 1. Core idea

In **example-based testing**, the developer specifies both the input and the expected output:

```python
def test_reverse_list():
    assert reverse([1, 2, 3]) == [3, 2, 1]
    assert reverse([]) == []
    assert reverse([1]) == [1]
```

In **property-based testing**, the developer specifies a property that should hold for *all* valid inputs:

```python
from hypothesis import given
import hypothesis.strategies as st

@given(st.lists(st.integers()))
def test_reverse_is_its_own_inverse(xs):
    assert reverse(reverse(xs)) == xs
```

The framework generates hundreds or thousands of inputs — including edge cases the developer would never think of — and checks the property for each. If any fails, it reports a minimal counterexample.

**Why this is more powerful:** A single property test can cover an effectively unlimited input space. It regularly finds inputs that developers do not anticipate, especially: empty inputs, very large values, negative values, repeated elements, Unicode strings, and extreme combinations.

---

## 2. The QuickCheck origin and Hypothesis

**QuickCheck (Claessen & Hughes, 2000, Haskell):** The first practical PBT library. Established the core concepts: generators, properties, and shrinking. Spawned ports to every major language.

**Hypothesis (Python, David MacIver):** The most mature PBT library in Python and widely considered the best-designed PBT library overall. Key innovations over QuickCheck:
- **Stateful shrinking:** Hypothesis remembers past failures and tries to find smaller versions in subsequent runs
- **Database of failures:** Hypothesis saves failing examples and re-runs them first in future runs (regression without manual test case entry)
- **Better shrinking:** Hypothesis shrinks more aggressively and produces more minimal counterexamples
- **Swappable strategies:** Composable strategy objects for generating structured data

---

## 3. Generators and strategies

The framework must know how to generate valid inputs for each property. **Generators** (Hypothesis calls them **strategies**) are composable objects that describe how to produce values of a given type.

**Built-in strategies (Hypothesis):**

```python
from hypothesis import strategies as st

st.integers()                        # any integer
st.integers(min_value=0, max_value=100)  # bounded integers
st.floats(allow_nan=False)           # floats excluding NaN
st.text()                            # arbitrary Unicode text
st.text(alphabet=string.ascii_letters, min_size=1)  # restricted text
st.lists(st.integers())              # lists of integers
st.lists(st.integers(), min_size=1, max_size=10)
st.tuples(st.integers(), st.text())  # tuple types
st.dictionaries(st.text(), st.integers())  # dict with string keys
st.one_of(st.integers(), st.text())  # union type
st.sampled_from([1, 2, 3, "a"])      # draw from a fixed set
st.booleans()
st.none()                            # only None
st.just(42)                          # always produces 42
```

**Composing strategies:**

```python
# Custom domain object
from dataclasses import dataclass
from hypothesis import given
import hypothesis.strategies as st

@dataclass
class Order:
    items: list[str]
    quantity: int

order_strategy = st.builds(
    Order,
    items=st.lists(st.text(min_size=1), min_size=1),
    quantity=st.integers(min_value=1, max_value=1000)
)

@given(order_strategy)
def test_order_total_is_positive(order):
    assert order_total(order) > 0
```

---

## 4. Shrinking

**The problem without shrinking:** Failing inputs found by random generation are often large and complex. A failing list of 100 integers is hard to debug.

**Shrinking:** When a failing input is found, the framework tries to find a *smaller* input that also fails. "Smaller" is defined by the strategy: for lists, shorter; for integers, closer to zero; for strings, shorter and with lower character codes.

**Result:** The failing case reported to the developer is typically the *minimal* counterexample — the simplest possible input that reveals the bug. This makes PBT failures as actionable as hand-written unit tests.

**Hypothesis shrinking example:**
```
Falsifying example (after 47 tests and 12 shrinks):
  xs = [0, 0]

where the property `all_unique(deduplicate(xs)) == True` failed
because deduplicate([0, 0]) returned [0, 0] instead of [0]
```

The library found the two-element list `[0, 0]` as the minimal counterexample, avoiding the developer's need to manually minimize a 47-element failing input.

---

## 5. Property patterns (invariant discovery)

The hardest part of PBT is writing meaningful properties. Several canonical patterns apply across many domains:

### 5.1 Roundtrip (encode-decode)

If encoding and decoding are inverses, the roundtrip should be the identity:

```python
@given(st.text())
def test_json_roundtrip(text):
    assert json.loads(json.dumps(text)) == text

@given(st.binary())
def test_compress_decompress_roundtrip(data):
    assert decompress(compress(data)) == data
```

### 5.2 Oracle properties

Compare the SUT against a known-correct reference implementation:

```python
@given(st.lists(st.integers()))
def test_sort_matches_reference(xs):
    assert optimized_sort(xs) == sorted(xs)  # compare to stdlib's sort
```

Useful for: optimized implementations of known algorithms, numerical approximations, parallel implementations of sequential algorithms.

### 5.3 Metamorphic relations

Even without knowing expected outputs, predictable *relationships* between outputs for related inputs can be stated:

```python
@given(st.lists(st.integers()), st.integers())
def test_search_result_count_increases_with_relaxed_filter(items, threshold):
    strict_count = count_above(items, threshold)
    relaxed_count = count_above(items, threshold - 1)
    assert relaxed_count >= strict_count  # metamorphic relation

@given(st.text(), st.text())
def test_concatenation_search(haystack, needle):
    in_original = needle in haystack
    in_doubled = needle in (haystack + haystack)
    assert in_doubled >= in_original  # if found once, found in doubled version
```

Metamorphic testing is particularly powerful for ML systems where ground truth doesn't exist: if a stop word is added to a search query, the top result should remain the same.

### 5.4 Model-based properties

The SUT behavior should match a simpler reference model:

```python
import collections

@given(st.lists(st.tuples(st.text(), st.integers())))
def test_cache_matches_dict(operations):
    cache = LRUCache(capacity=3)
    model = {}
    for key, value in operations:
        cache.set(key, value)
        model[key] = value
    # For keys that fit in cache capacity, should match
    for key in list(model.keys())[-3:]:  # last 3 keys guaranteed in LRU
        assert cache.get(key) == model[key]
```

### 5.5 Idempotence and monotonicity

```python
@given(st.lists(st.integers()))
def test_sort_is_idempotent(xs):
    once = sorted(xs)
    twice = sorted(sorted(xs))
    assert once == twice

@given(st.lists(st.integers(), min_size=1), st.integers())
def test_adding_element_to_set_is_monotone(xs, new_element):
    s = set(xs)
    s_with_new = set(xs) | {new_element}
    assert len(s_with_new) >= len(s)
```

---

## 6. Filtering inputs: `assume()`

Use `assume()` to discard inputs that don't satisfy a precondition. The framework will generate more inputs until it has enough passing the assumption.

```python
from hypothesis import given, assume
import hypothesis.strategies as st

@given(st.integers(), st.integers())
def test_division(numerator, denominator):
    assume(denominator != 0)  # skip invalid inputs
    result = numerator / denominator
    assert abs(result * denominator - numerator) < 1e-10
```

**Caution: over-filtering kills diversity.** If `assume()` filters out a large fraction of generated inputs, the property test effectively covers a narrow slice of the input space. Prefer generator design (using `st.integers(min_value=1)`) over filtering when possible — it's both faster and more honest about what inputs are being tested.

---

## 7. Stateful property testing

Standard PBT tests stateless functions. Stateful PBT tests systems that maintain state across operations.

**The approach:** Generate random sequences of commands (operations that change state) and execute them against both the SUT and a simple model. If the SUT and the model ever disagree, report the minimal failing command sequence.

```python
from hypothesis.stateful import RuleBasedStateMachine, rule, initialize, Bundle

class QueueMachine(RuleBasedStateMachine):
    def __init__(self):
        super().__init__()
        self.sut_queue = FastQueue()      # implementation under test
        self.model_queue = collections.deque()  # reference model

    @rule(value=st.integers())
    def enqueue(self, value):
        self.sut_queue.push(value)
        self.model_queue.append(value)

    @rule()
    def dequeue(self):
        if not self.model_queue:
            return  # nothing to dequeue
        expected = self.model_queue.popleft()
        actual = self.sut_queue.pop()
        assert actual == expected, f"Queue mismatch: expected {expected}, got {actual}"

    @rule()
    def check_size(self):
        assert self.sut_queue.size() == len(self.model_queue)

TestQueue = QueueMachine.TestCase
```

**Stateful PBT is invaluable for:** thread-safe data structures, stateful protocols (HTTP session management, WebSocket connections), database transactions, UI state machines.

---

## 8. When property-based testing is most effective

**Excellent domains:**
- Parsers and serializers (roundtrip properties are always applicable)
- Data structures (model-based properties against simpler implementations)
- Algorithms with mathematical specifications (sort, search, crypto primitives)
- Protocol implementations (stateful PBT)
- Business logic with invariants (totals must be non-negative, ordering must be consistent)

**Harder domains:**
- UI rendering (no computable oracle for visual output)
- Systems with complex non-deterministic external dependencies (network, time)
- Underdetermined specifications (when there is no clear property to assert — go write the specification first)
- Performance-sensitive code (PBT adds overhead; run separately from unit tests)

**Complementing example-based tests:** PBT and example-based tests are complementary. PBT finds unexpected failures in large input spaces; example tests document specific known cases. Write both.

---

## 9. Integrating with existing test runners

```python
# pytest + Hypothesis: works automatically
# @given-decorated tests are discovered and run by pytest
# pytest-hypothesis plugin provides additional options

# Settings
from hypothesis import given, settings, HealthCheck

@settings(max_examples=500, suppress_health_check=[HealthCheck.too_slow])
@given(st.text())
def test_heavy_property(s):
    ...

# CI configuration: use --hypothesis-seed for reproducible failures
# pytest --hypothesis-seed=0 tests/
```

**The Hypothesis database:** Hypothesis saves failing examples in a local `.hypothesis/` directory. On subsequent runs, it re-runs saved failures first. Commit `.hypothesis/` to version control to share failures across the team.
