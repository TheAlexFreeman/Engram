---
source: agent-generated
origin_session: unknown
created: 2026-03-24
trust: medium
type: knowledge
domain: software-engineering
tags: [prompt-engineering, llm, coding, few-shot, chain-of-thought, system-prompts]
related:
  - ../../ai/frontier/multi-agent/agent-architecture-patterns.md
  - ai-code-review-and-quality.md
  - context-window-management.md
---

# Prompt Engineering for Code

Practical patterns for getting high-quality code output from LLMs — what works, what doesn't, and why.

## 1. Structured Prompting Patterns

**Zero-shot** is the baseline: describe the task, get output. Works well for common patterns (CRUD endpoints, unit tests, data transformations) where the model has seen thousands of examples in training.

**Few-shot** provides 1–3 examples of input→output pairs before the actual request. Most useful when you need a specific output format, naming convention, or style the model wouldn't default to. Keep examples minimal — one good example beats three mediocre ones.

**Chain-of-thought (CoT)** asks the model to reason step-by-step before producing code. Effective for algorithmic problems, complex refactors, and architecture decisions. The phrase "think step by step" or "reason through the approach before writing code" triggers more deliberate output. For complex problems, explicitly ask for a plan first, then implementation.

**Self-consistency** generates multiple approaches and selects the best. In practice: ask for 2–3 alternative implementations, then ask the model to compare tradeoffs. Useful for design decisions where there's no single correct answer.

## 2. System Prompt Design

System prompts set persistent context for the entire conversation. Effective elements:

- **Role framing**: "You are an expert Django/React developer" — narrows the solution space to relevant patterns
- **Constraint specification**: "Use only standard library functions", "Target Python 3.12+", "Follow our existing patterns in src/utils/"
- **Output format control**: "Return only the modified function, no explanation", "Include type annotations", "Write the test first, then the implementation"
- **Negative constraints**: "Do not use any deprecated APIs", "Never use `any` type in TypeScript" — models respond well to explicit exclusions

Keep system prompts under ~500 words. Front-load the most important constraints — models weight earlier instructions more heavily.

## 3. Code-Specific Patterns

**Test-first prompting**: "Write failing tests for [feature], then write the implementation that makes them pass." Forces the model to think about expected behavior before writing code. Produces better edge case coverage.

**Iterative refinement**: Start broad ("scaffold a Django view for user registration"), then narrow ("add email verification", "handle the race condition where two users register simultaneously"). Each step builds on verified output.

**Rubber-duck debugging**: Paste the error, the relevant code, and ask "What's causing this and how do I fix it?" Include the full traceback — models are surprisingly good at diagnosing errors when they have the complete stack trace.

**Diff-style requests**: "Show me only the lines that change" or "Output a diff" — reduces noise when modifying existing code. Especially useful in agent mode where the tool will apply edits.

**Spec-to-implementation**: Write a natural language spec first, get the model to confirm understanding, then ask for implementation. The confirmation step catches misunderstandings before they become code.

## 4. Context Loading Strategies

What you include in the prompt matters more than how you phrase the request:

- **Relevant code**: Include the file being modified, plus key interfaces/types it depends on. Don't dump the entire codebase.
- **Error context**: Full stack traces, not just the error message. Include the command that triggered it.
- **Architecture context**: A 3–5 line description of the system architecture helps the model make appropriate design choices.
- **Existing patterns**: Show one example of how similar code looks in your project. The model will match the style.
- **Constraints from dependencies**: Version numbers matter — "Django 6.0" vs. "Django 4.2" changes which APIs are available.

Prioritize specificity over volume. A 50-line focused context outperforms a 500-line dump.

## 5. Anti-Patterns

**Vague prompts**: "Make this code better" produces generic refactoring. Specify what "better" means — faster, more readable, more testable, handles edge case X.

**Over-constraining**: Specifying every implementation detail defeats the purpose. Give the model room to choose approach — constrain the outcome, not the path.

**Ignoring model strengths**: Don't ask for rote boilerplate (use snippets/templates instead). Do ask for complex logic, unfamiliar APIs, test generation, and code review.

**Prompt injection in user-facing apps**: If LLM output is shown to users or if user input feeds into prompts, sanitize inputs and use structured output parsing. Never concatenate untrusted input directly into system prompts.

**Anchoring on first output**: The first generation isn't always best. If the output feels wrong, rephrase rather than trying to patch. A fresh prompt with better context usually beats iterative correction of a bad start.

## 6. Model-Specific Tips

**Claude (Sonnet/Opus)**: Extended thinking mode excels at complex multi-step reasoning. Best results when you describe the problem fully and let it plan. Responds well to explicit constraint lists. Strong at maintaining consistency across long conversations.

**GPT o-series (o1, o3)**: Reasoning-optimized models benefit from problems stated as puzzles — "given these constraints, find the approach that..." Less benefit from chain-of-thought prompting (they do it internally). Excellent for algorithmic problems and optimization.

**Open-weight models (Llama, Mistral, Qwen)**: More sensitive to prompt formatting. Few-shot examples help more than with frontier models. Keep prompts shorter — smaller context windows and weaker long-range attention. Best for well-defined, bounded tasks.

**General principle**: Models improve fastest at tasks where you can clearly specify success criteria. Invest prompt effort proportional to task ambiguity.
