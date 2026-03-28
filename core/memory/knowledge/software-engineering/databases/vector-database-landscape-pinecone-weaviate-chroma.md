---
created: '2026-03-27'
last_verified: '2026-03-27'
origin_session: core/memory/activity/2026/03/27/chat-004
source: agent-generated
trust: medium
related: ann-index-algorithms-hnsw-ivf-lsh.md, hybrid-search-sparse-dense-retrieval.md, ../../../ai/frontier/multimodal/clip-contrastive-vision-language-pretraining.md
---

# Vector Database Landscape: Pinecone, Weaviate, Chroma, Qdrant, pgvector

Vector databases are purpose-built (or adapted) storage systems that combine **embedding storage, ANN indexing, metadata filtering, and retrieval orchestration** into a single service. The category exploded 2022–2024, driven by RAG (retrieval-augmented generation) adoption. This file maps the leading systems along architectural, operational, and capability dimensions.

---

## Category Overview

**What a vector database does vs. what faiss does:**

| Capability | faiss | Vector Database |
|-----------|-------|----------------|
| ANN index | ✅ | ✅ (HNSW, IVF, or custom) |
| Persistent storage | ❌ (in-memory) | ✅ |
| Metadata storage + filtering | ❌ | ✅ |
| CRUD operations | Partial | ✅ |
| Multi-tenancy | ❌ | ✅ |
| Replication/HA | ❌ | ✅ (varies) |
| API/SDK layer | ❌ | ✅ |
| Hybrid search (sparse+dense) | ❌ | ✅ (varies) |

Vector databases are not solely defined by their ANN implementations — the value is in the **operational infrastructure** around the index: storage durability, schema management, access control, and production SLOs.

---

## Pinecone

### Architecture

Pinecone is a **fully managed, serverless** vector database designed for production deployments without infrastructure management.

**Core abstractions:**
- **Index:** top-level organisational unit; created with a single dimensionality and metric (cosine, dotproduct, euclidean)
- **Namespace:** logical partition within an index; same index, separate vector spaces; enables multi-tenancy without separate indexes
- **Record:** `{id, values (vector), sparse_values (optional), metadata (dict)}`

**Index types:**
- **Serverless (pods-free):** storage-disaggregated architecture (vectors on S3-class storage, compute provisioned on query); ideal for sporadic workload or large corpora with moderate QPS
- **Pod-based:** traditional provisioned pods (s1/p1/p2) with fixed compute; predictable latency, suitable for high-QPS production

### Dense + Sparse Hybrid

Pinecone natively supports **sparse-dense hybrid retrieval** using the `sparse_values` field (BM25 or custom sparse embeddings alongside dense vector). Fusion is configurable via the `alpha` parameter:

$$\text{score} = \alpha \cdot \text{dense\_score} + (1-\alpha) \cdot \text{sparse\_score}$$

This makes Pinecone well-suited for RAG pipelines where keyword precision augments semantic recall.

### Metadata Filtering

Metadata conditions are applied as a **pre-filter** or **in-filter** depending on selectivity — a critical architectural detail: some implementations apply metadata filter after ANN (post-filter), which can return fewer than $k$ results when the filter is highly selective. Pinecone uses index-time filtering to avoid this problem.

### Key Capabilities and Limits

| Feature | Value (as of 2025) |
|---------|------------------|
| Max vector dimensionality | 20,000 |
| Max metadata size | 40 KB per record |
| Namespaces per index | Unlimited |
| Batch upsert | 1000 vectors/request |
| Deployment | Cloud-only (AWS, GCP, Azure) |

**Pricing model:** Requests + storage (serverless) or pod-hours (pod-based). No self-hosted option — a strategic constraint.

---

## Weaviate

### Architecture

Weaviate is an **open-source**, natively multi-modal vector database with a GraphQL API and a module system for embedding generation, re-ranking, and generative AI integration.

**Core abstractions:**
- **Class (Collection):** schema definition (analogous to SQL table); properties define metadata fields; `vectorizer` module defines how objects are embedded
- **Object:** individual stored unit with UUID, properties dict, and vector
- **Cross-reference:** links between objects across classes (enabling graph-like traversal)

**Storage engine:** Custom LSM-tree-based persistent storage; HNSW index per class stored in memory (configurable async-flush to disk for durability).

### Module System

Weaviate's modularity is a key architectural differentiator:

