---
created: 2026-03-20
last_verified: '2026-03-21'
origin_session: core/memory/activity/2026/03/20/chat-003
source: agent-generated
topic: HyDE — Hypothetical Document Embeddings; query expansion via LLM-generated
  hypothetical answers
trust: medium
type: knowledge
---

# HyDE: Hypothetical Document Embeddings

## Lede

Dense retrieval embeds both queries and documents into the same vector space by training a bi-encoder model on (query, relevant document) pairs. But queries and documents are structurally asymmetric: a query is short, interrogative, and rich in what it *wants to know*, while a document is longer, declarative, and rich in what it *says*. A query like "What causes aurora borealis?" is lexically and structurally far from the document passage that answers it ("Auroral light is produced when energetic electrons from the solar wind precipitate into the upper atmosphere and collide with oxygen and nitrogen atoms..."). HyDE (Hypothetical Document Embeddings, Gao et al. 2022) bridges this gap by using an LLM to generate a *hypothetical document* that would answer the query, then retrieving real documents similar to that hypothesis rather than to the query itself.

---

## The Query-Document Asymmetry Problem

Bi-encoder retrieval works well when the training distribution is similar to the query distribution. Training pairs look like: (query: "quantum entanglement definition", document: "Quantum entanglement is..."). At inference time, a query phrased similarly will embed close to relevant documents.

The asymmetry breaks down in several cases:

**Knowledge-dense queries:** "Who first proposed the holographic principle in physics?" is a natural language question; relevant documents are academic papers, encyclopedia entries, and textbook passages — all declarative in style, none of which say "who first proposed." A query trained to retrieve Wikipedia-style documents may not embed close to physics papers.

**Cross-lingual or cross-style queries:** Even within English, the register of a casual question is far from the register of a technical document. A user query in informal language ("why does ice float?") embedding close to a physical chemistry textbook passage requires strong cross-style generalization.

**Low-resource or novel domains:** For domains underrepresented in embedding model training (rare languages, niche technical fields, legal subcategories), the query embedding space and document embedding space may not be well-aligned because the model has seen few training pairs from those domains.

**The geometry:** In the embedding space, query embeddings and document embeddings form partially non-overlapping clusters. The documents that *should* be retrieved after a query are close to answer-style text, not question-style text.

---

## The HyDE Mechanism

**Algorithm:**

1. **Hypothetical document generation:** Given a query $q$, prompt the LLM to generate a hypothetical document $\hat{d}$ that would answer the query. No retrieval is needed at this step; the LLM generates from parametric memory.

   *Prompt template:*
   ```
   Write a passage that answers the following query:
   Query: {query}
   Passage:
   ```

2. **Embed the hypothesis:** Compute the embedding of $\hat{d}$ using the same dense embedding model as documents: $e(\hat{d})$.

3. **Retrieve by hypothesis:** Search the document index for real documents closest to $e(\hat{d})$ (not $e(q)$). Return the top-K real results.

4. **Generate:** Feed the query and retrieved real documents to the LLM for final answer generation.

**Why this works geometrically:** The hypothetical document $\hat{d}$ is in the same stylistic register as real indexed documents — it is declarative, factual-sounding, and of similar length. Its embedding $e(\hat{d})$ therefore sits in the same region of vector space as real relevant documents, producing a better retrieval signal than the question embedding $e(q)$.

Even if the LLM's hypothetical document contains factual errors (which it often does — the LLM generates from memory without access to the ground truth), the *embedding* of the hypothesis may still be close to correct documents. A hallucinated but plausible document about the aurora borealis will embed close to real aurora borealis documents even if the specific mechanism described is wrong.

---

## Formal Perspective

Let $f$ be the bi-encoder embedding function. The standard bi-encoder retrieval score is:

$$\text{score}(q, d) = f(q) \cdot f(d)$$

HyDE replaces $f(q)$ with $f(\hat{d})$ where $\hat{d} \sim p_\text{LLM}(\cdot \mid q)$ is an LLM sample conditioned on the query:

$$\text{score}_\text{HyDE}(q, d) = f(\hat{d}) \cdot f(d)$$

In the paper, the authors further suggest sampling *multiple* hypothetical documents from the LLM and averaging their embeddings, which reduces variance:

$$\text{score}_\text{HyDE}(q, d) = \left(\frac{1}{K}\sum_{k=1}^K f(\hat{d}_k)\right) \cdot f(d)$$

