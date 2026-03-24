---
source: agent-generated
origin_session: unknown
created: 2026-03-24
trust: medium
type: knowledge
domain: software-engineering
tags: [code-review, quality, ai-generated, testing, hallucination, verification]
related:
  - ai-assisted-development-workflows.md
  - ../testing/behavioral-testing-and-red-teaming.md
  - ../testing/ml-evaluation-methodology.md
---

# AI Code Review and Quality

How to verify AI-generated code, common failure modes to watch for, and strategies for maintaining code quality when working with AI assistants.

## 1. Common Failure Modes

AI-generated code fails in predictable ways. Knowing the failure taxonomy lets you focus review effort where it matters.

**Hallucinated APIs**: The model invents function signatures, method names, or configuration options that don't exist. Most common when working with newer library versions, niche packages, or when the model confuses similar APIs across frameworks. Example: generating `django.utils.functional.cached_classproperty` — plausible name, doesn't exist.

**Subtle logic errors**: The code looks correct on inspection but handles edge cases wrong. Off-by-one errors, incorrect null/empty handling, race conditions in async code, and wrong operator precedence. These pass cursory review because the overall structure is sound.

**Security blind spots**: AI readily generates code with SQL injection vectors (string interpolation in queries), XSS vulnerabilities (unescaped output), insecure defaults (debug mode enabled, CORS wildcard), and weak cryptographic choices. Models optimize for "code that works" not "code that's secure."

**Outdated patterns**: Training data includes years of deprecated API usage. The model may generate `componentWillMount` in React, `url()` patterns in Django 4+, or Python 2-era string formatting. Most likely with older or less popular frameworks.

**Over-engineering**: Given freedom, models tend to generate more abstraction than needed — unnecessary design patterns, premature generalization, wrapper classes that add indirection without value. The model optimizes for "looks professional" which sometimes conflicts with simplicity.

**Inconsistent style**: AI output may not match your codebase conventions — different import ordering, naming patterns, error handling approaches, or logging formats. This is solvable with good context but requires explicit attention.

## 2. Review Checklist for AI Output

When reviewing AI-generated code, check in this order:

1. **Does it compile/type-check?** Run `mypy`, `tsc`, or your language's type checker. Catches hallucinated APIs immediately.
2. **Does it handle the stated requirements?** Trace through the happy path manually. Does the code actually do what was asked?
3. **Edge cases**: What happens with empty input, null values, maximum sizes, concurrent access? AI often handles the happy path well but misses boundaries.
4. **Security**: Check for injection vectors, authentication/authorization gaps, data exposure. See OWASP Top 10 as a mental checklist.
5. **Error handling**: Does it fail gracefully? Are exceptions caught at the right level? Are error messages helpful for debugging?
6. **Performance**: Any N+1 queries, unbounded loops, missing pagination, or excessive memory allocation? AI-generated ORM code is particularly prone to N+1 patterns.
7. **Style consistency**: Does it match the existing codebase in naming, structure, and patterns? Check import ordering, docstring format, error handling conventions.

## 3. Testing AI-Generated Code

**Standard unit tests** are the minimum. If the AI generated the code, ask it to generate tests too — but review the tests independently, since AI-generated tests often test the implementation rather than the behavior (tautological testing).

**Property-based testing** (Hypothesis, fast-check) is particularly valuable for AI-generated code because it explores edge cases the model didn't consider. Define properties the code should satisfy and let the framework find counterexamples.

**Mutation testing** reveals whether your test suite actually catches bugs. If you can mutate the AI-generated code and tests still pass, the tests are too weak. Tools: `mutmut` (Python), Stryker (JS/TS).

**Boundary analysis**: Explicitly test at boundaries — empty collections, single elements, maximum values, unicode strings, concurrent calls. AI code most commonly fails at boundaries.

**Integration testing**: AI-generated code that passes unit tests may still fail in integration. Test the actual API endpoint, not just the handler function. Test with the real database if the code involves queries.

## 4. Hallucination Detection

**Type checking**: The fastest hallucination detector. If the model generates a call to `response.json_body` and the response object has no such attribute, `mypy` or `tsc` catches it instantly.

**Documentation cross-reference**: For any library API the model uses that you don't recognize, check the official docs. Takes 30 seconds and prevents hours of debugging.

**Compilation/import check**: Run the code. If it crashes on import, the model hallucinated a function or class name. This is a faster feedback loop than reading the code for correctness.

**Version checking**: When the model uses a library feature, verify it exists in the version you're using, not just in the latest release. Check changelogs if uncertain.

**Confidence calibration**: When the model says "this is the standard way to do X," verify independently. Models present hallucinated information with the same confidence as correct information.

## 5. Trust Calibration

**High trust** (lighter review): Well-established patterns the model has seen millions of times — standard CRUD operations, common data transformations, idiomatic test structures, configuration boilerplate.

**Medium trust** (normal review): Framework-specific code, API integrations, database queries, error handling logic. Check edge cases and verify API correctness.

**Low trust** (thorough review): Security-sensitive code, performance-critical paths, concurrency/async logic, code involving state machines or complex business rules. Verify line by line.

**Never trust without verification**: Cryptographic implementations, authentication/authorization logic, financial calculations, medical/safety-critical code.

## 6. CI/CD Integration

Build automated gates that catch AI-generated code issues before they merge:

- **Type checking**: `mypy --strict` (Python) or `tsc --noEmit` (TypeScript) — catches hallucinated APIs
- **Linting**: `ruff` or `eslint` with strict configs — catches style inconsistencies and common errors
- **Test coverage**: Require minimum coverage for new code — ensures AI output actually has tests
- **Security scanning**: `bandit` (Python), `npm audit`, Semgrep rules — catches known vulnerability patterns
- **Import checking**: `isort --check` / import-sorted linting — catches phantom imports

The goal: make it harder for bad AI-generated code to reach production than to write it correctly in the first place.
