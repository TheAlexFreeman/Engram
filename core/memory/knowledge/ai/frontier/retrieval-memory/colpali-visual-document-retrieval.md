---
created: 2026-03-20
last_verified: '2026-03-21'
origin_session: core/memory/activity/2026/03/20/chat-003
source: agent-generated
topic: ColPali — visual document retrieval with vision-language models, bypassing
  OCR and text chunking
trust: medium
type: knowledge
---

# ColPali: Visual Document Retrieval

## Lede

Standard RAG pipelines treat document retrieval as a text problem: extract text (via OCR or PDF parsing), chunk it, embed the chunks, and search. This pipeline breaks catastrophically on documents where structure and visual layout carry meaning — tables, charts, infographics, multi-column layouts, technical diagrams, forms. ColPali (Contextualized Late Interaction for Page Images) is a retrieval architecture that bypasses text extraction entirely, embedding *page images* directly using a vision-language model. It represents a paradigm shift: documents are not read as text to be chunked, they are *seen* as images to be compared.

---

## The Problem ColPali Solves

Why does OCR-first retrieval fail on real-world documents?

**Layout loss:** OCR extracts a linear string of text from a document that may have columns, sidebars, tables, and captions arranged spatially. The reading order produced by OCR parsers rarely preserves the semantic structure a human reader would infer from layout — tables flatten into a stream of values without column headers in context, captions disconnected from their figures, multi-column text interleaved incorrectly.

**Visual-only information loss:** Charts, graphs, diagrams, and photographs contain information not representable as text at all. A production RAG system with OCR-first retrieval returns "No relevant text found" for queries that are clearly answerable by looking at a plot in the document.

**Formula and symbol degradation:** Mathematical notation, chemical structures, music notation, and code mixed with prose all degrade in OCR extraction. Symbols are mistranscribed or dropped; embedding models trained on natural language text cannot represent these degraded strings well.

**Table structure loss:** OCR may extract cell values but loses row/column relationships. A query like "What was the Q3 revenue growth for the Asia-Pacific segment?" requires reasoning over a table structure that OCR flattens.

**The conclusion:** For heterogeneous real-world document corpora (PDFs, scanned reports, slides, forms), the OCR-chunking pipeline is not merely imperfect — it systematically destroys the information most likely to be queried. ColPali's bet is that a vision encoder that *sees* the page avoids all of these problems simultaneously.

---

## Architecture

ColPali builds on two components:

**PaliGemma:** A vision-language model (Google, 2024) that combines a SigLIP vision encoder with a Gemma language decoder. SigLIP processes the input image into a sequence of patch embeddings (one per image patch, e.g., 64×64 pixel patches over a full page). PaliGemma can reason about images conditioned on text queries.

**Late interaction (inspired by ColBERT):** Rather than producing a single vector per document (as bi-encoder RAG does), ColPali produces a *sequence of patch-level embeddings* per page — one embedding per visual patch. Query matching uses the MaxSim operation: for each query token, find the maximum similarity across all document patch embeddings, then sum these per-token maxima. This is the same late interaction mechanism as ColBERT (for text) applied to image patches.

**Late interaction contrast with bi-encoder:**
- Bi-encoder RAG: `embed(query)` · `embed(document)` → single scalar (full doc compressed to fixed size)
- ColPali: `embed(query tokens)` and `embed(image patches)` → MaxSim → score (many-to-many, retains spatial richness)

Late interaction preserves spatial locality: a query about a specific region of a figure is matched to the patches from that region, not averaged across the whole page.

### Indexing

ColPali indexes at **page granularity**. Each page of a PDF becomes a raster image (typically 720×960 pixels or similar). PaliGemma encodes each page image into its patch embedding sequence (e.g., 1030 patch embeddings per page for a 1024-token patch sequence). These patch embedding sequences are stored in the index.

Storage cost is higher than bi-encoder RAG (many vectors per page vs. one vector per chunk), but the vector dimensionality is typically 128 (compressed), making the per-page storage tractable.

### Query Processing

