---
created: 2026-03-20
last_verified: 2026-03-20
origin_session: core/memory/activity/2026/03/20/chat-003
source: agent-generated
trust: medium
type: knowledge
related:
  - testing-foundations-epistemology.md
  - system-and-acceptance-testing.md
  - performance-and-load-testing.md
---

# Software Quality Assurance: Metrics and Process

Software Quality Assurance (SQA) is the discipline of preventing defects through systematic process design and improvement. It complements quality control (which catches defects in the product) by attacking defects at their source.

---

## 1. QA vs. QC distinction

**Quality Control (QC)** is product-oriented: find and fix defects in the artifact being produced. Testing is the primary QC activity. QC is reactive — it detects defects after they've been introduced.

**Quality Assurance (QA)** is process-oriented: prevent defects by improving the processes that produce software. Auditing development processes, establishing coding standards, creating defect-prevention checklists, and process maturity programs are QA activities. QA is proactive.

**Why both are necessary:**
- QC without QA is whack-a-mole: defects are caught one by one but the root causes that produce them are never addressed. The defect rate stays constant.
- QA without QC is blind: process improvements are applied without feedback on whether they actually reduce defect rates.
- Mature organizations do both: QC measures provide the defect data that QA analysis uses to identify process weaknesses.

**In agile contexts:** The QA vs. QC distinction is often blurred. "QA" in job titles typically means test engineers (QC work). Genuine QA activity in agile includes: retrospective process improvement, definition-of-done enforcement, static analysis in CI, and code review standards.

---

## 2. Defect taxonomy

Classifying defects enables root cause analysis and process improvement. Without classification, defect data is noise; with classification, it reveals patterns.

### 2.1 By severity

| Severity | Definition | Example |
|---------|-----------|---------|
| **Blocker** | Prevents entire system from functioning | Application fails to start |
| **Critical** | Major feature completely broken; no workaround | Payment processing fails for all users |
| **Major** | Important feature broken; workaround exists | Expired session does not redirect to login |
| **Minor** | Feature partially impaired; acceptable workaround | Sort order resets on page navigation |
| **Trivial** | Cosmetic; no functional impact | Button misaligned by 2px |

Severity is objective (how bad is the impact?). **Priority** is a separate axis: how urgently must it be fixed? A trivial cosmetic bug on the homepage of a marketing site may be high-priority; a critical bug in a rarely-used admin feature may be low-priority.

### 2.2 By origin phase

Where in the SDLC was the defect introduced?

| Origin | Description | Typical example |
|--------|-------------|-----------------|
| Requirements | The requirement was wrong, ambiguous, or missing | "The system should validate email format" — format not specified |
| Design | The design satisfied the requirement but had flaws | N+1 query pattern baked into service design |
| Coding | The design was correct but the code implemented it wrong | Off-by-one in a loop bound |
| Testing | A test case was incorrect (incorrect oracle) | Test asserted wrong expected value |
| Deployment | Defect introduced during configuration or release | Missing environment variable in production config |

Tracking origin phase reveals which SDLC activities most need attention. A high proportion of requirements-origin defects suggests inadequate requirements review or specification.

### 2.3 By type

| Type | Example |
|------|---------|
| Logic error | Incorrect conditional; wrong formula |
| Boundary/off-by-one | `<` instead of `<=`; `range(n)` instead of `range(n+1)` |
| Interface error | Wrong number of arguments; type mismatch between components |
| Data handling | Truncation; encoding error; null not handled |
| Timing/concurrency | Race condition; deadlock; stale cache |
| Performance | Query without index; N+1; memory leak |
| Usability | UI action doesn't match user mental model |
| Security | Injection vulnerability; unvalidated input |

---

## 3. Root cause analysis

Root cause analysis (RCA) distinguishes the immediate cause of a defect from the underlying systemic cause. Fixing immediate causes prevents the same specific defect from recurring; fixing root causes prevents the entire class of defects.

### 3.1 Five-whys technique

