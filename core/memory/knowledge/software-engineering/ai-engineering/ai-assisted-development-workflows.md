---
source: agent-generated
origin_session: unknown
created: 2026-03-24
trust: medium
type: knowledge
domain: software-engineering
tags: [ai-assisted, workflow, delegation, pair-programming, code-generation, productivity]
related:
  - prompt-engineering-for-code.md
  - agent-configuration-and-tooling.md
  - ../../ai/tools/ai-tools-landscape-2026.md
  - ai-engineering-trajectory.md
---

# AI-Assisted Development Workflows

When to use AI, how to structure the interaction, and what actually makes you faster versus what just feels productive.

## 1. When to Delegate vs. Hand-Code

Not every task benefits from AI assistance. Use this heuristic:

**Delegate to AI** when:
- The task is well-defined with clear success criteria (CRUD endpoints, test scaffolding, data transformations)
- You need to work in an unfamiliar API or framework — the model knows the docs
- The task is repetitive across many files (migrations, renaming, adding logging)
- You need a first draft to react to rather than a blank page
- Debugging with a clear error message and stack trace

**Hand-code** when:
- The domain logic is novel and the model has no training examples
- Security-critical paths where subtle errors have outsized consequences
- Performance-sensitive hot paths requiring measurement-driven optimization
- You need to deeply understand the code for future maintenance (writing it yourself builds the mental model)

**Gray zone**: Architecture decisions, complex refactors, and design tradeoffs benefit from AI as a sounding board, but the human should drive the final decision.

## 2. Workflow Patterns

### Generate-Then-Edit
The most common pattern. Ask the model to generate a first draft, then manually edit to fit your codebase. Works well for boilerplate-heavy tasks. The key insight: treat AI output as a starting point, not a finished product.

### Spec-First Generation
Write a natural language specification first. Have the model confirm its understanding. Then generate implementation. The spec becomes documentation. This pattern catches misunderstandings before they become code and produces more coherent output for complex features.

### Test-Driven AI
1. Write the test (or have the model write it from a spec)
2. Verify the test captures the intended behavior
3. Ask the model to implement code that passes the test
4. Run the test — if it fails, give the model the failure output and iterate

This inverts the usual AI workflow and produces better-tested code. The test serves as an unambiguous specification.

### Scaffold-and-Refine
Ask for a complete scaffold of a feature (all files, all functions, empty implementations with type signatures). Review the structure. Then fill in implementations one function at a time. Good for large features where you want architectural control but don't want to wire everything by hand.

### Conversation Funneling
Start with a broad question ("How should I architect real-time notifications in Django+React?"), narrow to a design decision ("Should I use Channels or SSE for this use case?"), then implement ("Write the Django consumer and React hook"). Each step builds on verified understanding.

## 3. Pair Programming with AI

**Conversation management**: Keep one topic per conversation. When the context drifts, start a new session rather than trying to redirect. Long conversations accumulate stale context that degrades output quality.

**Maintaining context**: Periodically summarize what's been decided. "So far we've implemented X, Y, Z. The remaining task is W." This resets the model's attention to what matters now.

**Iterative deepening**: Don't try to get everything in one prompt. Ask for the high-level approach, validate it, then drill into each component. This mirrors how experienced developers think — architecture first, then details.

**When to restart**: If the model is stuck in a loop, producing variations of the same wrong answer, or has accumulated too much wrong context — restart with a fresh prompt that includes only the relevant code and the specific problem.

## 4. IDE Integration Patterns

**Inline completions** (Tab-complete): Best for boilerplate, predictable patterns, and finishing thoughts. Accept when it saves keystrokes; reject quickly and don't let wrong suggestions anchor your thinking.

**Chat-based**: Best for exploration, debugging, and generating larger code blocks. Include file context explicitly. Use for "how do I..." questions where you need explanation alongside code.

**Agent mode**: Best for multi-file changes, refactors, and well-specified features. Give clear specifications and let the agent plan its approach. Review the plan before letting it execute. Agent mode excels when the task can be broken into atomic, verifiable steps.

**Terminal agents**: Best for investigation tasks — "find all places where we handle authentication", "what's the call graph for this function?". They can run commands, read output, and iterate. Good for tasks that require exploring the codebase.

## 5. Task Decomposition for Agents

Agents perform best with:
- **Atomic tasks**: One clear objective per request ("add input validation to the registration endpoint")
- **Verifiable outcomes**: Tasks where success can be checked (tests pass, types check, linter is clean)
- **Bounded scope**: Changes to 1–5 files, not sweeping cross-codebase refactors
- **Clear context**: The relevant files and interfaces needed to complete the task

Break large features into a sequence of atomic tasks. Each task should build on the previous one and be independently verifiable. This gives you checkpoints to catch errors early.

## 6. Measuring Impact

**What actually speeds you up**: Boilerplate elimination, unfamiliar API exploration, test generation, debugging assistance, code review as a second pair of eyes.

**What feels productive but isn't always**: Generating code you then spend equal time understanding and debugging. Over-engineering simple tasks with AI-generated abstractions. Using AI for tasks where a shell script or snippet would suffice.

**Honest measurement**: Track time from task start to merged PR, not time from prompt to generated code. Include review, testing, and debugging of AI output. Compare against tasks you did manually to calibrate your intuition.
