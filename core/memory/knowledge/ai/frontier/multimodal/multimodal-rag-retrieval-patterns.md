---
created: '2026-03-27'
last_verified: '2026-03-27'
origin_session: core/memory/activity/2026/03/27/chat-005
source: agent-generated
trust: medium
related: clip-contrastive-vision-language-pretraining.md, vision-language-models-gpt4v-gemini-llava.md, audio-language-models-whisper-speech.md, embodied-ai-rt2-gato-saycan.md, multimodal-synthesis-agent-implications.md, ../retrieval-memory/agentic-rag-patterns.md, ../retrieval-memory/colpali-visual-document-retrieval.md
---

# Multimodal RAG and Retrieval Patterns

Standard retrieval-augmented generation (RAG) operates over text corpora, retrieving text chunks to augment a text-generation prompt. Multimodal RAG extends this to **heterogeneous corpora** containing images, tables, charts, audio, video, and mixed-media documents. The extension raises new challenges at every stage of the retrieval pipeline: indexing, query formulation, cross-modal matching, and result integration.

**Prerequisite**: Text-only RAG fundamentals (`../retrieval-memory/rag-architecture.md`); CLIP embeddings (`clip-contrastive-vision-language-pretraining.md`); ColPali visual document retrieval (`../retrieval-memory/colpali-visual-document-retrieval.md`).

---

## The Multimodal Retrieval Challenge

The core challenge is that **modality-specific representations are not natively compatible**. A CLIP text embedding for "quarterly revenue growth" is not in the same space as an image embedding of a bar chart showing quarterly revenue — even though they are semantically related.

Three architectural strategies exist for bridging this gap:

1. **Late-fusion alignment**: Embed each modality independently; project all embeddings into a shared semantic space; retrieve uniformly across modalities.
2. **Middle-fusion joint encoding**: Feed multimodal content to a single joint encoder (e.g., a vision-language model) that produces a unified representation.
3. **Early-fusion multi-modal indexing**: Represent documents as a unified token sequence (text + image tokens) and retrieve over this unified representation.

ColPali (Faysse et al. 2024) instantiates approach 3 at the visual-document level; full multimodal RAG for arbitrary content types requires combining all three.

---

## Late-Interaction Multimodal Retrieval

### ColPali Extended

ColPali encodes document pages as collections of patch embeddings (via PaliGemma) and computes query-document scores through a MaxSim operation over patch-level late interactions:

$$\text{score}(q, d) = \sum_{i \in \text{query tokens}} \max_{j \in \text{doc patches}} \langle e_i^q, e_j^d \rangle$$

This captures fine-grained patch-level alignment between query tokens and document regions, enabling accurate retrieval over documents with dense visual content (charts, equations, tables).

**Extension to multi-document types**: The late-interaction pattern extends to audio-text via:
- Audio → spectrogram patches → AudioPaLM embeddings, then same MaxSim scoring against text queries
- Video → frame patches + audio patches, late interaction over both streams

The **ViDoRe benchmark** (Visual Document Retrieval Benchmark) evaluates retrieval over visually rich PDFs; ColPali and variants achieve state-of-the-art performance there, while standard text-OCR pipelines fail on chart-heavy documents.

### Embedding Space Alignment for Cross-Modal Search

The fundamental operation for cross-modal retrieval is **contrastive alignment**: train a loss that pushes semantically matched pairs from different modalities together and pushes non-matching pairs apart.

Given image-text pairs $(I, T)$, the InfoNCE loss (the CLIP loss) is:

$$\mathcal{L}_\text{InfoNCE} = -\frac{1}{B}\sum_{i=1}^B \log \frac{\exp(\text{sim}(e_i^I, e_i^T)/\tau)}{\sum_{j=1}^B \exp(\text{sim}(e_i^I, e_j^T)/\tau)}$$

where $e^I$ and $e^T$ are the image and text encoder outputs, and $\tau$ is a temperature parameter.

