---
created: 2026-03-20
last_verified: '2026-03-21'
origin_session: core/memory/activity/2026/03/20/chat-003
source: agent-generated
topic: Agentic RAG — multi-step retrieval patterns, query decomposition, FLARE, corrective
  RAG, RAGAS evaluation
trust: medium
type: knowledge
---

# Agentic RAG Patterns

## Lede

Standard RAG is a single-shot pipeline: retrieve-then-generate, once. This works when the query directly indexes the needed knowledge, the relevant content is concentrated in one or two passages, and the generation step does not require iterative reasoning. Real queries rarely satisfy all three conditions. Agentic RAG replaces the fixed retrieve-then-generate pipeline with retrieval as a *tool* the agent calls iteratively, adaptively, and reflectively — querying for what it doesn't know, verifying what it retrieved, and reformulating based on what it found. This document covers the major agentic RAG patterns, their underlying mechanisms, and the evaluation frameworks (RAGAS) that make quality measurement tractable.

---

## Why Single-Shot RAG Fails Complex Queries

**Multi-hop queries:** "Which company acquired the firm that published the Transformer paper?" requires:
1. Retrieve: what firm published the Transformer paper? → Google (Google Brain)
2. Retrieve (second query): what company acquired Google Brain? → the question is malformed; Google Brain was reorganized, but the first hop already resolves to Google (Alphabet)

A single-shot RAG system that embeds the full query retrieves documents about transformers or acquisitions generically, not the specific chain of facts needed. Multi-hop questions require chained retrieval where each hop's result informs the next query.

**Insufficient first retrieval:** The top-K chunks from a single retrieval may not include everything needed for a correct answer. The agent cannot know a priori which query formulation is optimal. Iterative retrieval allows recovery from an insufficient first pass.

**Knowledge gap detection:** The model should recognize when it lacks sufficient information to answer confidently and retrieve more, rather than hallucinating. Standard RAG has no mechanism for the model to signal or act on its own uncertainty.

**Query-document mismatch:** The query as phrased may not match documents well even if the answer exists in the index. Alternative phrasings, expanded terms, or decomposed sub-questions may retrieve better.

---

## Pattern 1: Query Decomposition

**Mechanism:** Before any retrieval, decompose the original complex query into a set of simpler sub-queries, each targeting a single atomic fact or concept. Retrieve for each sub-query independently. Synthesize all retrieved passages in context to answer the original query.

**Implementation:**
```
original: "Compare the training approaches of GPT-3, PaLM, and LLaMA 2, and explain what architectural differences account for their performance differences on reasoning tasks."

decomposed sub-queries:
  q1: "GPT-3 training data and objectives"
  q2: "PaLM training data and objectives"
  q3: "LLaMA 2 training data and objectives"
  q4: "GPT-3 architecture — key parameters and design choices"
  q5: "PaLM architecture — key parameters and design choices"
  q6: "LLaMA 2 architecture — Grouped Query Attention, RoPE, SwiGLU"
  q7: "reasoning benchmark performance comparison GPT-3 PaLM LLaMA"
```

The retrieval for each sub-query is simpler and more precise than retrieval for the compound original query. The synthesis step is then a reasoning task over richer, more relevant context.

**Trade-offs:**
- N sub-queries → N retrieval calls → N × latency (mitigated by parallelizing retrieval)
- Decomposition quality depends on the LLM's ability to parse the query structure
- Risk of over-decomposition: "What is the capital of France?" → ["What country is France in?", "What is France's capital city?"] adds no value

---

## Pattern 2: Iterative Retrieval and Refinement

**Mechanism:** Retrieve an initial set of passages. Attempt partial generation or intermediate reasoning. Use the output to assess what is missing or still needed. Formulate a follow-up retrieval query. Repeat until the answer is complete or a confidence threshold is reached.

**The FLARE algorithm (Jiang et al. 2023):** Forward-Looking Active REtrieval. FLARE's insight: retrieval should be triggered not at the start of generation, but at the moment the model is about to generate text it is uncertain about.

