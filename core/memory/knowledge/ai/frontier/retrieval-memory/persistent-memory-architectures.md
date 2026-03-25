---
created: 2026-03-19
last_verified: '2026-03-21'
origin_session: core/memory/activity/2026/03/19/chat-001
source: external-research
topic: Persistent memory architectures — vector stores, knowledge graphs, episodic/semantic/procedural,
  git-backed
trust: medium
type: knowledge
related: rag-architecture.md, reranking-two-stage-retrieval.md, agentic-rag-patterns.md, long-context-architecture.md, colpali-visual-document-retrieval.md, ../../tools/agent-memory-in-ai-ecosystem.md
---

# Persistent Memory Architectures for AI Systems

## Lede

The most significant architectural gap in language models is the absence of persistent memory across contexts. Each conversation is a fresh slate; every insight, preference, and established fact must be re-established from scratch or injected through retrieval. The memory thread runs through this repo's entire purpose — this git-backed structured knowledge system is an explicit bet that persistent structured memory is a tractable and superior alternative to the dominant vector-store approach. Understanding why different memory architectures make different tradeoffs reveals why the design decisions here (semantic frontmatter, trust levels, access logs, structured curation) exist. It also connects to the cognitive science thread: episodic, semantic, and procedural memory are not just metaphors — they are distinct processing modes with different architectural requirements.

---

## The Memory Problem

A language model has two forms of "knowledge" in a standard deployment:
1. **Parametric memory:** Facts, skills, and relationships encoded in model weights during pretraining. Cheap to access (just run the forward pass), impossible to update without retraining.
2. **Contextual memory:** Information in the current context window. Free to query (the model attends to it), expensive to fill (tokens cost compute), and ephemeral (gone when the session ends).

The missing tier: **persistent external memory** that survives across sessions, can be updated without retraining, and can be queried selectively rather than injected wholesale into context.

---

## The Cognitive Science Frame

Three memory types from cognitive science provide a useful taxonomy:

**Episodic memory:** Memory for specific events — "the conversation I had last Tuesday about X," "the error I encountered in file Y during session Z." Temporally organized, high specificity, bounded by experience. In AI systems: conversation logs, access logs, session summaries.

**Semantic memory:** Memory for facts and their relationships — "X is a concept in domain Y," "the architecture of system Z works like this." Not temporally organized; organized by meaning. In AI systems: knowledge files, documentation, structured fact stores.

**Procedural memory:** Memory for how to do things — skills, patterns, workflows. Manifest as behavior, not declarative content. In AI systems: encoded in model weights (hard to update), or as skill files / prompt templates that parameterize behavior.

**The architectural implication:** Different memory types need different storage and retrieval mechanisms:
- Episodic → append-only logs with temporal indexing
- Semantic → structured knowledge bases with schema and update semantics
- Procedural → parameterizable prompt templates or fine-tuned model components

Most AI memory systems conflate these types into a single vector store, which works poorly for all three: vector similarity is good for semantic similarity lookup but bad for temporal queries (episodic), doesn't enforce schema (semantic), and can't represent parameterized behaviors (procedural).

---

## Vector Store Memory

**The dominant approach:** Embed conversations, documents, and facts into vectors; store in a vector database (Pinecone, Weaviate, Qdrant, FAISS, pgvector). At query time, embed the current query and retrieve similar vectors.

**Strengths:**
- Works at scale (billions of vectors)
- Handles fuzzy matching well (semantic similarity, not exact match)
- Easy to add new items (just embed and insert)
- No schema required

**Weaknesses:**
- **No update semantics:** Vectors are identified by IDs, not content. Updating a fact requires either mutating the vector (which breaks similarity-based retrieval) or adding a new vector and soft-deleting the old one — neither is elegant. Contradictions between old and new entries cannot be detected.
- **No trust or source tracking:** All vectors are treated equally regardless of source quality, age, or verification status.
- **No explicit structure:** Relationships between facts are implicit in embedding proximity, not explicit in schema. "X is a prerequisite for Y" cannot be represented without additional layers.
- **Query expressiveness:** Semantic similarity search cannot express "all facts about X from sources dated after Y" or "all facts I marked as uncertain."
- **No reasoning over stored content:** The vector store does not support inferential queries; it only retrieves.

**MemGPT / memory server approach (OpenAI-adjacent):** A model is given a structured tool interface for reading and writing a memory store. The model decides what to write, what to update, and what to retrieve. The memory store is still vector-backed but the model mediates access, enabling more structured updates. Limitation: the model makes all curation decisions in-context, which is expensive and error-prone.

---

## Knowledge Graph Memory

**Approach:** Store facts as a directed graph of (entity, relation, entity) or (subject, predicate, object) triples. Relations can be typed, temporally scoped, and confidence-weighted. Traversal and inference are explicit operations.

**Strengths:**
- Explicit relationship representation ("X causes Y," "X is a type of Y")
- Update semantics are well-defined (add/remove/modify edges)
- Contradiction detection is explicit (two conflicting relations between the same entities)
- Inferential queries are possible (SPARQL-style queries, graph traversal for multi-hop reasoning)

