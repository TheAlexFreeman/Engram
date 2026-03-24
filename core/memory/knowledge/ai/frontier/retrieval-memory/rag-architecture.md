---
created: 2026-03-19
last_verified: '2026-03-21'
origin_session: core/memory/activity/2026/03/19/chat-001
source: external-research
topic: RAG — retrieval-augmented generation architecture and failure modes
trust: medium
type: knowledge
related: agentic-rag-patterns.md, long-context-architecture.md, ../multi-agent/agent-architecture-patterns.md
---

# RAG Architecture: When It Works and When It Doesn't

## Lede

Retrieval-Augmented Generation connects to the four threads as follows: the capability thread (RAG was the dominant way to extend LLMs beyond their training cutoff before long-context became practical), the memory thread (RAG is effectively external episodic memory for LLMs — the core technique underlying any nontrivial persistent memory system), the scaling thread (RAG delays the need for larger context windows or retraining by outsourcing factual storage to retrieval indices), and the agent-design thread (agentic RAG is a case study in how tool use and reasoning combine). This repo uses git-backed structured memory as an alternative to vector-store RAG, and understanding RAG's failure modes directly explains the design decisions that led here.

---

## Core Architecture

A RAG system has three logical stages:
1. **Indexing:** Documents are chunked, embedded into vectors, and stored in a vector index
2. **Retrieval:** At query time, the query is embedded and the index is searched for similar chunks
3. **Generation:** Retrieved chunks are concatenated into the LLM context along with the query; the LLM generates a response conditioned on both

### Retrieval Methods

**Sparse retrieval (BM25, TF-IDF):** Term-frequency based matching. Fast, no model required, handles exact term matches well. Fails on semantic similarity: "automobile" and "car" are unrelated in sparse space.

**Dense retrieval (bi-encoder):** Both query and document are embedded by neural models into the same vector space. Similarity is cosine or dot-product. Captures semantic similarity. The query and document encoders are usually the same model (bi-encoder architecture, e.g., FAISS + sentence-transformers). Faster than cross-encoder at retrieval time because document embeddings are precomputed.

**Cross-encoder (reranker):** The query and candidate document are processed jointly by a single encoder that attends across both simultaneously. Much more accurate than bi-encoder for relevance judgments (the model can compare them directly), but requires a separate forward pass for each (query, document) pair — too slow to apply at full index scale.

**The standard production pipeline:**
1. BM25 or bi-encoder retrieves a large candidate set (top-100)
2. Cross-encoder reranker scores and re-orders the candidates
3. Top-K reranked results go into the LLM context

The two-stage pipeline captures most of the accuracy benefits of cross-encoding without the latency of applying it at full index scale.

---

## Chunking Strategies

The chunking decision is often underestimated. How you split documents determines the quality of retrieved units.

**Fixed-size chunking:** Split on character count (e.g., 512 characters, 50-character overlap). Simple and predictable. Breaks semantic units arbitrarily — a chunk may cut mid-sentence or mid-argument.

**Sentence-window chunking:** Split on sentence boundaries. Retrieves more coherent units but sentence length varies widely; short sentences are sparse in signal density.

**Semantic chunking:** Use embedding similarity between consecutive sentences to detect topic shifts; only split when semantic similarity drops below a threshold. Better coherence but computationally expensive to build.

**Parent-document retrieval:** Store "parent" documents or large sections alongside fine-grained child chunks. The index retrieves fine-grained chunks (better precision for matching) but inserts the parent document or section into context (better context for generation). Requires extra complexity in the retrieval pipeline.

**Implications for this repo:** Git-backed structured memory avoids the chunking problem by design — knowledge files are intentionally written at a single-topic granularity, with explicit frontmatter metadata. The retrieval unit is identical to the storage unit, eliminating the coherence-loss problem of chunking longer documents.

---

## Embedding Quality

The quality of dense retrieval is dominated by the quality of embedding representations.

**What makes a good retrieval embedding:**
- Semantic similarity is preserved independently of surface form ("car" ≈ "automobile")
- Meaning is preserved across domains (medical terminology, legal language, code)
- The query embedding space and document embedding space are well-aligned (bi-encoders are trained for this)
- Out-of-domain generalization: a model trained on Wikipedia retrieval should still work on internal company documentation

**What makes a bad embedding:**
- Embedding models trained on one distribution poorly represent out-of-distribution content (code, highly technical material, non-English text)
- Short document embeddings are noisy — there is not enough content to establish strong meaning
- The embedding model may conflate related but distinct concepts (financial "capital" vs. city "capital")

**HyDE (Hypothetical Document Embeddings):** A query-expansion technique for addressing the query-document asymmetry: queries are short (sparse signal), documents are long (dense signal). HyDE uses the LLM to generate a hypothetical document that would answer the query, then embeds that hypothetical document and retrieves actual documents similar to it. This brings the query into the same representational regime as the documents. Works well for knowledge-dense retrieval tasks; adds LLM latency to the retrieval step.

---

## The RAG vs. Long-Context Decision

As context windows have grown (from 4K → 32K → 128K → 1M+ tokens), the calculus of when to use RAG vs. when to just put everything in context has shifted dramatically.