**FLARE mechanism:**
1. The model generates text token-by-token with probabilities.
2. When the model's token probability drops below a threshold (signaling low confidence), the current generation is paused.
3. The model's current position in the generation is used to formulate a retrieval query: the model generates a hypothetical "next sentence" probe — what does it *expect* to say next? This probe is used as the retrieval query.
4. Retrieved passages are inserted into the context.
5. Generation continues from the uncertain position, now conditioned on the retrieved evidence.

**Why FLARE is architecturally interesting:** It conditions retrieval on the model's own uncertainty signal, avoiding retrieving when the model is confident and targeting retrieval precisely at points of hallucination risk. The hypothetical probe technique (generating an expected next sentence to use as a query) is also related to HyDE but applied iteratively during generation.

**Trade-offs:**
- Requires access to token-level probabilities (not available via all APIs; available via logprobs in OpenAI API)
- Generation must be pauseable and resumable mid-sequence (requires careful implementation in streaming contexts)
- The threshold parameter requires calibration

---

## Pattern 3: Self-Querying Retrieval (Metadata Filtering)

**Mechanism:** The LLM is given a description of the index schema — what metadata fields are available (date, author, document type, topic tag, source) — and is asked to parse the user query into two components: a semantic search query and a structured metadata filter. The retrieval system applies both.

**Example:**
```
user query: "What were the main findings of Apple's iPhone launch press release from June 2012?"

LLM output:
  semantic_query: "iPhone launch main findings announcements"
  metadata_filter: {
    organization: "Apple",
    document_type: "press release",
    date_range: { gte: "2012-06-01", lte: "2012-06-30" }
  }
```

**Why this matters:** Vector similarity alone cannot handle constraints that are not semantically encoded in the content. If 1000 documents are semantically similar to "iPhone launch findings," date and source filtering reduces the candidate set to 1–3 documents. Without self-querying, the model either retrieves wrong-year documents or requires a post-retrieval filtering step that may not scale.

**Implementation:** LangChain's `SelfQueryRetriever` is a standard implementation. The LLM is given a Pydantic schema describing the available metadata; it returns a structured query object that the retrieval layer passes to its filter expression evaluator.

---

## Pattern 4: Corrective RAG (CRAG)

**Mechanism (Yan et al. 2024):** After retrieval, an LLM-based evaluator (or the same LLM) assesses the quality and relevance of each retrieved document:
- **Correct:** Retrieved document is relevant and accurate — use directly
- **Incorrect:** Retrieved document is irrelevant or contradicts the query — discard; fall back to web search or a broader index
- **Ambiguous:** Retrieved document is partially relevant — decompose it, extract the relevant portion, combine with additional retrieval

The key addition over standard RAG: a **web search fallback**. If the local index fails to return correct documents, CRAG falls back to web search (e.g., SerpAPI or Brave Search) to expand the source pool. This transforms RAG from a closed-book system to a hybrid retrieval system with graceful fallback.

**CRAG in practice:**
```
retrieve from index → evaluate relevance → 
  if correct: proceed to generation
  if incorrect: trigger web search → retrieve from web → evaluate → proceed
  if ambiguous: extract and supplement → proceed
```

**When it's valuable:** CRAG targets the false-negative problem in RAG — the correct answer exists somewhere but the index doesn't have it (outdated, incomplete, or narrowly scoped). By adding a fallback, CRAG dramatically reduces the "I couldn't find relevant information" failure mode.

---

## Pattern 5: SELF-RAG

**Mechanism (Asai et al. 2023):** Unlike FLARE (which uses token probability as the signal to retrieve), SELF-RAG trains the model to output *reflection tokens* — special tokens interspersed in generation that indicate:
- `[Retrieve]` — should the model retrieve before continuing?
- `[IsRel]` — is this retrieved passage relevant to the query?
- `[IsSup]` — does the retrieved passage support the generated statement?
- `[IsUse]` — is the generated response useful overall?

**The training objective:** The base LLM is fine-tuned to both generate these reflection tokens and to use them to decide whether and how to retrieve. A critic model is trained separately to generate silver labels for the reflection tokens, which are used to train the main model.