| Module Type | Examples |
|-----------|---------|
| Vectorizer | `text2vec-openai`, `text2vec-cohere`, `text2vec-huggingface`, `multi2vec-clip` |
| Reranker | `reranker-cohere`, `reranker-transformers` |
| Generative | `generative-openai` (RAG in one request), `generative-cohere` |
| Sparse | `text2vec-bm25` for hybrid |
| Named Entity | `ner-transformers` |

**Integrated end-to-end RAG:** Weaviate's `generate` API sends retrieved context + query to a configured generative model in a single API call — simplifying pipeline integration for basic use cases.

### GraphQL and REST APIs

Weaviate exposes GraphQL for flexible queries and REST for CRUD:

```graphql
{
  Get {
    Article(
      nearText: { concepts: ["machine learning generalisation"] }
      limit: 5
      where: { path: ["published_year"], operator: GreaterThan, valueInt: 2020 }
    ) {
      title
      abstract
      _additional { distance }
    }
  }
}
```

The `nearText`, `nearVector`, `hybrid`, and `bm25` operators enable different retrieval modes.

### Weaviate Cloud Services (WCS) vs Self-Hosted

- **Self-hosted:** Docker-compose or Kubernetes; fully open-source
- **WCS (managed):** Serverless (Weaviate's proprietary storage disaggregation) and fixed-size clusters
- **Embedded:** Python-native in-process server for local/testing use

---

## Chroma

### Architecture

Chroma is an **open-source, Python-native embedded vector store** designed for simplicity and developer experience in prototyping and local applications.

**Philosophy:** minimal setup, Python-first, SQLite-backed persistence by default, in-process execution (no separate server required in embedded mode).

**Backend:**
- **In-process (default):** SQLite + HNSW (via hnswlib); suitable for local dev and smaller datasets
- **HTTP server mode:** REST API server for shared access; client/server architecture
- **Chroma Cloud (managed):** serverless offering; launched 2024

**Core abstractions:**
- **Collection:** named vector collection; configured with distance metric and optional embedding function
- **Document:** text content with optional metadata; Chroma auto-generates embeddings if an embedding function is configured
- **Embedding function:** callable that Chroma invokes on document strings (OpenAI, Sentence Transformers, or custom)

```python
import chromadb
client = chromadb.Client()
col = client.create_collection("papers")
col.add(ids=["p1"], documents=["PAC-Bayes bounds for neural networks"],
        metadatas=[{"year": 2023}])
results = col.query(query_texts=["generalisation theory"], n_results=3)
```

### Strengths and Limitations

| Dimension | Assessment |
|-----------|-----------|
| Developer experience | Excellent — minimal boilerplate |
| Production scalability | Limited — single-node; no native sharding |
| Metadata filtering | Basic (`where` clause, limited operators) |
| Hybrid search | Not natively supported (sparse+dense) |
| Multi-tenancy | Via collections or Chroma Cloud namespaces |
| Deployment simplicity | Best-in-class for local use |

Chroma is the go-to choice for **prototyping, notebooks, and small-scale local RAG pipelines** but is typically replaced by Weaviate/Qdrant/Pinecone when moving to production at scale.

---

## Qdrant

### Architecture

Qdrant is an **open-source**, high-performance vector database written in **Rust**, designed for production workloads with advanced payload indexing and quantisation.

**Core design choices:**
- **Rust implementation:** memory safety, low latency, high throughput without GC pauses
- **HNSW** as primary index with custom extensions
- **Payload indexing:** metadata fields can be indexed with full/partial inverted indices for fast pre-filtering
- **Quantisation support:** Scalar (8-bit) and Product Quantisation for memory compression
- **On-disk collection mode:** mmap-based storage for datasets larger than RAM

**Core abstractions:**
- **Collection:** analogous to a table; configured with vector parameters and HNSW index config
- **Point:** `{id, vector, payload (dict)}`
- **Segment:** internal shard unit (a collection splits across segments for concurrent writes)

### Sparse Vector Support (Qdrant 1.7+)

Qdrant introduced native sparse vector support, enabling true hybrid search without a separate BM25 system:

```python
qdrant.search(
    collection_name="docs",
    query_vector=models.SparseVector(indices=[450, 1200], values=[0.8, 0.3]),
    query_vector_name="bm25"
)
```

Sparse and dense scores can be fused using Reciprocal Rank Fusion (RRF) or weighted linear combination.

### Deployment Options

| Option | Description |
|--------|-------------|
| **Local (single node)** | Docker; data stored on local disk |
| **Distributed cluster** | Raft-based shard replication; sharding across nodes |
| **Qdrant Cloud** | Managed; GCP/AWS/Azure |
| **Embedded (Rust/Python)** | In-process for testing |

**Performance characteristic:** Qdrant consistently scores top-tier on ANN benchmarks with full CRUD and filtering enabled — the Rust implementation delivers materially lower P99 latency than JVM-based alternatives.

---

## pgvector

### Architecture

**pgvector** is a **PostgreSQL extension** that adds a `vector` data type and ANN index operators, enabling vector search alongside relational queries within a single PostgreSQL instance.

**Installation:** `CREATE EXTENSION vector;` — added to existing PostgreSQL databases.

**Vector storage:**
```sql
CREATE TABLE papers (
  id SERIAL PRIMARY KEY,
  title TEXT,
  embedding vector(1536),  -- OpenAI text-embedding-ada-002 dimension
  published_year INT
);
```

### Index Types

| Index | Algorithm | Use Case |
|-------|-----------|---------|
| `USING ivfflat` | IVF with flat (exact exhaustive) search in lists | Default for most use cases; simple |
| `USING hnsw` | HNSW (added v0.5) | Better recall-speed trade-off; more memory |

```sql
CREATE INDEX ON papers USING hnsw (embedding vector_cosine_ops);
```

### Query Pattern

```sql
SELECT title, published_year,
       embedding <=> '[0.1, 0.2, ...]'::vector AS distance
FROM papers
WHERE published_year >= 2020
ORDER BY distance
LIMIT 5;
```

The `<=>` operator is cosine distance; `<->` is Euclidean; `<#>` is negative inner product. The query planner can combine the vector index with traditional B-tree/GIN indexes on other columns.

### Operational Simplicity Trade-off

| Benefit | Cost |
|---------|------|
| No separate vector infra | Lower raw ANN throughput than dedicated systems |
| SQL JOINs + vector search in one query | HNSW graph fully in memory (can pressure PG shared buffers) |
| Familiar PostgreSQL tooling (backups, RBAC, MVCC) | Less native quantisation support |
| Transactional consistency with business data | Horizontal scaling requires Citus/streaming replicas |

**Ideal for:** Applications where embeddings are tightly coupled to relational data and operational simplicity outweighs the highest-throughput requirements. AWS RDS, Supabase, and Neon all support pgvector natively.

---

## Selection Criteria Matrix

| Requirement | Pinecone | Weaviate | Chroma | Qdrant | pgvector |
|-------------|---------|---------|--------|--------|---------|
| Managed / zero-ops | ✅ Best | Partial | Partial | Partial | Via RDS |
| Open source | ❌ | ✅ | ✅ | ✅ | ✅ |
| Self-hosted | ❌ | ✅ | ✅ | ✅ | ✅ |
| High QPS production | ✅ | ✅ | ❌ | ✅ | Moderate |
| Native hybrid search | ✅ | ✅ | ❌ | ✅(1.7+) | Manual BM25 |
| Multi-modal vectorisers | Via custom | ✅ (CLIP module) | Custom | Manual | Manual |
| Relational data co-location | ❌ | Cross-refs | ❌ | ❌ | ✅ Best |
| Metadata pre-filtering | ✅ | ✅ | Basic | ✅ | ✅ |
| Billion-scale (on-disk) | Serverless | Partial | ❌ | ✅ | Difficult |
| Quantisation (PQ/SQ) | Internal | Partial | ❌ | ✅ | Limited |
| Developer quickstart | Good | Good | ✅ Best | Good | Good |

### Decision Heuristics

1. **RAG prototype → production migration path:** Start with Chroma for dev/testing; migrate to Qdrant or Weaviate for production without changing retrieval logic significantly
2. **Relational + vector in one database:** pgvector on Supabase or RDS — avoids syncing two systems
3. **Multi-modal (image + text):** Weaviate with multi2vec-clip module simplifies embedding generation
4. **Highest throughput, no ops team:** Pinecone serverless — highest QPS with zero infrastructure
5. **Data sovereignty / no cloud deps:** Qdrant self-hosted in Kubernetes — best performance + open source + enterprise support available

---

## References

1. Pinecone Documentation — <https://docs.pinecone.io>
2. Weaviate Documentation — <https://weaviate.io/developers/weaviate>
3. Chroma Documentation — <https://docs.trychroma.com>
4. Qdrant Documentation — <https://qdrant.tech/documentation>
5. Pgvector GitHub — <https://github.com/pgvector/pgvector>
6. Pan, J. et al. (2024). "Survey of Vector Database Management Systems." *Proc. VLDB Endow.*
7. ANN Benchmarks — <https://ann-benchmarks.com>
8. Douze, M. et al. (2024). "The faiss library." *arXiv:2401.08281*