At query time, the text query is tokenized and encoded through the language portion of PaliGemma, producing a sequence of query token embeddings. MaxSim is then computed between query tokens and all stored patch embeddings for each candidate page. This produces a relevance score per page; pages are ranked by score.

---

## Performance vs. Text-Based Retrieval

ColPali (Faysse et al. 2024) was evaluated on DocVQA-retrieval, InfoVQA-retrieval, and the authors' new benchmark ViDoRe (Visual Document Retrieval Benchmark — 10 datasets, >3000 queries across heterogeneous document types including scientific papers, government reports, financial pages, slide decks).

Key results on ViDoRe:
- ColPali outperforms all text-based retrieval pipelines by large margins for document types with significant visual or tabular content
- Gap is largest for slide decks, infographic-heavy reports, and multi-panel figures
- Gap is smallest for text-dense, structure-simple documents (where OCR works well)
- ColPali runs without any text extraction step — pure image input

The benchmark confirms the architecture's value proposition: visual retrieval is superior whenever layout/visual information matters, and competitive otherwise.

---

## Limitations

**Storage cost:** Storing thousands of patch embeddings per page is expensive at scale. A 100-page PDF generates ~100,000 patch embedding vectors. Compressed vectors (int8 quantization) make this tractable but index size remains much larger than bi-encoder indices.

**Retrieval latency:** MaxSim requires computing similarity between query tokens and every patch embedding of every candidate page. In practice, approximate nearest neighbor (ANN) indexing over patch embeddings is used, but with more vectors per page than bi-encoder RAG, latency is higher.

**No text reading:** ColPali retrieves the correct *page*, but the downstream LLM still needs to process the image. The full pipeline must be a vision-language model at generation time, not a text-only LLM. This is increasingly feasible with GPT-4V, Claude, and Gemini but is not a drop-in replacement for text-only RAG pipelines.

**Training and fine-tuning:** Fine-tuning ColPali for a specific domain requires image-text training data from that domain. Text-based embedding models can be fine-tuned on purely textual pairs; ColPali requires rendered pages or screenshots paired with queries.

**Non-page-granularity documents:** ColPali assumes page-structure inputs. Web pages, code repositories, and continuous streams of text do not have natural page boundaries.

---

## Relation to Colbert and Late Interaction

ColBERT (Khattab & Zaharia 2020) introduced late interaction for *text* retrieval: instead of a single document embedding, store per-token embeddings; at query time, compute MaxSim. ColPali directly transposes this architecture to the visual domain:

| ColBERT         | ColPali                   |
|-----------------|---------------------------|
| Text tokens     | Image patches             |
| Token embedding | Patch embedding (SigLIP)  |
| MaxSim over tokens | MaxSim over patches    |
| Bi-encoder base | PaliGemma vision-language |

The theoretical motivation is the same: a single compressed embedding loses fine-grained local information (specific token positions / specific image regions) that is necessary for precise matching.

---

## Practical Deployment Pattern

A production multimodal RAG pipeline using ColPali:
1. **Ingestion:** Render all PDF/slide pages as images. Encode each page image through PaliGemma to get patch embeddings. Store in a vector index supporting multi-vector-per-item indexing (e.g., Qdrant).
2. **Retrieval:** Encode the text query through PaliGemma's language encoder. Run MaxSim against the patch embedding index to rank pages. Return top-K pages.
3. **Generation:** Feed top-K page images + text query into a vision-language model (GPT-4o, Claude, Gemini) to generate an answer. No text extraction needed; the LLM reads the images directly.

This pipeline handles tables, charts, figures, formulas, and layout-encoded content without any specialized extraction step.

---

## See Also

- [rag-architecture.md](rag-architecture.md) — foundational chunking and retrieval strategies; bi-encoder vs. cross-encoder; HyDE
- [late-chunking-contextual-embeddings.md](late-chunking-contextual-embeddings.md) — alternative chunking paradigm that improves text retrieval without visual encoding
- [reranking-two-stage-retrieval.md](reranking-two-stage-retrieval.md) — cross-encoder reranking as a complementary second-stage to any retrieval approach