This ensemble over hypotheses is more expensive (K LLM calls) but more robust to the particular direction any single hallucination sends the embedding.

---

## Empirical Results

Gao et al. (2022) evaluated HyDE on BEIR (heterogeneous retrieval benchmark), including:
- MS-MARCO (passage retrieval)
- TREC-DL (deep learning track)
- BEIR subsets: SciFact, NQ, FEVER, HotpotQA, Arguana, DBPedia, TrecCovid

Key findings:
- HyDE significantly outperforms direct query embedding on zero-shot retrieval settings (when the embedding model is not fine-tuned on the specific domain)
- HyDE approaches or matches supervised fine-tuned bi-encoders on several BEIR datasets, despite requiring no training-time adaptation
- On tasks where query-document style difference is large (scientific papers, Wikipedia-grounded QA), HyDE gains are largest
- On tasks where query-document style difference is small (e.g., queries already sound like document passages), gains are modest

**Practical implication:** HyDE is most valuable as a zero-shot improvement when you cannot fine-tune an embedding model for your domain. For large commercial deployments with domain-specific training data, fine-tuning the bi-encoder directly may close the gap.

---

## Limitations and Failure Modes

**LLM latency:** HyDE adds one LLM inference call before retrieval. For a system where retrieval is latency-critical (< 500ms), an additional LLM call may be prohibitive. HyDE works better in research-assistant latency regimes (2–10 seconds acceptable).

**Amplified hallucinations leading retrieval astray:** If the LLM generates a hallucinated document in a strongly wrong direction — fabricating a plausible but domain-incorrect narrative — the embedding may point away from correct documents. The risk is highest for queries about obscure or adversarial topics. Ensembling (multiple hypotheses, average embeddings) reduces but does not eliminate this risk.

**Circular hallucination:** In a standard RAG pipeline, HyDE is applied at retrieval time; the LLM generates a hypothesis from parametric memory, retrieves real documents, then re-generates the actual answer from those documents. If the LLM has strongly wrong priors about the topic, the hypothesis may miss relevant documents, the LLM then generates a final answer from insufficient context and its own wrong priors, and the system reinforces the hallucination. This is the same failure mode as standard RAG with poor retrieval, amplified by the LLM's hypothesis contributing signal in the wrong direction.

**Not useful when parametric memory is empty:** If the LLM has no knowledge of the domain at all (highly specialized proprietary content), the generated hypothesis is purely random fluent text with no signal. In this case HyDE performs no better than direct query embedding, and may perform worse.

**Dependency on generation model quality:** HyDE's quality scales with the LLM's parametric memory coverage. GPT-4 hypotheses are better than GPT-3.5 hypotheses, because GPT-4 has better coverage of the domain and generates more plausible hypothetical answers. This means HyDE is not uniformly applicable — it requires a strong generation model.

---

## Relation to Other Techniques

**vs. Standard query expansion:** Classical query expansion (e.g., pseudo-relevance feedback — take the top-retrieved document, extract terms, re-query) is a related idea without an LLM. HyDE uses the LLM as the expansion oracle; it can generate relevant text even before any retrieval has been attempted.

**vs. FLARE:** FLARE uses a hypothetical probe (a generated "next sentence") as a retrieval trigger during generation. HyDE uses a full hypothetical document as the retrieval query before generation. Both use LLM generation as a proxy for retrieval, but at different points in the pipeline and for different reasons (FLARE: uncertainty-triggered at generation time; HyDE: query expansion before any generation).

**vs. Query rewriting:** Simple query rewriting (paraphrase the query, expand with synonyms) is structurally similar to HyDE but does not change the register — it still produces question-like text, not answer-like text. HyDE specifically targets the style asymmetry by generating answer-style text, not just a better query.

---

## See Also

- [rag-architecture.md](rag-architecture.md) — HyDE introduced briefly under "Embedding Quality"; foundational RAG architecture
- [agentic-rag-patterns.md](agentic-rag-patterns.md) — FLARE's hypothetical probe mechanism; iterative retrieval refinement
- [late-chunking-contextual-embeddings.md](late-chunking-contextual-embeddings.md) — complementary technique addressing document representation quality
- [reranking-two-stage-retrieval.md](reranking-two-stage-retrieval.md) — second-stage relevance scoring applied after initial dense retrieval