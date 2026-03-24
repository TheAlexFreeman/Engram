---

created: 2026-03-20
last_verified: 2026-03-20
source: agent-generated
type: summary
related:
  - black-box-test-design.md
  - integration-testing-strategies.md
  - test-doubles-mock-patterns.md
---

# Software Testing, Validation, and Verification

Core knowledge on software testing at every level — from unit tests through formal verification — and across AI/ML evaluation. Files are organized by testing level and technique.

## Files

| File | Scope |
|------|-------|
| [testing-foundations-epistemology.md](testing-foundations-epistemology.md) | Oracle problem, Dijkstra impossibility, testing hierarchy, V&V distinction, DeMillo-Lipton-Perlis hypothesis, coverage limits |
| [unit-testing-principles.md](unit-testing-principles.md) | FIRST properties, test doubles taxonomy (Meszaros), sociable vs. solitary, assertion patterns, test smells |
| [test-driven-development.md](test-driven-development.md) | Red-green-refactor, triangulation, emergent design, London vs. Detroit schools, BDD/Gherkin, ATDD |
| [black-box-test-design.md](black-box-test-design.md) | Equivalence partitioning, boundary value analysis, decision tables, state transition testing, pairwise, cause-effect graphing |
| [coverage-and-mutation-testing.md](coverage-and-mutation-testing.md) | Statement/branch/path/MC/DC coverage, data-flow analysis, Goodhart's Law applied, mutation operators, mutation score, tools |
| [property-based-testing.md](property-based-testing.md) | QuickCheck/Hypothesis, shrinking, invariant patterns (roundtrip, oracle, metamorphic, model-based), stateful PBT |
| [integration-testing-strategies.md](integration-testing-strategies.md) | Top-down/bottom-up/sandwich/big-bang integration, interface mismatch failures, contract testing (Pact) |
| [system-and-acceptance-testing.md](system-and-acceptance-testing.md) | Test pyramid and variants (trophy, honeycomb), E2E testing, regression testing, acceptance and exploratory testing |
| [performance-and-load-testing.md](performance-and-load-testing.md) | Latency percentile discipline, load/stress/soak/spike testing, chaos engineering, profiling, flame graphs |
| [software-qa-metrics-process.md](software-qa-metrics-process.md) | QA vs. QC, defect taxonomy, root cause analysis (five-whys, fishbone), defect density, code review, CMMI |
| [formal-verification-foundations.md](formal-verification-foundations.md) | Hoare logic, weakest precondition calculus, design by contract, formal methods spectrum, practical limits |
| [model-checking-abstract-interpretation.md](model-checking-abstract-interpretation.md) | Model checking (SPIN, TLA+, state explosion), abstract interpretation (Cousot), SAT/SMT solvers, bounded model checking |
| [ml-evaluation-methodology.md](ml-evaluation-methodology.md) | Contamination, cross-validation, metric choice (F1, BLEU, Brier), benchmark design, dataset shift, Goodhart's Law in ML |
| [behavioral-testing-and-red-teaming.md](behavioral-testing-and-red-teaming.md) | CheckList (MFT/INV/DIR), HELM, behavioral slicing, red-team methodology, prompt injection taxonomy, adversarial NLP |

## Key themes

- Testing is the primary epistemology of software — it converts behavioral claims into evidence
- The oracle problem (knowing what correct output is) and Dijkstra's impossibility result are the bedrock constraints
- Test pyramid → trophy → honeycomb: no universally optimal shape; depends on architecture and confidence boundaries
- Formal verification sits at the limit case of static analysis; most valuable for safety-critical or highly stable code
- AI/ML evaluation extends classical testing with distribution-shift awareness, benchmark contamination concerns, and behavioral capability decomposition

## Cross-knowledge connections

- `knowledge/software-engineering/systems-architecture/` — design-for-testability is a core architectural concern
- `knowledge/cognitive-science/` — metacognition and calibration apply directly to test-coverage reasoning
- `knowledge/ai/` — ML evaluation methodology sits at the intersection of testing and AI
- `cognitive-metacognition-calibration-research (historical plan reference)` — mutation testing as a Dunning-Kruger diagnostic