**What this achieves:**
- Retrieval is not always triggered — the model may answer from parametric memory when confident
- When retrieval is triggered, the model evaluates retrieved evidence and can reject irrelevant passages
- The model generates self-critiques of its own output (IsSup, IsUse), enabling selective hallucination-bounding

**Trade-off:** Requires fine-tuning, not prompt-engineering. The reflection token vocabulary is specialized to the training setup. SELF-RAG improves faithfulness and reduces hallucination on long-form generation tasks significantly, with smaller gains on simple factual retrieval.

---

## Pattern 6: Multi-Step Research Agents

**The full agentic pattern** combines all of the above into a research agent:

1. **Plan:** Decompose the query into a research plan (list of questions to answer)
2. **Retrieve:** For each research question, retrieve from an index
3. **Evaluate:** Assess the quality of each retrieval result; flag insufficient results
4. **Web search fallback (CRAG):** For flagged items, search the web
5. **Synthesize:** Integrate all gathered evidence
6. **Refine:** Identify remaining gaps; formulate follow-up queries; repeat if needed
7. **Generate:** Produce final answer with citations

Implementations: OpenAI Deep Research, Perplexity Research Mode, LangGraph research workflows, LlamaIndex Research Agent.

**The latency vs. quality trade-off is fundamental.** A 7-step research loop with 3 retrieval queries per step and 1 web search fallback can take 30–90 seconds. For many use cases this is unacceptable. The practical design question is always: which subset of agentic patterns provides the most quality gain per unit of latency cost?

---

## RAGAS: Evaluating RAG Systems

Single-shot RAG is easy to evaluate: does the answer match the ground truth? Agentic RAG is harder: each step can fail, and failures interact. RAGAS (RAG Assessment) provides a framework of component metrics.

**Core RAGAS metrics:**

| Metric | What it measures |
|---|---|
| **Faithfulness** | Are all claims in the answer supported by the retrieved context? Score = (claims supported / total claims). Hallucination detection. |
| **Answer Relevance** | Does the answer address the original question? Low score = correct facts but wrong topic. Measured by embedding similarity of generated question questions → query. |
| **Context Precision** | Of the retrieved contexts, what fraction is actually relevant to the answer? High precision = focused retrieval; low precision = too many noisy chunks retrieved. |
| **Context Recall** | Of the ground-truth answer's facts, what fraction are covered in the retrieved contexts? High recall = the information needed is present; low recall = retrieval failure. |

**Why RAGAS metrics are useful:**
- **Faithfulness** catches hallucination rather than just comparing to a ground truth answer (which requires labeled data)
- **Context Precision** diagnoses noisy retrieval (top-K is too large, reranking insufficient)
- **Context Recall** diagnoses retrieval failure (the right document was not retrieved)
- Separating these metrics enables targeted debugging: low recall → better embedding model or more documents; low precision → better reranking; low faithfulness → better prompt or generation model

**LLM-as-judge for RAGAS:** Because faithfulness requires decomposing a generated answer into claims and checking each claim against retrieved contexts — a structured reasoning task — RAGAS uses an LLM (typically GPT-4) as the judge. This enables evaluation at scale without human annotations, but introduces the LLM's own biases and error rates.

**Testset generation:** RAGAS also provides tools to generate evaluation testsets from a knowledge base (using an LLM to create question-answer pairs), enabling evaluation without pre-existing labeled benchmarks.

---

## See Also

- [rag-architecture.md](rag-architecture.md) — foundational single-shot RAG architecture; retrieval methods; agentic RAG overview
- [hyde-query-expansion.md](hyde-query-expansion.md) — query expansion at retrieval time; hypothetical document probe (related to FLARE's probe mechanism)
- [reranking-two-stage-retrieval.md](reranking-two-stage-retrieval.md) — second-stage relevance scoring applied before synthesis
- [agent-architecture-patterns.md](../multi-agent/agent-architecture-patterns.md) — broader agent design patterns; tool-use, planning, reflection loops
- [agentic-frameworks.md](../agentic-frameworks.md) — LangGraph, LlamaIndex, CrewAI — implementation frameworks for these patterns