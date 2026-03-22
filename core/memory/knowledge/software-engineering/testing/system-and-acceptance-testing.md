---
created: 2026-03-20
last_verified: 2026-03-20
origin_session: core/memory/activity/2026/03/20/chat-003
source: agent-generated
trust: medium
type: knowledge
related:
  - integration-testing-strategies.md
  - testing-foundations-epistemology.md
  - performance-and-load-testing.md
---

# System and Acceptance Testing

System testing verifies the complete, integrated application against its requirements. Acceptance testing verifies it meets stakeholder needs. These are the highest-level dynamic testing activities.

---

## 1. System testing scope

System testing treats the application as a complete integrated unit exposed only via its external interfaces (APIs, UI, message queues, files). It verifies:
- **Functional requirements:** All features behave as specified
- **Non-functional requirements:** Performance, reliability, security, usability, accessibility
- **Interface requirements:** Integration with third-party services, external APIs, browsers, operating systems

System testing is always black-box (from the system's external interface); testers do not need to know the source code. System tests are the primary tool for confirming that the system is ready for production.

---

## 2. Test pyramid and its variants

### 2.1 The test pyramid (Mike Cohn)

```
           /\
          /  \
         / E2E \        (few — slow, expensive, highest confidence)
        /────────\
       / Integration \  (some — moderate speed, catches interface bugs)
      /──────────────\
     /    Unit Tests   \ (many — fast, cheap, precise attribution)
    /──────────────────\
```

**Rationale:** Unit tests are orders of magnitude faster and cheaper per test than E2E tests. Build a large foundation of unit tests for fine-grained behavioral coverage, fewer integration tests for interface verification, and only the minimum E2E tests needed to verify critical flows in the complete system.

### 2.2 The testing trophy (Kent C. Dodds)

```
        /\
       /E2E\            (a few)
      /──────\
     / Integration \    (the most — primary confidence)
    /──────────────\
   /    Unit Tests   \  (some — for pure logic)
  /──────────────────\
 /  Static Analysis   \ (linting, type checking, always)
/──────────────────────\
```

The trophy advocates for prioritizing integration tests because: they test the way the software is actually used; they refactor well (no mock coupling); they provide the best ratio of confidence to maintenance cost. This perspective dominates in frontend testing communities (Testing Library philosophy).

### 2.3 The honeycomb (Spotify)

Used in microservices architectures:
- Many service integration tests (test each service against its real dependencies in isolation)
- Very few cross-service and E2E tests
- Minimal unit tests (mostly for pure functions and algorithms)

**No universally correct shape.** The right test distribution depends on:
- Architecture (monolith vs. microservices)
- Team confidence boundaries
- Cost of test maintenance vs. cost of defect escape
- Speed requirements for CI pipeline

---

## 3. End-to-end (E2E) testing

E2E tests drive the complete application stack — from UI or API surface through all layers to the database — without mocking internal components. They are the highest-confidence, highest-maintenance test type.

**When E2E tests are valuable:**
- Critical user journeys (checkout flow, authentication, payment)
- Multi-component state changes that span databases, caches, and external services
- Smoke tests after deployment to production (a small E2E suite that verifies the system is alive)

**Hermetic E2E tests:** Replace external dependencies (payment gateways, email, SMS) with test doubles even in E2E tests. This prevents external services from causing E2E test failures and makes tests repeatable.

**Flakiness:** E2E tests are the most prone to flakiness:
- Timing dependencies (asynchronous operations — use explicit waits, not `sleep()`)
- Race conditions in state setup
- Environment differences (browser rendering, OS font metrics)
- Network timeouts

**Managing flakiness:**
- Use retry logic sparingly and with exponential backoff
- Log full test context (screenshots, network traces) on failure
- Quarantine chronically flaky tests and fix them immediately — a flaky test is worse than no test (creates false confidence; wastes developer time; trains teams to ignore test failures)

**Tools:**
- **Playwright** (TypeScript/Python/Java) — modern, reliable, cross-browser; Microsoft-maintained
- **Cypress** (JavaScript) — excellent developer experience; stays within the browser (lower coverage of server-side)
- **Selenium** (any language) — legacy; verbose; widespread; high flakiness risk
- **httpx/requests-based API E2E** — for API-only systems; fast and reliable

---

## 4. Regression testing

**Definition:** Regression testing re-executes existing tests after a change to verify that previously correct behavior has not been broken.

**Why regression escapes happen:**
- Tight coupling: changing component A silently breaks component B
- Shared state: a change to a database schema or global config propagates unexpectedly
- Implicit dependencies: a downstream team depended on a side effect that was "fixed"

**Regression test selection strategies:**

1. **Run the full suite:** Highest confidence; only viable if the full suite completes within the CI pipeline's time budget. This is the standard approach for well-managed codebases.

2. **Change impact analysis (test selection):** Analyze which test files cover the modified source files and run only those. Tools: `pytest-testmon` (Python), Jest's `--onlyChanged` (JS). Risk: coverage analysis can miss indirect dependencies.

3. **Risk-based selection:** Run the tests for the most business-critical flows on every change; run the full suite only on release candidates. Acceptable when full-suite runtime makes this necessary.

**Regression test design:** Every bug fixed should produce a regression test. The test fails before the fix and passes after. This documents the fix, prevents re-introducing the bug, and increases coverage of previously failing behaviors.

---

## 5. Acceptance testing

Acceptance testing verifies that the system satisfies stakeholder requirements. It is the boundary between testing ("does the system behave as specified?") and validation ("is this the right system?").

**Formal acceptance tests:** Test cases derived directly from user stories or use cases. Often written by BAs or product owners in collaboration with developers. In BDD workflows, these are Gherkin scenarios executed by Cucumber or Behave.

**User Acceptance Testing (UAT):** Exploratory testing conducted by actual end users (or designated user representatives) in a staging environment before final sign-off. UAT is not scripted automated testing — it is human judgment applied to whether the software is fit for purpose. UAT failure means incorrect requirements or incorrect interpretation of correct requirements.

**Acceptance criteria quality:**
- Testable: "The system should load in under 2 seconds" (testable) vs. "the system should be fast" (not testable)
- Unambiguous: specifies exactly what "correct" means
- Achievable with the planned implementation
- Independent: does not assume implementation details

---

## 6. Exploratory testing

**Definition:** Simultaneous test design and execution by a skilled tester using analytical thinking, intuition, and domain expertise to find bugs not anticipated by scripted tests.

**Session-based exploratory testing (SBET):** A structured approach:
- Define a **charter** (the scope of exploration: "Explore the checkout flow under unusual cart configurations")
- Time-box the session (typically 90 minutes)
- Record observations, findings, and test ideas during the session
- Debrief with notes on what was covered, what was found, and what questions remain

**When exploratory testing is most valuable:**
- After a major feature release (scripted tests cover the expected cases; exploratory finds unexpected ones)
- For complex UI flows with many interaction patterns
- When the specification is incomplete or ambiguous
- When scripted test coverage is high but confidence remains low (gut-level doubt)
- As a source of new test cases to add to the automated suite

**Exploratory testing is not unstructured:** Skilled testers bring mental models, heuristics (error guessing, boundary probing, state-based exploration), and domain knowledge. The output should be documented findings and new test cases, not just ad-hoc clicking.

---

## 7. Smoke tests and sanity tests

**Smoke tests:** A small, fast subset of the test suite that verifies the application starts and basic functionality works. Named after hardware testing: "does it smoke when you power it on?" Smoke tests should run in under 2 minutes after every deployment and gate promotion to the next environment.

**Sanity tests:** A broader subset than smoke tests; verifies major functional areas without comprehensive coverage. Run on release candidates to confirm stability before UAT or production promotion.

**The distinction is fuzzy in practice.** The key design principle: have a small, known, curated subset of tests that can verify basic system health quickly after any change.

---

## 8. Test environment management

**Environment tiers (typical):**
```
Developer local → CI (automated tests) → Staging → Production
```

**Environment parity:** Each environment should be as similar to production as possible. Differences between environments are a class of integration failure. Containerization (Docker Compose for local and staging) reduces environment differences.

**Test data management in staging:**
- Never use real production user data in staging (privacy, GDPR)
- Use anonymized production data subsets or synthetic data
- Ensure test data does not accumulate in staging (run cleanup after E2E suites)

**Configuration isolation:** Tests should not depend on environment-specific configuration values that differ from production. Configuration differences between environments are defects. Use feature flags and environment-agnostic configurations wherever possible.