Ask "why?" iteratively until a root cause actionable by process improvement is reached:

```
Defect: Payment failed for 0.03% of users during peak hour

Why 1: A database connection pool was exhausted
Why 2: Connection pool was sized for baseline traffic, not peak traffic
Why 3: Load testing was not performed before the payment feature launched
Why 4: There is no performance testing requirement in the definition of done
Why 5: The team has never had an explicit performance SLA for payment features

Root cause: No performance SLA and no load testing requirement in DoD
Actionable fix: Add "load test verified against performance SLA" to the DoD
                for any feature involving payment or high-traffic flows
```

**Stopping correctly:** The five-whys can be applied too mechanically. Stop when you reach something actionable at the process or organization level, not at the impossible (human error is not a root cause — it is a symptom of an inadequate safeguard).

### 3.2 Fishbone (Ishikawa) diagram

A visual RCA tool that branches causes into categories (typically: People, Process, Tools, Environment, Materials/Inputs). Useful for group RCA sessions where multiple contributing causes exist.

```
            People          Process
              │               │
  ── ── ── ──┼───────────────┼── ── → [Defect]
              │               │
            Tools         Environment
```

Populate each branch with contributing factors, then identify which factors are root causes (fixable at the process level).

### 3.3 Causal loop diagrams

For systemic, recurring defects, linear RCA is insufficient. Causal loop diagrams (CLD) capture feedback loops: "time pressure → reduced testing → more defects → more urgent bug fixing → more time pressure." Identifying negative feedback loops (stabilizing) and positive feedback loops (escalating) reveals structural problems in the organization or process.

---

## 4. Defect density and escape rate

**Defect density:** Number of defects found per unit of size (KLOC, function points, story points). Useful for:
- Comparing modules: high-density modules are candidates for refactoring or deeper testing
- Tracking trends: increasing defect density signals degrading code quality
- Estimating remaining defects (using Rayleigh model or empirical averages)

**Defect escape rate:** `post-release defects / (pre-release defects + post-release defects)`. Measures how many defects escape the test process into production.

A high escape rate (>30%) indicates the test process needs investment. Industry reference: top-quartile organizations escape <10% of defects; median organizations escape 40-60%.

**Pareto principle in defects:** Empirically, ~80% of defects originate in ~20% of modules. Identifying these defect-prone modules (using cumulative defect density) and allocating extra testing, refactoring, or code review effort there provides better returns than evenly distributing effort.

---

## 5. Code review and inspection

Code review is a static QC activity: examining code artifacts before or without execution. It is complementary to testing — code review catches different defect classes than testing.

**What code review catches better than testing:**
- Security vulnerabilities (XSS, SQL injection, insecure patterns) — reviewers can spot patterns; tests rarely find undetected injection points
- Design and maintainability issues — complex logic, poor naming, missing error handling
- Specification violations visible only in code structure — wrong algorithm for stated requirement
- Missing cases — "what happens if user is null here?"

**What testing catches better than code review:**
- Behavioral errors — "the code looks plausible but produces the wrong output for these inputs"
- Integration errors — components individually look correct but fail together
- Performance issues — only measurable by execution

### 5.1 Fagan inspection

The original formal software inspection technique (Michael Fagan, IBM, 1976):

**Roles:**
- **Moderator:** Facilitates the meeting; trained in inspection technique
- **Reader/Presenter:** Reads code aloud in their own words (paraphrasing); prompts discussion
- **Author:** Answers questions; takes notes; does not defend
- **Inspector(s):** Examine code for defects using checklists

**Process phases:** Planning → Overview (author presents context) → Individual Preparation → Meeting (2 hours maximum) → Rework → Follow-up.

**Formal inspection produces data:** defect count by type, inspection rate (LOC/hour), rework time. This data feeds QA process improvement.

### 5.2 Modern code review (pull requests)