**Weaknesses:**
- **Entity disambiguation:** "Python" the language and "python" the snake must be reliably disambiguated for the graph to be coherent. This is hard, especially from unstructured text.
- **Schema rigidity:** Graphs with typed relations require schema design upfront; schema changes require migration
- **Natural language grounding:** How do you populate the graph from conversational text? Entity extraction and relation extraction are still errors-prone
- **Poor at fuzzy matching:** A graph stores facts; it does not support "find facts related to X" without explicit traversal from X. Combining graph and vector retrieval (hybrid systems) is complex.

---

## Git-Backed Structured Memory (This Repo)

**The design bet:** Use git-versioned markdown files with semantic frontmatter as the primary memory store. This trades the scalability advantages of vector stores and the inferential power of knowledge graphs for specific advantages:

**Advantages:**
- **Full version history:** Every change is tracked with author, timestamp, and diff. Memory provenance is complete.
- **Trust and source metadata:** Frontmatter fields (`trust:`, `source:`, `last_verified:`) provide explicit quality signals that vector stores cannot represent natively.
- **Human readability:** Files can be read and edited directly; memory is not locked in an opaque embedding.
- **Conflict detection:** Git handles merge conflicts; simultaneous update attempts on the same file are not silently lost.
- **Curation workflow:** The trust-level curation lifecycle (unverified → verified → archived) is natural in a file system with metadata; harder to implement in a vector store.
- **Tool compatibility:** Git repos work with all standard development tooling; vector databases require specialized tooling.

**Disadvantages:**
- **No semantic similarity search by default:** Retrieving the most relevant file requires either fulltext search (BM25) or adding an embedding index layer
- **Manual curation required:** Adding and updating files is not automatic; it requires deliberate curation decisions (this is a feature, not a bug, for high-trust use cases)
- **Does not scale to millions of entries:** Works for hundreds to low thousands of structured files; impractical for raw conversational logs at scale
- **Access pattern analysis required:** The ACCESS.jsonl log structure tracks what gets read, enabling session-start optimization — a feature not typically present in vector stores

**The design fit:** This architecture is well-suited for a curated knowledge base maintained by and for a specific agent/user, where quality matters more than scale. For general-purpose conversation memory at scale, a vector store would be more appropriate.

---

## Memory Extraction from Conversations

In any persistent memory system, the central challenge is deciding what to write:

**Entity and fact extraction:** What named entities, relationships, and facts from the conversation are worth recording? Rule-based extraction (NLP patterns) misses novel formulations; LLM-based extraction is higher quality but costs extra compute per conversation.

**Summarization vs. verbatim storage:** Storing full conversation transcripts is expensive and difficult to retrieve from; summarizing loses detail but is easier to work with. The optimal level of compression depends on what kinds of queries the store will face.

**Contradiction detection:** When adding new facts, check whether they contradict existing stored facts. Simple for explicit contradictions ("X is true" vs. "X is false"); hard for implicit contradictions (two facts that together imply a contradiction).

**Temporal decay:** Old facts can become stale. A memory system needs a policy for marking facts as potentially outdated and preventing their retrieval when temporal currency is important. (The curation policy in `core/governance/curation-policy.md` addresses this for this repo.)

---

## The Write Problem

The hardest problem in persistent memory is knowing when and what to write. Over-writing creates a cluttered, hard-to-use store; under-writing loses important information.

**Current approaches:**

- **Stream everything:** Store all conversation turns verbatim. Retrieve by timestamp or similarity. Suffers from retrieval quality degradation as size grows; no curation.
- **Agent-mediated writes:** The agent decides what to write after each turn. High quality if the agent is well-calibrated; expensive and inconsistent in practice.
- **Periodic summarization:** After every N turns, summarize the conversation and store the summary. Loses detail; time-triggered rather than content-triggered.
- **Human-in-the-loop:** Human reviews and approves writes. Highest quality; not scalable.

**This repo's approach:** The agent writes to scratchpad (low-friction, no curation), which is periodically promoted to knowledge (higher curation, explicit human review or agent reflection). The two-tier system separates fast capture from slow curation — a design borrowed from PKM (personal knowledge management) tools like Roam and Obsidian.

---

## Open Questions

- **The optimal memory granularity:** Should facts be stored at the sentence level (maximum specificity), paragraph level (better context), or document level (full coherence)? It depends entirely on query patterns, which vary by use case.
- **Active learning for memory:** Can a memory system identify its own gaps — facts it doesn't know but should — and trigger acquisition? Current systems are purely reactive (write when prompted).
- **Memory across agents:** In multi-agent systems, how do agents share memory without one agent's errors polluting another's store? Trust isolation and memory federation are understudied.
- **Forgetting as a feature:** Biological memory fades; AI memory usually doesn't. Should AI memory systems implement temporal decay, and if so, at what rate and on what criteria?

---

## Key Sources

- Packer et al. 2023 — "MemGPT: Towards LLMs as Operating Systems" (hierarchical memory for LLMs)
- Zhong et al. 2024 — "MemoryBank: Enhancing Large Language Models with Long-Term Memory"
- Bauer et al. 2023 — "Memory-Augmented LLM Persona Simulation with Emotional States"
- Tulving 1972 — "Episodic and semantic memory" (cognitive science foundation)
- Anderson et al. 2004 — "An integrated theory of the mind" (ACT-R, procedural memory model)
- This repo's `core/governance/curation-policy.md` and `core/memory/skills/` for the operational memory management approach