**When RAG beats long-context:**
- Knowledge base is larger than any feasible context window
- Most retrieval is from a large corpus and only a few documents are needed per query
- Retrieval latency is not a bottleneck; embedding precomputation amortizes cost
- The relevant information is clearly identifiable by content (good retrieval precision possible)
- The corpus changes frequently (re-indexing is easier than re-injecting into a fixed context)

**When long-context beats RAG:**
- The task requires integrating information from many parts of a document (reading comprehension over a full book)
- The retrieval precision problem is hard (unclear what is relevant, many false negatives in retrieval)
- The corpus is small and stable (just load it all in)
- Retrieval infrastructure is unavailable or expensive to maintain

**The "lost in the middle" problem (Liu et al. 2023):** LLMs attend better to information at the beginning and end of long contexts than in the middle. For a 128K context, information inserted at positions 40K–90K is retrieved with significantly lower accuracy than information at positions 0–20K or 100K–128K. This means naive long-context injection does not eliminate the retrieval problem — it just pushes it into a different form. Relevant content still needs to be placed where the model can attend to it effectively.

**Practical implication:** For most real retrieval workloads in 2025, the hybrid approach is dominant: use RAG to identify C candidates, fetch the top 5–10, and insert them at the beginning/end of context. Pure long-context is practical only when the corpus is small enough and query patterns are complex enough that retrieval precision is structurally low.

---

## Agentic RAG

Standard RAG is a single retrieval-then-generate step. Agentic RAG treats retrieval as a tool the agent can call multiple times, with each retrieval step informed by the results of prior steps.

**Query decomposition:** The agent decomposes a complex query into sub-queries, retrieves for each, integrates results, then generates. Better for multi-hop questions ("Who is the CEO of the company that makes Claude?" requires first finding "what company makes Claude" then "who is the company's CEO").

**Iterative retrieval:** After an initial retrieval and generation step, the agent evaluates whether the retrieved information is sufficient. If not, it formulates a follow-up retrieval query (possibly reformulated based on what it learned). Continues until a confidence threshold is met.

**Self-reflective RAG (SELF-RAG):** The model is trained to output special tokens indicating when to retrieve, how to evaluate retrieval results, and when the generated answer is supported by citations. Retrieval is not always triggered — it is model-controlled based on perceived need.

**Challenges of agentic RAG:**
- Multi-step retrieval compounds latency
- Error propagation: a bad first retrieval step leads to a bad reformulated query leads to further errors
- Evaluation is harder: partial credit is harder to measure than binary correctness
- Cost: each retrieval step calls an embedding model and vector search; multiple steps multiply cost

---

## Failure Modes

**Retrieval failure (false negatives):** The most relevant document is not retrieved because:
- The query phrasing and document phrasing use different vocabulary
- The embedding model poorly represents the domain
- The chunking strategy broke the relevant passage across chunk boundaries

**Hallucination with retrieval:** RAG reduces but does not eliminate hallucination. The model may:
- Ignore the retrieved content and generate from priors
- Misinterpret retrieved content that is accurate but not precisely answerable
- Combine retrieved content and parametric knowledge in ways that generate inaccurate claims

**Retrieval pollution:** Retrieved content that is topically related but factually misleading contaminates the context. The model may incorporate this "authoritative" (retrieved) content even when it is wrong or outdated.

**Context length pressure:** Injecting many retrieved documents can push other important context out of the window (system prompt, conversation history, tools). The information budget requires tradeoffs.

**Repo-relevant note:** This system's git-backed markdown approach avoids retrieval pollution by maintaining explicit trust metadata (`trust:` frontmatter field) and human-review gating. Vector stores lack native support for trust levels on retrieved content.

---

## Open Questions

- **Embedding model training for private corpora:** General-purpose embeddings underperform on specialized corpora. Domain fine-tuning of embedding models is understudied.
- **Optimal chunk size:** Theory suggests the optimal chunk size should match the precision of retrieval queries. This is task-dependent and not well-characterized.
- **Evaluating RAG:** RAGAS and similar frameworks exist but rely on LLM-as-judge, which has its own biases. Ground-truth annotated RAG benchmarks are scarce.
- **Retrieval compression:** In long-context settings, can retrieved content be compressed (summarized) before injection without losing the information needed for generation? Initial work is mixed.
- **Online RAG:** For corpora that update in real time (news, live databases), how do you avoid latency between index update and retrieval availability?

---

## Key Sources

- Lewis et al. 2020 — "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks" (original RAG paper)
- Karpukhin et al. 2020 — "Dense Passage Retrieval for Open-Domain Question Answering"
- Liu et al. 2023 — "Lost in the Middle: How Language Models Use Long Contexts"
- Gao et al. 2023 — "Retrieval Augmented Generation for Large Language Models: A Survey"
- Asai et al. 2023 — "Self-RAG: Learning to Retrieve, Generate, and Critique through Self-Reflection"
- Gao et al. 2022 — "Precise Zero-Shot Dense Retrieval without Relevance Labels" (HyDE)
- Robertson and Zaragoza 2009 — "The Probabilistic Relevance Framework: BM25 and Beyond"