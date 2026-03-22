---
created: 2026-03-20
last_verified: '2026-03-21'
origin_session: core/memory/activity/2026/03/20/chat-003
source: agent-generated
topic: Reranking and two-stage retrieval — cross-encoder rerankers, cascade architecture,
  position bias
trust: medium
type: knowledge
---

# Reranking and Two-Stage Retrieval

## Lede

Retrieval quality has two dimensions: recall (are the right documents *in* the candidate set?) and precision (are the right documents *ranked first*?). Bi-encoder dense retrieval optimizes for recall at scale — it efficiently searches millions of documents for candidates that are semantically related to the query. Cross-encoder reranking optimizes for precision — it deeply evaluates a small candidate set by processing query and document jointly, attending across both simultaneously. The cascade architecture (bi-encoder retrieval → cross-encoder reranking) is now the dominant production retrieval pattern because it captures the accuracy of cross-encoding without the latency of applying it at full-index scale. Understanding *why* cross-encoders are dramatically more accurate, and the engineering constraints that govern cascade design, is essential for building high-quality RAG systems.

---

## Why Bi-Encoders Are Inaccurate at Top-1

In a bi-encoder, query and document are encoded *independently*:

$$\text{score}(q, d) = f_q(q) \cdot f_d(d)$$

where $f_q$ and $f_d$ are neural encoders (often the same model), and relevance is computed as dot-product or cosine similarity of the resulting fixed-size vectors.

**The fundamental limitation:** All information about $q$ is compressed into a single vector before it encounters $d$, and vice versa. The model cannot attend to specific tokens of $q$ when encoding $d$, or vice versa. Fine-grained relevance relationships are lost in the compression.

**Consequences:**
- Two documents that discuss the same topic as the query score similarly, even if one directly answers the question and the other merely mentions the topic in passing
- Lexical ambiguity affects ranking: a query about a "bank" (financial) may rank documents about riverbanks high if the embedding model conflates these senses in a context-free vector
- Multi-part queries (queries with compound constraints) are particularly affected: the vector must encode all constraints simultaneously, and a document satisfying only some of them may score nearly as high as one satisfying all

**Empirical gap:** On standard benchmarks (MS-MARCO, TREC-DL), bi-encoder MRR@10 is typically 33–38%, while cross-encoder reranking of the same candidate set achieves 40–44% — a 15–20% relative improvement in top-1 precision with no change to the candidate pool.

---

## Cross-Encoder Architecture

In a cross-encoder, query and document are concatenated and processed *jointly* in a single forward pass:

$$\text{score}(q, d) = g([q; \text{[SEP]}; d])$$

where $g$ is a single classification head on top of a transformer (typically BERT-base or RoBERTa) and the `[SEP]` token separates query from document text.

**What cross-attention enables:**
- Token $q_i$ in the query can attend to token $d_j$ in the document and vice versa
- The model can detect lexical match, semantic entailment, and query-specific relevance — not just topical similarity
- Multi-part query constraints can be checked explicitly: the model can "look at" each constraint in $q$ against each passage in $d$
- Entity resolution and coreference are possible within the combined sequence

**The precision gain is structural:** Cross-attention is the right inductive bias for relevance judgment. Bi-encoder architecture is a constrained approximation that scales but trades precision.

**Why not just use cross-encoders everywhere?** Indexing cost. A cross-encoder must process each (query, document) pair at query time — no precomputation. For a 5M document index with queries arriving at 1000 QPS, that is $5 \times 10^9$ cross-encoder forward passes per second. Infeasible.

---

## The Cascade Architecture

The two-stage cascade solves the cross-encoder scaling problem:

**Stage 1 — Recall:** Bi-encoder dense retrieval over the full index. Returns top-100 or top-1000 candidates. Fast: document embeddings are precomputed; query is embedded once; ANN search scales sub-linearly with index size. This stage must have *high recall* — the correct documents must be in the candidate set, even if not ranked first.

**Stage 2 — Precision:** Cross-encoder reranker over the candidate set. Processes (query, doc) pairs for each of the 100–1000 candidates. Re-ranks them by the cross-encoder's relevance scores. Returns top-5 or top-10. Slow per document but applied to a small set — manageable latency.

**Latency math (rough estimate):**
- Bi-encoder: 1 query embedding (~10ms) + ANN search over 5M docs (~20ms) = ~30ms
- Cross-encoder reranking of top-100 candidates: 100 × 5ms per pass = ~500ms total, parallelized across batches to ~50ms with a GPU

For production systems, the 100-candidate batch can be processed in parallel with batch size = 100 in a single forward pass. Actual latency for a BERT-base cross-encoder on 100 candidates is typically 50–150ms on GPU.

**The set-size trade-off:** A larger Stage 1 candidate set (retrieve top-1000 instead of top-100) gives Stage 2 more recall margin but increases reranking latency linearly. Most production systems use 100–200 as the Stage 1 size.

---

## Major Cross-Encoder Rerankers

**Cohere Rerank:** Production-grade API reranker. Models: rerank-english-v3.0, rerank-multilingual-v3.0. Accepts query + list of candidate texts; returns relevance scores. Ease of integration, multilingual support, and competitive accuracy make it the default recommendation for many RAG systems. API-based — no self-hosting required.

