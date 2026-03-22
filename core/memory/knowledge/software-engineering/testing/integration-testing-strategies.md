---
created: 2026-03-20
last_verified: 2026-03-20
origin_session: core/memory/activity/2026/03/20/chat-003
source: agent-generated
trust: medium
type: knowledge
related:
  - testing-foundations-epistemology.md
  - unit-testing-principles.md
  - system-and-acceptance-testing.md
---

# Integration Testing Strategies

Integration testing verifies that separately developed components work correctly when combined. Unit tests guarantee isolated component behavior; integration tests catch interface mismatches, data format incompatibilities, and protocol errors that only emerge at component boundaries.

---

## 1. Why integration testing is necessary

The paradigm case of integration failure: the Mars Climate Orbiter loss (1999). The navigation team's software output thruster data in pound-force·seconds; the receiving software expected newton·seconds. Every individual component passed its own tests. The integration failure caused the $327.6M spacecraft to be lost.

**Classes of integration failures:**
- **Interface mismatches:** Function signature changes not propagated to callers; wrong return type expected
- **Data format incompatibilities:** One component serializes dates as ISO 8601; another expects Unix timestamps
- **Protocol errors:** Incorrect HTTP method, header, authentication scheme, or status code interpretation
- **Schema mismatches:** A database migration changed a column type; the ORM still maps the old type
- **Order-of-initialization bugs:** Component B assumes component A has initialized state; startup order is wrong
- **Implicit contract violations:** Component B assumes an API invariant that is not documented and not enforced by type checks

---

## 2. Integration strategies

### 2.1 Big-bang integration

**Approach:** Develop all components independently, then integrate them all at once.

**Advantages:** Lowest coordination overhead during development; all teams work in parallel without needing stubs or drivers.

**Disadvantages:** Highest debugging cost — when integration fails, it is impossible to attribute the failure to a specific interface. The integration phase becomes a long debugging period. Only appropriate for small, simple systems.

### 2.2 Top-down integration

**Approach:** Start with the highest-level component (entry point or main controller). Integrate lower-level components one at a time, replacing not-yet-integrated components with **stubs** (simplified implementations that return hardcoded data).

```
Level 1: [Controller]
               │ (stub)
Level 2:  [Service A]    [Service B]   ← stub both initially
               │ (stub)
Level 3:  [Repository]                 ← stub initially
```

**Advantages:** Early system-level operation (the system runs against stubs); tests the most important control flow first; design feedback on the top-level interface comes early.

**Disadvantages:** Many stubs must be written and maintained; lower-level components — where the most complex logic often lives — are tested last and integrated last.

### 2.3 Bottom-up integration

**Approach:** Start with the lowest-level components (utilities, repositories, infrastructure). Integrate toward higher levels, using **drivers** (test harnesses that call lower-level components in lieu of not-yet-integrated upper layers).

```
Level 3:  [Repository]           ← start here; use a driver to test
               │ (driver)
Level 2:  [Service A]  [Service B] ← integrate after repository
               │ (driver)
Level 1:  [Controller]             ← integrate last
```

**Advantages:** Lower-level components — which are often reused most — are tested in realistic context earlier. No stubs required (working lower-level components exist).

**Disadvantages:** No system-level operation until the highest-level component is integrated (late). Drivers must be written; the top-level design may not be validated until late.

### 2.4 Sandwich (hybrid) integration

**Approach:** Integrate from the middle outward in both directions simultaneously. Top-level and bottom-level components are developed first; middle-tier integration proceeds in both directions.

**Advantages:** Balances the advantages of top-down and bottom-up; minimizes both stub and driver count; allows parallel integration work.

**Disadvantages:** More complex coordination; requires more planning to identify the middle tier.

**Most common in practice** for large systems. The "middle tier" is typically domain services; infrastructure (databases, queues) and controllers are integrated from that midpoint outward.

---

## 3. Integration test design

**Integration test scope:** An integration test crosses one real interface and makes all other dependencies as real as is practical.

```python
# NOT an integration test — everything is mocked
def test_create_order_unit():
    repo_mock = Mock()
    email_mock = Mock()
    service = OrderService(repo=repo_mock, email=email_mock)
    service.create_order(...)
    repo_mock.save.assert_called_once()

# Integration test — real repository (in-memory or test DB), mocks external services
def test_create_order_persists_to_database(db_session):
    repo = SQLAlchemyOrderRepository(db_session)
    email_mock = Mock()  # still mock external email API
    service = OrderService(repo=repo, email=email_mock)
    order = service.create_order(user_id=1, items=["widget"])
    saved_order = repo.find_by_id(order.id)
    assert saved_order.user_id == 1
    assert len(saved_order.items) == 1
```