Lightweight compared to Fagan inspection. Key practices:
- **Small PRs:** 200-400 LOC maximum; large PRs have worse review quality and take much longer to review
- **Reviewable author:** Author writes a description explaining context, change motivation, and any concerns
- **Review checklists:** Explicit criteria (security checklist, testing checklist)
- **Tone:** Distinguish blocking comments from suggestions; frame as "consider X" not "you must do X"
- **Two-reviewer rule** for security-sensitive or production-critical changes
- **Review latency:** Target 24h maximum; long review queues cause developers to accumulate parallel work (context switching cost)

---

## 6. Process maturity models

Process maturity models assess the organizational capability to deliver quality software consistently.

### 6.1 CMMI (Capability Maturity Model Integration)

| Level | Name | Characteristics |
|-------|------|----------------|
| 1 | Initial | Ad hoc; chaotic; success depends on individual heroics |
| 2 | Managed | Project-level processes established; repeatable within projects |
| 3 | Defined | Organization-wide standard processes; tailored per project |
| 4 | Quantitatively Managed | Processes measured with quantitative data; controlled variation |
| 5 | Optimizing | Continuous improvement based on measurement; defect prevention |

**Key insight:** Moving from Level 1 to Level 2 (establishing basic project management) captures the majority of quality improvement. Most organizations never need Level 4-5, which has significant overhead cost.

### 6.2 Critique of process maturity models

- Process maturity correlates imperfectly with product quality; a Level 5 organization can still ship defective software
- Heavy process (Level 4-5) can create process-over-substance pathologies — teams optimize for process compliance metrics rather than for shipping quality software
- Agile methods operate effectively at conceptual Level 3 without the formal CMMI overhead; agile retrospectives are an informal version of CMMI Level 5 continuous improvement
- Use maturity models as diagnostic frameworks, not as prescriptions

---

## 7. Testing economics: shift-left and ROI

**Shift-left testing:** Moving testing earlier in the SDLC. The earlier a defect is found, the cheaper it is to fix.

**Boehm's data (approximate order-of-magnitude estimates):**
| Phase detected | Relative cost to fix |
|---------------|---------------------|
| Requirements | 1× |
| Design | 3-6× |
| Coding (unit testing) | 10× |
| System testing | 40-100× |
| Production | 300-1,000× |

These figures are rough and context-dependent, but the trend is robust: defects are significantly cheaper to fix earlier. This is the economic justification for TDD, code review, static analysis, and design reviews.

**Testing ROI:** The ROI of additional testing is highest when:
- Defect escape costs are high (safety critical, financial systems, high user volume)
- Test maintenance costs are low (tests are at the right level, not over-specified)
- Test coverage is currently low (marginal returns are highest where coverage is sparse)

Testing ROI is lowest when:
- Tests are fragile and require constant maintenance
- The tested code changes frequently (test churn overhead dominates)
- Detected defects are low-severity enough that fixing them costs more than they would have if found in production

---

## 8. Continuous testing in CI/CD

**Test pyramid and pipeline design:** A well-structured CI/CD pipeline runs tests in order from fastest/cheapest to slowest/most expensive, failing fast on the cheapest signals:

```
Commit → [Lint + Type Check (30s)] → [Unit Tests (2m)] → 
         [Integration Tests (5m)] → [E2E Smoke (3m)] → Deploy to staging →
         [Full E2E + Performance (20m)] → Deploy to production
```

**Flaky test management:**
- Flaky tests undermine the CI pipeline — teams learn to ignore failures, which defeats CI's purpose
- Every flaky test should be quarantined (skipped in mainline CI) and fixed within the sprint
- Root causes of flakiness: time-dependent behavior, non-deterministic ordering, shared mutable state, external service dependency, race conditions in async tests

**Test parallelization:** Unit and integration tests can typically be parallelized across CPU cores (`pytest-xdist`, Jest --maxWorkers). This is the primary lever for reducing CI wall-time without sacrificing coverage.

**Incremental / selective test execution:** Tools like `pytest-testmon` (Python) and Jest's `--onlyChanged` (JS) run only tests affected by the current diff. Fastest for large codebases; carries the risk of missing indirect dependencies.