**BGE Reranker (BAAI):** Open-weight cross-encoder series (bge-reranker-base, bge-reranker-large, bge-reranker-v2-m3). Available on HuggingFace; deployable on-premise. Strong performance on BEIR benchmarks, especially for non-English retrieval (v2-m3 is multilingual). bge-reranker-v2-m3 achieves near-sota performance at a fraction of the cost of API-based solutions for high-volume applications.

**ColBERT (late interaction):** Technically not a standard cross-encoder but occupies a middle ground. ColBERT stores per-token embeddings (not a single vector) per document. Query tokens are encoded and compared to all candidate document token embeddings via MaxSim. Effectively cross-attention approximated via precomputed per-token embeddings. Faster than full cross-encoder; more expressive than bi-encoder. Used in Stanford's DSP framework (DSPY) for research and in some production systems. Storage cost is 10–30× higher than bi-encoder.

**MonoT5 / RankLLM:** Generative rerankers: feed the (query, document) pair to a generative model and ask it to generate "relevant" or "irrelevant" (or a relevance score). More expensive but leverages the reasoning capabilities of larger models. Competitive on hard relevance tasks but not widely used in production due to cost.

---

## Position Bias and the "Lost in the Middle" Problem

After reranking, the top-K results are inserted into the LLM's context for generation. The order within the context matters:

**Position bias (the "lost in the middle" problem, Liu et al. 2023):** LLMs exhibit significantly better recall of information placed at the *beginning* and *end* of long contexts than in the *middle*. In experiments with 10–20 documents in context, models reliably retrieved facts from documents 1–3 and documents 18–20, but had substantially degraded recall for documents in the middle of the context.

**Implications for retrieval:**
- Reranking improves the *ranking* quality but does not solve the position bias problem if all top-K results are blindly concatenated into context
- The highest-relevance document should appear first in context (not in the middle)
- Reverse ranking insertion (most relevant last) sometimes outperforms forward ranking due to the primacy-recency asymmetry of attention in specific model architectures
- Reducing context length (fewer documents) often improves generation quality more than adding more documents — even if the additional documents contain relevant information, they may not be attended to effectively

**Mitigation strategies:**
1. Insert the single most relevant document first, then pad with supporting context
2. Use the reranker to select a smaller subset (top-3 instead of top-10) and accept lower recall
3. Use a "smart" context packing algorithm that places different relevant facts at the boundaries of the context
4. For long-context models with demonstrated uniform attention (if/when they exist), this problem diminishes

---

## Hybrid Retrieval: BM25 + Dense + Reranking

Production systems rarely use purely dense retrieval. Hybrid retrieval combines:

**BM25 (sparse):** Exact-match term frequency scoring. Fast, interpretable, no model needed. Best at handling rare terms, proper nouns, technical identifiers, and code — things that embedding models may lump together with semantically similar but textually different terms.

**Dense (bi-encoder):** Semantic similarity. Best at handling paraphrase, synonyms, concept-level matching, and cross-lingual retrieval.

**Reciprocal Rank Fusion (RRF):** Standard method for combining ranked lists from multiple retrieval sources. For each document, sum the reciprocal of its rank in each source list:

$$\text{RRF}(d) = \sum_{r \in R} \frac{1}{k + \text{rank}_r(d)}$$

where $k$ is a constant (typically 60) controlling the influence of high-ranked documents. RRF is robust to score-scale differences between BM25 and dense models and has been shown to outperform linear score fusion in most evaluations.

**The full production pipeline:**
```
BM25 retrieval (top-100) ──┐
                           ├── RRF fusion (top-100) → Cross-encoder reranker (top-10) → LLM context
Dense retrieval (top-100) ─┘
```

This pipeline achieves better recall than either retrieval method alone (because different queries are better served by sparse vs. dense) and better precision than either method after reranking.

---

## Thresholds: When Not to Retrieve

A subtler reranking design decision: the reranker score can be used as a *retrieval threshold*, not just a ranking signal. If the highest-scoring candidate after reranking still scores below a threshold $\tau$, the system can:
- Return "no relevant document found" (rather than hallucinating from low-confidence context)
- Fall back to a web search (CRAG pattern)
- Route to the LLM's parametric memory with a "I don't have specific documents on this" preamble

Thresholding converts the retrieval system from an unconditional pipeline into a conditional one that can express calibrated confidence in retrieval quality. The reranker score is a better threshold signal than the bi-encoder similarity score, because cross-encoder scores are more aligned with human relevance judgments.

---

## See Also

- [rag-architecture.md](rag-architecture.md) — two-stage retrieval introduced; bi-encoder vs. cross-encoder overview; the standard production pipeline
- [agentic-rag-patterns.md](agentic-rag-patterns.md) — CRAG fallback mechanism; corrective retrieval after reranking failure
- [hyde-query-expansion.md](hyde-query-expansion.md) — query-side improvement complementary to reranking
- [late-chunking-contextual-embeddings.md](late-chunking-contextual-embeddings.md) — document representation improvement that feeds into Stage 1 retrieval quality
- [colpali-visual-document-retrieval.md](colpali-visual-document-retrieval.md) — late interaction (ColBERT-style MaxSim) applied to visual document retrieval