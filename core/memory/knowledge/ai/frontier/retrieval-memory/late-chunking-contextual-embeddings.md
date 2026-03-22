---
created: 2026-03-20
last_verified: '2026-03-21'
origin_session: core/memory/activity/2026/03/20/chat-003
source: agent-generated
topic: Late chunking — embedding full documents then pooling by chunk boundaries to
  preserve cross-chunk context
trust: medium
type: knowledge
---

# Late Chunking and Contextual Embeddings

## Lede

Standard RAG embeds each chunk independently, severing the context that precedes it. A chunk containing "he is considered the father of the field" is meaningless in isolation — "he" has no referent, "the field" is unspecified. The embedding model encodes this decontextualized fragment and the resulting vector is semantically impoverished. Late chunking (Günther et al., JinaAI 2024) inverts the sequence: encode the full document first (capturing cross-chunk context in every token's embedding), then pool token embeddings by chunk boundaries after the fact. The result is chunk-level embeddings that retain full-document context — a structural fix to one of RAG's most persistent failure modes.

---

## The Standard Pipeline and Its Problem

**Early chunking (the default):**
1. Split the document into chunks (e.g., 512-token windows with 50-token overlap)
2. Feed each chunk independently through the embedding model
3. Store one embedding vector per chunk

The problem is step 2: when embedding chunk $i$, the model has no access to chunks $i-1$, $i-2$, etc. Co-reference, long-range entity resolution, and discourse structure are all severed at chunk boundaries.

**What is lost:**
- **Pronoun resolution:** "He was awarded the prize in 1947" — the referent of "he" established five sentences earlier is absent
- **Entity continuity:** A document introduces "the Chalmers Institute of Technology" then refers to it as "the institute" — each chunk sees only its sub-string
- **Argument structure across chunks:** The conclusion of an argument may only be meaningful given premises stated two chunks before
- **Statistical summary:** The embedding of a decontextualized chunk carries lower mutual information with the surrounding document topic than if context were preserved

The standard mitigation is overlapping windows (include 50–100 tokens of the preceding chunk in each chunk's input). This handles the immediate boundary but does not help with cross-sentence references or long-range structure.

---

## Late Chunking: The Mechanism

Late chunking requires a **long-context embedding model** — one capable of reading the full (or nearly full) document in a single forward pass.

**Steps:**
1. **Full-document encoding:** Feed the entire document into a long-context transformer. Every token in the document is encoded with attention over the full document — each token's embedding reflects that token in the context of the entire text.
2. **Boundary pooling:** The chunk boundaries (the same positions that early chunking would have cut at) are applied *to the token-level output embeddings*. For each chunk boundary range $[s_i, e_i]$, the chunk embedding is computed by mean-pooling the token embeddings in that range:

$$\text{chunk}_i = \text{MeanPool}(h_{s_i}, h_{s_i+1}, \ldots, h_{e_i})$$

3. **Store pooled embeddings:** The resulting vectors are stored in the retrieval index, one per chunk — identical index structure to early chunking. The retrieval pipeline is unchanged.

The key insight: mean-pooling over contextually enriched token embeddings produces a better chunk representation than embedding the chunk independently, because each token's hidden state already contains global document context via attention.

---

## Why It Works: The Attention Mechanism

In a standard transformer, token $t_i$'s hidden state $h_i$ is:

$$h_i = \text{Attention}(t_i, t_1 \ldots t_n)$$

where $n$ is the full sequence length. When the full document is processed, $h_i$ attends over all tokens — "he" in sentence 20 attends to "Einstein" in sentence 1 and its embedding captures this co-reference relationship.

In early chunking, token $t_i$ only attends over the tokens in its chunk. "he" in an isolated chunk sees no referent; its embedding reflects only local co-occurrence patterns, not the global entity binding.

Late chunking reuses the full-context token embeddings produced by full-document encoding. The pooled chunk embedding thus inherits the cross-document attention from every token within it.

---

## Empirical Results (JinaAI 2024)

JinaAI evaluated late chunking using their jina-embeddings-v3-long model (8192-token context) against early chunking with the same model, on retrieval benchmarks including BEIR and a set of long-document retrieval tasks.

Key findings:
- Late chunking consistently outperforms early chunking on tasks where co-reference or long-range context matters
- Improvement is largest for documents with extensive pronoun use, entity chains, or cross-paragraph argument structure
- For short, self-contained documents (e.g., encyclopedia articles that pack entity definition and facts into a single paragraph), the gap is small — both methods can capture relevant context within the chunk
- On BEIR benchmarks with short query-document pairs, late chunking provides modest but consistent improvements on most datasets

**The gain scales with document length:** For short documents (< 256 tokens), early and late chunking are nearly equivalent. For long documents with many chunks, late chunking's advantage grows because the unresolved references accumulate.

---

## Requirements and Limitations

**Long-context embedding model required:** Early chunking lets you use any embedding model regardless of context length, since each chunk is embedded independently. Late chunking requires the model to process the entire document in a single forward pass. For a 50-page document (~25,000 tokens) this requires a 32K or 128K context embedding model — jina-embeddings-v3, BGE-M3, or similar. Standard models like `text-embedding-ada-002` (8191-token limit) cannot process most long documents end-to-end.

**Higher per-document inference cost:** One forward pass over 25,000 tokens is expensive. Early chunking amortizes cost across 50 small passes, but total FLOPs per token are similar; the practical difference is that long-context models have higher memory requirements and may require batching.

**Index structure unchanged:** Once embeddings are computed, the retrieval index and serving infrastructure are identical. The improvement is entirely at embeddings-generation time, not query time. This makes late chunking a drop-in improvement with no serving-side changes required.

**Not a panacea:** Late chunking does not fix retrieval if the query is poorly matched to any chunk semantics regardless of context, or if the embedding model fundamentally lacks vocabulary for the domain (technical, legal, code). It also does not help with ColPali's problem domain — visual and layout-structured documents still require image-level processing.

---

## Contextual Retrieval (Anthropic, 2024): A Related Approach

Anthropic's "Contextual Retrieval" is a complementary technique that addresses the same decontextualization problem via a different mechanism: use an LLM (Claude) to prepend a chunk-level context summary to each chunk *before* embedding it.

**Steps:**
1. For each chunk, send a prompt to Claude: "Given this document: {document}. Situate the following chunk in the context of the whole document: {chunk}."
2. Prepend the returned context sentence(s) to the chunk text
3. Embed the enriched chunk with any standard embedding model

**Contextual Retrieval vs. Late Chunking:**

| | Contextual Retrieval | Late Chunking |
|---|---|---|
| Context source | LLM-generated summary prepended | Full-document attention in encoder |
| Embedding model | Any (short-context works) | Must be long-context |
| Indexing cost | High (LLM call per chunk) | Medium (long forward pass per doc) |
| Interpretability | High (human-readable context) | Opaque (hidden states) |
| Handles tables/code | Dependent on LLM ability | Same as embedding model |

Both approaches work well; late chunking is a purely structural improvement (no LLM call at index time), while contextual retrieval uses a powerful LLM to inject explicit context but at significant API cost.

---

## Relation to Parent-Document Retrieval

Parent-document retrieval (described in the rag-architecture.md file) is another cross-chunk context strategy: retrieve fine-grained chunks for precision, but insert the parent document or section into context for completeness. It sidesteps the embedding quality problem by always inserting more context than the matched chunk.

Late chunking is a cleaner approach: it produces better chunk embeddings directly, without the retrieval-time duplication of inserting parent context. The two can also be combined: late chunking for better matching + parent insertion for richer generation context.

---

## See Also

- [rag-architecture.md](rag-architecture.md) — chunking strategies overview, parent-document retrieval, early chunking baseline
- [colpali-visual-document-retrieval.md](colpali-visual-document-retrieval.md) — alternative to chunking for visual/structured documents; image-patch-level embeddings
- [hyde-query-expansion.md](hyde-query-expansion.md) — addresses query-document asymmetry from the query side (vs. late chunking which improves document representations)
- [reranking-two-stage-retrieval.md](reranking-two-stage-retrieval.md) — second-stage reranking as a complementary quality improvement