**At what level to mock:** Mock at system boundaries — external APIs, external databases outside your control, payment gateways, email providers, SMS services. Use real implementations for internal components: in-process services, in-memory queues, test databases.

**Test isolation:** Each integration test must leave shared resources (database rows, message queue messages) in a clean state. Use transactions rolled back after each test (pytest's `db_session` fixture with rollback), or truncate/recreate tables in test setup.

---

## 4. API contract testing

**Problem:** In a microservices or multi-team environment, API consumers and providers evolve independently. A provider change can silently break consumers. Integration tests in the provider's own test suite may not cover all the contracts that consumers depend on.

**Consumer-driven contract testing:** Contracts are defined by the consumer based on what it actually uses. The provider must satisfy all consumer contracts.

**Pact framework workflow:**
1. **Consumer:** Write a Pact test specifying what the consumer sends and what it expects back
2. **Consumer:** Run the tests against a Pact mock server; on success, a pact JSON file is generated
3. **Pact broker:** The pact file is published to a central Pact Broker
4. **Provider:** In CI, retrieve all pact files from the broker and run them against the real provider implementation
5. **Result:** Any provider change that breaks a consumer contract fails the provider's own CI pipeline before deployment

**Example Pact consumer test (Python):**
```python
from pact import Consumer, Provider

pact = Consumer("OrderService").has_pact_with(Provider("InventoryService"))

@pytest.fixture
def order_client(pact):
    pact.given("item SKU-123 has 5 units in stock") \
        .upon_receiving("a request for item stock") \
        .with_request("GET", "/items/SKU-123/stock") \
        .will_respond_with(200, body={"sku": "SKU-123", "quantity": 5})
    with pact:
        yield InventoryClient(base_url=pact.uri)

def test_order_service_checks_inventory(order_client):
    stock = order_client.get_stock("SKU-123")
    assert stock.quantity == 5
```

**When to use contract testing:**
- Microservices with multiple independent teams
- Mobile apps consuming internal APIs (the mobile app is the consumer)
- Any situation where the consumer and provider are deployed independently

**Bidirectional contract testing (Pact v4):** Schema-based matching rather than request/response replay, reducing the brittleness of traditional Pact and enabling async messaging contracts.

---

## 5. Database integration testing

**In-memory databases:** SQLite for testing SQL code that works on PostgreSQL or MySQL in production. Advantages: fast, no external dependency, always clean state. Disadvantages: SQLite has different behaviors (limited column types, different locking) that can hide real bugs.

**Test containers:** Spin up a real PostgreSQL, MySQL, or Redis container in Docker for the test run. Advantages: identical to production database engine; catches database-specific bugs. Disadvantages: slower startup; requires Docker.

**Recommended pattern (pytest + SQLAlchemy):**
```python
@pytest.fixture(scope="session")
def db_engine():
    engine = create_engine("postgresql://user:pass@localhost:5432/testdb")
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)

@pytest.fixture
def db_session(db_engine):
    connection = db_engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)
    yield session
    session.close()
    transaction.rollback()  # rollback ensures each test starts fresh
    connection.close()
```

---

## 6. Message queue and event integration testing

**Challenge:** Testing that service A emits the correct event when an action occurs, and that service B correctly handles that event.

**In-process testing with a fake bus:**
```python
class FakeEventBus:
    def __init__(self):
        self.published_events = []

    def publish(self, event):
        self.published_events.append(event)

def test_order_creation_publishes_event():
    bus = FakeEventBus()
    service = OrderService(event_bus=bus)
    service.create_order(user_id=1, items=["widget"])
    assert len(bus.published_events) == 1
    assert bus.published_events[0].type == "OrderCreated"
    assert bus.published_events[0].user_id == 1
```

**Integration testing with real queues:** Use test-scoped queues in a real RabbitMQ/Redis/Kafka instance (via test containers). Publish events from the service, consume from the queue, verify message content. This catches serialization bugs, routing key errors, and schema mismatches.

---

## 7. Integration testing in CI pipelines

**Separation from unit tests:** Integration tests are slower and require external resources. They should be:
- Discoverable separately (`pytest -m integration`)
- Run in a separate CI job after unit tests pass
- Run against an ephemeral, isolated environment (test containers or a dedicated test environment)

**Test data management:** Integration tests that touch databases need controlled, known test data. Options:
- **Fixtures:** Static SQL or JSON that is loaded before each test run and rolled back after
- **Factory functions:** `make_user()`, `make_order()` factories that create minimal test data in the test database
- **Snapshot restore:** Restore the database to a known snapshot before the integration test run

**Integration test runtime budget:** Integration tests should complete within the CI pipeline's timeout. Common target: under 5 minutes for integration tests, under 15 minutes for the full integration suite. Achieve this via parallelism, fast containers, and excluding non-critical test configurations from the mainline CI run.