**Practical implication**: Any two modalities aligned via a shared contrastive loss can be used for cross-modal retrieval — text queries can retrieve images, image queries can retrieve text, audio queries can retrieve documents. This is the foundation of all late-fusion multimodal RAG.

---

## Cross-Modal Query Expansion

### Text Query → Image Retrieval

A user query in text form can be used to retrieve image content by:
1. Text encoding the query via CLIP-Text (or similar)
2. ANN search against a CLIP-Image indexed corpus
3. Re-ranking retrieved images using a VLM cross-encoder (e.g., GPT-4V scoring relevance of each image to the query)

**Use case**: A financial analyst's query "show me charts with declining revenue in Q3 2023" should retrieve PDF pages containing relevant charts, not just pages mentioning those words in text.

### Image Query → Text Chunk Retrieval

An image (e.g., a scanned diagram) can serve as the query:
1. Encode the query image via CLIP-Image
2. ANN search against both CLIP-Image (for similar images) and CLIP-Text (for text that describes images like this)
3. Merge results and rerank via VLM

This enables **visual question answering over text corpora**: given a diagram, retrieve the textual explanations that describe it.

### Query Expansion: Text → Image → Text

A more powerful pattern:
1. Expand a text query using a VLM to generate an image description
2. Use the description to retrieve images
3. Feed retrieved images to a VLM to extract relevant text
4. Use the extracted text to retrieve additional text chunks

This multi-hop cross-modal retrieval chain can answer questions that require integrating visual and textual evidence from separate documents.

---

## Hybrid Retrieval Pipelines

Full multimodal RAG systems combine multiple retrieval signals:

| Signal | What It Captures | Technique |
|--------|-----------------|----------|
| Sparse text BM25 | Exact keyword matches in OCR'd text | Inverted index |
| Dense text vector | Semantic content of text | BERT/E5 embeddings + HNSW |
| Dense image vector | Visual semantic content | CLIP-Image embeddings + HNSW |
| Late-interaction multimodal | Fine-grained patch-level matching | ColPali MaxSim |
| Structural metadata | Page number, section, document type | Structured filter |

These signals are combined via a **reciprocal rank fusion (RRF)** step or a learned reranker:

$$\text{RRF score}(d) = \sum_{r \in \text{rankers}} \frac{1}{k + r(d)}$$

where $r(d)$ is the rank of document $d$ in ranker $r$ and $k$ is a smoothing constant (typically 60).

### Reranking Across Modalities

After initial retrieval, a VLM cross-encoder reranker can score the relevance of each retrieved item (text chunk or image) to the query by conditioning on both query and retrieved content:

$$\text{relevance}(q, c) = \text{VLM}(q \| c)[\text{"yes"}]$$

This is expensive (VLM forward pass per candidate) but achieves the highest accuracy. Practical systems use it only for the top-$k$ candidates from the cheaper retrievers.

---

## Benchmarks

| Benchmark | Task | Key Challenge |
|-----------|------|---------------|
| ViDoRe | Retrieve PDF pages for text queries | Dense visual content (charts, tables) |
| BEIR (multimodal extension) | Text-to-image and image-to-text retrieval | Cross-modal semantic alignment |
| MMDocQA | Question answering over mixed-media documents | Multi-hop evidence across modalities |
| MIRAGE-Bench | Multimodal RAG end-to-end evaluation | Full pipeline: retrieval + generation |

---

## References

1. Faysse, M. et al. (2024). ColPali: Efficient Document Retrieval with Vision Language Models. *arXiv:2407.01449*.
2. Izacard, G. & Grave, E. (2021). Leveraging Passage Retrieval with Generative Models for Open Domain Question Answering. *EACL*.
3. Radford, A. et al. (2021). Learning Transferable Visual Models From Natural Language Supervision (CLIP). *ICML*.
4. Xiong, G. et al. (2024). MRAG: Multimodal Retrieval-Augmented Generation Survey. *arXiv*.
5. Cormack, G. et al. (2009). Reciprocal Rank Fusion outperforms Condorcet and individual Rank Learning Methods. *SIGIR*.
